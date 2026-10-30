"""Exercise the separate speaker worker process without installing pyannote."""
from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import diarization_runner


class WorkerIsolationTests(unittest.TestCase):
    def test_conversion_and_worker_do_not_put_secret_on_command_line(self):
        commands = []
        def fake_run(cmd, **kwargs):
            commands.append((cmd, kwargs))
            if "--output" in cmd:
                output = Path(cmd[cmd.index("--output") + 1])
                output.write_text(json.dumps({"turns": [
                    {"start": 0, "end": 1, "speaker": "SPEAKER_00"}
                ]}), encoding="utf-8")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        with patch.object(diarization_runner, "ensure_diarization_ready"), \
             patch.object(diarization_runner, "diarization_python", return_value=Path("worker-python")), \
             patch.object(diarization_runner.subprocess, "run", side_effect=fake_run), \
             patch.dict(os.environ, {"HF_TOKEN": "test-secret-do-not-expose"}):
            turns = diarization_runner.run_diarization("recording.mp3", "ffmpeg", 2)

        self.assertEqual(turns[0]["speaker"], "SPEAKER_00")
        self.assertEqual(len(commands), 2)
        self.assertIn("-ar", commands[0][0])
        self.assertIn("16000", commands[0][0])
        worker_cmd, kwargs = commands[1]
        self.assertIn("--num-speakers", worker_cmd)
        self.assertNotIn("test-secret-do-not-expose", str(worker_cmd))
        self.assertEqual(kwargs["env"]["PYANNOTE_METRICS_ENABLED"], "0")

    def test_secret_redacted_from_worker_errors(self):
        def fake_run(cmd, **kwargs):
            if "--output" in cmd:
                return subprocess.CompletedProcess(cmd, 1, "", "Failed: test-secret-do-not-expose")
            return subprocess.CompletedProcess(cmd, 0, "", "")

        with patch.object(diarization_runner, "ensure_diarization_ready"), \
             patch.object(diarization_runner, "diarization_python", return_value=Path("worker-python")), \
             patch.object(diarization_runner.subprocess, "run", side_effect=fake_run), \
             patch.dict(os.environ, {"HF_TOKEN": "test-secret-do-not-expose"}):
            with self.assertRaises(RuntimeError) as caught:
                diarization_runner.run_diarization("recording.mp3", "ffmpeg")
        self.assertNotIn("test-secret-do-not-expose", str(caught.exception))
        self.assertIn("[redacted]", str(caught.exception))

    def test_invalid_speaker_count(self):
        with patch.object(diarization_runner, "ensure_diarization_ready"):
            with self.assertRaises(ValueError):
                diarization_runner.run_diarization("recording.mp3", "ffmpeg", 9)


if __name__ == "__main__":
    unittest.main()
