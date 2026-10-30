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

1. Install **Python 3.12** (64-bit) and confirm FFmpeg is on PATH. Python 3.11 is also supported by the setup script.
2. From the repository folder, run the safe Windows setup script:

   ```powershell
   .\\scripts\\setup-speaker-diarization.ps1
   ```

   This creates `.venv-diarize`, installs pyannote there, and reports
   whether that *separate* Python environment can use CUDA. It does **not**
   alter the original Whisper `.venv`. To verify without installing:

   ```powershell
   .\\scripts\\setup-speaker-diarization.ps1 -VerifyOnly
   ```

   If PowerShell blocks the script, you can invoke it for this process only:

   ```powershell
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\setup-speaker-diarization.ps1
   ```

   The setup script defaults to Python 3.12. If you only have Python 3.11,
   run it with `-PythonVersion 3.11`. On Windows, use `py -0p` to list
   installed Python interpreters. Do **not** install pyannote into the
   existing `.venv` (which may use a different Python version).

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

## Test speaker detection before using the GUI

After completing setup and Hugging Face login, choose a short recording
containing two or more speakers (use a recording you have permission to process).
Run this PowerShell command from the project folder:

```powershell
.\\scripts\\smoke-test-speakers.ps1 -InputMedia "C:\\path\\to\\sample.wav"
```

If exactly two speakers are expected, add `-Speakers 2`. The command prints
the number of recognized speakers and the first 25 speaker turns. It deletes
temporary audio/JSON and leaves the original recording untouched. Compare the
reported speaker changes to the recording before enabling diarization in the
GUI. The first run may download model weights.

## Usage

Select the audio or video files. Check **Identify speakers (local, optional
setup)** and leave **Speakers: Auto** unless the speaker count is known; a
specific count between 1 and 8 may be selected. Choose any export format
or **All Formats**. The app runs Whisper with word timestamps, converts the
original media to temporary mono 16-kHz WAV with FFmpeg, runs the pyannote
worker, aligns Whisper words to exclusive speaker turns, and deletes the
temporary WAV and JSON files afterward. The worker loads FFmpeg's temporary
16-kHz mono PCM16 WAV into a memory-backed waveform using Python's standard
library, then passes it directly to pyannote. This bypasses TorchCodec's
file-decoder DLLs (which may fail to load on some Windows installations).
TorchCodec may remain installed as a pyannote dependency, but the worker
does not invoke it to open the recording.

Exports use **Speaker 1**, **Speaker 2**, etc., for model-generated labels.
Words outside detected speech are labelled **Unknown speaker**. The JSON
export also preserves the model's raw `SPEAKER_00` labels and diarization
turns. When diarization is disabled, original transcript formats are unchanged.

**Subtitle cleanup:** when diarization succeeds, the app removes empty or
zero-duration subtitle segments. It also removes an obviously implausible
end-of-recording echo only when a long phrase repeats earlier dialogue within
60 seconds yet is squeezed into fewer than 1/9 of a second per word. Plausible
repetitions are retained and flagged in the GUI log for human review, rather
than silently erased. The JSON export includes a `transcript_cleanup` audit
summary; its top-level `text` remains the original Whisper text, while
`segments` holds the cleaned speaker-aligned output.

To save the full diagnostic JSON alongside the subtitle file, select
**All Formats** (or **JSON (Full Whisper Result)** for JSON only). The default
**SRT (Subtitles)** option saves only an SRT.

**Failure handling:** if the optional speaker model encounters an error, the app
keeps the successful Whisper transcription, saves it **without speaker labels**,
and displays a warning. A failed diarization pass never implies that speakers
were accurately distinguished.

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

Automated GitHub Actions checks run on Windows and Linux, with Python 3.11 and
3.12, and validate both PowerShell scripts' syntax. These tests check model
integration contracts, segmentation, exports, and error handling; they do
not run pyannote weights or measure actual GPU performance or speaker accuracy.
Integration validation still requires a real multi-speaker recording on the
target Windows computer.
