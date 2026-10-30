# Integration-test the PowerShell smoke-test report with fake FFmpeg and fake worker.
# Requires Python but no GPU, pyannote, audio model, or FFmpeg installation.
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$sourceScript = Join-Path $repoRoot "scripts\smoke-test-speakers.ps1"
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ("whisper-speakers-test-" + [guid]::NewGuid().ToString("N"))
$oldTelemetry = $env:PYANNOTE_METRICS_ENABLED

try {
    $scriptsDir = Join-Path $testRoot "scripts"
    New-Item -ItemType Directory -Force -Path $scriptsDir | Out-Null
    Copy-Item -LiteralPath $sourceScript -Destination $scriptsDir

    $venvDir = Join-Path $testRoot ".venv-diarize"
    & python -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { throw "Could not prepare test-only Python venv." }

    # This fake worker writes a representative speaker timeline; it does
    # not import torch or pyannote and never touches the user's real venv.
    $fakeWorker = @'
import json
import sys
from pathlib import Path
args = sys.argv[1:]
target = Path(args[args.index("--output") + 1])
target.write_text(json.dumps({"turns": [
    {"start": 0.00, "end": 0.75, "speaker": "SPEAKER_00"},
    {"start": 0.75, "end": 1.25, "speaker": "SPEAKER_01"},
    {"start": 1.25, "end": 2.00, "speaker": "SPEAKER_00"}
]}), encoding="utf-8")
'@
    Set-Content -LiteralPath (Join-Path $testRoot "diarization_worker.py") -Value $fakeWorker -Encoding utf8

    $sample = Join-Path $testRoot "sample.wav"
    Set-Content -LiteralPath $sample -Value "placeholder" -NoNewline

    # Simulate FFmpeg output so the test exercises argument handling and
    # PowerShell timeline formatting, not an external audio decoder.
    function ffmpeg {
        $destination = $args[-1]
        [IO.File]::WriteAllBytes([string]$destination, [byte[]](0, 1, 2, 3))
        $global:LASTEXITCODE = 0
    }

    $testScript = Join-Path $scriptsDir "smoke-test-speakers.ps1"
    foreach ($requested in @(0, 2)) {
        if ($requested -eq 0) {
            $result = (& $testScript -InputMedia $sample 2>&1 | Out-String)
        } else {
            $result = (& $testScript -InputMedia $sample -Speakers $requested 2>&1 | Out-String)
        }
        if ($result -notmatch "Recognized 2 distinct speaker label\(s\), 3 speaker turn\(s\)\.") {
            throw "Incorrect speaker summary for -Speakers $requested : $result"
        }
        if ($result -notmatch "0\.75s to 1\.25s: SPEAKER_01") {
            throw "Incorrect speaker turns for -Speakers $requested : $result"
        }
        Write-Host "PASS: smoke-test output (requested speakers=$requested)"
    }
}
finally {
    $env:PYANNOTE_METRICS_ENABLED = $oldTelemetry
    if (Test-Path -LiteralPath $testRoot) {
        Remove-Item -LiteralPath $testRoot -Recurse -Force
    }
}
