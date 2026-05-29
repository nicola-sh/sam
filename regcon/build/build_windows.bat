@echo off
setlocal
cd /d "%~dp0\..\.."
echo Building RegCon.exe ...
pyinstaller --noconfirm regcon\build\regcon.spec
if errorlevel 1 (
  echo Build failed.
  exit /b 1
)
echo OK: dist\RegCon.exe
echo For SmartScreen see docs\REGCON_WINDOWS.md
endlocal
