param(
    [string]$Version,
    [string]$ISCCPath = $env:ISCC_PATH
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
if (-not $Version) {
    $Version = (Get-Content (Join-Path $projectRoot "VERSION") -Raw).Trim()
}
$applicationSource = Join-Path $projectRoot "dist\FreshSenseAI"
$application = Join-Path $applicationSource "FreshSenseAI.exe"
if (-not (Test-Path -LiteralPath $application -PathType Leaf)) {
    throw "Build the standalone application before running the installer smoke test."
}
if ([System.Diagnostics.FileVersionInfo]::GetVersionInfo($application).ProductVersion -ne $Version) {
    throw "The standalone application version does not match the requested smoke-test version."
}

function Resolve-InnoCompiler {
    param([string]$PreferredPath)

    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($PreferredPath) { $candidates.Add($PreferredPath) }
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) { $candidates.Add($command.Source) }
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
    if (-not $compiler) { throw "Inno Setup 6 compiler was not found." }
    return $compiler
}

$localAppData = [System.IO.Path]::GetFullPath($env:LOCALAPPDATA)
$installPath = [System.IO.Path]::GetFullPath(
    (Join-Path $localAppData "FreshSenseAI-ReleaseSmoke-$Version")
)
if (
    -not $installPath.StartsWith($localAppData, [System.StringComparison]::OrdinalIgnoreCase) -or
    (Split-Path -Leaf $installPath) -ne "FreshSenseAI-ReleaseSmoke-$Version"
) {
    throw "Refusing to use an unsafe installer smoke-test path: $installPath"
}
if (Test-Path -LiteralPath $installPath) {
    throw "Installer smoke-test directory already exists: $installPath"
}

$smokeDisplayName = "FreshSense AI Release Smoke"
$uninstallRoot = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall"
$existingSmoke = Get-ChildItem $uninstallRoot -ErrorAction SilentlyContinue |
    Where-Object {
        (Get-ItemProperty $_.PSPath -ErrorAction SilentlyContinue).DisplayName -like "$smokeDisplayName*"
    }
if ($existingSmoke) {
    throw "A prior FreshSense smoke-test registration exists; uninstall it before retrying."
}

$workDir = [System.IO.Path]::GetFullPath((Join-Path $projectRoot "work"))
New-Item -ItemType Directory -Force $workDir | Out-Null
$smokeInstallerName = "FreshSenseAI-Smoke-Setup-$Version"
$smokeInstaller = Join-Path $workDir "$smokeInstallerName.exe"
$logPath = Join-Path $workDir "installer-smoke-$Version.log"

$tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$stagingRoot = [System.IO.Path]::GetFullPath(
    (Join-Path $tempBase "FreshSenseAI-smoke-payload-$Version")
)
if (
    -not $stagingRoot.StartsWith($tempBase, [System.StringComparison]::OrdinalIgnoreCase) -or
    (Split-Path -Leaf $stagingRoot) -ne "FreshSenseAI-smoke-payload-$Version"
) {
    throw "Refusing to use an unsafe smoke payload path: $stagingRoot"
}
if (Test-Path -LiteralPath $stagingRoot) {
    throw "Smoke payload staging path already exists: $stagingRoot"
}

$compiler = Resolve-InnoCompiler -PreferredPath $ISCCPath
New-Item -ItemType Directory -Force $stagingRoot | Out-Null
$stagedApplication = Join-Path $stagingRoot "FreshSenseAI"
Copy-Item -LiteralPath $applicationSource -Destination $stagedApplication -Recurse

try {
    & $compiler `
        "/DMyAppVersion=$Version" `
        "/DMyAppName=$smokeDisplayName" `
        "/DMyAppId={{C73AA09C-D776-466D-9AE7-E3321F767D3F}" `
        "/DMyOutputBaseFilename=$smokeInstallerName" `
        "/DMyCompression=zip/1" `
        "/DMySkipIcons=1" `
        "/DMyAppSourceDir=$stagedApplication" `
        "/O$workDir" `
        "installer\FreshSenseAI.iss"
    if ($LASTEXITCODE -ne 0) {
        throw "Smoke installer compilation returned exit code $LASTEXITCODE."
    }
} finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}

if (-not (Test-Path -LiteralPath $smokeInstaller -PathType Leaf)) {
    throw "Smoke installer was not created: $smokeInstaller"
}
try {
    $installProcess = Start-Process `
        -FilePath $smokeInstaller `
        -ArgumentList @(
            "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/NOICONS",
            "/DIR=$installPath", "/LOG=$logPath"
        ) `
        -Wait -PassThru -WindowStyle Hidden
    if ($installProcess.ExitCode -ne 0) {
        throw "Silent installer returned exit code $($installProcess.ExitCode)."
    }

    $installedApplication = Join-Path $installPath "FreshSenseAI.exe"
    $model = Join-Path $installPath "_internal\models\densenet201.h5"
    $gate = Join-Path $installPath "_internal\models\open_set_gate.npz"
    $artifactManifest = Join-Path $installPath "_internal\artifacts\model_manifest.json"
    $evaluationReport = Join-Path $installPath "_internal\evaluation\reports\expanded_12_class\gated_test\evaluation_report.json"
    $embedding = Get-ChildItem `
        (Join-Path $installPath "_internal\models\embedding_cache") `
        -Recurse -Filter "*.onnx" -File -ErrorAction SilentlyContinue |
        Select-Object -First 1
    $uninstaller = Join-Path $installPath "unins000.exe"
    foreach ($required in @(
        $installedApplication, $model, $gate, $artifactManifest, $evaluationReport, $uninstaller
    )) {
        if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
            throw "Installed release asset is missing: $required"
        }
    }
    if (-not $embedding) {
        throw "Installed release contains no local ONNX embedding model."
    }
    $installedVersion = [System.Diagnostics.FileVersionInfo]::GetVersionInfo(
        $installedApplication
    ).ProductVersion
    if ($installedVersion -ne $Version) {
        throw "Installed application version '$installedVersion' does not match '$Version'."
    }

    $startupMarker = Join-Path $workDir "installed-startup-$Version.ready"
    if (Test-Path -LiteralPath $startupMarker) {
        Remove-Item -LiteralPath $startupMarker -Force
    }
    $env:FRESHSENSE_STARTUP_SMOKE_FILE = $startupMarker
    try {
        $launchProcess = Start-Process `
            -FilePath $installedApplication `
            -PassThru -WindowStyle Hidden
        for ($attempt = 0; $attempt -lt 120 -and -not (Test-Path -LiteralPath $startupMarker); $attempt++) {
            Start-Sleep -Milliseconds 500
            $launchProcess.Refresh()
            if ($launchProcess.HasExited -and -not (Test-Path -LiteralPath $startupMarker)) {
                throw "Installed application exited before runtime assets became ready."
            }
        }
        if (-not (Test-Path -LiteralPath $startupMarker)) {
            throw "Installed application did not initialize its runtime assets within 60 seconds."
        }
        $launchProcess.WaitForExit(15000) | Out-Null
        if (-not $launchProcess.HasExited) {
            Stop-Process -Id $launchProcess.Id -Force
            $launchProcess.WaitForExit()
        }
    } finally {
        Remove-Item Env:FRESHSENSE_STARTUP_SMOKE_FILE -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $startupMarker) {
            Remove-Item -LiteralPath $startupMarker -Force
        }
    }

    $uninstallProcess = Start-Process `
        -FilePath $uninstaller `
        -ArgumentList @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART") `
        -Wait -PassThru -WindowStyle Hidden
    if ($uninstallProcess.ExitCode -ne 0) {
        throw "Silent uninstaller returned exit code $($uninstallProcess.ExitCode)."
    }
    for ($attempt = 0; $attempt -lt 30 -and (Test-Path -LiteralPath $installPath); $attempt++) {
        Start-Sleep -Milliseconds 250
    }
    if (Test-Path -LiteralPath $installPath) {
        throw "Uninstall did not remove the isolated application directory: $installPath"
    }
} finally {
    if (Test-Path -LiteralPath $smokeInstaller -PathType Leaf) {
        $removed = $false
        for ($cleanupAttempt = 0; $cleanupAttempt -lt 20 -and -not $removed; $cleanupAttempt++) {
            try {
                Remove-Item -LiteralPath $smokeInstaller -Force -ErrorAction Stop
                $removed = $true
            } catch {
                if ($cleanupAttempt -eq 19) { throw }
                Start-Sleep -Milliseconds 500
            }
        }
    }
}

Write-Host "FreshSense $Version isolated installer smoke passed."
Write-Host "Install, bundled assets, desktop launch, version metadata, and uninstall were verified."
