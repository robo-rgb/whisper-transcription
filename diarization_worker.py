"""Isolated pyannote Community-1 inference; run only in .venv-diarize.

Writes JSON to a caller-supplied temporary file. No audio or credentials are
transmitted to the application; a Hugging Face login is needed for model download.
"""
from __future__ import annotations

import argparse
import json
import os
import wave
from pathlib import Path

# Disable pyannote usage metrics before importing it.
os.environ["PYANNOTE_METRICS_ENABLED"] = "0"


def load_pcm16_waveform(path: str, torch_module):
    """Load FFmpeg's mono PCM16 WAV directly without using TorchCodec.

    pyannote 4 accepts {'waveform': Tensor[channels, samples], 'sample_rate': int}
    as an alternative to a filename. Loading the generated WAV with Python's
    standard-library wave module avoids native TorchCodec/FFmpeg DLL issues
    on Windows, while model inference still runs on CUDA.
    """
    with wave.open(path, "rb") as audio:
        sample_rate = audio.getframerate()
        if (
            audio.getnchannels() != 1
            or audio.getsampwidth() != 2
            or audio.getcomptype() != "NONE"
            or sample_rate != 16000
        ):
            raise ValueError(
                "Expected 16-kHz mono, uncompressed 16-bit PCM WAV. "
                "Convert the media using the provided FFmpeg runner."
            )
        pcm = audio.readframes(audio.getnframes())

    if not pcm:
        raise ValueError("The input WAV contains no audio samples.")

    # A mutable buffer avoids torch.frombuffer's read-only-buffer warning.
    # Conversion to float32 copies samples before the buffer is discarded.
    waveform = (
        torch_module.frombuffer(bytearray(pcm), dtype=torch_module.int16)
        .to(dtype=torch_module.float32)
        .div_(32768.0)
        .unsqueeze(0)
    )
    return waveform, sample_rate


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
    waveform, sample_rate = load_pcm16_waveform(args.input, torch)
    output = pipeline({"waveform": waveform, "sample_rate": sample_rate}, **options)
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
