param(
    [Parameter(Mandatory = $true)][string]$GoldenSuite,
    [Parameter(Mandatory = $true)][string]$OutputPath
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$workRoot = Join-Path $projectRoot "work\runtime-bundle"
$resolvedProject = [System.IO.Path]::GetFullPath($projectRoot)
$resolvedWork = [System.IO.Path]::GetFullPath($workRoot)
if (-not $resolvedWork.StartsWith($resolvedProject, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to use runtime staging outside the project workspace."
}
if (Test-Path -LiteralPath $resolvedWork) {
    Remove-Item -LiteralPath $resolvedWork -Recurse -Force
}

$paths = @(
    "models\densenet201.h5",
    "models\open_set_gate.npz",
    "models\embedding_cache",
    "data\fruit_catalog.json",
    "data\food_knowledge_base.json",
    "artifacts\model_manifest.json",
    "evaluation\manifests\legacy_grouped_v1.json",
    "evaluation\reports\current_model\evaluation_report.json",
    "evaluation\reports\gate_calibration_final.json"
)
foreach ($relative in $paths) {
    $source = Join-Path $projectRoot $relative
    if (-not (Test-Path -LiteralPath $source)) {
        throw "Required runtime bundle input is unavailable: $source"
    }
    $destination = Join-Path $resolvedWork $relative
    New-Item -ItemType Directory -Force (Split-Path -Parent $destination) | Out-Null
    Copy-Item -LiteralPath $source -Destination $destination -Recurse
}

$goldenDestination = Join-Path $resolvedWork "ci\golden"
New-Item -ItemType Directory -Force (Split-Path -Parent $goldenDestination) | Out-Null
Copy-Item -LiteralPath $GoldenSuite -Destination $goldenDestination -Recurse

$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
New-Item -ItemType Directory -Force (Split-Path -Parent $resolvedOutput) | Out-Null
if (Test-Path -LiteralPath $resolvedOutput) {
    Remove-Item -LiteralPath $resolvedOutput -Force
}
$tar = Get-Command tar -ErrorAction Stop
Push-Location $resolvedWork
try {
    & $tar.Source -a -c -f $resolvedOutput .
    if ($LASTEXITCODE -ne 0) {
        throw "tar failed to create the runtime ZIP (exit code $LASTEXITCODE)."
    }
} finally {
    Pop-Location
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($resolvedOutput)
try {
    $invalid = @($archive.Entries | Where-Object { $_.FullName.Contains("\") })
    if ($invalid.Count -gt 0) {
        throw "Runtime ZIP contains non-POSIX path separators."
    }
} finally {
    $archive.Dispose()
}
$hash = (Get-FileHash -LiteralPath $resolvedOutput -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath "$resolvedOutput.sha256" -Value "$hash  $([System.IO.Path]::GetFileName($resolvedOutput))" -Encoding ascii
Write-Host "Runtime bundle: $resolvedOutput"
Write-Host "SHA-256: $hash"
