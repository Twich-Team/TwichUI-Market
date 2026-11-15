# Records observed Windows signature state; never authorizes distribution.
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') { throw 'Disposable Windows runner only' }
$installer=@(Get-ChildItem 'desktop/src-tauri/target/release/bundle/nsis/*-setup.exe')
if ($installer.Count -ne 1 -or $installer[0].Length -gt 64MB) { throw 'Expected one bounded candidate installer' }
$signature=Get-AuthenticodeSignature -FilePath $installer[0].FullName
if ($signature.Status -ne 'NotSigned') { throw 'This engineering candidate must be observed unsigned, not assumed unsigned' }
$evidence=Join-Path (Get-Location) 'artifacts/companion-v2'
$accepted=Get-Content (Join-Path $evidence 'installed-smoke.json') -Raw | ConvertFrom-Json
if ($accepted.update_checks_blocked_for_custom_server -ne $true) { throw 'Custom test-server credentials must not reach the production updater' }
$key=(Get-Content 'desktop/src-tauri/updater-public-key.txt' -Raw).Trim()
$hasher=[Security.Cryptography.SHA256]::Create()
try { $keyHash=[Convert]::ToHexString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($key))).ToLowerInvariant() } finally { $hasher.Dispose() }
if ($accepted.updater_public_key_sha256 -ne $keyHash) { throw 'Installed public verification key differs from source' }
$source=(git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $accepted.source_commit -ne $source) { throw 'Installed candidate source differs' }
if ($accepted.installed_executable_sha256 -notmatch '^[a-f0-9]{64}$') { throw 'Actual installed executable hash is required; a build-directory reference is insufficient' }
@{schema_version=1;source_commit=$source;status='NotSigned';sha256=(Get-FileHash $installer[0].FullName -Algorithm SHA256).Hash.ToLowerInvariant();bytes=$installer[0].Length;updater_public_key_sha256=$keyHash;executable_sha256=$accepted.installed_executable_sha256;executable_reference='actual-installed-windows-executable';build_executable_sha256=(Get-FileHash 'desktop/src-tauri/target/release/twichui-market-companion.exe' -Algorithm SHA256).Hash.ToLowerInvariant()} |
    ConvertTo-Json | Set-Content (Join-Path $evidence 'windows-signature.json')
Write-Output 'Observed unsigned Windows installer and compiled public updater key recorded; final owner publication approval is still required.'
