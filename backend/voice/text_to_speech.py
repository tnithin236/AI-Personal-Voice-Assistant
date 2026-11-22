"""English TTS via Piper, plus a router that sends Tamil text to the separate Tamil service.

Piper runs IN-PROCESS (voice model loaded once and kept in memory) so each sentence is fast.
If the in-process API is unavailable or fails, it falls back automatically to launching Piper as a
subprocess (`python -m piper` or piper.exe) - slower (~1 s extra per sentence) but always works."""
import io
import logging
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path

from backend.core.lang import detect_language

from .tamil_tts import TamilTTS, TTSUnavailable

log = logging.getLogger(__name__)


def clean_for_speech(text: str, max_chars: int = 600) -> str:
    text = re.sub(r"https?://\S+", "link", text)
    text = re.sub(r"[*_`#>|~]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


_LATIN_BRACKETS = re.compile(r"\s*[\(\[][A-Za-z0-9 ,.'!?;:\-]+[\)\]]")


def strip_latin_brackets(text: str) -> str:
    """Tamil replies sometimes carry a romanised copy in brackets, e.g. '(Vanakkam!)'. The Tamil voice cannot say
    Latin letters, so drop those brackets before speaking."""
    return re.sub(r"\s{2,}", " ", _LATIN_BRACKETS.sub("", text)).strip()


class PiperTTS:
    def __init__(self, cfg):
        self.cfg = cfg
        self._voices: dict = {}
        self._load_lock = threading.Lock()
        self._synth_lock = threading.Lock()  # espeak phonemizer is not thread-safe
        self._inproc_ok = not cfg.piper_exe  # an explicit piper.exe means "use the subprocess"
        self.mode = "unknown"

    @property
    def voices_dir(self) -> Path:
        return self.cfg.models_dir / "piper"

    def voice_path(self, voice: str) -> Path:
        return self.voices_dir / f"{voice}.onnx"

    def list_voices(self) -> list[str]:
        return sorted(p.stem for p in self.voices_dir.glob("*.onnx")) if self.voices_dir.exists() else []

    def status(self, voice: str) -> dict:
        ok = self.voice_path(voice).exists()
        return {"ok": ok, "voice": voice, "voices": self.list_voices(), "mode": self.mode,
                "error": None if ok else f"Voice file not found: {self.voice_path(voice)}"}

    # ---- in-process (fast path) -----------------------------------------
    def _load_voice(self, name: str):
        with self._load_lock:
            v = self._voices.get(name)
            if v is None:
                from piper import PiperVoice
                t = time.perf_counter()
                v = PiperVoice.load(str(self.voice_path(name)))
                self._voices[name] = v
                log.info("Piper voice '%s' loaded in %.1fs", name, time.perf_counter() - t)
            return v

    def _synth_inproc(self, text: str, voice: str, speed: float) -> bytes:
        from piper import SynthesisConfig
        v = self._load_voice(voice)
        syn = SynthesisConfig(length_scale=1.0 / max(speed, 0.25))
        buf = io.BytesIO()
        with self._synth_lock, wave.open(buf, "wb") as wf:
            v.synthesize_wav(text, wf, syn_config=syn)
        return buf.getvalue()

    def warm(self, voice: str) -> None:
        """Preload the voice at startup so the first spoken sentence is not slow."""
        if not self._inproc_ok or not self.voice_path(voice).exists():
            return
        try:
            self._synth_inproc("Ready.", voice, 1.0)
            self.mode = "in-process"
            log.info("Piper ready (in-process)")
        except Exception as e:  # noqa: BLE001 - API differences between piper-tts versions
            log.warning("In-process Piper unavailable (%s: %s); using subprocess fallback", type(e).__name__, e)
            self._inproc_ok = False
            self.mode = "subprocess"

    # ---- subprocess (fallback) ------------------------------------------
    def _synth_subprocess(self, text: str, model: Path, speed: float) -> bytes:
        cmd = [self.cfg.piper_exe] if self.cfg.piper_exe else [sys.executable, "-m", "piper"]
        fd, out = tempfile.mkstemp(suffix=".wav", dir=self.cfg.audio_dir)
        os.close(fd)
        cmd += ["-m", str(model), "-f", out, "--length-scale", f"{1.0 / max(speed, 0.25):.3f}"]
        try:
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            r = subprocess.run(cmd, input=text.encode("utf-8"), capture_output=True, timeout=90,
                               creationflags=flags)
            if r.returncode != 0:
                raise TTSUnavailable(f"Piper failed: {r.stderr.decode('utf-8', 'replace')[-300:]}")
            data = Path(out).read_bytes()
            if len(data) < 100:
                raise TTSUnavailable("Piper produced no audio.")
            return data
        except FileNotFoundError as e:
            raise TTSUnavailable("Piper is not installed (pip install piper-tts).") from e
        except subprocess.TimeoutExpired as e:
            raise TTSUnavailable("Piper timed out.") from e
        finally:
            Path(out).unlink(missing_ok=True)

    # ---- public ---------------------------------------------------------
    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> bytes:
        model = self.voice_path(voice)
        if not model.exists():
            raise TTSUnavailable(f"Piper voice not found: {model}. See README, section 'Piper voice'.")
        if self._inproc_ok:
            try:
                data = self._synth_inproc(text, voice, speed)
                if len(data) > 100:
                    self.mode = "in-process"
                    return data
                raise RuntimeError("empty audio")
            except Exception as e:  # noqa: BLE001
                log.warning("In-process Piper failed (%s: %s); switching to subprocess", type(e).__name__, e)
                self._inproc_ok = False
        self.mode = "subprocess"
        return self._synth_subprocess(text, model, speed)


class TTSManager:
    def __init__(self, cfg, settings):
        self.cfg, self.settings = cfg, settings
        self.piper = PiperTTS(cfg)
        self.tamil = TamilTTS(cfg.tamil_tts_url)

    def synthesize(self, text: str, language: str | None = None) -> tuple[bytes, str]:
        text = clean_for_speech(text)
        if not text:
            raise TTSUnavailable("Nothing to speak.")
        lang = language if language in ("en", "ta") else detect_language(text)
        s = self.settings.all()
        t = time.perf_counter()
        if lang == "ta":
            audio = self.tamil.synthesize(strip_latin_brackets(text) or text, float(s.get("tamil_pitch", 1.0)))
            mode = "tamil-service"
        else:
            audio = self.piper.synthesize(text, s["piper_voice"], float(s["voice_speed"]))
            mode = f"piper-{self.piper.mode}"
        log.info("TTS %s %dms %d chars", mode, (time.perf_counter() - t) * 1000, len(text))
        return audio, lang
