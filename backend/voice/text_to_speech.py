"""English TTS via Piper (run as a subprocess; works with both `python -m piper` and piper.exe),
plus a router that sends Tamil text to the separate Tamil service."""
import logging
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from backend.core.lang import detect_language

from .tamil_tts import TamilTTS, TTSUnavailable

log = logging.getLogger(__name__)


def clean_for_speech(text: str, max_chars: int = 600) -> str:
    text = re.sub(r"https?://\S+", "link", text)
    text = re.sub(r"[*_`#>|~]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars]


class PiperTTS:
    def __init__(self, cfg):
        self.cfg = cfg

    @property
    def voices_dir(self) -> Path:
        return self.cfg.models_dir / "piper"

    def voice_path(self, voice: str) -> Path:
        return self.voices_dir / f"{voice}.onnx"

    def list_voices(self) -> list[str]:
        return sorted(p.stem for p in self.voices_dir.glob("*.onnx")) if self.voices_dir.exists() else []

    def status(self, voice: str) -> dict:
        ok = self.voice_path(voice).exists()
        return {"ok": ok, "voice": voice, "voices": self.list_voices(),
                "error": None if ok else f"Voice file not found: {self.voice_path(voice)}"}

    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> bytes:
        model = self.voice_path(voice)
        if not model.exists():
            raise TTSUnavailable(f"Piper voice not found: {model}. See README, step 'Piper voice'.")
        cmd = ([self.cfg.piper_exe] if self.cfg.piper_exe else [sys.executable, "-m", "piper"])
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
        if lang == "ta":
            return self.tamil.synthesize(text), "ta"
        return self.piper.synthesize(text, s["piper_voice"], float(s["voice_speed"])), "en"
