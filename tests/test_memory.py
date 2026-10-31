import unittest

from backend.memory.conversation import ConversationRepo, DocumentRepo
from backend.memory.database import Database, SettingsStore


class DbTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.repo = ConversationRepo(self.db)

    def test_conversation_flow(self):
        cid = self.repo.create()
        self.repo.add_message(cid, "user", "Hello   there, how are you today my friend?", "en")
        self.repo.add_message(cid, "assistant", "Fine!", "en", {"tool": "datetime"})
        conv = self.repo.get(cid)
        self.assertEqual(conv["title"], "Hello there, how are you today my friend?")
        self.assertEqual([m["role"] for m in conv["messages"]], ["user", "assistant"])
        self.assertEqual(conv["messages"][1]["meta"], {"tool": "datetime"})
        self.assertEqual(self.repo.last_user_text(cid), "Hello   there, how are you today my friend?")
        self.repo.delete_last_assistant(cid)
        self.assertEqual(len(self.repo.messages(cid)), 1)
        self.repo.delete_last_assistant(cid)          # last is a user message -> untouched
        self.assertEqual(len(self.repo.messages(cid)), 1)
        self.repo.clear(cid)
        self.assertEqual(self.repo.messages(cid), [])
        self.repo.delete(cid)
        self.assertIsNone(self.repo.get(cid))

    def test_tamil_roundtrip_and_cascade(self):
        cid = self.repo.create()
        self.repo.add_message(cid, "user", "வணக்கம்", "ta")
        self.assertEqual(self.repo.messages(cid)[0]["content"], "வணக்கம்")
        self.repo.delete(cid)
        self.assertEqual(self.db.query("SELECT COUNT(*) n FROM messages")[0]["n"], 0)

    def test_list_order(self):
        a, b = self.repo.create("a"), self.repo.create("b")
        self.repo.add_message(a, "user", "x")
        self.assertEqual(self.repo.list()[0]["id"], a)

    def test_settings(self):
        st = SettingsStore(self.db, {"language": "auto", "voice_speed": 1.0, "mic_device": None})
        self.assertEqual(st.all()["language"], "auto")
        st.update({"language": "ta", "mic_device": 3})
        self.assertEqual((st.get("language"), st.get("mic_device")), ("ta", 3))
        with self.assertRaises(KeyError):
            st.update({"nope": 1})
        self.assertEqual(st.reset()["language"], "auto")

    def test_documents_repo(self):
        d = DocumentRepo(self.db)
        d.add("id1", "a.pdf", "/x/a.pdf", 5, 2, 100)
        self.assertEqual(d.count(), 1)
        self.assertEqual(d.get("id1")["chunks"], 5)
        d.delete("id1")
        self.assertEqual(d.count(), 0)


if __name__ == "__main__":
    unittest.main()
