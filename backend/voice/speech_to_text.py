"""Faster-Whisper (CPU, INT8, VAD). English + Tamil with automatic or explicit language."""
import logging
import threading
import time

import numpy as np

log = logging.getLogger(__name__)
ALLOWED = ("en", "ta")


class SpeechToText:
    def __init__(self, cfg):
        self.cfg = cfg
        self._model = None
        self._name = None
        self._lock = threading.Lock()

    @property
    def loaded_model(self) -> str | None:
        return self._name if self._model else None

    def ensure_loaded(self, name: str):
        with self._lock:
            if self._model is None or name != self._name:
                from faster_whisper import WhisperModel
                t = time.perf_counter()
                log.info("Loading Whisper '%s' (%s/%s)...", name, self.cfg.whisper_device, self.cfg.whisper_compute)
                self._model = WhisperModel(name, device=self.cfg.whisper_device,
                                           compute_type=self.cfg.whisper_compute,
                                           cpu_threads=self.cfg.whisper_threads,
                                           download_root=str(self.cfg.models_dir / "whisper"))
                self._name = name
                log.info("Whisper loaded in %.1fs", time.perf_counter() - t)
            return self._model

    def transcribe(self, audio, model_name: str, language: str | None = None) -> dict:
        """audio: float32 16 kHz ndarray OR a file-like/path. language: 'en' | 'ta' | None (auto)."""
        if isinstance(audio, np.ndarray) and audio.size < 16000 * 0.3:
            return {"text": "", "language": language or "en", "probability": 0.0, "duration": 0.0, "ms": 0}
        model = self.ensure_loaded(model_name)
        t = time.perf_counter()
        kw = dict(beam_size=self.cfg.whisper_beam, vad_filter=True,
                  vad_parameters={"min_silence_duration_ms": 500}, condition_on_previous_text=False)
        segments, info = model.transcribe(audio, language=language, **kw)
        text = " ".join(s.text.strip() for s in segments).strip()
        detected, prob = info.language, float(info.language_probability or 0)

        # Auto mode but Whisper guessed something other than English/Tamil -> force the likelier of the two.
        if language is None and detected not in ALLOWED:
            probs = dict(getattr(info, "all_language_probs", None) or [])
            forced = max(ALLOWED, key=lambda c: probs.get(c, 0.0))
            log.info("Detected '%s'; re-running as '%s'", detected, forced)
            if isinstance(audio, np.ndarray):  # (file-like objects may already be consumed)
                segments, info = model.transcribe(audio, language=forced, **kw)
                text = " ".join(s.text.strip() for s in segments).strip()
            detected, prob = forced, probs.get(forced, 0.0)
        ms = round((time.perf_counter() - t) * 1000)
        log.info("STT %dms lang=%s (%.2f): %s", ms, detected, prob, text[:80])
        return {"text": text, "language": detected, "probability": prob,
                "duration": round(info.duration, 2), "ms": ms}
