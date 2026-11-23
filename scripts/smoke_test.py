"""End-to-end check of the RUNNING Vaani backend. Start everything first, then:

    python scripts\\smoke_test.py            # all checks
    python scripts\\smoke_test.py --skip-stt # skip the speech-recognition check

It uses a temporary folder in your home directory for the delete tests and cleans up after itself.
Real folders (Desktop, C:\\Windows\\...) are only ever tested with DENY, so nothing real can be deleted.
"""
import argparse
import io
import math
import os
import struct
import sys
import time
import uuid
import wave
from pathlib import Path


class Skip(Exception):
    pass


CHECKS: list = []


def check(name):
    def wrap(fn):
        CHECKS.append((name, fn))
        return fn
    return wrap


def tone_wav(seconds: float = 1.5, rate: int = 16000, hz: float = 440.0) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * hz * i / rate)))
                               for i in range(int(seconds * rate))))
    return buf.getvalue()


def ok_json(r, what):
    assert r.status_code == 200, f"{what}: HTTP {r.status_code} {r.text[:150]}"
    return r.json()


# ---------------------------------------------------------------- basics
@check("backend reachable, Ollama model ready")
def c_health(ctx):
    h = ok_json(ctx["api"].get("/health"), "health")
    assert h["llm"]["ok"], f"Ollama not reachable: {h['llm'].get('error')}"
    assert h["llm"]["model_available"], f"model {h['llm']['model']} is not pulled"
    return h["llm"]["model"]


@check("chat returns a reply")
def c_chat(ctx):
    d = ok_json(ctx["api"].post("/chat", json={"text": "Reply with the single word: ready"}), "chat")
    assert d["reply"].strip(), "empty reply"
    ctx["conversation"] = d["conversation_id"]
    return f"{d['reply'].strip()[:40]!r} ({d['timings'].get('total_ms')} ms)"


@check("calculator tool")
def c_calc(ctx):
    d = ok_json(ctx["api"].post("/tools/run", json={"tool": "calculator", "args": {"expression": "12*(3+4)"}}), "calc")
    assert "84" in d["result"], d
    return d["result"]


# ---------------------------------------------------------------- memory and documents
@check("memory: save, find, delete")
def c_memory(ctx):
    api = ctx["api"]
    m = ok_json(api.post("/memories", json={"text": "SMOKE TEST: the test sky is green"}), "add memory")
    try:
        hits = ok_json(api.get("/memories/search", params={"q": "what colour is the test sky", "k": 5}), "search")
        assert any(h["id"] == m["id"] for h in hits), "saved memory not found by search"
    finally:
        api.delete(f"/memories/{m['id']}")
    ids = [x["id"] for x in ok_json(api.get("/memories"), "list")]
    assert m["id"] not in ids, "memory still listed after delete"


@check("documents: upload, retrieve, delete")
def c_docs(ctx):
    api = ctx["api"]
    note = "The smoke-test launch code is PELICAN-7421. It was agreed on a Tuesday."
    doc = ok_json(api.post("/documents", files={"file": ("smoke_test_note.txt", note.encode(), "text/plain")}), "upload")
    try:
        hits = ok_json(api.post("/documents/search", json={"query": "what is the launch code", "k": 5}), "doc search")
        assert any("PELICAN-7421" in h["text"] for h in hits), "uploaded text not retrieved"
    finally:
        api.delete(f"/documents/{doc['id']}")
    assert doc["id"] not in [d["id"] for d in ok_json(api.get("/documents"), "doc list")], "document still listed"


# ---------------------------------------------------------------- voice
@check("English speech (Piper)")
def c_tts_en(ctx):
    r = ctx["api"].post("/tts", json={"text": "Smoke test.", "language": "en"})
    assert r.status_code == 200, f"HTTP {r.status_code} {r.text[:150]}"
    assert r.content[:4] == b"RIFF" and len(r.content) > 1000, "not a WAV file"
    return f"{len(r.content) // 1024} KB"


@check("Tamil speech (optional service)")
def c_tts_ta(ctx):
    r = ctx["api"].post("/tts", json={"text": "வணக்கம்", "language": "ta"})
    if r.status_code == 503:
        raise Skip("Tamil voice service is not running")
    assert r.status_code == 200, f"HTTP {r.status_code} {r.text[:150]}"
    assert r.content[:4] == b"RIFF" and len(r.content) > 1000, "not a WAV file"
    return f"{len(r.content) // 1024} KB"


@check("speech recognition runs (Whisper)")
def c_stt(ctx):
    if ctx.get("skip_stt"):
        raise Skip("skipped by --skip-stt")
    d = ok_json(ctx["api"].post("/transcribe", files={"file": ("tone.wav", tone_wav(), "audio/wav")},
                                data={"language": "en"}), "transcribe")
    assert "text" in d, d
    return "ran on a test tone (an empty transcript is correct)"


# ---------------------------------------------------------------- safety
def request_delete(api, path):
    r = api.post("/tools/run", json={"tool": "delete_path", "args": {"path": str(path)}})
    assert r.status_code == 200, f"HTTP {r.status_code} {r.text[:150]}"
    pending = r.json().get("pending_action")
    assert pending, "NO confirmation was requested for a delete"
    return pending


@check("SAFETY: delete asks first; Deny keeps the folder")
def c_deny(ctx):
    api, folder = ctx["api"], ctx["tmp"]
    pending = request_delete(api, folder)
    assert folder.exists(), "folder was deleted BEFORE confirmation"
    r = ok_json(api.post(f"/actions/{pending['id']}/confirm", json={"approve": False}), "deny")
    assert r["approved"] is False
    assert folder.exists(), "folder was deleted although Deny was chosen"


@check("SAFETY: Approve deletes (only after confirmation)")
def c_approve(ctx):
    api, folder = ctx["api"], ctx["tmp"]
    pending = request_delete(api, folder)
    assert folder.exists(), "folder was deleted BEFORE confirmation"
    r = ok_json(api.post(f"/actions/{pending['id']}/confirm", json={"approve": True}), "approve")
    assert r["approved"] is True and not folder.exists(), f"folder still exists after Approve: {r.get('text')}"
    return r["text"][:60]


@check("SAFETY: confirmation ids cannot be reused or guessed")
def c_bad_id(ctx):
    api = ctx["api"]
    assert api.post("/actions/not-a-real-id/confirm", json={"approve": True}).status_code == 404, "unknown id accepted"
    folder = ctx["home"] / f"vaani_smoketest_{uuid.uuid4().hex[:8]}"
    folder.mkdir()
    try:
        pending = request_delete(api, folder)
        api.post(f"/actions/{pending['id']}/confirm", json={"approve": False})
        again = api.post(f"/actions/{pending['id']}/confirm", json={"approve": True})
        assert again.status_code == 404 and folder.exists(), "a used confirmation was accepted a second time"
    finally:
        if folder.exists():
            folder.rmdir()


@check("SAFETY: Desktop and a Windows file also ask first (Deny only)")
def c_protected(ctx):
    api = ctx["api"]
    targets = [ctx["home"] / "Desktop", Path(os.environ.get("SystemRoot", "C:\\Windows")) / "notepad.exe"]
    for target in targets:
        existed = target.exists()
        pending = request_delete(api, target)
        api.post(f"/actions/{pending['id']}/confirm", json={"approve": False})
        assert target.exists() == existed, f"{target} changed although Deny was chosen"
    return "refusal rules themselves are covered by the unit tests"


@check("SAFETY: unlisted app and javascript: link are refused")
def c_refuse(ctx):
    api = ctx["api"]
    for tool, args in (("open_app", {"name": "format c:"}), ("open_website", {"url": "javascript:alert(1)"})):
        r = api.post("/tools/run", json={"tool": tool, "args": args})
        asked = r.status_code == 200 and r.json().get("pending_action")   # stricter mode asks first: also fine
        if asked:
            api.post(f"/actions/{r.json()['pending_action']['id']}/confirm", json={"approve": False})
        assert r.status_code == 400 or asked, f"{tool} was not refused: HTTP {r.status_code} {r.text[:100]}"


# ---------------------------------------------------------------- runner
def run_checks(api, home: Path, skip_stt: bool = False, out=print) -> list[tuple[str, str, str]]:
    ctx = {"api": api, "home": home, "skip_stt": skip_stt, "tmp": home / f"vaani_smoketest_{uuid.uuid4().hex[:8]}"}
    ctx["tmp"].mkdir()
    results = []
    try:
        for name, fn in CHECKS:
            t = time.perf_counter()
            try:
                status, detail = "PASS", fn(ctx) or ""
            except Skip as e:
                status, detail = "SKIP", str(e)
            except AssertionError as e:
                status, detail = "FAIL", str(e)
            except Exception as e:  # noqa: BLE001
                status, detail = "FAIL", f"{type(e).__name__}: {e}"
            ms = (time.perf_counter() - t) * 1000
            results.append((name, status, detail))
            out(f"[{status}] {name:58s} {ms:7.0f} ms  {detail}")
    finally:
        try:
            ctx["tmp"].rmdir()
        except OSError:
            pass
        if ctx.get("conversation"):
            try:
                api.delete(f"/conversations/{ctx['conversation']}")
            except Exception:  # noqa: BLE001
                pass
    return results


def main():
    import httpx
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--skip-stt", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    client = httpx.Client(base_url=a.base.rstrip("/") + "/api", timeout=180)
    try:
        client.get("/health")
    except httpx.HTTPError as e:
        sys.exit(f"Backend not reachable at {a.base}: {e}\nStart it first (scripts\\start_all.ps1).")
    print(f"Smoke test against {a.base}\n")
    results = run_checks(client, Path.home(), a.skip_stt)
    counts = {s: sum(1 for _, st, _ in results if st == s) for s in ("PASS", "FAIL", "SKIP")}
    print(f"\n{counts['PASS']} passed, {counts['FAIL']} failed, {counts['SKIP']} skipped")
    sys.exit(1 if counts["FAIL"] else 0)


if __name__ == "__main__":
    main()
