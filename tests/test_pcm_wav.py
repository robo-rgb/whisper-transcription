"""Regression checks for TorchCodec-free WAV decoding; no torch install needed."""
from __future__ import annotations

import struct
import tempfile
import unittest
import wave
from pathlib import Path

from diarization_worker import load_pcm16_waveform


class FakeTensor:
    def __init__(self, raw):
        self.values = list(struct.unpack("<" + "h" * (len(raw) // 2), raw))
        self.shape = (len(self.values),)

    def to(self, dtype):
        self.values = [float(value) for value in self.values]
        return self

    def div_(self, denominator):
        self.values = [value / denominator for value in self.values]
        return self

    def unsqueeze(self, axis):
        assert axis == 0
        self.shape = (1, len(self.values))
        return self


class FakeTorch:
    int16 = "int16"
    float32 = "float32"

    def frombuffer(self, buffer, dtype):
        if dtype != self.int16:
            raise AssertionError("Expected int16 PCM")
        if not isinstance(buffer, bytearray):
            raise AssertionError("Input needs writable storage")
        return FakeTensor(buffer)


class PcmWavTests(unittest.TestCase):
    def _wav(self, path, samples, *, sample_rate=16000, channels=1, sampwidth=2):
        with wave.open(str(path), "wb") as target:
            target.setnchannels(channels)
            target.setsampwidth(sampwidth)
            target.setframerate(sample_rate)
            target.writeframes(samples)

    def test_decode_s16_mono_without_torchcodec(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "pcm.wav"
            self._wav(path, struct.pack("<4h", 0, 16384, -32768, 32767))
            waveform, rate = load_pcm16_waveform(str(path), FakeTorch())

        self.assertEqual(rate, 16000)
        self.assertEqual(waveform.shape, (1, 4))
        self.assertAlmostEqual(waveform.values[0], 0.0)
        self.assertAlmostEqual(waveform.values[1], 0.5)
        self.assertAlmostEqual(waveform.values[2], -1.0)
        self.assertAlmostEqual(waveform.values[3], 32767 / 32768.0)

    def test_rejects_non_mono_wav(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "stereo.wav"
            self._wav(path, struct.pack("<2h", 123, -123), channels=2)
            with self.assertRaisesRegex(ValueError, "16-kHz mono"):
                load_pcm16_waveform(str(path), FakeTorch())

    def test_rejects_incorrect_rate(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "wrongrate.wav"
            self._wav(path, struct.pack("<h", 123), sample_rate=44100)
            with self.assertRaisesRegex(ValueError, "16-kHz mono"):
                load_pcm16_waveform(str(path), FakeTorch())

    def test_rejects_empty_wav(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "empty.wav"
            self._wav(path, b"")
            with self.assertRaisesRegex(ValueError, "no audio samples"):
                load_pcm16_waveform(str(path), FakeTorch())


if __name__ == "__main__":
    unittest.main()
