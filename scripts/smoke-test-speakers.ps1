# Test local pyannote with a real file, without launching the GUI.
# Does not alter the existing Whisper environment; deletes temporary WAV/JSON.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InputMedia,
    [ValidateRange(0, 8)]
    [int]$Speakers = 0
)

$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $AppRoot ".venv-diarize\Scripts\python.exe"
$Worker = Join-Path $AppRoot "diarization_worker.py"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Missing .venv-diarize. Run .\scripts\setup-speaker-diarization.ps1 first."
}
if (-not (Test-Path -LiteralPath $Worker)) {
    throw "Diarization worker not found in the project directory."
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw "FFmpeg is not available on PATH."
}

$Media = (Resolve-Path -LiteralPath $InputMedia -ErrorAction Stop).Path
if (-not (Test-Path -LiteralPath $Media -PathType Leaf)) {
    throw "InputMedia must be an audio or video file."
}

$Work = Join-Path ([IO.Path]::GetTempPath()) ("whisper-diarize-smoke-" + [Guid]::NewGuid().ToString("N"))
New-Item -Path $Work -ItemType Directory -Force | Out-Null
$Wave = Join-Path $Work "audio.wav"
$Json = Join-Path $Work "turns.json"

try {
    & ffmpeg -nostdin -hide_banner -loglevel error -y -i $Media -vn -ac 1 -ar 16000 -c:a pcm_s16le $Wave
    if ($LASTEXITCODE -ne 0) {
        throw "FFmpeg could not convert the file."
    }

    # Keep telemetry disabled for the subprocess.
    $env:PYANNOTE_METRICS_ENABLED = "0"
    $arguments = @($Worker, "--input", $Wave, "--output", $Json)
    if ($Speakers -gt 0) {
        $arguments += @("--num-speakers", [string]$Speakers)
    }

    Write-Host "Running local speaker recognition. First use may download model weights."
    & $Python @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Diarization worker failed. Verify Hugging Face model access and Python environment."
    }
    if (-not (Test-Path -LiteralPath $Json)) {
        throw "Diarization worker did not produce an output timeline."
    }

    $data = Get-Content -Raw -LiteralPath $Json | ConvertFrom-Json
    $turns = @($data.turns | Where-Object { $null -ne $_ })
    # Do not reuse the -Speakers [int] parameter: PowerShell variables are case-insensitive.
    $detectedSpeakerLabels = @($turns | ForEach-Object { $_.speaker } | Sort-Object -Unique)
    Write-Host "Recognized $($detectedSpeakerLabels.Count) distinct speaker label(s), $($turns.Count) speaker turn(s)."
    if ($turns.Count -eq 0) {
        throw "No speaker turns detected in this recording."
    }
    Write-Host "First 25 turns:"
    $turns | Select-Object -First 25 | ForEach-Object {
        Write-Host ("  {0:N2}s to {1:N2}s: {2}" -f $_.start, $_.end, $_.speaker)
    }
    Write-Host "Review accuracy against the recording; these labels do not establish identity."
}
finally {
    Remove-Item -LiteralPath $Work -Recurse -Force -ErrorAction SilentlyContinue
}
