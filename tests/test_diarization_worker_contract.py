"""Test pyannote integration contract using stubs, without model download."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import diarization_worker


class WorkerContractTests(unittest.TestCase):
    def _invoke(self, num_speakers=None, gpu=False):
        pipeline = MagicMock()
        annotation = types.SimpleNamespace(
            itertracks=lambda yield_label: [
                (types.SimpleNamespace(start=0.25, end=1.25), None, "SPEAKER_00"),
                (types.SimpleNamespace(start=1.25, end=2.50), None, "SPEAKER_01"),
            ]
        )
        pipeline.return_value = types.SimpleNamespace(exclusive_speaker_diarization=annotation)
        factory = MagicMock(return_value=pipeline)
        audio_stub = types.ModuleType("pyannote.audio")
        audio_stub.Pipeline = types.SimpleNamespace(from_pretrained=factory)
        pyannote_stub = types.ModuleType("pyannote")
        pyannote_stub.audio = audio_stub
        torch_stub = types.ModuleType("torch")
        torch_stub.cuda = types.SimpleNamespace(is_available=lambda: gpu)
        torch_stub.device = lambda name: name
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "turns.json"
            argv = ["diarization_worker.py", "--input", "example.wav", "--output", str(output)]
            if num_speakers is not None:
                argv.extend(["--num-speakers", str(num_speakers)])
            with patch.dict(sys.modules, {
                "torch": torch_stub, "pyannote": pyannote_stub,
                "pyannote.audio": audio_stub,
            }), patch.object(sys, "argv", argv), patch.dict(os.environ, {"HF_TOKEN": "fake-hf-token"}):
                diarization_worker.main()
            data = json.loads(output.read_text(encoding="utf-8"))
        return data, factory, pipeline

    def test_worker_with_known_speaker_count_on_gpu(self):
        data, factory, pipeline = self._invoke(num_speakers=2, gpu=True)
        factory.assert_called_once_with(
            "pyannote/speaker-diarization-community-1", token="fake-hf-token"
        )
        pipeline.to.assert_called_once_with("cuda")
        pipeline.assert_called_once_with("example.wav", num_speakers=2)
        self.assertEqual([t["speaker"] for t in data["turns"]], ["SPEAKER_00", "SPEAKER_01"])
        self.assertEqual(data["turns"][0]["start"], 0.25)

    def test_auto_speaker_count_cpu(self):
        data, _, pipeline = self._invoke()
        pipeline.to.assert_not_called()
        pipeline.assert_called_once_with("example.wav")
        self.assertEqual(len(data["turns"]), 2)


if __name__ == "__main__":
    unittest.main()
