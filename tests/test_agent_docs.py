"""Agent behaviour around documents/memory, with fake services (no Ollama, Qdrant or models needed)."""
import asyncio
import unittest
from types import SimpleNamespace

from tests import _stubs  # noqa: F401
from backend.brain import agent as agent_mod
from backend.brain.prompts import system_prompt


class FakeConvo:
    def __init__(self): self.msgs = []
    def add_message(self, cid, role, content, language=None, meta=None):
        self.msgs.append({"role": role, "content": content}); return len(self.msgs)
    def messages(self, cid): return list(self.msgs)


class FakeVectors:
    def __init__(self, doc_hits, memories=()):
        self.doc_hits, self.memories, self.doc_calls = doc_hits, list(memories), []
    def search_memories(self, q, k=5, min_score=0.0):
        return [{"text": m, "score": 0.5} for m in self.memories]
    def search_docs(self, q, k=4, min_score=0.0):
        self.doc_calls.append(min_score)
        return [h for h in self.doc_hits if h["score"] >= min_score][:k]


class FakeLLM:
    def __init__(self): self.last_stats, self.system = {}, None
    async def stream(self, messages, options=None):
        self.system = messages[0]["content"]
        yield "ok"


def run_agent(user_text, doc_count, doc_hits, memories=(), use_tools=False, router=None):
    cfg = {"language": "auto", "use_memory": True, "use_documents": True, "use_tools": use_tools, "auto_memory": False,
           "confirm_all_actions": False, "max_tokens": 400, "num_ctx": 4096}
    s = SimpleNamespace(
        cfg=SimpleNamespace(app_name="Vaani"), settings=SimpleNamespace(all=lambda: cfg),
        convo=FakeConvo(), vectors=FakeVectors(doc_hits, memories), llm=FakeLLM(),
        documents_repo=SimpleNamespace(count=lambda: doc_count), actions=None)
    events = []

    async def emit(e): events.append(e)

    original = agent_mod.tool_router.route
    if router is not None:
        agent_mod.tool_router.route = router
    try:
        asyncio.run(agent_mod.Agent(s).respond("c1", user_text, emit))
    finally:
        agent_mod.tool_router.route = original
    return s, events


class DocBehaviourTests(unittest.TestCase):
    def test_deleted_document_gets_not_found_note(self):
        s, ev = run_agent("Introduce Nithin based on his resume.", 0, [], memories=["The user works as a data analyst."])
        self.assertIn("couldn't find it in the uploaded documents", s.llm.system)
        self.assertIn("Never invent facts", s.llm.system)
        self.assertIn("data analyst", s.llm.system)            # memory still available
        self.assertEqual(s.vectors.doc_calls, [])               # nothing indexed -> no search at all
        self.assertEqual(ev[-1]["type"], "done")

    def test_plain_question_gets_no_document_note(self):
        s, _ = run_agent("What is the capital of France?", 1, [])
        self.assertNotIn("uploaded document", s.llm.system)

    def test_found_document_is_used_instead_of_note(self):
        hit = {"score": 0.5, "filename": "cv.pdf", "page": 1, "text": "Nithin knows SQL."}
        s, _ = run_agent("Summarise my resume", 1, [hit])
        self.assertIn("cv.pdf", s.llm.system)
        self.assertNotIn("no uploaded document matched", s.llm.system)

    def test_weak_match_accepted_when_user_names_a_document(self):
        weak = {"score": 0.12, "filename": "cv.pdf", "page": None, "text": "Experience: analyst."}
        s, _ = run_agent("Tell me about my resume", 1, [weak])
        self.assertEqual(s.vectors.doc_calls, [0.30, 0.05])    # strict search first, then the loose retry
        self.assertIn("cv.pdf", s.llm.system)

    def test_weak_match_ignored_for_ordinary_question(self):
        weak = {"score": 0.12, "filename": "cv.pdf", "page": None, "text": "Experience: analyst."}
        s, _ = run_agent("What is the tallest mountain?", 1, [weak])
        self.assertEqual(s.vectors.doc_calls, [0.30])
        self.assertNotIn("cv.pdf", s.llm.system)

    def test_document_answer_beats_web_search(self):
        calls = []

        async def router(llm, text):
            calls.append(text)
            return None

        hit = {"score": 0.6, "filename": "sample_notes.txt", "page": None, "text": "Orion launches on 14 March 2027."}
        s, _ = run_agent("When does the Orion project launch?", 1, [hit], use_tools=True, router=router)
        self.assertEqual(calls, [])                                  # router never ran -> no web search
        self.assertIn("14 March 2027", s.llm.system)

    def test_explicit_web_request_still_uses_tools_when_documents_match(self):
        calls = []

        async def router(llm, text):
            calls.append(text)
            return None

        hit = {"score": 0.6, "filename": "n.txt", "page": None, "text": "Orion notes."}
        run_agent("Search the web for the Orion spacecraft", 1, [hit], use_tools=True, router=router)
        self.assertEqual(len(calls), 1)

    def test_router_still_runs_when_no_document_matches(self):
        calls = []

        async def router(llm, text):
            calls.append(text)
            return None

        run_agent("what time is it", 1, [], use_tools=True, router=router)
        self.assertEqual(len(calls), 1)

    def test_launch_as_a_noun_does_not_trigger_tools(self):
        from backend.brain import tool_router as tr
        self.assertFalse(tr.looks_like_tool_request("When does the Orion project launch?"))
        self.assertFalse(tr.looks_like_tool_request("What was the launch date?"))
        self.assertTrue(tr.looks_like_tool_request("launch notepad"))
        self.assertTrue(tr.looks_like_tool_request("open notepad"))

    def test_prompt_builder_extra_note(self):
        p = system_prompt("Vaani", "auto", "now", extra_note="NOTE-XYZ")
        self.assertIn("NOTE-XYZ", p)


if __name__ == "__main__":
    unittest.main()
