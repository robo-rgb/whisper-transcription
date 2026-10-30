# Installs pyannote only into .venv-diarize. Never changes the Whisper .venv.
[CmdletBinding()]
param(
    [switch]$VerifyOnly,
    [ValidateSet("3.11", "3.12")]
    [string]$PythonVersion = "3.12"
)

$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $PSScriptRoot
$DiarizePython = Join-Path $AppRoot ".venv-diarize\Scripts\python.exe"

function Assert-ExitCode([string]$Operation) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed (exit code $LASTEXITCODE). The original Whisper environment was not changed."
    }
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw "FFmpeg was not found on PATH. Install it before setting up speaker identification."
}

if (-not (Test-Path $DiarizePython)) {
    if ($VerifyOnly) {
        throw "The separate speaker environment is missing. Run this script without -VerifyOnly to install."
    }
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw "Python Launcher (py.exe) not found. Install 64-bit Python 3.12 and try again."
    }
    Write-Host "Creating .venv-diarize using Python $PythonVersion. Existing .venv will not be touched."
    & py "-$PythonVersion" -m venv (Join-Path $AppRoot ".venv-diarize")
    Assert-ExitCode "Creating separate speaker environment"
}

if (-not $VerifyOnly) {
    Write-Host "Installing pyannote in the separate speaker environment..."
    & $DiarizePython -m pip install --upgrade pip
    Assert-ExitCode "Updating pip in separate speaker environment"
    & $DiarizePython -m pip install "pyannote.audio>=4.0,<5"
    Assert-ExitCode "Installing pyannote"
}

Write-Host "Verifying speaker environment..."
& $DiarizePython -c "import sys, torch, pyannote.audio; print('Python:', sys.version.split()[0]); print('Torch:', torch.__version__); print('CUDA:', torch.cuda.is_available()); print('pyannote:', getattr(pyannote.audio, '__version__', 'installed'))"
Assert-ExitCode "Verifying speaker environment"

Write-Host ""
Write-Host "Speaker dependencies are installed in .venv-diarize (separate from Whisper)."
Write-Host "Before the first model download:"
Write-Host "  1. Accept model terms at https://huggingface.co/pyannote/speaker-diarization-community-1"
Write-Host "  2. Create a read token at https://huggingface.co/settings/tokens"
Write-Host "  3. Run: .\.venv-diarize\Scripts\hf.exe auth login"
Write-Host "Then select 'Identify speakers' in the Whisper app."
