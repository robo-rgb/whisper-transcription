"""Exercise GUI exporters without importing heavy Whisper/torch dependencies."""
from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path
from typing import Any

from speaker_segments import speaker_display_name


class ExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (Path(__file__).resolve().parents[1] / "transcribe-gui.py").read_text(encoding="utf-8")
        module = ast.parse(source)
        names = {
            "_milliseconds_total", "_split_milliseconds", "format_timestamp_srt",
            "format_timestamp_vtt", "_segment_text", "segments_to_srt",
            "segments_to_vtt", "segments_to_txt", "segments_to_timestamped_txt",
            "result_to_json", "result_to_tsv",
        }
        funcs = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name in names]
        namespace = {"Any": Any, "json": json, "speaker_display_name": speaker_display_name}
        exec(compile(ast.Module(body=funcs, type_ignores=[]), "<exporters>", "exec"), namespace)
        cls.exports = namespace

    def test_legacy_plain_text_unchanged(self):
        result = {"text": "Hello world", "segments": [{"start": 0, "end": 1, "text": "Hello world"}]}
        self.assertEqual(self.exports["segments_to_txt"](result), "Hello world\n")
        self.assertEqual(self.exports["result_to_tsv"](result), "start\tend\ttext\n00:00:00.000\t00:00:01.000\tHello world\n")

    def test_diarized_text_and_subtitles(self):
        result = {"text": "Hello there", "speaker_turns": [], "segments": [
            {"start": 0, "end": 1, "text": "Hello", "speaker": "SPEAKER_00"},
            {"start": 1, "end": 2, "text": " there", "speaker": "SPEAKER_01"},
        ]}
        self.assertIn("[Speaker 1] Hello", self.exports["segments_to_txt"](result))
        self.assertIn("[Speaker 2] there", self.exports["segments_to_srt"](result))
        self.assertIn("[Speaker 1] Hello", self.exports["segments_to_vtt"](result))
        self.assertIn("speaker\ttext", self.exports["result_to_tsv"](result))
        self.assertIn("Speaker 2\tthere", self.exports["result_to_tsv"](result))
        self.assertEqual(len(json.loads(self.exports["result_to_json"](result))["segments"]), 2)

    def test_unknown_speaker_is_visible(self):
        result = {"speaker_turns": [], "segments": [
            {"start": 0, "end": 1, "text": "test", "speaker": None},
        ]}
        self.assertIn("[Unknown speaker] test", self.exports["segments_to_txt"](result))


if __name__ == "__main__":
    unittest.main()
