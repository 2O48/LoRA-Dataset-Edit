@echo off
setlocal
cd /d %~dp0

set WITH_QWEN=0
if /I "%1"=="--with-qwen" set WITH_QWEN=1

set PYTHON_CMD=
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) and sys.version_info < (3, 13) else 1)" >nul 2>nul
  if not errorlevel 1 set PYTHON_CMD=.venv\Scripts\python.exe
)
if "%PYTHON_CMD%"=="" (
  where python >nul 2>nul
  if not errorlevel 1 (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) and sys.version_info < (3, 13) else 1)" >nul 2>nul
    if not errorlevel 1 set PYTHON_CMD=python
  )
)
if "%PYTHON_CMD%"=="" (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) and sys.version_info < (3, 13) else 1)" >nul 2>nul
    if not errorlevel 1 set PYTHON_CMD=py -3.11
  )
)
if "%PYTHON_CMD%"=="" (
  echo Python was not found.
  echo Install Python 3.11 from https://www.python.org/downloads/ and enable "Add Python to PATH".
  exit /b 1
)

echo Preparing project virtual environment for Vision Dataset Studio...
if "%WITH_QWEN%"=="1" (
  %PYTHON_CMD% bootstrap_env.py --ensure-qwen
) else (
  %PYTHON_CMD% bootstrap_env.py --ensure-base
)
if not "%errorlevel%"=="0" exit /b %errorlevel%

echo.
echo Environment ready.
for /f "usebackq delims=" %%p in (`%PYTHON_CMD% bootstrap_env.py --print-python`) do echo Project Python: %%p
echo Next step: run.bat
