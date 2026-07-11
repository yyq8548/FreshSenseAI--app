param(
    [string]$PythonExecutable = "python",
    [string]$ISCCPath = $env:ISCC_PATH,
    [string]$SigningCertificateThumbprint = $env:FRESHSENSE_SIGNING_CERTIFICATE_THUMBPRINT,
    [string]$TimestampServer = $env:FRESHSENSE_TIMESTAMP_SERVER,
    [switch]$SkipTests,
    [switch]$PrepareEmbeddingModel,
    [switch]$SkipApplicationBuild,
    [switch]$SkipInstaller,
    [switch]$RequireSignedRelease
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$outputDir = Join-Path (Split-Path -Parent $projectRoot) "outputs"
Set-Location $projectRoot

function Invoke-Python {
    param([string[]]$Arguments)

    & $PythonExecutable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: $PythonExecutable $($Arguments -join ' ')"
    }
}

function Resolve-InnoCompiler {
    param([string]$PreferredPath)

    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($PreferredPath) {
        $candidates.Add($PreferredPath)
    }
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) {
        $candidates.Add($command.Source)
    }
    if (${env:ProgramFiles(x86)}) {
        $candidates.Add((Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"))
    }
    if ($env:ProgramFiles) {
        $candidates.Add((Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"))
    }
    if ($env:LOCALAPPDATA) {
        $candidates.Add((Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"))
    }

    $compiler = $candidates |
        Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
        Select-Object -First 1
    if (-not $compiler) {
        throw (
            "Inno Setup 6 was not found. Install it with " +
            "'winget install --id JRSoftware.InnoSetup' or set ISCC_PATH."
        )
    }
    return $compiler
}

$version = (Get-Content "VERSION" -Raw).Trim()
Write-Host "Building FreshSense AI $version for Windows x64"
if ($RequireSignedRelease -and -not $SigningCertificateThumbprint) {
    throw "-RequireSignedRelease requires a trusted code-signing certificate thumbprint."
}
if ($SigningCertificateThumbprint -and -not $TimestampServer) {
    throw "A timestamp server is required when code signing is enabled."
}

if (-not $SkipTests) {
    Invoke-Python @(
        "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider",
        "--basetemp", "work\pytest-release"
    )
}

if ($PrepareEmbeddingModel) {
    Invoke-Python @("scripts\prepare_embedding_model.py")
}

Invoke-Python @("scripts\release_tools.py", "validate")
if (-not $SkipApplicationBuild) {
    Invoke-Python @(
        "scripts\release_tools.py", "version-info",
        "--output", "work\windows_version_info.txt"
    )
    Invoke-Python @("-m", "PyInstaller", "--noconfirm", "--clean", "FreshSenseAI.spec")
}

$applicationPath = Join-Path $projectRoot "dist\FreshSenseAI\FreshSenseAI.exe"
if (-not (Test-Path -LiteralPath $applicationPath -PathType Leaf)) {
    throw "PyInstaller did not create $applicationPath"
}
$productVersion = [System.Diagnostics.FileVersionInfo]::GetVersionInfo(
    $applicationPath
).ProductVersion
if ($productVersion -ne $version) {
    throw "Executable version '$productVersion' does not match VERSION '$version'."
}
if ($SigningCertificateThumbprint) {
    & "$PSScriptRoot\sign_windows_artifact.ps1" `
        -FilePath $applicationPath `
        -CertificateThumbprint $SigningCertificateThumbprint `
        -TimestampServer $TimestampServer
}

if ($SkipInstaller) {
    Write-Host "Standalone application created at $applicationPath"
    Write-Warning "-SkipInstaller produces a developer artifact, not a release package."
    exit 0
}

New-Item -ItemType Directory -Force $outputDir | Out-Null
$compiler = Resolve-InnoCompiler -PreferredPath $ISCCPath
$tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$stagingRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $tempBase "FreshSenseAI-release-$version")
)
if (
    -not $stagingRoot.StartsWith($tempBase, [System.StringComparison]::OrdinalIgnoreCase) -or
    (Split-Path -Leaf $stagingRoot) -ne "FreshSenseAI-release-$version"
) {
    throw "Refusing to use an unsafe release staging path: $stagingRoot"
}
if (Test-Path -LiteralPath $stagingRoot) {
    Remove-Item -LiteralPath $stagingRoot -Recurse -Force
}
New-Item -ItemType Directory -Force $stagingRoot | Out-Null
$stagingApplication = Join-Path $stagingRoot "FreshSenseAI"
Copy-Item -LiteralPath (Join-Path $projectRoot "dist\FreshSenseAI") `
    -Destination $stagingApplication -Recurse

try {
    & $compiler `
        "/DMyAppVersion=$version" `
        "/DMyAppSourceDir=$stagingApplication" `
        "/O$outputDir" `
        "installer\FreshSenseAI.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup failed with exit code $LASTEXITCODE."
    }
} finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}

$installerName = "FreshSenseAI-Setup-$version.exe"
$installerPath = Join-Path $outputDir $installerName
if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) {
    throw "Inno Setup did not create $installerPath"
}
if ($SigningCertificateThumbprint) {
    & "$PSScriptRoot\sign_windows_artifact.ps1" `
        -FilePath $installerPath `
        -CertificateThumbprint $SigningCertificateThumbprint `
        -TimestampServer $TimestampServer
}

$finalizeArguments = @{ Version = $version }
if ($RequireSignedRelease) {
    $finalizeArguments.RequireSigned = $true
}
& "$PSScriptRoot\finalize_windows_release.ps1" @finalizeArguments

Write-Host "Release installer: $installerPath"
Write-Host "SHA-256 file: $installerPath.sha256"
Write-Host "Release manifest: $(Join-Path $outputDir "FreshSenseAI-Release-$version.json")"
