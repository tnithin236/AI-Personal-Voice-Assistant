"""Standalone Tamil TTS service (HTTP, port 8010). Vaani's backend calls it; if it is not running,
Vaani simply shows Tamil replies as text.

Engines (pick with the TAMIL_TTS_ENGINE environment variable):
  mms    (default)  Meta MMS-TTS Tamil (VITS, `facebook/mms-tts-tam`). Runs in the main .venv on CPU with the
                    `transformers` + `torch` you already have. License CC-BY-NC 4.0 (non-commercial use).
  indic             AI4Bharat Indic-TTS (Coqui fork). Needs its own venv and manual model download.
                    NOT verified by the project author; Linux/conda is the documented setup.

Run:  scripts\\start_tamil_tts.ps1
"""
import io
import logging
import math
import os
import threading
import time
import wave
from pathlib import Path

import numpy as np

log = logging.getLogger("tamil_tts")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MAX_CHARS = 600
PITCH_MIN, PITCH_MAX = 1.0, 1.8
FALLBACK_PITCH_MAX = 1.3   # the no-Praat fallback sounds unnatural above this


def clamp_pitch(pitch) -> float:
    try:
        return min(PITCH_MAX, max(PITCH_MIN, float(pitch)))
    except (TypeError, ValueError):
        return 1.0


def praat_available() -> bool:
    try:
        import parselmouth  # noqa: F401
        return True
    except ImportError:
        return False


def feminise(samples, rate: int, pitch_ratio: float):
    """Praat's "Change gender": multiplies the median pitch by `pitch_ratio` and moves the formants up with it
    (a formant ratio of about 1.1 turns a male voice into approximately female formants, per the Praat manual).
    Returns a float32 array, or None if Praat is missing, the clip has no measurable pitch, or Praat fails."""
    try:
        import parselmouth
        from parselmouth.praat import call
    except ImportError:
        return None
    try:
        sound = parselmouth.Sound(np.asarray(samples, dtype=np.float64).reshape(-1), sampling_frequency=rate)
        pitch = call(sound, "To Pitch", 0.8 / 75, 75, 600)
        median = call(pitch, "Get quantile", 0.0, 0.0, 0.5, "Hertz")
        if not median or math.isnan(median):
            return None
        formant_ratio = min(1.2, 1.0 + 0.3 * (pitch_ratio - 1.0))
        out = call(sound, "Change gender", 75, 600, formant_ratio, median * pitch_ratio, 1.0, 1.0)
        audio = np.asarray(out.values, dtype=np.float32).reshape(-1)
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        return audio / peak * 0.99 if peak > 0.99 else audio
    except Exception as e:  # noqa: BLE001 - never let post-processing break speech
        log.warning("Voice change failed (%s: %s); speaking with the original voice", type(e).__name__, e)
        return None


def pcm16_wav(samples, rate: int) -> bytes:
    """float waveform in [-1, 1] -> 16-bit mono WAV bytes."""
    x = np.clip(np.asarray(samples, dtype=np.float32).reshape(-1), -1.0, 1.0)
    if x.size == 0:
        raise ValueError("The model produced no audio.")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(rate))
        w.writeframes((x * 32767.0).astype("<i2").tobytes())
    return buf.getvalue()


class MmsEngine:
    name = "mms"

    def __init__(self, model_name: str | None = None, cache_dir: Path | None = None):
        self.model_name = model_name or os.environ.get("MMS_TTS_MODEL", "facebook/mms-tts-tam")
        self.cache_dir = cache_dir or Path(os.environ.get("MMS_TTS_CACHE", ROOT / "data" / "models" / "mms"))
        self.model = None
        self.tokenizer = None

    def available(self) -> bool:
        import importlib.util
        return importlib.util.find_spec("transformers") is not None and importlib.util.find_spec("torch") is not None

    def info(self) -> dict:
        return {"engine": self.name, "model": self.model_name, "loaded": self.model is not None,
                "note": "" if self.model else "model downloads on first use (needs internet once)"}

    def load(self) -> None:
        if self.model is not None:
            return
        from transformers import AutoTokenizer, VitsModel
        t = time.perf_counter()
        log.info("Loading %s ...", self.model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, cache_dir=str(self.cache_dir))
        self.model = VitsModel.from_pretrained(self.model_name, cache_dir=str(self.cache_dir)).eval()
        log.info("Loaded in %.1fs", time.perf_counter() - t)

    def _waveform(self, inputs, speaking_rate=None):
        import torch
        torch.manual_seed(555)  # VITS is stochastic; a fixed seed keeps the voice consistent
        base_rate = getattr(self.model, "speaking_rate", 1.0)
        try:
            if speaking_rate is not None:
                self.model.speaking_rate = speaking_rate
            with torch.no_grad():
                wave_out = self.model(**inputs).waveform
        finally:
            self.model.speaking_rate = base_rate
        return wave_out.squeeze().cpu().numpy()

    def synthesize(self, text: str, pitch=None) -> bytes:
        """pitch = 1.0 keeps the model's own (male) voice. pitch > 1 makes it higher and more feminine:
        with Praat installed it is a proper pitch + formant change; without Praat it falls back to relabelling
        the sample rate (higher pitch and faster, so the model is asked to speak slower to compensate)."""
        self.load()
        pitch = clamp_pitch(pitch if pitch is not None else 1.0)
        inputs = self.tokenizer(text, return_tensors="pt")
        if inputs["input_ids"].shape[-1] == 0:
            raise ValueError("No speakable Tamil characters in that text.")
        rate = self.model.config.sampling_rate
        if pitch == 1.0:
            return pcm16_wav(self._waveform(inputs), rate)
        if praat_available():
            wave = self._waveform(inputs)
            shifted = feminise(wave, rate, pitch)
            return pcm16_wav(wave if shifted is None else shifted, rate)   # Praat failed on this clip: speak unshifted
        pitch = min(pitch, FALLBACK_PITCH_MAX)
        return pcm16_wav(self._waveform(inputs, speaking_rate=getattr(self.model, "speaking_rate", 1.0) / pitch),
                         round(rate * pitch))


class IndicEngine:
    """AI4Bharat Indic-TTS via the Coqui `Synthesizer` API. Unverified; see module docstring."""
    name = "indic"

    def __init__(self):
        models = Path(os.environ.get("INDIC_TTS_MODELS", HERE / "models" / "ta"))
        self.tts_ckpt = Path(os.environ.get("INDIC_TTS_CKPT", models / "fastpitch" / "best_model.pth"))
        self.tts_cfg = Path(os.environ.get("INDIC_TTS_CONFIG", models / "fastpitch" / "config.json"))
        self.tts_spk = Path(os.environ.get("INDIC_TTS_SPEAKERS", models / "fastpitch" / "speakers.pth"))
        self.voc_ckpt = Path(os.environ.get("INDIC_VOCODER_CKPT", models / "hifigan" / "best_model.pth"))
        self.voc_cfg = Path(os.environ.get("INDIC_VOCODER_CONFIG", models / "hifigan" / "config.json"))
        self.speaker = os.environ.get("INDIC_TTS_SPEAKER", "female")
        self.use_cuda = os.environ.get("INDIC_TTS_CUDA", "0") == "1"  # keep 0: the GPU belongs to the LLM
        self.synth = None

    def _missing(self) -> list[str]:
        return [str(p) for p in (self.tts_ckpt, self.tts_cfg, self.voc_ckpt, self.voc_cfg) if not p.exists()]

    def available(self) -> bool:
        return not self._missing()

    def info(self) -> dict:
        return {"engine": self.name, "loaded": self.synth is not None, "missing": self._missing()}

    def load(self) -> None:
        if self.synth is None:
            if self._missing():
                raise RuntimeError("Missing model files: " + ", ".join(self._missing()))
            from TTS.utils.synthesizer import Synthesizer
            self.synth = Synthesizer(
                tts_checkpoint=str(self.tts_ckpt), tts_config_path=str(self.tts_cfg),
                tts_speakers_file=str(self.tts_spk) if self.tts_spk.exists() else None,
                vocoder_checkpoint=str(self.voc_ckpt), vocoder_config=str(self.voc_cfg), use_cuda=self.use_cuda)

    def synthesize(self, text: str, pitch=None) -> bytes:  # pitch is not supported by this engine
        self.load()
        wav = self.synth.tts(text, speaker_name=self.speaker if self.tts_spk.exists() else None)
        return pcm16_wav(wav, self.synth.output_sample_rate)


def make_engine(name: str | None = None):
    name = (name or os.environ.get("TAMIL_TTS_ENGINE", "mms")).lower()
    if name == "indic":
        return IndicEngine()
    if name == "mms":
        return MmsEngine()
    raise ValueError(f"Unknown TAMIL_TTS_ENGINE '{name}' (use 'mms' or 'indic')")


def create_app(engine):
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import Response
    from pydantic import BaseModel

    app = FastAPI(title="Vaani Tamil TTS")
    lock = threading.Lock()

    class Req(BaseModel):
        text: str
        pitch: float | None = None   # 1.0 = unchanged (male); higher = more feminine; see MmsEngine.synthesize

    @app.get("/health")
    def health():
        return {"models_found": engine.available(), **engine.info()}

    @app.post("/synthesize")
    def synthesize(req: Req):
        text = " ".join(req.text.split())[:MAX_CHARS]
        if not text:
            raise HTTPException(422, "Empty text")
        t = time.perf_counter()
        try:
            with lock:
                wav = engine.synthesize(text, req.pitch)
        except ValueError as e:
            raise HTTPException(422, str(e))
        except Exception as e:  # noqa: BLE001
            log.exception("synthesis failed")
            raise HTTPException(500, f"{type(e).__name__}: {e}")
        log.info("synth %d ms, %d chars -> %d KB", (time.perf_counter() - t) * 1000, len(text), len(wav) // 1024)
        return Response(wav, media_type="audio/wav")

    return app


if __name__ == "__main__":
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
    eng = make_engine()
    log.info("Tamil TTS engine: %s", eng.name)

    def warm():  # load the model in the background so the first sentence is not slow
        try:
            if eng.available():
                eng.load()
        except Exception as e:  # noqa: BLE001
            log.warning("Warm-up failed (will retry on first request): %s", e)

    threading.Thread(target=warm, daemon=True).start()
    uvicorn.run(create_app(eng), host="127.0.0.1", port=int(os.environ.get("PORT", "8010")))
