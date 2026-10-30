"""Run optional diarization in a separate venv to protect Whisper's CUDA stack."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent


def diarization_python() -> Path:
    if sys.platform == "win32":
        return APP_DIR / ".venv-diarize" / "Scripts" / "python.exe"
    return APP_DIR / ".venv-diarize" / "bin" / "python"


def ensure_diarization_ready() -> None:
    if not diarization_python().is_file():
        raise RuntimeError(
            "Speaker recognition is not installed. Follow README-speaker-diarization.md "
            "to create the separate .venv-diarize environment."
        )


def run_diarization(audio_path: str, ffmpeg_path: str, num_speakers: int | None = None) -> list[dict[str, Any]]:
    """Convert media to mono WAV and invoke the pyannote worker.

    Hugging Face credentials are read from the worker's environment / local login,
    never passed on a command line or written into transcript outputs.
    """
    ensure_diarization_ready()
    if num_speakers is not None and not 1 <= num_speakers <= 8:
        raise ValueError("Speaker count must be between 1 and 8.")
    if not ffmpeg_path:
        raise RuntimeError("FFmpeg is required for speaker recognition.")

    with tempfile.TemporaryDirectory(prefix="whisper-speakers-") as tmp:
        wave = Path(tmp) / "audio.wav"
        output = Path(tmp) / "speakers.json"
        ffmpeg = subprocess.run(
            [ffmpeg_path, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
             "-i", audio_path, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wave)],
            capture_output=True, text=True, check=False,
        )
        if ffmpeg.returncode:
            raise RuntimeError("FFmpeg failed to prepare speaker audio: " + ffmpeg.stderr[-900:])

        cmd = [
            str(diarization_python()), str(APP_DIR / "diarization_worker.py"),
            "--input", str(wave), "--output", str(output),
        ]
        if num_speakers:
            cmd.extend(["--num-speakers", str(num_speakers)])
        env = os.environ.copy()
        env["PYANNOTE_METRICS_ENABLED"] = "0"
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
        if proc.returncode:
            # Never echo the user's access token (including if a dependency logs it).
            details = ((proc.stderr or proc.stdout).strip() or "Unknown worker error")[-1200:]
            secret = env.get("HF_TOKEN")
            if secret:
                details = details.replace(secret, "[redacted]")
            raise RuntimeError(
                "Speaker detection failed. Verify pyannote installation, Hugging Face "
                "model access, and available GPU memory. Details: " + details
            )
        if not output.is_file():
            raise RuntimeError("Speaker worker returned no timeline.")
        data = json.loads(output.read_text(encoding="utf-8"))
        turns = data.get("turns")
        if not isinstance(turns, list):
            raise RuntimeError("Speaker worker returned an invalid timeline.")
        return turns
