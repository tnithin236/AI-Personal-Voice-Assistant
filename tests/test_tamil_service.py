"""Tamil TTS service logic with fake torch/transformers (no model download needed)."""
import io
import sys
import types
import unittest
import wave
from contextlib import contextmanager
from types import SimpleNamespace

import numpy as np

from services.tamil_tts import server


def read_wav(data: bytes):
    with wave.open(io.BytesIO(data), "rb") as w:
        return w.getnchannels(), w.getsampwidth(), w.getframerate(), w.readframes(w.getnframes())


class Pcm16Tests(unittest.TestCase):
    def test_encodes_mono_16bit(self):
        ch, width, rate, frames = read_wav(server.pcm16_wav(np.array([0.0, 0.5, -0.5, 1.0]), 16000))
        self.assertEqual((ch, width, rate), (1, 2, 16000))
        samples = np.frombuffer(frames, dtype="<i2")
        self.assertEqual(list(samples), [0, 16383, -16383, 32767])

    def test_clips_out_of_range_and_flattens(self):
        _, _, _, frames = read_wav(server.pcm16_wav(np.array([[2.0, -3.0]]), 22050))
        self.assertEqual(list(np.frombuffer(frames, dtype="<i2")), [32767, -32767])

    def test_empty_audio_rejected(self):
        with self.assertRaises(ValueError):
            server.pcm16_wav(np.array([]), 16000)


class EngineSelectionTests(unittest.TestCase):
    def test_default_is_mms_and_indic_selectable(self):
        self.assertIsInstance(server.make_engine("mms"), server.MmsEngine)
        self.assertIsInstance(server.make_engine("INDIC"), server.IndicEngine)
        with self.assertRaises(ValueError):
            server.make_engine("nonsense")

    def test_indic_reports_missing_models_without_loading(self):
        eng = server.IndicEngine()
        self.assertFalse(eng.available())
        self.assertTrue(eng.info()["missing"])


class FakeTensor:
    def __init__(self, arr): self.arr = arr
    def squeeze(self): return self
    def cpu(self): return self
    def numpy(self): return self.arr


def install_fakes(token_count=5, seeds=None):
    torch = types.ModuleType("torch")
    torch.manual_seed = lambda s: (seeds.append(s) if seeds is not None else None)

    @contextmanager
    def no_grad():
        yield

    torch.no_grad = no_grad

    class Tok:
        @classmethod
        def from_pretrained(cls, name, cache_dir=None):
            return cls()

        def __call__(self, text, return_tensors=None):
            return {"input_ids": np.zeros((1, token_count))}

    class Vits:
        config = SimpleNamespace(sampling_rate=16000)

        @classmethod
        def from_pretrained(cls, name, cache_dir=None):
            return cls()

        def eval(self): return self
        def __call__(self, **inputs): return SimpleNamespace(waveform=FakeTensor(np.sin(np.linspace(0, 50, 4000))))

    tf = types.ModuleType("transformers")
    tf.AutoTokenizer, tf.VitsModel = Tok, Vits
    sys.modules["torch"], sys.modules["transformers"] = torch, tf


class MmsEngineTests(unittest.TestCase):
    def tearDown(self):
        sys.modules.pop("torch", None)
        sys.modules.pop("transformers", None)

    def test_synthesize_returns_wav_and_uses_fixed_seed(self):
        seeds = []
        install_fakes(seeds=seeds)
        eng = server.MmsEngine()
        out = eng.synthesize("வணக்கம்")
        self.assertEqual(read_wav(out)[:3], (1, 2, 16000))
        self.assertEqual(seeds, [555])
        self.assertTrue(eng.info()["loaded"])

    def test_text_with_no_speakable_characters_is_a_clean_error(self):
        install_fakes(token_count=0)
        with self.assertRaises(ValueError):
            server.MmsEngine().synthesize("12345")


if __name__ == "__main__":
    unittest.main()
