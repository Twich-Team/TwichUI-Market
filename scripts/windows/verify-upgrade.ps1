# Real compatibility upgrade, isolated to this disposable runner's fresh app data.
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') { throw 'Disposable Windows CI only' }
$old=@(Get-Item 'desktop/test-fixtures/legacy-0.1.0-unsigned-setup.exe')
$current=@(Get-ChildItem 'desktop/src-tauri/target/release/bundle/nsis/*-setup.exe')
if ($old.Count -ne 1 -or $current.Count -ne 1) { throw 'Expected one old and one current installer' }
if ((Get-FileHash $old[0].FullName -Algorithm SHA256).Hash -ne '16D1B2E10813A7692FA641EA6E23B6DB9A1386BAF448508A43C2A17C28CDCED4') { throw 'Legacy installer differs from verified ab1c886 artifact' }
$data=Join-Path $env:APPDATA 'team.twich.market'
if (Test-Path $data) { throw 'Upgrade acceptance must begin without existing app data' }
$install=Join-Path $env:RUNNER_TEMP 'TwichMarket-Upgrade'
if (Test-Path $install) { throw 'Upgrade installation must begin empty' }
$result=Start-Process -FilePath $old[0].FullName -ArgumentList @('/S',"/D=$install") -Wait -PassThru
if ($result.ExitCode -ne 0) { throw 'Verified old installer failed' }
$executable=Join-Path $install 'twichui-market-companion.exe'
$env:MARKET_TEST_INSTALLED_EXE=$executable;$env:MARKET_TEST_INSTALL_DIRECTORY=$install
$env:MARKET_TEST_NEW_INSTALLER=$current[0].FullName;$env:MARKET_TEST_APP_DATA=$data
$probe=[System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback,0);$probe.Start()
$env:MARKET_TEST_CDP_PORT=$probe.LocalEndpoint.Port.ToString();$probe.Stop()
$env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS="--remote-debugging-port=$env:MARKET_TEST_CDP_PORT --remote-debugging-address=127.0.0.1"
$env:WEBVIEW2_USER_DATA_FOLDER=Join-Path $env:RUNNER_TEMP 'TwichMarket-Upgrade-WebView'
$policy='HKLM:\SOFTWARE\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments';$name='twichui-market-companion.exe'
$null=New-Item -Path $policy -Force
if ($null -ne (Get-ItemProperty -Path $policy -Name $name -ErrorAction SilentlyContinue)) { throw 'Refusing to replace existing test policy' }
$null=New-ItemProperty -Path $policy -Name $name -PropertyType String -Value $env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS
try {
    $app=Start-Process -FilePath $executable -PassThru
    python scripts/verify-companion-authorization.py --upgrade
    if ($LASTEXITCODE -ne 0) { throw 'Actual installed upgrade acceptance failed' }
} finally {
    Remove-ItemProperty -Path $policy -Name $name -ErrorAction SilentlyContinue
    Get-Process -Name 'twichui-market-companion' -ErrorAction SilentlyContinue | Where-Object {$_.Path -eq $executable} | ForEach-Object {
        $null=$_.CloseMainWindow();if (-not $_.WaitForExit(10000)) {$_.Kill();$_.WaitForExit()}
    }
    $cache=Join-Path $data 'market-v1.sqlite';$connection=Join-Path $data 'connection.json'
    $hashes=@{};foreach ($file in @($cache,$connection)) {if(Test-Path $file){$hashes[$file]=(Get-FileHash $file -Algorithm SHA256).Hash}}
    $uninstaller=Join-Path $install 'uninstall.exe'
    if (Test-Path $uninstaller) {
        $removed=Start-Process -FilePath $uninstaller -ArgumentList @('/S',"_?=$install") -Wait -PassThru
        if ($removed.ExitCode -ne 0) { throw 'Upgrade test uninstaller failed' }
    }
    foreach ($file in $hashes.Keys) {
        if (-not(Test-Path $file) -or (Get-FileHash $file -Algorithm SHA256).Hash -ne $hashes[$file]) { throw 'Uninstall changed retained upgrade data' }
    }
    $receipt=Join-Path (Get-Location) 'artifacts/companion-v2/legacy-upgrade.json'
    if (Test-Path $receipt) {
        if ($hashes.Count -ne 2 -or (Test-Path $executable)) { throw 'Uninstall retention proof is incomplete' }
        $accepted=Get-Content $receipt -Raw | ConvertFrom-Json
        $accepted.uninstall_data_preservation_verified_by_parent=$true
        $accepted | ConvertTo-Json -Depth 4 | Set-Content $receipt
    }
    if (Test-Path $data) {
        # Preserve the entire synthetic test profile, then allow a separate clean
        # first-run test. Never delete/reuse a real user's profile.
        Move-Item $data (Join-Path $env:RUNNER_TEMP 'TwichMarket-Upgrade-RetainedData')
    }
}
Write-Output 'Actual legacy upgrade and uninstall retention acceptance passed.'
