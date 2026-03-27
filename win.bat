@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

:: --- Administrator Check ---
>nul 2>&1 "%SYSTEMROOT%\system32\cacls.exe" "%SYSTEMROOT%\system32\config\system"
if '%errorlevel%' NEQ '0' (
    echo ==========================================================
    echo ERROR: Administrator privileges are required for symlinks.
    echo Please right-click this .bat file and select 'Run as administrator'.
    echo ==========================================================
    pause
    goto :eof
)

:: --- Launch Python ---
python deploy\deploy_all.py %*
pause
