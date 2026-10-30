"""Isolated pyannote Community-1 inference; run only in .venv-diarize.

Writes JSON to a caller-supplied temporary file. No audio or credentials are
transmitted to the application; a Hugging Face login is needed for model download.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

# Disable pyannote usage metrics before importing it.
os.environ["PYANNOTE_METRICS_ENABLED"] = "0"


def main() -> None:
    parser = argparse.ArgumentParser(description="Local speaker diarization worker")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--num-speakers", type=int, default=0)
    args = parser.parse_args()

    import torch
    from pyannote.audio import Pipeline

    model_id = "pyannote/speaker-diarization-community-1"
    token = os.environ.get("HF_TOKEN")
    pipeline = Pipeline.from_pretrained(model_id, token=token) if token else Pipeline.from_pretrained(model_id)
    if pipeline is None:
        raise RuntimeError("Unable to load Community-1. Accept the model terms and log in to Hugging Face.")
    if torch.cuda.is_available():
        pipeline.to(torch.device("cuda"))

    options = {"num_speakers": args.num_speakers} if args.num_speakers > 0 else {}
    output = pipeline(args.input, **options)
    diarization = getattr(output, "exclusive_speaker_diarization", None)
    if diarization is None:
        raise RuntimeError("Community-1 did not provide exclusive speaker diarization.")

    turns = [
        {"start": float(turn.start), "end": float(turn.end), "speaker": str(speaker)}
        for turn, _, speaker in diarization.itertracks(yield_label=True)
    ]
    Path(args.output).write_text(json.dumps({"turns": turns}), encoding="utf-8")


if __name__ == "__main__":
    main()
