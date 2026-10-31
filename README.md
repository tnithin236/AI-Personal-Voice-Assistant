# Vaani — AI Personal Voice Assistant

A local, private voice assistant for Windows 11. Hold a button, speak English or Tamil, and Vaani transcribes,
remembers, searches your documents, uses tools, and answers by voice. No paid APIs, no cloud LLM.

**Pipeline:** Listen → Transcribe → Understand → Retrieve Memory → Think → Respond → Speak

| Layer | Technology |
|---|---|
| UI | React + Vite, Tailwind CSS v4, Framer Motion, Lucide |
| Backend | FastAPI, REST + WebSocket |
| LLM | Gemma 3 4B (`gemma3:4b`) via Ollama, 4096 ctx |
| Speech-to-text | Faster-Whisper `small`, CPU, INT8, VAD, auto language |
| Text-to-speech | Piper (English), AI4Bharat Indic-TTS (Tamil, separate service) |
| Storage | SQLite (chats, settings) + embedded Qdrant (memories, documents) |
| Embeddings | all-MiniLM-L6-v2 (CPU) |

## Honest status: what is verified and what is not

This code was written in an environment with **no internet, no Windows, no GPU and no microphone**. So:

| Part | Status |
|---|---|
| Calculator, chunking, router validation, SQLite, settings, file-safety rules, URL/app allow-lists | **Unit-tested** (`python -m unittest`) |
| All Python files compile; all JS/JSX files parse | **Checked** |
| Ollama chat, Whisper, microphone, Piper, Qdrant, MiniLM, PDF reading, web search, React build, WebSocket flow | **Written but NOT run.** Test each one using the checklist below |
| Tamil TTS (Indic-TTS) | **Least certain.** Written against the documented Coqui API; model paths and install on Windows may need adjusting |

Treat each phase below as "implemented, awaiting your test", and send me the output of any step that fails.

## 1. Setup (Windows PowerShell)

Prerequisites you already have: Python 3.12, Node, Git, Ollama with `gemma3:4b`.

```powershell
cd "C:\Users\Nithin T\Desktop\project_new\AI-Personal-Voice-Assistant"
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
```

This creates `.venv`, installs CPU PyTorch + requirements, copies `.env`, downloads the Piper voice, and runs `npm install`.
Whisper `small` and MiniLM download automatically from Hugging Face on first use (one-time, needs internet).

## 2. Run

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1
```

Or in two terminals: `scripts\start_backend.ps1` and `scripts\start_frontend.ps1`. Open http://localhost:5173.
API docs: http://127.0.0.1:8000/docs. Backend and frontend run independently.

Only run **one** backend at a time: embedded Qdrant locks `data\memory`.

## 3. Test phase by phase

Activate the venv first: `.\.venv\Scripts\Activate.ps1`

**Phase 1 — Environment + LLM.**
`python scripts\check_env.py` then `python scripts\benchmark_llm.py` (run once with browsers/Docker open and once closed; also try `--num-ctx 2048`).
Pass = all required checks PASS, and a tokens/sec figure for English and Tamil.

**Phase 2 — Backend.** Start the backend. Import `postman\Vaani.postman_collection.json` into Postman.
Pass = *Health* shows `llm.ok: true`; *Chat* returns a reply; *Chat (calculator tool)* returns `tool: "calculator"`.

**Phase 3 — Frontend.** Open the UI, type a message. Pass = tokens stream in, sidebar dot is green, history lists the chat.

**Phase 4 — Voice.**
1. Settings → pick your microphone. Hold the mic button (or Space), speak, release.
2. Pass = your words appear as a message, Vaani answers and speaks.
3. Tamil: set language to தமிழ் (or Auto) and speak Tamil. Tamil speech output needs section 5; without it you get text only.

**Phase 5 — Memory.** Say "Remember that my favourite colour is green." Check the Memory page; restart the backend; ask "What's my favourite colour?"
Pass = memory persists and is used.

**Phase 6 — Documents.** Upload a PDF, ask something in it, then ask something not in it.
Pass = it answers from the file, and says it could not find the second.

**Phase 7 — Tools.** "What's 15% of 2480", "what time is it", "search the web for …", "open notepad", "create a folder called test".
Then "delete C:\Users\Nithin T\Desktop\test" — Pass = a confirmation card appears and nothing is deleted until you approve.

**Phase 8 — Performance.** `python scripts\benchmark_pipeline.py`, and watch Settings → System status (RAM / VRAM). Timings also appear under each reply.

Unit tests (no models needed): `python -m unittest tests.test_core tests.test_tools tests.test_memory -v`
Full-stack vector test (after install): `python -m unittest tests.test_integration -v`

## 4. Piper voice (English)

`setup.ps1` runs this for you. If it failed, do it manually:

```powershell
cd data\models\piper
..\..\..\.venv\Scripts\python.exe -m piper.download_voices en_US-lessac-medium
```

You need `en_US-lessac-medium.onnx` and its `.onnx.json` in `data\models\piper`. If `python -m piper` does not work on your machine,
download `piper.exe` from the Piper releases page and set `VAANI_PIPER_EXE=C:\path\to\piper.exe` in `.env`.
Other voices: drop their files in the same folder; they appear in Settings.

## 5. Tamil speech output (optional, isolated)

Indic-TTS depends on an older Coqui TTS fork, so it runs in its **own** venv as a small local service (port 8010). The main app never imports it.

1. Create a venv, ideally with Python 3.10: `py -3.10 -m venv .venv-tamil` (install 3.10 first if `py -0` doesn't list it).
2. Follow https://github.com/AI4Bharat/Indic-TTS to install its TTS fork into `.venv-tamil` and download the Tamil models.
3. Put the models under `services\tamil_tts\models\ta\{fastpitch,hifigan}\` or point to them with env vars (see top of `services\tamil_tts\server.py`).
4. `pip install -r services\tamil_tts\requirements.txt` in `.venv-tamil`, then `scripts\start_tamil_tts.ps1`.
5. Settings → System status shows "Tamil voice: running".

If this service is off, Vaani still understands and answers Tamil in text. Tamil TTS runs on CPU so it never competes with Gemma for VRAM.

## 6. How it fits a 4 GB GPU

- Only Gemma (via Ollama) uses the GPU; Ollama splits layers between GPU and CPU automatically.
- Whisper, MiniLM, Piper and Tamil TTS run on CPU.
- Tune in Settings: context window, max reply length, GPU layers. Fallback model: `ollama pull gemma3:1b`, then choose it in Settings.
- Memory/document retrieval and the tool-router add small amounts of prompt; history is trimmed to fit the context budget.

## 7. Safety

- Tools are a fixed allow-list; the model can only choose a tool name and fill declared arguments, which are validated.
- Deleting always requires your approval. "Confirm every desktop action" (Tools page) extends that to opening apps, sites, folders, and key presses.
- File tools are confined to your user folder; only single files or empty folders can be deleted; top-level folders are protected.
- Apps open only from an allow-list (`backend/tools/desktop_control.py`); URLs must be http(s).
- Everything stays on your machine, except web search, which sends your query to a search engine.

## 8. Known limitations

- MiniLM is an English-focused embedding model, so Tamil memory/document retrieval is weaker. Auto-saved memories are written in English to help.
- "Live transcription" appears as soon as you release the button (Whisper is not streamed in this version).
- Scanned PDFs need OCR, which is not included.
- Each Piper sentence starts a short subprocess (~1 s overhead). Fine for v1; a persistent Piper worker is a later optimisation.
- Push-to-talk only. No wake word or continuous listening, as specified.
- The auto-memory extractor uses Gemma itself and can occasionally miss or over-save facts; review them on the Memory page.

## 9. Project layout

```
backend/   api/ brain/ voice/ memory/ documents/ tools/ core/   FastAPI app (run: uvicorn backend.main:app)
frontend/  src/{components,pages,hooks,services}                React + Vite UI
services/tamil_tts/                                             optional Tamil TTS service (own venv)
scripts/   setup, start, check_env, benchmarks
tests/     unit + integration tests          postman/  API collection
data/      database, qdrant memory, documents, models, logs (git-ignored)
```
Logs: `data\logs\vaani.log`. Config: `.env` (see `.env.example`) and the Settings page.
