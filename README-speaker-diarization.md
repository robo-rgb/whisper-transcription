# Optional local speaker identification

This feature is under development on `feature/speaker-diarization`. It
transcribes with the existing OpenAI Whisper installation and optionally
labels *who spoke when* using **pyannote Community-1**. It does not identify
the actual names of speakers. Always review speaker labels before publication.

## Why a separate environment?

Our working Whisper GPU environment is left untouched. The pyannote worker
runs in a separate `.venv-diarize` Python environment so its PyTorch,
torchcodec, and other dependencies cannot overwrite Whisper's CUDA packages.
Ordinary transcription still works with the speaker checkbox unchecked,
without requiring pyannote or Hugging Face credentials.

## Initial setup on Windows (PowerShell)

1. Install **Python 3.11 or newer** (64-bit) and confirm FFmpeg is on PATH.
2. From the repository folder, create the *separate* environment and install:

   ```powershell
   py -3.11 -m venv .venv-diarize
   .\.venv-diarize\Scripts\python.exe -m pip install --upgrade pip
   .\.venv-diarize\Scripts\python.exe -m pip install "pyannote.audio>=4.0,<5"
   ```

   If the `py -3.11` launcher is unavailable, use the path to a Python 3.11+
   executable. Do **not** install pyannote into the existing `.venv`.

3. Sign into Hugging Face, accept the conditions for the model, and log in
   **inside the speaker environment**:

   - Model terms: `https://huggingface.co/pyannote/speaker-diarization-community-1`
   - Token setup: `https://huggingface.co/settings/tokens`
   - Login: `.\.venv-diarize\Scripts\hf.exe auth login`

   Use a read-capable token. Do not put a token in application files or Git.
   You can instead set the `HF_TOKEN` environment variable if needed.
   Authentication is required for the initial model download. Model weights
   are cached locally afterward.

4. Check GPU visibility in the speaker environment:

   ```powershell
   .\.venv-diarize\Scripts\python.exe -c "import torch; print(torch.cuda.is_available())"
   ```

   `True` enables GPU inference; `False` runs on CPU (typically slower).
   For CUDA setup issues, follow the matching installation instructions for
   your GPU and PyTorch version **in .venv-diarize only**.

5. Launch the application normally using `transcribe-app.bat`.

## Usage

Select the audio or video files. Check **Identify speakers (local, optional
setup)** and leave **Speakers: Auto** unless the speaker count is known; a
specific count between 1 and 8 may be selected. Choose any export format
or **All Formats**. The app runs Whisper with word timestamps, converts the
original media to temporary mono 16-kHz WAV with FFmpeg, runs the pyannote
worker, aligns Whisper words to exclusive speaker turns, and deletes the
temporary WAV and JSON files afterward.

Exports use **Speaker 1**, **Speaker 2**, etc., for model-generated labels.
Words outside detected speech are labelled **Unknown speaker**. The JSON
export also preserves the model's raw `SPEAKER_00` labels and diarization
turns. When diarization is disabled, original transcript formats are unchanged.

**Limits:** speaker assignments are estimates, not identity verification.
Rapid interruptions, overlapping speech, background noise, and music can
produce incorrect or unknown labels. A Whisper word may span a real speaker
change. Verify recordings against transcripts before publication.

**Privacy:** recognition happens locally. During first setup/download the
Hugging Face library contacts Hugging Face to download the model. This
implementation disables pyannote usage telemetry in its subprocess; it does
not upload the recording to a transcription API.

**Licensing:** Community-1 is distributed under CC-BY-4.0. Review the model
card and its attribution requirements before redistribution.

## Testing

No model download is necessary for lightweight regression tests:

```powershell
python -m unittest discover -s tests -v
python -m compileall -q transcribe-gui.py speaker_segments.py diarization_runner.py diarization_worker.py
```

These tests check segmentation and exports, not actual GPU performance or
speaker accuracy. Integration validation requires a real multi-speaker
recording on the target Windows computer.
