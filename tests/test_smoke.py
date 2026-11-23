"""The smoke-test script, run against an in-memory fake backend (no network, no models).
Includes deliberately UNSAFE fakes to prove the safety checks can actually fail."""
import json
import tempfile
import unittest
import uuid
from pathlib import Path

from scripts import smoke_test


class R:
    def __init__(self, status=200, payload=None, content=b"", text=""):
        self.status_code, self._payload, self.content = status, payload, content
        self.text = text or json.dumps(payload)

    def json(self):
        return self._payload


class FakeBackend:
    def __init__(self, delete_before_confirm=False, ignore_deny=False, reuse_ids=False, tamil=False, llm_ok=True):
        self.flags = dict(delete_before_confirm=delete_before_confirm, ignore_deny=ignore_deny, reuse_ids=reuse_ids,
                          tamil=tamil, llm_ok=llm_ok)
        self.memories, self.docs, self.pending = {}, {}, {}

    def get(self, path, params=None):
        if path == "/health":
            return R(payload={"llm": {"ok": self.flags["llm_ok"], "model": "gemma3:4b", "model_available": True,
                                      "error": "connection refused"}})
        if path == "/memories":
            return R(payload=[{"id": i} for i in self.memories])
        if path == "/memories/search":
            return R(payload=[{"id": i, "text": t} for i, t in self.memories.items()])
        if path == "/documents":
            return R(payload=[{"id": i} for i in self.docs])
        return R(404, {"detail": "nope"})

    def post(self, path, json=None, files=None, data=None):
        if path == "/chat":
            return R(payload={"conversation_id": "c1", "reply": "ready", "timings": {"total_ms": 5}})
        if path == "/tools/run":
            return self._tool(json)
        if path.startswith("/actions/") and path.endswith("/confirm"):
            return self._confirm(path.split("/")[2], json["approve"])
        if path == "/memories":
            mid = uuid.uuid4().hex
            self.memories[mid] = json["text"]
            return R(payload={"id": mid})
        if path == "/documents":
            did = uuid.uuid4().hex
            self.docs[did] = files["file"][1].decode()
            return R(payload={"id": did})
        if path == "/documents/search":
            return R(payload=[{"text": t} for t in self.docs.values()])
        if path == "/tts":
            if json["language"] == "ta" and not self.flags["tamil"]:
                return R(503, {"detail": "Tamil voice service is not running"})
            return R(content=b"RIFF" + b"\0" * 2000)
        if path == "/transcribe":
            return R(payload={"text": "", "language": "en"})
        return R(404, {"detail": "nope"})

    def delete(self, path):
        kind, ident = path.strip("/").split("/", 1)
        {"memories": self.memories, "documents": self.docs}.get(kind, {}).pop(ident, None)
        return R(payload={"ok": True})

    def _tool(self, body):
        tool, args = body["tool"], body["args"]
        if tool == "calculator":
            return R(payload={"result": "12*(3+4) = 84"})
        if tool == "delete_path":
            path = Path(args["path"])
            if self.flags["delete_before_confirm"] and path.is_dir():
                path.rmdir()                                   # the dangerous bug
            pid = uuid.uuid4().hex[:8]
            self.pending[pid] = path
            return R(payload={"pending_action": {"id": pid, "tool": tool, "description": f"DELETE {path}"}})
        return R(400, {"detail": "not on my allowed apps list"})

    def _confirm(self, pid, approve):
        if pid not in self.pending:
            return R(404, {"detail": "expired"})
        path = self.pending[pid] if self.flags["reuse_ids"] else self.pending.pop(pid)
        if (approve or self.flags["ignore_deny"]) and path.is_dir() and path.name.startswith("vaani_smoketest_"):
            path.rmdir()
        return R(payload={"approved": approve, "text": "Deleted empty folder" if approve else "Okay, I cancelled that."})


def run(fake, skip_stt=False):
    home = Path(tempfile.mkdtemp())
    (home / "Desktop").mkdir()
    res = smoke_test.run_checks(fake, home, skip_stt, out=lambda *_: None)
    return {name: (status, detail) for name, status, detail in res}, home


class SmokeTests(unittest.TestCase):
    def test_correct_backend_passes_everything_and_cleans_up(self):
        res, home = run(FakeBackend())
        self.assertFalse([n for n, (s, d) in res.items() if s == "FAIL"], res)
        self.assertEqual(res["Tamil speech (optional service)"][0], "SKIP")
        self.assertEqual(sum(1 for s, _ in res.values() if s == "PASS"), len(res) - 1)
        self.assertEqual(list(home.glob("vaani_smoketest_*")), [])          # temp folder removed

    def test_tamil_is_checked_when_the_service_is_up(self):
        res, _ = run(FakeBackend(tamil=True))
        self.assertEqual(res["Tamil speech (optional service)"][0], "PASS")

    def test_skip_stt_flag(self):
        res, _ = run(FakeBackend(), skip_stt=True)
        self.assertEqual(res["speech recognition runs (Whisper)"][0], "SKIP")

    def test_unreachable_ollama_fails_the_health_check(self):
        res, _ = run(FakeBackend(llm_ok=False))
        status, detail = res["backend reachable, Ollama model ready"]
        self.assertEqual(status, "FAIL")
        self.assertIn("connection refused", detail)

    def test_detects_a_delete_that_happens_before_confirmation(self):
        res, _ = run(FakeBackend(delete_before_confirm=True))
        status, detail = res["SAFETY: delete asks first; Deny keeps the folder"]
        self.assertEqual(status, "FAIL")
        self.assertIn("BEFORE confirmation", detail)

    def test_detects_a_deny_that_is_ignored(self):
        res, _ = run(FakeBackend(ignore_deny=True))
        status, detail = res["SAFETY: delete asks first; Deny keeps the folder"]
        self.assertEqual(status, "FAIL")
        self.assertIn("although Deny", detail)

    def test_detects_a_confirmation_that_can_be_reused(self):
        res, _ = run(FakeBackend(reuse_ids=True))
        self.assertEqual(res["SAFETY: confirmation ids cannot be reused or guessed"][0], "FAIL")

    def test_tone_wav_is_a_valid_16k_mono_wav(self):
        import io
        import wave
        with wave.open(io.BytesIO(smoke_test.tone_wav(0.5)), "rb") as w:
            self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()), (1, 2, 16000, 8000))


if __name__ == "__main__":
    unittest.main()
