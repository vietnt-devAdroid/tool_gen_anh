@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Dang tao moi truong Python...
  py -3 -m venv .venv 2>nul || python -m venv .venv
)
if not exist ".venv\Scripts\python.exe" (
  echo Khong tao duoc .venv. Hay cai Python 3.11 tro len (64-bit) roi chay lai.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
echo.
echo Xong. Bam "LUO Chat.bat" de mo.
pause
