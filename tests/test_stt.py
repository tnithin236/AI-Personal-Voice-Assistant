"""Speech-to-text option logic with a fake Whisper model (no download, no audio)."""
import unittest
from types import SimpleNamespace

import numpy as np

from backend.voice.speech_to_text import SpeechToText


class FakeModel:
    def __init__(self, detected="en", probs=None):
        self.calls, self.detected, self.probs = [], detected, probs or [("en", 0.1), ("ta", 0.5), ("hi", 0.34)]

    def transcribe(self, audio, language=None, **kw):
        self.calls.append({"language": language, **kw})
        info = SimpleNamespace(language=language or self.detected, language_probability=0.9, duration=1.0,
                               all_language_probs=self.probs)
        return iter([SimpleNamespace(text=" hello ")]), info


def make(model):
    cfg = SimpleNamespace(whisper_beam=5, whisper_beam_en=1, whisper_device="cpu", whisper_compute="int8",
                          whisper_threads=0, models_dir=None)
    st = SpeechToText(cfg)
    st._model, st._name = model, "small"
    return st


AUDIO = np.zeros(16000, dtype=np.float32)


class BeamTests(unittest.TestCase):
    def test_english_uses_fast_beam(self):
        m = FakeModel()
        make(m).transcribe(AUDIO, "small", "en")
        self.assertEqual(m.calls[0]["beam_size"], 1)

    def test_tamil_and_auto_keep_the_accurate_beam(self):
        for lang in ("ta", None):
            m = FakeModel(detected="ta")
            make(m).transcribe(AUDIO, "small", lang)
            self.assertEqual(m.calls[0]["beam_size"], 5, lang)

    def test_unexpected_language_is_forced_to_en_or_ta(self):
        m = FakeModel(detected="hi")            # probs say Tamil (0.5) beats English (0.1)
        out = make(m).transcribe(AUDIO, "small", None)
        self.assertEqual(out["language"], "ta")
        self.assertEqual([c["language"] for c in m.calls], [None, "ta"])

    def test_very_short_audio_is_skipped(self):
        m = FakeModel()
        out = make(m).transcribe(np.zeros(100, dtype=np.float32), "small", "en")
        self.assertEqual((out["text"], m.calls), ("", []))


if __name__ == "__main__":
    unittest.main()
