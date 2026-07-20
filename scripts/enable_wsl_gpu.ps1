$ErrorActionPreference = "Stop"
$LogPath = Join-Path $PSScriptRoot "enable_wsl_gpu.log"
Start-Transcript -Path $LogPath -Force

try {

Write-Host "Enabling Windows Subsystem for Linux..." -ForegroundColor Cyan
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
if ($LASTEXITCODE -notin @(0, 3010)) { throw "Failed to enable Windows Subsystem for Linux." }

Write-Host "Enabling Virtual Machine Platform..." -ForegroundColor Cyan
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
if ($LASTEXITCODE -notin @(0, 3010)) { throw "Failed to enable Virtual Machine Platform." }

Write-Host "Setting WSL 2 as the default..." -ForegroundColor Cyan
wsl.exe --set-default-version 2

Write-Host "Installing Ubuntu 24.04..." -ForegroundColor Cyan
wsl.exe --install -d Ubuntu-24.04 --no-launch

Write-Host "WSL features are configured. Restart Windows if requested." -ForegroundColor Green
}
catch {
    Write-Error $_
    exit 1
}
finally {
    Stop-Transcript
}
