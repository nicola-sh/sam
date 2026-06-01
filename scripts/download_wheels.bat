@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

if not exist "DATA\wheels" mkdir "DATA\wheels"

echo Downloading wheels for Windows amd64, Python 3.13 ...
echo Target: DATA\wheels

python -m pip install --upgrade pip
if errorlevel 1 exit /b 1

python -m pip download -r DATA\requirements-sam-core.txt -d DATA\wheels ^
  --platform win_amd64 --python-version 3.13 --implementation cp --only-binary=:all:
if errorlevel 1 exit /b 1

echo.
echo Optional: full offline set (may skip PySimpleGUI, cx_Oracle) ...
python scripts\download_wheels.py
if errorlevel 1 (
  echo [WARN] Some optional packages failed — core SAM set is usually enough.
)

echo.
echo Done. Files in DATA\wheels
dir /b DATA\wheels\*.whl | find /c /v ""
exit /b 0
