"""Microphone capture (push-to-talk) with sounddevice. Output: float32 mono, 16 kHz."""
import logging
import threading

import numpy as np

log = logging.getLogger(__name__)
TARGET_SR = 16000
MAX_SECONDS = 120


def list_input_devices() -> list[dict]:
    import sounddevice as sd
    hostapis = sd.query_hostapis()
    try:
        default_in = sd.default.device[0]
    except Exception:  # noqa: BLE001
        default_in = None
    out = []
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            out.append({"index": i, "name": d["name"], "hostapi": hostapis[d["hostapi"]]["name"],
                        "default": i == default_in})
    return out


def resample(audio: np.ndarray, sr: int, target: int = TARGET_SR) -> np.ndarray:
    if sr == target or audio.size == 0:
        return audio
    n = int(round(audio.size * target / sr))
    return np.interp(np.linspace(0, audio.size - 1, n), np.arange(audio.size), audio).astype(np.float32)


class Recorder:
    def __init__(self):
        self._stream = None
        self._chunks: list[np.ndarray] = []
        self._sr = TARGET_SR
        self._samples = 0
        self._lock = threading.Lock()
        self.level = 0.0

    @property
    def recording(self) -> bool:
        return self._stream is not None

    def start(self, device: int | None = None) -> None:
        import sounddevice as sd
        if self._stream is not None:
            self.stop()
        self._chunks, self._samples, self.level = [], 0, 0.0

        def callback(indata, frames, time_info, status):  # runs on the audio thread
            if status:
                log.debug("audio status: %s", status)
            mono = indata[:, 0].copy()
            self.level = float(np.sqrt(np.mean(mono ** 2)))
            with self._lock:
                if self._samples < MAX_SECONDS * self._sr:
                    self._chunks.append(mono)
                    self._samples += mono.size

        def open_stream(sr: int):
            return sd.InputStream(samplerate=sr, channels=1, dtype="float32", device=device, callback=callback)

        try:
            self._sr = TARGET_SR
            stream = open_stream(TARGET_SR)
        except sd.PortAudioError:  # device refuses 16 kHz -> use its native rate and resample later
            self._sr = int(sd.query_devices(device, "input")["default_samplerate"])
            stream = open_stream(self._sr)
        stream.start()
        self._stream = stream
        log.info("Recording started (device=%s, sr=%d)", device, self._sr)

    def stop(self) -> np.ndarray:
        stream, self._stream = self._stream, None
        if stream is not None:
            stream.stop()
            stream.close()
        with self._lock:
            audio = np.concatenate(self._chunks) if self._chunks else np.zeros(0, dtype=np.float32)
            self._chunks, self._samples = [], 0
        self.level = 0.0
        audio = resample(audio, self._sr)
        log.info("Recording stopped: %.2fs", audio.size / TARGET_SR)
        return audio
