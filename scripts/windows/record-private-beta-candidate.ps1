# Records observed Windows signature state; never authorizes distribution.
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') { throw 'Disposable Windows runner only' }
$installer=@(Get-ChildItem 'desktop/src-tauri/target/release/bundle/nsis/*-setup.exe')
if ($installer.Count -ne 1 -or $installer[0].Length -gt 64MB) { throw 'Expected one bounded candidate installer' }
$signature=Get-AuthenticodeSignature -FilePath $installer[0].FullName
if ($signature.Status -ne 'NotSigned') { throw 'This engineering candidate must be observed unsigned, not assumed unsigned' }
$evidence=Join-Path (Get-Location) 'artifacts/companion-v2'
$accepted=Get-Content (Join-Path $evidence 'installed-smoke.json') -Raw | ConvertFrom-Json
if ($accepted.updater_disabled -ne $true) { throw 'Private manual-update candidate must prove its native updater is disabled' }
$source=(git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $accepted.source_commit -ne $source) { throw 'Installed candidate source differs' }
@{schema_version=1;source_commit=$source;status='NotSigned';sha256=(Get-FileHash $installer[0].FullName -Algorithm SHA256).Hash.ToLowerInvariant();bytes=$installer[0].Length} |
    ConvertTo-Json | Set-Content (Join-Path $evidence 'windows-signature.json')
Write-Output 'Observed unsigned Windows installer and disabled updater recorded; private publication still requires owner authorization.'
