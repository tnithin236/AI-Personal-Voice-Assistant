"""Client for the optional Tamil TTS service (services/tamil_tts, AI4Bharat Indic-TTS in its own venv).
If the service is down, callers get TTSUnavailable and the UI falls back to text only."""
import logging

import httpx

log = logging.getLogger(__name__)


class TTSUnavailable(Exception):
    pass


class TamilTTS:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def status(self) -> dict:
        try:
            r = httpx.get(f"{self.base_url}/health", timeout=httpx.Timeout(2.0))
            r.raise_for_status()
            return {"ok": True, **r.json()}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"Tamil TTS service not reachable at {self.base_url} ({type(e).__name__})"}

    def synthesize(self, text: str) -> bytes:
        # Fail fast (2 s) if the service isn't running; allow up to 2 min once connected (CPU synthesis is slow).
        try:
            r = httpx.post(f"{self.base_url}/synthesize", json={"text": text},
                           timeout=httpx.Timeout(120.0, connect=2.0))
        except httpx.HTTPError as e:
            raise TTSUnavailable("Tamil voice service is not running; showing text only.") from e
        if r.status_code != 200:
            raise TTSUnavailable(f"Tamil TTS error {r.status_code}: {r.text[:200]}")
        return r.content