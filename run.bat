@echo off
setlocal
cd /d %~dp0

if "%HOST%"=="" set HOST=127.0.0.1
if "%PORT%"=="" set PORT=8100
if "%KILL_EXISTING%"=="" set KILL_EXISTING=0
set PYTHONUNBUFFERED=1

set PYTHON_CMD=
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) and sys.version_info < (3, 13) else 1)" >nul 2>nul
  if not errorlevel 1 set PYTHON_CMD=.venv\Scripts\python.exe
)
if not "%PYTHON%"=="" (
  if "%PYTHON_CMD%"=="" (
    where "%PYTHON%" >nul 2>nul
    if not errorlevel 1 (
      "%PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) and sys.version_info < (3, 13) else 1)" >nul 2>nul
      if not errorlevel 1 set PYTHON_CMD=%PYTHON%
    )
  )
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
  echo If a project .venv already exists, make sure .venv\Scripts\python.exe is usable.
  exit /b 1
)

echo Starting Vision Dataset Studio Web GUI on http://%HOST%:%PORT%
echo Local access:  http://127.0.0.1:%PORT%
echo LAN access:    use your machine IP with port %PORT%

%PYTHON_CMD% -c "import socket,sys; host=sys.argv[1]; port=int(sys.argv[2]); s=socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind((host, port)); s.close()" "%HOST%" "%PORT%" >nul 2>nul
if not "%errorlevel%"=="0" (
  if "%KILL_EXISTING%"=="1" (
    echo Port %PORT% is already in use. Trying to stop existing process.
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT%" ^| findstr "LISTENING"') do taskkill /PID %%a /F >nul 2>nul
  ) else (
    echo Port %PORT% is already in use.
    echo Open the existing service at: http://127.0.0.1:%PORT%
    echo Or restart by running: set KILL_EXISTING=1 ^&^& run.bat
    echo Or use another port: set PORT=8101 ^&^& run.bat
    exit /b 1
  )
)

%PYTHON_CMD% bootstrap_env.py --ensure-base
if not "%errorlevel%"=="0" (
  echo Failed to prepare the local .venv environment.
  exit /b 1
)

for /f "usebackq delims=" %%p in (`%PYTHON_CMD% bootstrap_env.py --print-python`) do set VENV_PYTHON=%%p
"%VENV_PYTHON%" -u web_server.py --host "%HOST%" --port "%PORT%"
