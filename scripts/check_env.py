"""Environment check. Run from the project root with the venv active:  python scripts\\check_env.py"""
import importlib
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
results = []  # (ok, name, detail, optional)


def check(name, fn, optional=False):
    try:
        detail = fn()
        results.append((True, name, detail or "", optional))
    except Exception as e:  # noqa: BLE001
        results.append((False, name, f"{type(e).__name__}: {e}", optional))


def py_version():
    assert sys.version_info[:2] == (3, 12), f"found {sys.version.split()[0]}, wanted 3.12"
    return sys.version.split()[0]


def imp(mod):
    return lambda: getattr(importlib.import_module(mod), "__version__", "ok")


def http_json(url):
    with urllib.request.urlopen(url, timeout=3) as r:
        return json.loads(r.read())


def ollama():
    from backend.config import Config
    c = Config()
    names = [m["name"] for m in http_json(f"{c.ollama_url}/api/tags")["models"]]
    assert c.llm_model in names, f"{c.llm_model} not pulled (have: {names})"
    return f"{c.llm_model} available"


def piper():
    from backend.config import Config
    c = Config()
    cmd = [c.piper_exe, "--help"] if c.piper_exe else [sys.executable, "-m", "piper", "--help"]
    r = subprocess.run(cmd, capture_output=True, timeout=30)
    assert r.returncode == 0, r.stderr.decode()[-200:]
    voice = c.models_dir / "piper" / f"{c.piper_voice}.onnx"
    assert voice.exists(), f"voice file missing: {voice}"
    return f"piper OK, voice {voice.name}"


def mics():
    import sounddevice as sd
    ins = [d["name"] for d in sd.query_devices() if d["max_input_channels"] > 0]
    assert ins, "no input devices"
    return f"{len(ins)} input devices"


def gpu():
    out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader"],
                         capture_output=True, text=True, timeout=10)
    assert out.returncode == 0, "nvidia-smi failed"
    return out.stdout.strip()


def tamil():
    from backend.config import Config
    d = http_json(Config().tamil_tts_url + "/health")
    assert d.get("models_found"), f"models missing: {d.get('missing')}"
    return "Tamil TTS service running"


check("Python 3.12", py_version)
for m in ["fastapi", "uvicorn", "httpx", "pydantic_settings", "numpy", "faster_whisper", "sounddevice",
          "qdrant_client", "sentence_transformers", "pymupdf", "pyautogui", "ddgs", "psutil", "pynvml", "multipart"]:
    check(f"import {m}", imp(m))
check("NVIDIA GPU", gpu)
check("Ollama + model", ollama)
check("Piper + English voice", piper)
check("Microphone", mics)
check("Tamil TTS service (optional)", tamil, optional=True)

print()
for ok, name, detail, optional in results:
    tag = "PASS" if ok else ("SKIP" if optional else "FAIL")
    print(f"[{tag}] {name:34s} {detail}")

required = [r for r in results if not r[3]]
passed = [r for r in required if r[0]]
failed = [r[1] for r in required if not r[0]]
print(f"\n{len(passed)}/{len(required)} required checks passed"
      + (f"  |  needs attention: {', '.join(failed)}" if failed else ""))
sys.exit(1 if failed else 0)