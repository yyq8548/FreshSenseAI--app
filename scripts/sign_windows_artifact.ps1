param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath,
    [Parameter(Mandatory = $true)]
    [string]$CertificateThumbprint,
    [Parameter(Mandatory = $true)]
    [string]$TimestampServer
)

$ErrorActionPreference = "Stop"

$artifact = [System.IO.Path]::GetFullPath($FilePath)
if (-not (Test-Path -LiteralPath $artifact -PathType Leaf)) {
    throw "Signing target is unavailable: $artifact"
}
if (-not $TimestampServer.StartsWith("http://", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Windows PowerShell signing requires an http:// timestamp server URL."
}

$normalizedThumbprint = $CertificateThumbprint.Replace(" ", "").ToUpperInvariant()
$certificate = @(
    Get-ChildItem Cert:\CurrentUser\My, Cert:\LocalMachine\My -ErrorAction SilentlyContinue |
        Where-Object { $_.Thumbprint -eq $normalizedThumbprint }
) | Select-Object -First 1
if (-not $certificate) {
    throw "The requested code-signing certificate is not installed."
}
if (-not $certificate.HasPrivateKey) {
    throw "The requested code-signing certificate has no accessible private key."
}
$codeSigningOid = "1.3.6.1.5.5.7.3.3"
if ($certificate.EnhancedKeyUsageList.ObjectId -notcontains $codeSigningOid) {
    throw "The requested certificate is not valid for code signing."
}
$now = Get-Date
if ($now -lt $certificate.NotBefore -or $now -gt $certificate.NotAfter) {
    throw "The requested code-signing certificate is outside its validity period."
}

$signature = Set-AuthenticodeSignature `
    -LiteralPath $artifact `
    -Certificate $certificate `
    -HashAlgorithm SHA256 `
    -IncludeChain All `
    -TimestampServer $TimestampServer
if ($signature.Status -ne "Valid") {
    throw "Authenticode signing did not produce a trusted signature: $($signature.Status)"
}
if (-not $signature.TimeStamperCertificate) {
    throw "Authenticode signing completed without a trusted timestamp."
}

Write-Host "Signed and timestamped: $artifact"
Write-Host "Signer: $($signature.SignerCertificate.Subject)"
