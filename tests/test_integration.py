"""Needs the full install (fastapi, qdrant-client, sentence-transformers) and runs the real stack
WITHOUT Ollama. Skipped automatically if dependencies are missing. Run:  python -m unittest tests.test_integration -v"""
import tempfile
import unittest
from pathlib import Path

try:
    import qdrant_client  # noqa: F401
    import sentence_transformers  # noqa: F401
    HAVE = True
except ImportError:
    HAVE = False


@unittest.skipUnless(HAVE, "qdrant-client / sentence-transformers not installed")
class VectorTests(unittest.TestCase):
    def test_memory_and_docs(self):
        from backend.memory.embeddings import Embedder
        from backend.memory.qdrant_store import VectorStore
        tmp = Path(tempfile.mkdtemp())
        vs = VectorStore(tmp / "q", Embedder("all-MiniLM-L6-v2", tmp))
        vs.add_memory("The user's favourite colour is green.", "user")
        vs.add_memory("The user works as a data analyst.", "auto")
        hit = vs.search_memories("what colour does the user like?", k=1, min_score=0.1)
        self.assertIn("green", hit[0]["text"])
        self.assertEqual(len(vs.search_memories("analyst job", k=5, min_score=0.0, source="user")), 1)
        mid = vs.list_memories()[0]["id"]
        vs.delete_memory(mid)
        self.assertEqual(len(vs.list_memories()), 1)
        vs.add_chunks("d1", "cats.txt", [{"page": None, "text": "Cats sleep for up to sixteen hours a day."},
                                         {"page": None, "text": "The Eiffel Tower is in Paris."}])
        top = vs.search_docs("how long do cats sleep", k=1, min_score=0.0, doc_ids=["d1"])
        self.assertIn("Cats", top[0]["text"])
        vs.delete_document("d1")
        self.assertEqual(vs.search_docs("cats", k=3, min_score=0.0), [])
        vs.close()


if __name__ == "__main__":
    unittest.main()
