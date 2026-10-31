"""Decides whether a request needs a tool. Gemma 3 has no native function calling, so we use
JSON-mode prompting + strict validation against the registry (the model can only choose listed tools)."""
import logging
import re
from dataclasses import dataclass

from backend.tools.registry import REGISTRY

log = logging.getLogger(__name__)

_DATETIME = re.compile(
    r"\b(what('?s| is)( the)? (current )?(time|date|day)|current (time|date)|time is it|today'?s date|what day is)\b", re.I)
_HINTS = re.compile(
    r"(\d\s*[+\-*/x×÷^%]\s*\d|\bcalculat|\bhow much is\b|\bwhat is \d|\bsquare root\b|"
    r"\bsearch\b|\bgoogle\b|\blook up\b|\blatest\b|\bnews\b|\bweather\b|\bprice of\b|"
    r"\bopen\b|\blaunch\b|\bstart (the )?\w+ app|\bfolder\b|\bfind\b.*\bfile|\bwhere is my\b|\blocate\b|"
    r"\bdelete\b|\bremove\b|\bscreenshot\b|\bvolume\b|\bmute\b|\bpause\b|\bplay\b|\bnext track\b|"
    r"கணக்கிட|தேடு|திற|நேரம்|தேதி|நீக்கு|கோப்பு)", re.I)


@dataclass
class ToolCall:
    tool: str
    args: dict


def router_prompt() -> str:
    lines = ["You decide whether the user's request needs exactly one of these tools.",
             "Reply with JSON only: {\"tool\": \"<name or null>\", \"args\": {...}}.", "", "Tools:"]
    for t in REGISTRY.values():
        params = ", ".join(f'"{k}": <{v}>' for k, v in t.params.items()) or "no args"
        lines.append(f"- {t.name}: {t.description} args: {{{params}}}")
    lines += ["", 'Use {"tool": null, "args": {}} when the request is just conversation or general knowledge '
                  "that does not need a tool. Never invent tool names. "
                  "Use web_search only for current events, live data or things you cannot know. "
                  "For math, convert wording to a plain expression (15% of 200 -> 0.15*200)."]
    return "\n".join(lines)


def looks_like_tool_request(text: str) -> bool:
    return bool(_DATETIME.search(text) or _HINTS.search(text))


def validate_call(obj: dict) -> ToolCall | None:
    tool = obj.get("tool") if isinstance(obj, dict) else None
    if not isinstance(tool, str) or tool not in REGISTRY:
        return None
    spec = REGISTRY[tool]
    raw_args = obj.get("args") or {}
    if not isinstance(raw_args, dict):
        return None
    args = {}
    for key in spec.params:
        val = raw_args.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            val = str(val)
        if not isinstance(val, str) or not val.strip() or len(val) > 500:
            log.info("Router rejected %s: bad/missing arg %s", tool, key)
            return None
        args[key] = val.strip()
    return ToolCall(tool, args)


async def route(llm, text: str) -> ToolCall | None:
    if _DATETIME.search(text):
        return ToolCall("datetime", {})
    if not _HINTS.search(text):
        return None
    obj = await llm.chat_json(
        [{"role": "system", "content": router_prompt()}, {"role": "user", "content": text}],
        options={"temperature": 0, "num_predict": 120})
    call = validate_call(obj)
    log.info("Router decision for %r: %s", text[:60], call)
    return call
