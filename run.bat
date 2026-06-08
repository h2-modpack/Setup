@echo off
if "%~1"=="" (
  echo Usage: ModpackTools\run.bat SCRIPT.py [args...]
  exit /b 2
)

where py >nul 2>nul
if %errorlevel%==0 py -3 -c "import sys; raise SystemExit(0 if sys.version_info[0] == 3 else 1)" >nul 2>nul
if %errorlevel%==0 (
  py -3 %*
  exit /b %errorlevel%
)

where python >nul 2>nul
if %errorlevel%==0 python -c "import sys; raise SystemExit(0 if sys.version_info[0] == 3 else 1)" >nul 2>nul
if %errorlevel%==0 (
  python %*
  exit /b %errorlevel%
)

where python3 >nul 2>nul
if %errorlevel%==0 python3 -c "import sys; raise SystemExit(0 if sys.version_info[0] == 3 else 1)" >nul 2>nul
if %errorlevel%==0 (
  python3 %*
  exit /b %errorlevel%
)

echo No Python 3 runner found. Install py -3, python, or python3.
exit /b 2
