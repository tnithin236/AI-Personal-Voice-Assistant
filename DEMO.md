# Vaani — demo guide (about 4 minutes)

## Before you present (5 minutes)

1. Plug in the laptop and set Windows power mode to **Best performance**.
2. Close GPU-hungry apps (Docker Desktop, browsers with many tabs). More free GPU memory means more of Gemma runs on the GPU;
   `ollama ps` shows the CPU/GPU split.
3. Start everything: `powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1 -Tamil` and wait for four "ready" lines.
4. Run `python scripts\smoke_test.py`. Everything should pass (Tamil is skipped if its service is off). It also warms up
   speech recognition, so your first spoken question is not slow.
5. In the UI: language **Auto**, pick the right microphone in Settings, check the volume, open the **Memory** page and clear
   old memories so you can show learning live. Upload one PDF or TXT with a few facts you know well.
6. Plan B: if the microphone misbehaves, type; if Tamil voice is off, the reply still shows as text; if Ollama stops,
   `ollama serve` and try again.

## The walkthrough

| Time | Do | Say / show |
|---|---|---|
| 0:00 | Open **Settings → System status** | "Everything runs on this laptop: Gemma 3 4B through Ollama, Whisper for speech, Piper and MMS for the voice, Qdrant for memory. Nothing leaves the machine except web search." Point at the RAM and GPU lines. |
| 0:30 | Hold the mic (or Space): "What is the capital of France?" | The transcript appears, the answer streams in and is spoken. Hover over the reply to show the timing (first word about 1.5 s). |
| 1:00 | Language **தமிழ்**: "உன்னுடைய பெயர் என்ன?" | Tamil transcription, Tamil reply, spoken with the Tamil voice. Mention the male-to-female voice conversion and the pitch slider. |
| 1:30 | "Remember that my favourite colour is green and I work as a data analyst." Then open **Memory** | After a few seconds two short facts appear. **New** chat: "What do I do for work?" — it answers from memory. Delete a memory to show control. |
| 2:00 | **Documents**: upload the file, ask something it contains, then something it does not | Answer cites the file; the second question gets "I couldn't find that in your documents". Stress that it does not invent. |
| 2:45 | "What is 15 percent of 2480?" then "Open Notepad" and "Open Camera" | The calculator is a safe evaluator; apps come from an allow-list; the reply is the tool's own sentence. |
| 3:15 | "Create a folder called demo_test", then "Delete the folder C:\Users\<you>\Desktop\demo_test" | A yellow confirmation card appears and nothing is deleted. Click **Deny**, ask again, click **Approve**. |
| 3:45 | Show the README architecture diagram and `TESTING.md` | "105+ automated tests, a live smoke test that checks the safety flow, and measured performance on a 4 GB GPU." |

## Talking points (engineering decisions)

- **4 GB VRAM:** only about 44% of Gemma fits on the GPU, so it is split with the CPU. The speech models run on CPU so they do not
  compete. All numbers in the README are measured, not estimated.
- **Safety by design:** the language model can only pick a tool *name*; arguments are validated; deleting always needs approval;
  apps come from an allow-list; desktop actions reply with the tool's own text so the model cannot misreport them.
- **Honest answers:** document questions are grounded in retrieved text, and "not found" is a valid answer.
- **Graceful degradation:** no Tamil service → text only; no Praat → simpler voice effect; Ollama down → a readable error.

## Be upfront about the limits

Gemma 3 4B can still make mistakes. Tamil transcription is good with the language set to Tamil but not perfect. The Tamil voice is a
converted male voice, not a native female neural voice. Push-to-talk only. Scanned PDFs are not read (no OCR).
