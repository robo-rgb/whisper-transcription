$host.UI.RawUI.WindowTitle = "Whisper App Launcher"

$AppRoot    = $PSScriptRoot
$VenvFolder = Join-Path $AppRoot ".venv"
$PythonExe  = Join-Path $VenvFolder "Scripts\python.exe"
$PythonWExe = Join-Path $VenvFolder "Scripts\pythonw.exe"
$PipExe     = Join-Path $VenvFolder "Scripts\pip.exe"
$GuiScript  = Join-Path $AppRoot "transcribe-gui.py"
$ErrorLog   = Join-Path $AppRoot "launcher-last-error.log"

Add-Type -AssemblyName System.Windows.Forms

function Show-Error($title, $message) {
    [System.Windows.Forms.MessageBox]::Show(
        $message,
        $title,
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Error
    ) | Out-Null
}

function Show-Info($title, $message) {
    [System.Windows.Forms.MessageBox]::Show(
        $message,
        $title,
        [System.Windows.Forms.MessageBoxButtons]::OK,
        [System.Windows.Forms.MessageBoxIcon]::Information
    ) | Out-Null
}

function Test-SystemPython {
    try {
        $pyVersion = & python --version 2>&1
        if ($pyVersion -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 9) { return $true }
            Show-Error "Python Version Too Old" "Python $major.$minor was found, but Whisper requires Python 3.9 or newer.`n`nInstall Python from python.org and check 'Add Python to PATH'."
            return $false
        }
    } catch {}

    Show-Error "Python Not Found" "Python was not found on this system.`n`nInstall Python 3.9+ from python.org and check 'Add Python to PATH'."
    return $false
}

function Invoke-And-Capture($file, $arguments) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $file
    $psi.Arguments = $arguments
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.CreateNoWindow = $true
    $proc = New-Object System.Diagnostics.Process
    $proc.StartInfo = $psi
    [void]$proc.Start()
    $stdout = $proc.StandardOutput.ReadToEnd()
    $stderr = $proc.StandardError.ReadToEnd()
    $proc.WaitForExit()
    return [PSCustomObject]@{ ExitCode = $proc.ExitCode; StdOut = $stdout; StdErr = $stderr }
}

if (-not (Test-Path $GuiScript)) {
    Show-Error "Launcher Error" "transcribe-gui.py was not found in:`n$AppRoot"
    exit 1
}

if (-not (Test-Path $VenvFolder)) {
    if (-not (Test-SystemPython)) { exit 1 }
    Show-Info "Setup" "First run detected. Creating Python environment.`nThis happens once and may take a moment."
    $createResult = Invoke-And-Capture "python" "-m venv `"$VenvFolder`""
    if ($createResult.ExitCode -ne 0 -or -not (Test-Path $PythonExe)) {
        $createResult | Out-String | Set-Content -Encoding UTF8 $ErrorLog
        Show-Error "Setup Error" "Failed to create the Python environment.`n`nDetails were written to:`n$ErrorLog"
        exit 1
    }
}

$check = Invoke-And-Capture $PythonExe "-c `"import tkinter, whisper, torch; print('ok')`""
if ($check.ExitCode -ne 0) {
    $check | Out-String | Set-Content -Encoding UTF8 $ErrorLog
    $confirm = [System.Windows.Forms.MessageBox]::Show(
        "Required Python packages are missing from the app environment.`n`nThis can happen after deleting/rebuilding .venv.`n`nInstall the standard Whisper dependencies now?`n`nNote: For GPU/CUDA PyTorch, use the manual CUDA install command after this if needed.",
        "Install Required",
        [System.Windows.Forms.MessageBoxButtons]::OKCancel,
        [System.Windows.Forms.MessageBoxIcon]::Question
    )
    if ($confirm -ne [System.Windows.Forms.DialogResult]::OK) { exit 1 }

    $install = Start-Process -FilePath $PipExe -ArgumentList "install --upgrade pip openai-whisper --disable-pip-version-check" -Wait -PassThru -NoNewWindow
    if ($install.ExitCode -ne 0) {
        Show-Error "Install Error" "Installation failed with pip exit code $($install.ExitCode).`n`nOpen PowerShell in the project folder and repair the environment manually."
        exit 1
    }
}

$ffmpeg = & where.exe ffmpeg 2>$null
if (-not $ffmpeg) {
    Show-Error "FFmpeg Not Found" "FFmpeg was not found on PATH.`n`nWhisper needs FFmpeg to decode media files.`n`nInstall FFmpeg or add your FFmpeg bin folder to PATH, then relaunch."
    exit 1
}

if (Test-Path $PythonWExe) {
    $proc = Start-Process -FilePath $PythonWExe -ArgumentList "`"$GuiScript`"" -WindowStyle Hidden -PassThru
    Start-Sleep -Seconds 3
    if ($proc.HasExited -and $proc.ExitCode -ne 0) {
        $msg = "The GUI crashed immediately. Relaunching with a visible console so the error stays on screen."
        $msg | Set-Content -Encoding UTF8 $ErrorLog
        Start-Process -FilePath $PythonExe -ArgumentList "`"$GuiScript`"" -WorkingDirectory $AppRoot
    }
} elseif (Test-Path $PythonExe) {
    Start-Process -FilePath $PythonExe -ArgumentList "`"$GuiScript`"" -WorkingDirectory $AppRoot
} else {
    Show-Error "Launcher Error" "Python interpreter not found in .venv\Scripts.`nTry deleting the .venv folder and relaunching."
    exit 1
}
