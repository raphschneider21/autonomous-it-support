@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_all_windows.ps1"
set "exitcode=%ERRORLEVEL%"
echo.
if not "%DEMO_NO_PAUSE%"=="1" pause
exit /b %exitcode%
