@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Hay chay "Cai dat.bat" truoc.
  pause
  exit /b 1
)
echo === Cai them (tuy chon, nang khoang 1-2 GB): tach nhac nen (Demucs) va nhan dang giong noi (Whisper) ===
echo Can khi: lam video co LOI NOI va muon long tieng moi nhung GIU nhac nen goc.
".venv\Scripts\python.exe" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
".venv\Scripts\python.exe" -m pip install demucs soundfile numpy faster-whisper
echo.
echo Xong. Lan dau chay se tu tai mo hinh (htdemucs ~80 MB, whisper small ~480 MB).
pause
