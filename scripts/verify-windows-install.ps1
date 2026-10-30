# Read-only post-install validation for the two independent environments.
[CmdletBinding()]
param([switch]$RequireCuda)

$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $PSScriptRoot

function Check-Python([string]$RelativePath, [string]$Code, [string]$Label) {
    $Path = Join-Path $AppRoot $RelativePath
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label is missing: $Path"
    }
    Write-Host "$Label"
    & $Path -c $Code
    if ($LASTEXITCODE -ne 0) {
        throw "$Label validation failed with exit code $LASTEXITCODE."
    }
}

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw "FFmpeg is not on PATH."
}
Write-Host "FFmpeg: $((Get-Command ffmpeg).Source)"
$MustUseCuda = if ($RequireCuda) { "True" } else { "False" }

$BaseCode = @'
import sys
import whisper
import torch
print("Python:", sys.version.split()[0])
print("Whisper:", getattr(whisper, "__version__", "installed"))
print("Torch:", torch.__version__)
print("CUDA:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
'@
$SpeakerCode = @'
import sys
import torch
import pyannote.audio
print("Python:", sys.version.split()[0])
print("Torch:", torch.__version__)
print("pyannote:", getattr(pyannote.audio, "__version__", "installed"))
print("CUDA:", torch.cuda.is_available())
if torch.cuda.is_available():
    print("GPU:", torch.cuda.get_device_name(0))
'@
if ($RequireCuda) {
    $BaseCode += "`nassert torch.cuda.is_available(), 'Whisper CUDA is not available'"
    $SpeakerCode += "`nassert torch.cuda.is_available(), 'Speaker CUDA is not available'"
}

Check-Python ".venv\Scripts\python.exe" $BaseCode "Whisper environment:"
Check-Python ".venv-diarize\Scripts\python.exe" $SpeakerCode "Speaker environment:"
Write-Host "PASS: Both application environments are available. Model access and real-audio accuracy are not tested here."
