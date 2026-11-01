"""Piper wrapper logic with a fake `piper` module (no real model needed)."""
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests import _stubs  # noqa: F401
from backend.voice import text_to_speech as tts
from backend.voice.tamil_tts import TTSUnavailable


def make_cfg(tmp: Path):
    (tmp / "piper").mkdir(parents=True, exist_ok=True)
    (tmp / "piper" / "v.onnx").write_bytes(b"x")
    (tmp / "audio").mkdir(exist_ok=True)
    return SimpleNamespace(models_dir=tmp, audio_dir=tmp / "audio", piper_exe="", tamil_tts_url="http://x")


def install_fake_piper(loads: list, scales: list, broken=False):
    mod = types.ModuleType("piper")

    class SynthesisConfig:
        def __init__(self, length_scale=1.0):
            self.length_scale = length_scale

    class PiperVoice:
        @classmethod
        def load(cls, path):
            if broken:
                raise AttributeError("API differs in this piper version")
            loads.append(path)
            return cls()

        def synthesize_wav(self, text, wf, syn_config=None):
            scales.append(syn_config.length_scale)
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(22050)
            wf.writeframes(b"\x00\x01" * 2000)

    mod.PiperVoice, mod.SynthesisConfig = PiperVoice, SynthesisConfig
    sys.modules["piper"] = mod


class PiperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.p = tts.PiperTTS(make_cfg(self.tmp))

    def tearDown(self):
        sys.modules.pop("piper", None)

    def test_inprocess_loads_once_and_applies_speed(self):
        loads, scales = [], []
        install_fake_piper(loads, scales)
        a = self.p.synthesize("Hello", "v", 1.0)
        b = self.p.synthesize("World", "v", 2.0)
        self.assertTrue(a.startswith(b"RIFF") and b.startswith(b"RIFF"))
        self.assertEqual(len(loads), 1)                      # model loaded once, not per sentence
        self.assertAlmostEqual(scales[1], 0.5)               # faster speech -> smaller length_scale
        self.assertEqual(self.p.mode, "in-process")

    def test_falls_back_to_subprocess_when_api_breaks(self):
        install_fake_piper([], [], broken=True)
        calls = []
        self.p._synth_subprocess = lambda text, model, speed: calls.append(text) or b"RIFF" + b"\0" * 200
        out = self.p.synthesize("Hello", "v", 1.0)
        self.assertTrue(out.startswith(b"RIFF"))
        self.assertEqual(calls, ["Hello"])
        self.assertFalse(self.p._inproc_ok)
        self.p.synthesize("Again", "v", 1.0)
        self.assertEqual(self.p.mode, "subprocess")

    def test_warm_failure_switches_mode_quietly(self):
        install_fake_piper([], [], broken=True)
        self.p.warm("v")
        self.assertEqual(self.p.mode, "subprocess")

    def test_missing_voice(self):
        with self.assertRaises(TTSUnavailable):
            self.p.synthesize("Hi", "nope", 1.0)

    def test_exe_setting_forces_subprocess(self):
        cfg = make_cfg(self.tmp); cfg.piper_exe = "C:/piper.exe"
        self.assertFalse(tts.PiperTTS(cfg)._inproc_ok)

    def test_clean_for_speech(self):
        self.assertEqual(tts.clean_for_speech("**Hi** see https://x.com/a now"), "Hi see link now")


if __name__ == "__main__":
    unittest.main()
