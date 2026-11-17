@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "run.py"
) else (
  echo Chua cai dat. Hay chay "Cai dat.bat" truoc.
  pause
)
