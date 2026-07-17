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
Compress-Archive -Path (Join-Path $resolvedWork "*") -DestinationPath $resolvedOutput
$hash = (Get-FileHash -LiteralPath $resolvedOutput -Algorithm SHA256).Hash.ToLowerInvariant()
Set-Content -LiteralPath "$resolvedOutput.sha256" -Value "$hash  $([System.IO.Path]::GetFileName($resolvedOutput))" -Encoding ascii
Write-Host "Runtime bundle: $resolvedOutput"
Write-Host "SHA-256: $hash"
