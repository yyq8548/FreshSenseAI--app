$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if (-not (Test-Path "models\densenet201.h5")) {
    throw "Missing models\densenet201.h5. The desktop build fails closed without a trained model."
}

if (-not (Test-Path "data\fruit_catalog.json")) {
    throw "Missing data\fruit_catalog.json. The desktop build requires a validated fruit catalog."
}

python -m PyInstaller --noconfirm --clean FreshSenseAI.spec

Write-Host "FreshSense desktop build created at dist\FreshSenseAI\FreshSenseAI.exe"
