@echo off
cd /d %~dp0
where conda >nul 2>nul
if %errorlevel%==0 (
  conda run -n caption-codex python vision_dataset_reviewer.py
) else (
  python vision_dataset_reviewer.py
)
