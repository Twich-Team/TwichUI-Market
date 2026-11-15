# Observe Windows publisher identity honestly. Tauri signatures are independently
# mandatory; no commercial certificate, private key or trust-root import is needed.
param([string]$Installer,[string]$Output)
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') { throw 'Disposable Windows runner only' }
$signature=Get-AuthenticodeSignature -FilePath $Installer
if ($signature.Status -notin @('NotSigned','Valid')) { throw 'Unexpected Windows publisher observation' }
$thumb=if ($signature.SignerCertificate) {$signature.SignerCertificate.Thumbprint} else {''}
@{status=$signature.Status.ToString();thumbprint=$thumb;timestamped=($null -ne $signature.TimeStamperCertificate);sha256=(Get-FileHash $Installer -Algorithm SHA256).Hash.ToLowerInvariant()} |
    ConvertTo-Json | Set-Content $Output
