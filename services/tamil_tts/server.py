"""Standalone Tamil TTS service (AI4Bharat Indic-TTS / Coqui). Runs in its OWN virtualenv.

!! Not verified by the project author on real hardware. It follows the documented Coqui
   `Synthesizer` API used by AI4Bharat/Indic-TTS. If a model path differs on your machine,
   override it with the environment variables below.

Run:  .venv-tamil\\Scripts\\python services\\tamil_tts\\server.py
"""
import io
import os
import tempfile
import threading
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

HERE = Path(__file__).resolve().parent
MODELS = Path(os.environ.get("INDIC_TTS_MODELS", HERE / "models" / "ta"))
TTS_CKPT = Path(os.environ.get("INDIC_TTS_CKPT", MODELS / "fastpitch" / "best_model.pth"))
TTS_CFG = Path(os.environ.get("INDIC_TTS_CONFIG", MODELS / "fastpitch" / "config.json"))
TTS_SPK = Path(os.environ.get("INDIC_TTS_SPEAKERS", MODELS / "fastpitch" / "speakers.pth"))
VOC_CKPT = Path(os.environ.get("INDIC_VOCODER_CKPT", MODELS / "hifigan" / "best_model.pth"))
VOC_CFG = Path(os.environ.get("INDIC_VOCODER_CONFIG", MODELS / "hifigan" / "config.json"))
SPEAKER = os.environ.get("INDIC_TTS_SPEAKER", "female")  # "male" or "female"
USE_CUDA = os.environ.get("INDIC_TTS_CUDA", "0") == "1"  # keep 0: the 4 GB GPU belongs to the LLM

app = FastAPI(title="Vaani Tamil TTS")
_synth = None
_lock = threading.Lock()


class Req(BaseModel):
    text: str


def get_synth():
    global _synth
    with _lock:
        if _synth is None:
            missing = [str(p) for p in (TTS_CKPT, TTS_CFG, VOC_CKPT, VOC_CFG) if not p.exists()]
            if missing:
                raise RuntimeError("Missing model files: " + ", ".join(missing))
            from TTS.utils.synthesizer import Synthesizer
            _synth = Synthesizer(tts_checkpoint=str(TTS_CKPT), tts_config_path=str(TTS_CFG),
                                 tts_speakers_file=str(TTS_SPK) if TTS_SPK.exists() else None,
                                 vocoder_checkpoint=str(VOC_CKPT), vocoder_config=str(VOC_CFG),
                                 use_cuda=USE_CUDA)
        return _synth


@app.get("/health")
def health():
    missing = [str(p) for p in (TTS_CKPT, TTS_CFG, VOC_CKPT, VOC_CFG) if not p.exists()]
    return {"models_found": not missing, "missing": missing, "loaded": _synth is not None, "speaker": SPEAKER}


@app.post("/synthesize")
def synthesize(req: Req):
    try:
        synth = get_synth()
        with _lock:
            wav = synth.tts(req.text, speaker_name=SPEAKER if synth.tts_speakers_file else None)
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            synth.save_wav(wav, tmp)
            return Response(Path(tmp).read_bytes(), media_type="audio/wav")
        finally:
            Path(tmp).unlink(missing_ok=True)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(500, f"{type(e).__name__}: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8010")))
