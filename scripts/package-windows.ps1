# Build a clean, reinstallable Windows application ZIP.
# Does not modify the installed application or either virtual environment.
[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')]
    [string]$Version = "1.4.0"
)

$ErrorActionPreference = "Stop"
$AppRoot = Split-Path -Parent $PSScriptRoot
$Dist = Join-Path $AppRoot "dist"
$Product = "Auto-Transcriber"
$ArchiveName = "$Product-$Version-Windows.zip"
$ArchivePath = Join-Path $Dist $ArchiveName
$HashPath = "$ArchivePath.sha256"

# Explicit whitelist: NEVER include .venv, .venv-diarize, token caches,
# recordings, generated transcripts, local logs or Git credentials.
$Files = @(
    "transcribe-app.bat",
    "launch-transcribe.ps1",
    "transcribe-gui.py",
    "diarization_worker.py",
    "diarization_runner.py",
    "speaker_segments.py",
    "transcript_cleanup.py",
    "README-Windows-package.md",
    "README-speaker-diarization.md",
    "requirements-cuda-cu130.txt",
    "scripts/setup-speaker-diarization.ps1",
    "scripts/smoke-test-speakers.ps1",
    "scripts/verify-windows-install.ps1"
)

New-Item -ItemType Directory -Force -Path $Dist | Out-Null
$Stage = Join-Path $Dist (".package-" + [Guid]::NewGuid().ToString("N"))
$PackageRoot = Join-Path $Stage $Product

try {
    New-Item -ItemType Directory -Force -Path $PackageRoot | Out-Null
    foreach ($File in $Files) {
        $Source = Join-Path $AppRoot $File
        if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
            throw "Package input is missing: $File"
        }
        $Destination = Join-Path $PackageRoot $File
        $Parent = Split-Path -Parent $Destination
        New-Item -ItemType Directory -Force -Path $Parent | Out-Null
        Copy-Item -LiteralPath $Source -Destination $Destination
    }

    @(
        "Auto Transcriber $Version"
        "Package contents: application code, launchers, optional speaker identification, setup and usage documentation."
        "Python virtual environments, CUDA packages, model weights, Hugging Face credentials, recordings and transcripts are NOT included."
        "See README-Windows-package.md before launching a fresh installation."
    ) | Set-Content -LiteralPath (Join-Path $PackageRoot "PACKAGE-INFO.txt") -Encoding UTF8

    if (Test-Path -LiteralPath $ArchivePath) {
        Remove-Item -LiteralPath $ArchivePath -Force
    }
    Compress-Archive -LiteralPath $PackageRoot -DestinationPath $ArchivePath -CompressionLevel Optimal

    # Validate archive contents and refuse accidental additions to the whitelist.
    Add-Type -AssemblyName System.IO.Compression
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $Zip = [System.IO.Compression.ZipFile]::OpenRead($ArchivePath)
    try {
        $Actual = @(
            $Zip.Entries |
            Where-Object { $_.Name } |
            ForEach-Object { $_.FullName.Replace('\', '/') }
        )
        $Expected = @($Files | ForEach-Object { "$Product/$($_.Replace('\', '/'))" })
        $Expected += "$Product/PACKAGE-INFO.txt"
        $Extra = @($Actual | Where-Object { $_ -notin $Expected })
        $Missing = @($Expected | Where-Object { $_ -notin $Actual })
        if ($Extra.Count -gt 0 -or $Missing.Count -gt 0) {
            throw ("ZIP validation failed. Extra: " + ($Extra -join ", ") +
                   ". Missing: " + ($Missing -join ", "))
        }
        foreach ($Entry in $Zip.Entries | Where-Object { $_.Name }) {
            if ($Entry.Length -le 0) {
                throw "Empty entry in package: $($Entry.FullName)"
            }
        }
    }
    finally {
        $Zip.Dispose()
    }

    $Sha = (Get-FileHash -Algorithm SHA256 -LiteralPath $ArchivePath).Hash.ToLowerInvariant()
    "$Sha  $ArchiveName" | Set-Content -LiteralPath $HashPath -Encoding ascii
    Write-Host "Created: $ArchivePath"
    Write-Host "SHA256:  $Sha"
    Write-Host "Checksum: $HashPath"
    Write-Host "Validated $($Expected.Count) application files. Existing environments were not modified."
}
finally {
    if (Test-Path -LiteralPath $Stage) {
        Remove-Item -LiteralPath $Stage -Recurse -Force
    }
}
