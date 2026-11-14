# Trust checks only; owner supplies an existing approved Windows signing setup.
param([string]$Installer,[string]$Output)
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') { throw 'Owner Windows release runner only' }
$signature=Get-AuthenticodeSignature -FilePath $Installer
$expected=$env:COMPANION_PUBLISHER_THUMBPRINT.ToUpperInvariant()
if ($signature.Status -ne 'Valid' -or $null -eq $signature.SignerCertificate -or $signature.SignerCertificate.Thumbprint -ne $expected) {
    throw 'Actual Authenticode trust or pinned publisher differs'
}
if ($null -eq $signature.TimeStamperCertificate) { throw 'A trusted timestamp is required for this permanent installer' }
@{status='Valid';thumbprint=$expected;timestamped=$true;sha256=(Get-FileHash $Installer -Algorithm SHA256).Hash.ToLowerInvariant()} |
    ConvertTo-Json | Set-Content $Output
