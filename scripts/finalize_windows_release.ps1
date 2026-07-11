param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [switch]$RequireSigned
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$outputDir = Join-Path (Split-Path -Parent $projectRoot) "outputs"
$installerName = "FreshSenseAI-Setup-$Version.exe"
$installerPath = Join-Path $outputDir $installerName
if (-not (Test-Path -LiteralPath $installerPath -PathType Leaf)) {
    throw "Release installer is missing: $installerPath"
}

$signature = Get-AuthenticodeSignature -FilePath $installerPath
if ($RequireSigned -and $signature.Status -ne "Valid") {
    throw "A trusted, valid Authenticode signature is required for this release."
}
$sha256 = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$checksumPath = "$installerPath.sha256"
[System.IO.File]::WriteAllText(
    $checksumPath,
    "$sha256 *$installerName`n",
    $utf8NoBom
)

$manifest = [ordered]@{
    schema_version = 1
    app_name = "FreshSense AI"
    version = $Version
    architecture = "windows-x64"
    installer = $installerName
    sha256 = $sha256
    signed = ($signature.Status -eq "Valid")
    signature_status = $signature.Status.ToString()
    built_at_utc = [DateTime]::UtcNow.ToString("o")
}
$manifestPath = Join-Path $outputDir "FreshSenseAI-Release-$Version.json"
[System.IO.File]::WriteAllText(
    $manifestPath,
    ($manifest | ConvertTo-Json) + "`n",
    $utf8NoBom
)

$verifyArguments = @{ Version = $Version }
if ($RequireSigned) {
    $verifyArguments.RequireSigned = $true
}
& "$PSScriptRoot\verify_windows_release.ps1" @verifyArguments

Write-Host "Finalized FreshSense AI $Version release artifacts."
