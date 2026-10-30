"""Tests for conservative diarized transcript cleanup and review diagnostics."""
from __future__ import annotations

import unittest

from transcript_cleanup import cleanup_diarized_result


def seg(start, end, text, speaker="SPEAKER_00"):
    return {"start": start, "end": end, "text": text, "speaker": speaker}


class TranscriptCleanupTests(unittest.TestCase):
    def test_empty_and_zero_duration_cues_are_removed_without_mutation(self):
        source = {"text": "raw Whisper output", "speaker_turns": [{"speaker": "SPEAKER_00"}],
                  "segments": [
                      seg(0, 1, "Real dialogue"),
                      seg(1, 1, ""),
                      seg(1, 1, " "),
                      seg(1, 2, "More dialogue"),
                  ]}
        result, report = cleanup_diarized_result(source)
        self.assertEqual(report["removed_empty_cues"], 2)
        self.assertEqual([x["text"] for x in result["segments"]], ["Real dialogue", "More dialogue"])
        self.assertEqual(result["text"], source["text"])
        self.assertEqual(len(source["segments"]), 4)
        self.assertEqual(result["transcript_cleanup"], report)
        self.assertEqual(result["speaker_turns"], source["speaker_turns"])

    def test_final_impossible_repeated_line_split_across_speakers_removed(self):
        passage = "I do not think there is a reasonable argument that this is true"
        source = {"segments": [
            seg(60, 60.2, "I", "SPEAKER_01"),
            seg(60.2, 68, "do not think there is a reasonable argument that this is true"),
            seg(70, 73, "Other speech", "SPEAKER_01"),
            seg(77, 77.8, passage, None),
        ]}
        result, report = cleanup_diarized_result(source)
        self.assertEqual(report["removed_terminal_echoes"], 1)
        self.assertEqual(len(result["segments"]), 3)
        self.assertEqual(source["segments"][-1]["text"], passage)

    def test_consecutive_potential_repeat_is_preserved_and_flagged(self):
        source = {"segments": [
            seg(15.46, 17.88, "Well, and I was a little older at the time"),
            seg(17.88, 19.72, "And I was a little older at the time"),
            seg(19.88, 22, "So I lived through it in a very different way"),
        ]}
        result, report = cleanup_diarized_result(source)
        self.assertEqual(len(result["segments"]), 3)
        self.assertEqual(report["removed_terminal_echoes"], 0)
        self.assertEqual(report["possible_repetitions_to_review"],
                         [{"start": 17.88, "end": 19.72}])

    def test_genuine_repetition_stays_when_spoken_at_plausible_rate(self):
        phrase = "This sentence was spoken again with clear emphasis"
        source = {"segments": [seg(0, 4, phrase), seg(4, 8, phrase)]}
        result, report = cleanup_diarized_result(source)
        self.assertEqual(len(result["segments"]), 2)
        self.assertEqual(report["removed_terminal_echoes"], 0)

    def test_fast_unique_ending_is_not_deleted(self):
        source = {"segments": [
            seg(2, 8, "The first sentence gives a different piece of information"),
            seg(8, 8.45, "It may be badly timed but these are completely different words"),
        ]}
        result, report = cleanup_diarized_result(source)
        self.assertEqual(len(result["segments"]), 2)
        self.assertEqual(report["removed_terminal_echoes"], 0)

    def test_repeated_phrase_outside_lookback_window_is_kept(self):
        phrase = "This particular sentence contains many words that could be repeated later"
        source = {"segments": [
            seg(1, 10, phrase),
            seg(10, 100, "Different dialogue spanning plenty of time"),
            seg(101, 101.3, phrase),
        ]}
        result, report = cleanup_diarized_result(source)
        self.assertEqual(len(result["segments"]), 3)
        self.assertEqual(report["removed_terminal_echoes"], 0)

    def test_short_fast_interjection_is_preserved(self):
        source = {"segments": [seg(1, 1.2, "Right"), seg(1.2, 1.3, "Right")]}
        result, report = cleanup_diarized_result(source)
        self.assertEqual(len(result["segments"]), 2)
        self.assertEqual(report["removed_terminal_echoes"], 0)


if __name__ == "__main__":
    unittest.main()
