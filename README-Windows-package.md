# Auto Transcriber 1.4.0 — Windows package

This ZIP contains the Auto Transcriber GUI, Whisper transcription integration,
optional pyannote Community-1 speaker diarization, subtitle cleanup, and the
scripts needed to launch and set up the application on Windows.

## Recommended: update the existing tested installation

Your existing installation at `C:\Projects\whisper` already has the two working
Python environments and cached speaker model. To upgrade with the packaged
source files:

1. Close Auto Transcriber.
2. Back up `C:\Projects\whisper` or confirm you can restore it from Git.
3. Extract the ZIP. Open the inner `Auto-Transcriber` directory.
4. Copy **its contents** into `C:\Projects\whisper`, allowing replacement
   of application code and launcher scripts.
5. **Leave `.venv`, `.venv-diarize`, and your local Hugging Face cache alone.**
   Do not copy, move, rename, or rebuild either Python environment.
6. Start `C:\Projects\whisper\transcribe-app.bat`.

If you maintain the existing Git checkout, simply running `git pull --ff-only`
on the release branch is more convenient than copying ZIP files.

## New installation on another Windows computer

This is a source-and-setup bundle, **not a self-contained EXE or offline
installer**. A new machine needs 64-bit Python, FFmpeg on PATH, and access to
package downloads. Model weights are not bundled.

1. Install Python 3.13 or other compatible Python version for Whisper and
   Python 3.12 for speaker diarization. Install FFmpeg and verify
   `ffmpeg -version` succeeds in a new PowerShell window.
2. Extract the ZIP into a directory you will keep unchanged.
3. Run `transcribe-app.bat`. The launcher can create the base `.venv`
   and install standard Whisper dependencies if they are missing.
   Depending on the installed PyTorch build, CUDA GPU support may need
   manual configuration in `.venv`. The pre-existing working
   `C:\Projects\whisper\.venv` is the validated CUDA configuration;
   copying it between installation paths is **not supported**.
4. To add speaker diarization, run
   `.\scripts\setup-speaker-diarization.ps1` in PowerShell. It creates
   a separate `.venv-diarize`, without changing `.venv`.
   Verify its CUDA status and install a compatible CUDA-enabled PyTorch build
   in that environment if required.
5. Accept the gated pyannote Community-1 model terms at
   https://huggingface.co/pyannote/speaker-diarization-community-1 and
   authenticate with `.\.venv-diarize\Scripts\hf.exe auth login`.
   Model files download to the local Hugging Face cache on first use.
6. Run `.\scripts\verify-windows-install.ps1` to check dependencies.
7. Open the GUI, enable **Identify speakers (local, optional setup)**, and
   select a suitable speaker count. Use **All Formats** to export SRT,
   VTT, TXT, timestamped TXT, JSON, and TSV.

## Performance and accuracy

The validated configuration uses an RTX 4090 with CUDA for Whisper Large and
a separate CUDA-enabled pyannote worker. Triton timing warnings can occur on
Windows; Whisper falls back to a slower word-alignment implementation while
the main transcription still runs on CUDA.

Speaker labels identify voice clusters, not actual people. Overlapping speech
can cause incorrect speaker changes. Always review before publication.
Normal transcription works without speaker diarization enabled.

The diarization output cleanup removes empty subtitle cues and certain
implausible terminal echoes, but preserves plausible repeated dialogue for
human review. The full JSON contains the cleanup report and underlying speaker
turns. See `README-speaker-diarization.md` for details.

## Privacy and distribution

The ZIP intentionally excludes both Python environments, Hugging Face tokens,
model caches, recordings, transcripts, and logs. Never put those data in a
public release ZIP. Transcription audio stays local; initial model and package
downloads require internet connectivity. Review model attribution and third-party
licensing before redistributing dependencies or model weights.

A SHA256 file accompanies the ZIP. In PowerShell, verify it with:

```powershell
Get-FileHash -Algorithm SHA256 "Auto-Transcriber-1.4.0-Windows.zip"
```

Compare the result to the SHA256 text in the accompanying
`.zip.sha256` file.
