import unittest

from tests import _stubs  # noqa: F401
from backend.brain.agent import fit_history
from backend.brain.llm import parse_json_loose
from backend.core.lang import detect_language, estimate_tokens
from backend.documents.chunking import chunk_text
from backend.documents.retrieval import format_chunks


class LangTests(unittest.TestCase):
    def test_detect(self):
        self.assertEqual(detect_language("Hello there"), "en")
        self.assertEqual(detect_language("வணக்கம், எப்படி இருக்கிறீர்கள்?"), "ta")
        self.assertEqual(detect_language("12345"), "en")

    def test_tokens_tamil_costs_more(self):
        self.assertGreater(estimate_tokens("வணக்கம்" * 10), estimate_tokens("hello!!" * 10))


class JsonTests(unittest.TestCase):
    def test_loose(self):
        self.assertEqual(parse_json_loose('```json\n{"a":1}\n```'), {"a": 1})
        self.assertEqual(parse_json_loose('sure! {"a": 2} ok'), {"a": 2})
        self.assertEqual(parse_json_loose("nope"), {})
        self.assertEqual(parse_json_loose("[1,2]"), {})


class HistoryTests(unittest.TestCase):
    def test_fit_keeps_recent(self):
        h = [{"role": "user", "content": "a" * 350}, {"role": "assistant", "content": "b" * 350},
             {"role": "user", "content": "c" * 35}]
        self.assertEqual(len(fit_history(h, 5000)), 3)
        kept = fit_history(h, 150)
        self.assertEqual(kept[-1]["content"], "c" * 35)
        self.assertLess(len(kept), 3)
        self.assertEqual(fit_history(h, 0), [])


class ChunkTests(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(chunk_text("   \n\n "), [])

    def test_size_and_overlap(self):
        text = "\n\n".join(f"Paragraph {i}. " + "word " * 40 for i in range(20))
        chunks = chunk_text(text, size=500, overlap=80)
        self.assertGreater(len(chunks), 3)
        self.assertTrue(all(len(c) <= 500 + 80 + 4 for c in chunks))
        self.assertIn("Paragraph 19", chunks[-1])

    def test_long_paragraph_split(self):
        chunks = chunk_text("This is a sentence. " * 200, size=300, overlap=0)
        self.assertTrue(all(len(c) <= 300 for c in chunks))
        self.assertGreater(len(chunks), 5)

    def test_unbroken_text(self):
        chunks = chunk_text("x" * 2500, size=800, overlap=0)
        self.assertEqual(sum(len(c) for c in chunks), 2500)

    def test_tamil(self):
        chunks = chunk_text("இது ஒரு வாக்கியம். " * 100, size=400, overlap=50)
        self.assertGreater(len(chunks), 1)

    def test_format_chunks(self):
        out = format_chunks([{"filename": "a.pdf", "page": 3, "text": "hello"}, {"filename": "b.txt", "page": None, "text": "x"}])
        self.assertIn("(a.pdf, page 3)", out)
        self.assertIn("(b.txt)", out)
        self.assertEqual(format_chunks([{"filename": "a", "text": "y" * 5000}], max_chars=100), "")


if __name__ == "__main__":
    unittest.main()
