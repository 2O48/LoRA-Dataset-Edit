@echo off
cd /d %~dp0
where conda >nul 2>nul
if %errorlevel%==0 (
  conda run -n caption-codex python lora_reviewer.py
) else (
  python lora_reviewer.py
)
