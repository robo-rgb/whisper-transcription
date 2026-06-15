@echo off
set "APPDIR=%~dp0"
%SystemRoot%\system32\WindowsPowerShell\v1.0\powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%APPDIR%launch-transcribe.ps1"
