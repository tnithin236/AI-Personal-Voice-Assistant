"""Tamil TTS service logic with fake torch/transformers (no model download needed)."""
import io
import sys
import types
import unittest
import wave
from contextlib import contextmanager
from types import SimpleNamespace
from unittest import mock

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


SEEN_RATES: list = []


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

    SEEN_RATES.clear()

    class Vits:
        config = SimpleNamespace(sampling_rate=16000)
        speaking_rate = 1.0

        @classmethod
        def from_pretrained(cls, name, cache_dir=None):
            return cls()

        def eval(self): return self
        def __call__(self, **inputs):
            SEEN_RATES.append(self.speaking_rate)
            return SimpleNamespace(waveform=FakeTensor(np.sin(np.linspace(0, 50, 4000))))

    tf = types.ModuleType("transformers")
    tf.AutoTokenizer, tf.VitsModel = Tok, Vits
    sys.modules["torch"], sys.modules["transformers"] = torch, tf


def install_fake_parselmouth(calls, median=120.0, change_fails=False, out=None):
    pm = types.ModuleType("parselmouth")

    class Sound:
        def __init__(self, values, sampling_frequency=None):
            self.values = np.asarray(values).reshape(1, -1)
            self.sampling_frequency = sampling_frequency

    pm.Sound = Sound
    praat = types.ModuleType("parselmouth.praat")

    def call(obj, name, *args):
        calls.append((name, args))
        if name == "To Pitch":
            return "PITCH"
        if name == "Get quantile":
            return median
        if name == "Change gender":
            if change_fails:
                raise RuntimeError("praat exploded")
            return Sound(out if out is not None else np.full(3000, 0.25), obj.sampling_frequency)
        raise AssertionError(f"unexpected praat call {name}")

    praat.call = call
    pm.praat = praat
    sys.modules["parselmouth"], sys.modules["parselmouth.praat"] = pm, praat


class MmsEngineTests(unittest.TestCase):
    def tearDown(self):
        for name in ("torch", "transformers", "parselmouth", "parselmouth.praat"):
            sys.modules.pop(name, None)

    def test_praat_changes_gender_with_the_expected_arguments(self):
        install_fakes()
        calls = []
        install_fake_parselmouth(calls, median=120.0)
        out = server.MmsEngine().synthesize("வணக்கம்", pitch=1.5)
        self.assertEqual(read_wav(out)[2], 16000)                       # sample rate untouched: a real pitch shift
        self.assertEqual(SEEN_RATES[-1], 1.0)                           # speaking speed untouched
        name, args = next(c for c in calls if c[0] == "Change gender")
        self.assertEqual(args[:2], (75, 600))
        self.assertAlmostEqual(args[2], 1.15)                           # formant ratio
        self.assertAlmostEqual(args[3], 180.0)                          # 120 Hz median * 1.5
        self.assertEqual(args[4:], (1.0, 1.0))

    def test_formant_ratio_is_capped_at_1_2(self):
        install_fakes()
        calls = []
        install_fake_parselmouth(calls)
        server.MmsEngine().synthesize("வணக்கம்", pitch=1.8)
        self.assertAlmostEqual(next(c for c in calls if c[0] == "Change gender")[1][2], 1.2)

    def test_pitch_1_never_touches_praat(self):
        install_fakes()
        calls = []
        install_fake_parselmouth(calls)
        server.MmsEngine().synthesize("வணக்கம்", pitch=1.0)
        self.assertEqual(calls, [])

    def test_praat_failure_speaks_with_the_original_voice_instead_of_failing(self):
        install_fakes()
        install_fake_parselmouth([], change_fails=True)
        out = server.MmsEngine().synthesize("வணக்கம்", pitch=1.5)
        self.assertEqual(read_wav(out)[:3], (1, 2, 16000))

    def test_unmeasurable_pitch_speaks_with_the_original_voice(self):
        install_fakes()
        install_fake_parselmouth([], median=float("nan"))
        self.assertEqual(read_wav(server.MmsEngine().synthesize("வணக்கம்", pitch=1.5))[2], 16000)

    def test_loud_praat_output_is_normalised_to_avoid_clipping(self):
        install_fakes()
        install_fake_parselmouth([], out=np.array([3.0, -3.0, 1.5] * 1000))
        frames = read_wav(server.MmsEngine().synthesize("வணக்கம்", pitch=1.5))[3]
        self.assertLessEqual(int(np.max(np.abs(np.frombuffer(frames, dtype="<i2")))), 32767 * 0.995)

    def test_feminise_returns_none_when_praat_is_not_installed(self):
        sys.modules["parselmouth"] = None                                # makes `import parselmouth` fail
        self.assertIsNone(server.feminise(np.zeros(1000), 16000, 1.5))

    def test_synthesize_returns_wav_and_uses_fixed_seed(self):
        seeds = []
        install_fakes(seeds=seeds)
        eng = server.MmsEngine()
        out = eng.synthesize("வணக்கம்")
        self.assertEqual(read_wav(out)[:3], (1, 2, 16000))
        self.assertEqual(seeds, [555])
        self.assertTrue(eng.info()["loaded"])

    @mock.patch.object(server, "praat_available", return_value=False)
    def test_without_praat_pitch_raises_sample_rate_and_slows_the_model_to_keep_speed(self, _):
        install_fakes()
        eng = server.MmsEngine()
        self.assertEqual(read_wav(eng.synthesize("வணக்கம்"))[2], 16000)                 # default: unchanged
        out = eng.synthesize("வணக்கம்", pitch=1.25)
        self.assertEqual(read_wav(out)[2], 20000)                                       # 16000 * 1.25
        self.assertAlmostEqual(SEEN_RATES[-1], 1 / 1.25)                                # model asked to speak slower
        self.assertEqual(eng.model.speaking_rate, 1.0)                                  # ...and restored afterwards

    @mock.patch.object(server, "praat_available", return_value=False)
    def test_without_praat_pitch_is_clamped_and_capped(self, _):
        install_fakes()
        eng = server.MmsEngine()
        self.assertEqual(read_wav(eng.synthesize("வணக்கம்", pitch=9))[2], round(16000 * server.FALLBACK_PITCH_MAX))
        self.assertEqual(read_wav(eng.synthesize("வணக்கம்", pitch=0.2))[2], 16000)       # never lower than normal
        self.assertEqual(server.clamp_pitch("abc"), 1.0)
        self.assertEqual(server.clamp_pitch(None), 1.0)

    @mock.patch.object(server, "praat_available", return_value=False)
    def test_speaking_rate_is_restored_even_if_synthesis_fails(self, _):
        install_fakes()
        eng = server.MmsEngine()
        eng.load()
        eng.model.__class__.__call__ = lambda self, **kw: (_ for _ in ()).throw(RuntimeError("boom"))
        with self.assertRaises(RuntimeError):
            eng.synthesize("வணக்கம்", pitch=1.3)
        self.assertEqual(eng.model.speaking_rate, 1.0)

    def test_text_with_no_speakable_characters_is_a_clean_error(self):
        install_fakes(token_count=0)
        with self.assertRaises(ValueError):
            server.MmsEngine().synthesize("12345")


if __name__ == "__main__":
    unittest.main()
