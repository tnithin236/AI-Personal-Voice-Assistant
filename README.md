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

## Status: what has been verified

Everything below was run by the author on the target machine (Windows 11, RTX 3050 4 GB, `gemma3:4b`).
The full checklist, with a PASS column to fill in, is in [TESTING.md](TESTING.md).

| Confirmed working | Not yet confirmed |
|---|---|
| Chat with streaming replies, history, React UI, WebSocket | Time tool, file search, folder creation |
| Push-to-talk (button and Space key), English transcription | Delete confirmation and refusal flow (H1-H4) |
| Tamil transcription (Whisper `small`, beam 5, language set to Tamil) | Indic-TTS engine (the optional alternative) |
| English speech (Piper, in-process, ~0.1 s per sentence) | Long-running stability |
| Tamil speech (MMS-TTS engine) | Performance report (section J of TESTING.md) |
| Long-term memory: save, recall, restart, delete | |
| Document Q&A, including "not found" and deleted files | |
| Calculator, web search, opening apps (incl. `apps.json`) | |

Automated tests: `python -m unittest discover -s tests -t .` (67 tests, no models needed).

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

**Phase 8 — Performance.** Use the assistant for a while, then `python scripts\log_report.py` (latency per stage from the log) and
`python scripts\resource_report.py --seconds 90` (RAM / VRAM while you use it). `python scripts\benchmark_pipeline.py` runs a fixed set of text prompts. Timings also appear under each reply.

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

## 5. Tamil speech output (optional)

Tamil replies are always shown as text. To also hear them, start the small Tamil voice service (port 8010):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_tamil_tts.ps1
```

- **Default engine: MMS-TTS Tamil** (Meta, `facebook/mms-tts-tam`). It runs on CPU inside the main `.venv` with packages you
  already have, so there is nothing to install. The model (a small download) is fetched from Hugging Face on first start.
  Its license is CC-BY-NC 4.0 (non-commercial), which is fine for personal and portfolio use.
- **AI4Bharat Indic-TTS** (the originally specified engine) is still supported: `$env:TAMIL_TTS_ENGINE = "indic"` before starting,
  from a separate `.venv-tamil`. It follows a Linux/conda setup with an old Coqui fork and is **not verified on Windows**.
- Digits and Latin letters inside Tamil sentences are not spoken by MMS; write numbers as words if that matters.
- Settings -> System status shows "Tamil voice: running" when the service is up. If it is off, Vaani falls back to text only.

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
