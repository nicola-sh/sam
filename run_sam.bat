@echo off
cd /d "%~dp0"
python -m sam %*
if errorlevel 1 pause
