@echo off
setlocal EnableExtensions
cd /d "%~dp0\.."

if not exist "DATA\wheels" (
    echo [ERROR] Folder DATA\wheels not found.
    echo Copy all .whl and .tar.gz files from req.txt into DATA\wheels\
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment .venv ...
    python -m venv .venv
    if errorlevel 1 exit /b 1
)

call .venv\Scripts\activate.bat

echo Upgrading pip and setuptools from local wheels ...
python -m pip install --no-index --find-links=DATA\wheels --upgrade pip setuptools
if errorlevel 1 exit /b 1

echo Installing SAM dependencies from DATA\requirements-offline.txt ...
python -m pip install --no-index --find-links=DATA\wheels -r DATA\requirements-offline.txt
if errorlevel 1 (
    echo.
    echo [WARN] Full install failed. Try grouped install - see docs\AVAILABLE_LIBRARIES.md
    exit /b 1
)

echo.
echo Verifying imports ...
python -c "import paramiko; import django; import bcrypt; import cryptography; import yaml; print('All core imports OK')"
if errorlevel 1 exit /b 1

echo.
echo Done. Activate: .venv\Scripts\activate.bat
exit /b 0
