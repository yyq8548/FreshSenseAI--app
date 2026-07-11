param(
    [string]$Version,
    [switch]$RequireSigned
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$outputDir = Join-Path (Split-Path -Parent $projectRoot) "outputs"
if (-not $Version) {
    $Version = (Get-Content (Join-Path $projectRoot "VERSION") -Raw).Trim()
}

$manifestPath = Join-Path $outputDir "FreshSenseAI-Release-$Version.json"
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
    throw "Release manifest is missing: $manifestPath"
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.schema_version -ne 1 -or $manifest.version -ne $Version) {
    throw "Release manifest metadata is invalid."
}

$installerPath = Join-Path $outputDir $manifest.installer
$checksumPath = "$installerPath.sha256"
if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) {
    throw "Release installer is missing: $installerPath"
}
if (-not (Test-Path -LiteralPath $checksumPath -PathType Leaf)) {
    throw "Release checksum is missing: $checksumPath"
}

$actualHash = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $manifest.sha256) {
    throw "Installer SHA-256 does not match the release manifest."
}
$checksumText = (Get-Content -LiteralPath $checksumPath -Raw).Trim()
$expectedChecksum = "$actualHash *$($manifest.installer)"
if ($checksumText -ne $expectedChecksum) {
    throw "Installer SHA-256 file is invalid."
}

$signature = Get-AuthenticodeSignature -FilePath $installerPath
if ($signature.Status -eq "Valid") {
    Write-Host "Authenticode signature: valid"
} else {
    if ($RequireSigned) {
        throw "Release signature is not trusted and valid: $($signature.Status)"
    }
    Write-Warning (
        "Authenticode signature: $($signature.Status). Windows may display an " +
        "unrecognized publisher warning until a trusted signing certificate is configured."
    )
}

Write-Host "Verified FreshSense AI $Version"
Write-Host "Installer: $installerPath"
Write-Host "SHA-256: $actualHash"
