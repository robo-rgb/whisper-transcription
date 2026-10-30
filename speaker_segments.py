"""Pure-Python alignment of Whisper words with diarization speaker turns.

No pyannote or torch imports: the existing Whisper environment remains unchanged.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from math import isfinite
from typing import Any


def speaker_display_name(speaker_id: str | None) -> str:
    """Convert machine labels to human-readable, non-identifying speaker labels."""
    if not speaker_id:
        return "Unknown speaker"
    if speaker_id.startswith("SPEAKER_") and speaker_id[8:].isdigit():
        return f"Speaker {int(speaker_id[8:]) + 1}"
    return str(speaker_id)


def normalize_turns(turns: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Validate and sort time intervals returned by the diarization subprocess."""
    normalized = []
    for turn in turns:
        start, end = float(turn["start"]), float(turn["end"])
        speaker = str(turn["speaker"]).strip()
        if not (isfinite(start) and isfinite(end) and 0 <= start < end and speaker):
            raise ValueError("Invalid diarization turn encountered.")
        normalized.append({"start": start, "end": end, "speaker": speaker})
    return sorted(normalized, key=lambda item: (item["start"], item["end"], item["speaker"]))


def speaker_at(start: float, end: float, turns: list[Mapping[str, Any]]) -> str | None:
    """Assign the speaker with the largest time overlap; leave gaps unidentified."""
    if end < start:
        raise ValueError("Word end precedes its start.")
    best_speaker, best_overlap, best_distance = None, 0.0, float("inf")
    midpoint = (start + end) / 2
    for turn in turns:
        overlap = max(0.0, min(end, turn["end"]) - max(start, turn["start"]))
        distance = abs(midpoint - (turn["start"] + turn["end"]) / 2)
        if overlap > best_overlap or (overlap > 0 and overlap == best_overlap and distance < best_distance):
            best_overlap, best_distance, best_speaker = overlap, distance, str(turn["speaker"])
    # A very short word can straddle diarization gaps without overlap.
    if best_speaker is None:
        containing = [t for t in turns if t["start"] <= midpoint <= t["end"]]
        if containing:
            return str(containing[0]["speaker"])
    return best_speaker


def _segment_runs(segment: Mapping[str, Any], turns: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    words = segment.get("words") or []
    valid_words = (
        bool(words)
        and all(
            isinstance(w, Mapping) and "word" in w
            and isinstance(w.get("start"), (int, float))
            and isinstance(w.get("end"), (int, float))
            and isfinite(float(w["start"])) and isfinite(float(w["end"]))
            and w["end"] >= w["start"]
            for w in words
        )
    )
    if not valid_words:
        # Whisper can omit word timing for very short or unusual segments.
        speaker = speaker_at(float(segment["start"]), float(segment["end"]), turns)
        return [{
            "start": segment["start"], "end": segment["end"],
            "text": segment.get("text", "").strip(), "speaker": speaker,
            "source_segment_id": segment.get("id"),
        }]

    runs: list[dict[str, Any]] = []
    for word in words:
        speaker = speaker_at(float(word["start"]), float(word["end"]), turns)
        if runs and runs[-1]["speaker"] == speaker:
            runs[-1]["end"] = max(runs[-1]["end"], float(word["end"]))
            runs[-1]["words"].append(deepcopy(word))
        else:
            runs.append({
                "start": float(word["start"]), "end": float(word["end"]),
                "speaker": speaker, "source_segment_id": segment.get("id"),
                "words": [deepcopy(word)],
            })
    for run in runs:
        run["text"] = "".join(w["word"] for w in run["words"]).strip()
    return [run for run in runs if run["text"]]


def apply_diarization(result: Mapping[str, Any], turns: list[Mapping[str, Any]]) -> dict[str, Any]:
    """Return a new Whisper result with word-level speaker changes exposed as segments.

    The top-level transcript text and language remain intact. Original segments
    are not mutated. No speaker is invented for words outside the detected turns.
    """
    timeline = normalize_turns(turns)
    if not timeline:
        raise ValueError("No speaker turns detected. Check the audio or try without diarization.")
    merged = deepcopy(dict(result))
    segments: list[dict[str, Any]] = []
    for source in result.get("segments", []):
        segments.extend(_segment_runs(source, timeline))
    for index, segment in enumerate(segments):
        segment["id"] = index
    merged["segments"] = segments
    merged["speaker_turns"] = timeline
    merged["speaker_labels"] = {
        speaker: speaker_display_name(speaker)
        for speaker in sorted({turn["speaker"] for turn in timeline})
    }
    return merged
