"""The pipeline: Understand -> Retrieve memory -> Think (tool?) -> Respond (stream) -> remember."""
import asyncio
import logging
import re
import time
from datetime import datetime
from typing import Awaitable, Callable

from backend.core.lang import detect_language, estimate_tokens
from backend.documents.retrieval import format_chunks
from backend.tools.base import ToolError
from backend.tools.registry import REGISTRY, describe_action

from . import tool_router
from .llm import LLMError
from .prompts import MEMORY_EXTRACT_PROMPT, system_prompt

log = logging.getLogger(__name__)
Emit = Callable[[dict], Awaitable[None]]

# Retrieval cut-offs. MiniLM scores first-person questions ("What do I do for work?") low against
# third-person facts ("The user works as..."), so the memory cut-off must be loose. Measured: 0.187.
MEMORY_MIN_SCORE = 0.12
MEMORY_TOP_K = 5
DOC_MIN_SCORE = 0.30
DOC_TOP_K = 4

_REMEMBER = re.compile(
    r"(\bremember\b|\bmy name\b|\bi am\b|\bi'm\b|\bi live\b|\bi work\b|\bi study\b|\bi like\b|\bi love\b|\bi prefer\b|"
    r"\bi hate\b|\bi don'?t like\b|\bmy fav|\bcall me\b|\bmy birthday\b|\bi was born\b|\bmy (wife|husband|mother|father|"
    r"brother|sister|friend|son|daughter)\b|என் பெயர்|நினைவில்|எனக்கு பிடி)", re.I)

# Words that suggest the user is asking about an uploaded document.
_DOC_WORDS = re.compile(r"\b(documents?|docs?|pdf|resume|cv|files?|notes|uploaded|attachment|report|paper|article)\b"
                        r"|ஆவணம்|கோப்பு", re.I)

# An explicit request for the web is allowed to override document answers.
_WEB_REQUEST = re.compile(r"\b(search|google|look up|on the web|online|internet)\b", re.I)


def fit_history(history: list[dict], budget: int) -> list[dict]:
    """Keep the most recent messages that fit in `budget` estimated tokens."""
    chosen = []
    for m in reversed(history):
        cost = estimate_tokens(m["content"]) + 8
        if budget - cost < 0:
            break
        budget -= cost
        chosen.append({"role": m["role"], "content": m["content"]})
    return list(reversed(chosen))


class Agent:
    def __init__(self, services):
        self.s = services
        self._bg: set[asyncio.Task] = set()

    # ------------------------------------------------------------------
    async def respond(self, conv_id: str, user_text: str, emit: Emit, stt_lang: str | None = None,
                      save_user: bool = True) -> None:
        s, t0 = self.s, time.perf_counter()
        cfg = s.settings.all()
        lang_mode = cfg["language"]
        user_lang = stt_lang or detect_language(user_text)
        if save_user:
            s.convo.add_message(conv_id, "user", user_text, user_lang)

        # 1. Retrieve memory + documents ---------------------------------
        await emit({"type": "status", "stage": "retrieving"})
        memories, chunks = await asyncio.to_thread(self._retrieve, user_text, cfg)
        t_retr = time.perf_counter()

        doc_note = None
        if cfg["use_documents"] and not chunks and _DOC_WORDS.search(user_text):
            doc_note = ("The user seems to be asking about an uploaded document, but no uploaded document matched "
                        f"({s.documents_repo.count()} indexed). Say you couldn't find it in the uploaded documents "
                        "and suggest uploading it on the Documents page. Do not guess or invent its contents.")

        # 2. Think: does this need a tool? -------------------------------
        await emit({"type": "status", "stage": "thinking"})
        tool_used, tool_result, direct_text = None, None, None
        # If the user's own documents already matched, answer from them: don't also go to the web or run
        # tools, unless the user explicitly asked for a web search.
        if cfg["use_tools"] and not (chunks and not _WEB_REQUEST.search(user_text)):
            try:
                call = await tool_router.route(s.llm, user_text)
            except LLMError as e:
                await self._fail(emit, str(e))
                return
            if call:
                spec = REGISTRY[call.tool]
                if spec.sensitive or (cfg["confirm_all_actions"] and spec.automation):
                    pending = s.actions.create(call.tool, call.args, conv_id)
                    desc = describe_action(call.tool, call.args)
                    text = f"I need your confirmation before I {desc}."
                    mid = s.convo.add_message(conv_id, "assistant", text, "en",
                                              {"pending_action": {"id": pending.id, "description": desc}})
                    await emit({"type": "pending_action", "id": pending.id, "tool": call.tool, "description": desc})
                    await emit({"type": "done", "conversation_id": conv_id, "message_id": mid, "text": text,
                                "language": "en", "tool": None, "timings": {}})
                    return
                try:
                    tool_result = await asyncio.to_thread(spec.fn, **call.args)
                    tool_used = call.tool
                    await emit({"type": "tool", "tool": call.tool, "result": tool_result})
                    if spec.direct_reply:
                        direct_text = tool_result
                except ToolError as e:
                    tool_used, tool_result = call.tool, f"The tool failed: {e}"
                    await emit({"type": "tool", "tool": call.tool, "result": tool_result, "error": True})
                    if spec.direct_reply:
                        direct_text = f"I couldn't do that. {e}"
                except Exception as e:  # noqa: BLE001
                    log.exception("tool %s crashed", call.tool)
                    tool_used, tool_result = call.tool, f"The tool crashed: {e}"
                    if spec.direct_reply:
                        direct_text = "Sorry, that action failed unexpectedly. Check the backend log."
        t_tool = time.perf_counter()

        # Desktop actions are answered with the tool's own words. A small model must not get the chance to
        # misreport (or copy an earlier refusal from the chat history) about something that really happened.
        if direct_text is not None:
            reply_lang = detect_language(direct_text)
            timings = {"retrieval_ms": round((t_retr - t0) * 1000), "tool_ms": round((t_tool - t_retr) * 1000),
                       "first_token_ms": None, "total_ms": round((t_tool - t0) * 1000), "tokens_per_s": None}
            mid = s.convo.add_message(conv_id, "assistant", direct_text, reply_lang,
                                      {"tool": tool_used, "timings": timings, "direct": True})
            log.info("Direct tool reply (%s): %s", tool_used, direct_text[:80])
            await emit({"type": "done", "conversation_id": conv_id, "message_id": mid, "text": direct_text,
                        "language": reply_lang, "tool": tool_used, "timings": timings})
            return

        # 3. Build the prompt within the context budget ------------------
        now = datetime.now().strftime("%A, %d %B %Y, %I:%M %p")
        system = system_prompt(
            s.cfg.app_name, lang_mode, now,
            memories=[m["text"] for m in memories] or None,
            doc_context=format_chunks(chunks) if chunks else None,
            tool_result=(tool_used, tool_result) if tool_used else None,
            extra_note=doc_note)
        history = s.convo.messages(conv_id)
        if history and history[-1]["role"] == "user":
            history = history[:-1]
        reserve = int(cfg["max_tokens"]) + 64
        budget = int(cfg["num_ctx"]) - reserve - estimate_tokens(system) - estimate_tokens(user_text)
        messages = [{"role": "system", "content": system}, *fit_history(history, max(budget, 0)),
                    {"role": "user", "content": user_text}]

        # 4. Respond: stream tokens --------------------------------------
        await emit({"type": "status", "stage": "responding"})
        parts, t_first = [], None
        try:
            async for tok in s.llm.stream(messages):
                if t_first is None:
                    t_first = time.perf_counter()
                parts.append(tok)
                await emit({"type": "token", "text": tok})
        except LLMError as e:
            await self._fail(emit, str(e))
            return
        text = "".join(parts).strip() or "Sorry, I couldn't generate a response."
        t_end = time.perf_counter()

        stats = s.llm.last_stats or {}
        tps = None
        if stats.get("eval_count") and stats.get("eval_duration"):
            tps = round(stats["eval_count"] / (stats["eval_duration"] / 1e9), 1)
        timings = {"retrieval_ms": round((t_retr - t0) * 1000), "tool_ms": round((t_tool - t_retr) * 1000),
                   "first_token_ms": round((t_first - t_tool) * 1000) if t_first else None,
                   "total_ms": round((t_end - t0) * 1000), "tokens_per_s": tps}
        reply_lang = detect_language(text)
        mid = s.convo.add_message(conv_id, "assistant", text, reply_lang,
                                  {"tool": tool_used, "timings": timings,
                                   "memories": len(memories), "doc_chunks": len(chunks)})
        log.info("Reply done: %s", timings)
        await emit({"type": "done", "conversation_id": conv_id, "message_id": mid, "text": text,
                    "language": reply_lang, "tool": tool_used, "timings": timings})

        # 5. Remember (background, never blocks the reply) ---------------
        if cfg["auto_memory"] and _REMEMBER.search(user_text):
            task = asyncio.create_task(self._remember(user_text, conv_id))
            self._bg.add(task)
            task.add_done_callback(self._bg.discard)

    # ------------------------------------------------------------------
    def _retrieve(self, text: str, cfg: dict):
        memories, chunks = [], []
        try:
            if cfg["use_memory"]:
                memories = self.s.vectors.search_memories(text, k=MEMORY_TOP_K, min_score=MEMORY_MIN_SCORE)
                if memories:
                    log.info("Memories used: %s",
                             [(round(m["score"], 3), m["text"][:40]) for m in memories])
            if cfg["use_documents"] and self.s.documents_repo.count() > 0:
                chunks = self.s.vectors.search_docs(text, k=DOC_TOP_K, min_score=DOC_MIN_SCORE)
                if not chunks and _DOC_WORDS.search(text):  # user named a document: accept weaker matches
                    chunks = self.s.vectors.search_docs(text, k=3, min_score=0.05)
                if chunks:
                    log.info("Document chunks used: %s",
                             [(round(c["score"], 3), c["filename"]) for c in chunks])
        except Exception:  # noqa: BLE001 - retrieval must never break chat
            log.exception("Retrieval failed; continuing without it")
        return memories, chunks

    async def _remember(self, user_text: str, conv_id: str) -> None:
        try:
            obj = await self.s.llm.chat_json(
                [{"role": "system", "content": MEMORY_EXTRACT_PROMPT}, {"role": "user", "content": user_text}],
                options={"temperature": 0, "num_predict": 200})
            facts = [f.strip() for f in obj.get("facts", []) if isinstance(f, str) and 8 <= len(f.strip()) <= 240][:3]
            for fact in facts:
                dup = await asyncio.to_thread(self.s.vectors.search_memories, fact, 1, 0.88)
                if dup:
                    continue
                await asyncio.to_thread(self.s.vectors.add_memory, fact, "auto", conv_id)
                log.info("Saved memory: %s", fact)
        except Exception:  # noqa: BLE001
            log.exception("Memory extraction failed")

    async def _fail(self, emit: Emit, message: str) -> None:
        log.error("Agent error: %s", message)
        await emit({"type": "error", "message": message})

    # ------------------------------------------------------------------
    async def run_confirmed(self, action_id: str, approve: bool) -> dict:
        s = self.s
        action = s.actions.pop(action_id)
        if not action:
            raise KeyError("That confirmation has expired or was already handled.")
        if not approve:
            text = "Okay, I cancelled that."
        else:
            try:
                result = await asyncio.to_thread(REGISTRY[action.tool].fn, **action.args)
                text = result
            except ToolError as e:
                text = f"I couldn't do that: {e}"
        mid = (s.convo.add_message(action.conversation_id, "assistant", text, "en", {"tool": action.tool})
               if action.conversation_id else None)
        return {"conversation_id": action.conversation_id, "message_id": mid, "text": text, "approved": approve}
