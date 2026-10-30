"""Unit tests for timeline-to-Whisper alignment (no model download)."""
from __future__ import annotations

import unittest

from speaker_segments import apply_diarization, normalize_turns, speaker_at, speaker_display_name


class SpeakerAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.turns = [
            {"start": 0, "end": 1.0, "speaker": "SPEAKER_00"},
            {"start": 1.0, "end": 2.5, "speaker": "SPEAKER_01"},
            {"start": 3, "end": 4, "speaker": "SPEAKER_00"},
        ]

    def test_word_speaker_switch_within_whisper_segment(self):
        original = {"text": "Hello there friend", "language": "en", "segments": [
            {"id": 7, "start": 0, "end": 2.0, "text": "Hello there friend", "words": [
                {"word": " Hello", "start": 0.1, "end": 0.8},
                {"word": " there", "start": 1.1, "end": 1.5},
                {"word": " friend", "start": 1.5, "end": 1.9},
            ]},
        ]}
        output = apply_diarization(original, self.turns)
        self.assertEqual([x["speaker"] for x in output["segments"]], ["SPEAKER_00", "SPEAKER_01"])
        self.assertEqual([x["text"] for x in output["segments"]], ["Hello", "there friend"])
        self.assertEqual(output["segments"][1]["source_segment_id"], 7)
        self.assertEqual(original["segments"][0]["words"][1]["word"], " there")
        self.assertEqual(output["text"], "Hello there friend")

    def test_unassigned_gap_remains_unknown(self):
        self.assertIsNone(speaker_at(2.6, 2.8, self.turns))

    def test_overlap_wins_over_closest_midpoint(self):
        self.assertEqual(speaker_at(0.9, 1.4, self.turns), "SPEAKER_01")

    def test_fallback_without_whisper_words(self):
        result = {"segments": [{"start": 0.2, "end": 0.7, "text": " hi"}]}
        self.assertEqual(apply_diarization(result, self.turns)["segments"][0]["speaker"], "SPEAKER_00")

    def test_empty_turns_refused(self):
        with self.assertRaisesRegex(ValueError, "No speaker turns"):
            apply_diarization({"segments": []}, [])

    def test_unsorted_turns_sorted(self):
        self.assertEqual(normalize_turns(list(reversed(self.turns))), self.turns)

    def test_invalid_intervals_refused(self):
        with self.assertRaises(ValueError):
            normalize_turns([{"start": 2, "end": 1, "speaker": "X"}])

    def test_display_names(self):
        self.assertEqual(speaker_display_name("SPEAKER_00"), "Speaker 1")
        self.assertEqual(speaker_display_name("SPEAKER_01"), "Speaker 2")
        self.assertEqual(speaker_display_name(None), "Unknown speaker")


if __name__ == "__main__":
    unittest.main()
