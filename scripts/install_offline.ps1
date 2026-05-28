$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$wheels = Join-Path (Get-Location) "DATA\wheels"
if (-not (Test-Path $wheels)) {
    Write-Error "Folder DATA\wheels not found. Copy wheels from DATA\req.txt into DATA\wheels\"
}

$venvPython = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment .venv ..."
    python -m venv .venv
}

$python = $venvPython
$findLinks = "DATA\wheels"

Write-Host "Upgrading pip and setuptools ..."
& $python -m pip install --no-index --find-links=$findLinks --upgrade pip setuptools

Write-Host "Installing from DATA\requirements-offline.txt ..."
& $python -m pip install --no-index --find-links=$findLinks -r DATA\requirements-offline.txt

Write-Host "Verifying imports ..."
& $python -c "import paramiko; import django; import bcrypt; import cryptography; import yaml; print('All core imports OK')"

Write-Host "Done. Activate: .\.venv\Scripts\Activate.ps1"
