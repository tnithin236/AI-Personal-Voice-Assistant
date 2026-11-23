import io
import unittest
import wave

import numpy as np

from backend.voice.audio_handler import wav_bytes_to_audio


def make_wav(samples, rate=16000, channels=1, width=2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(np.asarray(samples, dtype="<i2").tobytes() if width == 2 else bytes(samples))
    return buf.getvalue()


class WavDecodeTests(unittest.TestCase):
    def test_mono_16k_values_are_scaled_to_float(self):
        audio = wav_bytes_to_audio(make_wav([0, 16384, -16384, 32767]))
        self.assertEqual(audio.dtype, np.float32)
        np.testing.assert_allclose(audio, [0.0, 0.5, -0.5, 32767 / 32768], atol=1e-6)

    def test_stereo_is_averaged_to_mono(self):
        audio = wav_bytes_to_audio(make_wav([1000, 3000, -2000, -4000], channels=2))   # two frames
        np.testing.assert_allclose(audio, [2000 / 32768, -3000 / 32768], atol=1e-6)

    def test_other_sample_rates_are_resampled_to_16k(self):
        audio = wav_bytes_to_audio(make_wav(np.zeros(8000), rate=8000))                 # 1 second at 8 kHz
        self.assertEqual(audio.size, 16000)

    def test_non_wav_and_unsupported_widths_return_none(self):
        self.assertIsNone(wav_bytes_to_audio(b"ID3 this is an mp3, not a wav"))
        self.assertIsNone(wav_bytes_to_audio(b""))
        self.assertIsNone(wav_bytes_to_audio(make_wav([128, 130, 120], width=1)))        # 8-bit PCM

    def test_empty_wav_gives_empty_audio(self):
        self.assertEqual(wav_bytes_to_audio(make_wav([])).size, 0)


if __name__ == "__main__":
    unittest.main()
