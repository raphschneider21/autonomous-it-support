@echo off
setlocal
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0launch_all_windows.ps1"
set "DEMO_EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%DEMO_NO_PAUSE%"=="1" pause
exit /b %DEMO_EXIT_CODE%
