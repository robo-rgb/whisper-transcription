"""Conservative cleanup of speaker-labelled transcript segments.

Leave Whisper's original top-level text and raw pyannote speaker turns intact.
Do not remove normally timed repeated phrases: a speaker may actually repeat.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from math import isfinite
import re
from typing import Any


def _tokens(value: str) -> list[str]:
    return re.findall(r"\w+", str(value).casefold(), flags=re.UNICODE)


def _contains_sequence(haystack: list[str], needle: list[str]) -> bool:
    if not needle or len(needle) > len(haystack):
        return False
    return any(haystack[i : i + len(needle)] == needle
               for i in range(len(haystack) - len(needle) + 1))


def cleanup_diarized_result(result: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Remove empty cues and highly implausible *terminal* echo hallucinations.

    A terminal echo is discarded only when its phrase has at least 10 words,
    appears verbatim within the previous 60 seconds of dialogue (including
    words split across speaker boundaries), and would require a speaking rate
    greater than 9 words/second. Suspicious, normally timed repeats are kept
    and flagged for human review. No speaker identity is inferred.
    """
    cleaned = deepcopy(dict(result))
    original = list(cleaned.get("segments", []))
    kept: list[dict[str, Any]] = []
    removed_empty = 0
    for item in original:
        text = str(item.get("text", "")).strip()
        start, end = float(item.get("start", 0)), float(item.get("end", 0))
        if not text or not (isfinite(start) and isfinite(end)) or end - start <= 0.001:
            removed_empty += 1
            continue
        kept.append(item)

    removed_terminal_echo = 0
    if len(kept) >= 2:
        last = kept[-1]
        start, end = float(last["start"]), float(last["end"])
        words = _tokens(last.get("text", ""))
        duration = end - start
        if len(words) >= 10 and len(words) / duration > 9.0:
            preceding = [
                item for item in kept[:-1]
                if float(item.get("end", 0)) >= start - 60.0
                and float(item.get("start", 0)) < start
            ]
            preceding_words = _tokens(" ".join(str(x.get("text", "")) for x in preceding))
            if _contains_sequence(preceding_words, words):
                kept.pop()
                removed_terminal_echo = 1

    review_repeats: list[dict[str, Any]] = []
    for previous, current in zip(kept, kept[1:]):
        old_words = _tokens(previous.get("text", ""))
        new_words = _tokens(current.get("text", ""))
        gap = float(current["start"]) - float(previous["end"])
        if (
            len(new_words) >= 6 and len(old_words) >= len(new_words)
            and old_words[-len(new_words):] == new_words
            and previous.get("speaker") == current.get("speaker")
            and -0.01 <= gap <= 0.20
        ):
            review_repeats.append({"start": float(current["start"]), "end": float(current["end"])})

    cleaned["segments"] = kept
    # Retain all non-segment Whisper metadata, including the original 'text'.
    # Recording the cleanup in JSON makes the edit auditable.
    summary = {
        "removed_empty_cues": removed_empty,
        "removed_terminal_echoes": removed_terminal_echo,
        "possible_repetitions_to_review": review_repeats,
    }
    cleaned["transcript_cleanup"] = summary
    return cleaned, summary
