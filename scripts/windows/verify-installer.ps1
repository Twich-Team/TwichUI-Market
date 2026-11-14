# Runs only on the disposable Windows CI runner; no server or addon files involved.
param([switch]$CheckTray)
if ($CheckTray) { $env:MARKET_TEST_TRAY_ACCEPTANCE='true' } else { Remove-Item Env:MARKET_TEST_TRAY_ACCEPTANCE -ErrorAction SilentlyContinue }
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') {
    throw 'This script is restricted to disposable GitHub Windows runners'
}
$installer = @(Get-ChildItem 'desktop/src-tauri/target/release/bundle/nsis/*-setup.exe')
if ($installer.Count -ne 1) { throw 'Expected exactly one NSIS installer' }
$installPath = Join-Path $env:RUNNER_TEMP 'TwichMarket-Install'
if (Test-Path $installPath) { throw 'Installer test directory must start empty' }
$process = Start-Process -FilePath $installer[0].FullName -ArgumentList @('/S', "/D=$installPath") -Wait -PassThru
if ($process.ExitCode -ne 0) { throw "Installer failed with code $($process.ExitCode)" }
$executable = Join-Path $installPath 'twichui-market-companion.exe'
$env:MARKET_TEST_INSTALLED_EXE = $executable
$env:MARKET_TEST_APP_DATA = Join-Path $env:APPDATA 'team.twich.market'
if (-not (Test-Path $executable)) { throw 'Installed executable is missing' }
$probe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
$probe.Start()
$env:MARKET_TEST_CDP_PORT = $probe.LocalEndpoint.Port.ToString()
$probe.Stop()
$env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS = "--remote-debugging-port=$env:MARKET_TEST_CDP_PORT --remote-debugging-address=127.0.0.1"
$env:WEBVIEW2_USER_DATA_FOLDER = Join-Path $env:RUNNER_TEMP 'TwichMarket-WebView'
# Elevated GitHub runner processes ignore WEBVIEW2_* overrides. An exact-app
# machine policy is honored by WebView2; remove this test-only value in finally.
$policy = 'HKLM:\SOFTWARE\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments'
$policyName = 'twichui-market-companion.exe'
$null = New-Item -Path $policy -Force
if ($null -ne (Get-ItemProperty -Path $policy -Name $policyName -ErrorAction SilentlyContinue)) {
    throw 'Refusing to replace an existing WebView2 application policy'
}
$null = New-ItemProperty -Path $policy -Name $policyName -PropertyType String -Value $env:WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS
$app = $null
try {
    $cold=[System.Diagnostics.Stopwatch]::StartNew()
    $app = Start-Process -FilePath $executable -PassThru
    $env:MARKET_TEST_PRIMARY_PID = $app.Id.ToString()
    $ready = $false
    for ($attempt = 0; $attempt -lt 600; $attempt++) {
        Start-Sleep -Milliseconds 50
        $app.Refresh()
        if ($app.HasExited) { throw "Installed application exited early: $($app.ExitCode)" }
        if ($app.MainWindowHandle -ne 0 -and $app.MainWindowTitle -eq 'TwichUI Market Companion') {
            $ready = $true
            break
        }
    }
    if (-not $ready) { throw 'Installed application did not create its expected native window' }
    $cold.Stop()
    $evidence=Join-Path (Get-Location) 'artifacts/companion-v2'
    $null=New-Item -Path $evidence -ItemType Directory -Force
    @{fixture=$true;cold_start_to_native_window_ms=$cold.Elapsed.TotalMilliseconds;poll_resolution_ms=50;installer_bytes=$installer[0].Length} | ConvertTo-Json | Set-Content (Join-Path $evidence 'launch-metrics.json')
    Write-Output 'Installed release executable created the expected native window.'
    python scripts/verify-companion-authorization.py --ui
    if ($LASTEXITCODE -ne 0) { throw 'Native WebView2 workflow failed' }
} finally {
    Remove-ItemProperty -Path $policy -Name $policyName -ErrorAction SilentlyContinue
    if ($null -ne $app -and -not $app.HasExited) {
        $null = $app.CloseMainWindow()
        if (-not $app.WaitForExit(10000)) { $app.Kill(); $app.WaitForExit() }
    }
    # Acceptance deliberately restarts the installed executable. Cleanup only
    # this exact installation, including a failed hidden-startup assertion.
    Get-Process -Name 'twichui-market-companion' -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $executable } | ForEach-Object {
        $null = $_.CloseMainWindow()
        if (-not $_.WaitForExit(10000)) { $_.Kill(); $_.WaitForExit() }
    }
}
$retained=@{}
foreach ($file in @('market-v1.sqlite','settings.json')) {
    $path=Join-Path $env:MARKET_TEST_APP_DATA $file
    if (-not(Test-Path $path)) { throw 'Expected retained companion data before uninstall' }
    $retained[$path]=(Get-FileHash $path -Algorithm SHA256).Hash
}
$uninstaller = Join-Path $installPath 'uninstall.exe'
if (-not (Test-Path $uninstaller)) { throw 'Uninstaller is missing' }
$remove = Start-Process -FilePath $uninstaller -ArgumentList @('/S', "_?=$installPath") -Wait -PassThru
if ($remove.ExitCode -ne 0) { throw "Uninstaller failed: $($remove.ExitCode)" }
if (Test-Path $executable) { throw 'Uninstall left the application executable behind' }
$startup = [Microsoft.Win32.Registry]::GetValue('HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Run','TwichUI Market Companion',$null)
if ($startup -eq "`"$executable`" --background") { throw 'Uninstall left its current-user startup entry behind' }
foreach ($path in $retained.Keys) {
    if (-not(Test-Path $path) -or (Get-FileHash $path -Algorithm SHA256).Hash -ne $retained[$path]) { throw 'Uninstall changed saved settings or offline data' }
}
$receipt=Join-Path (Get-Location) 'artifacts/companion-v2/installed-smoke.json'
$accepted=Get-Content $receipt -Raw | ConvertFrom-Json
$accepted | Add-Member -NotePropertyName uninstall_settings_and_cache_preserved -NotePropertyValue $true -Force
$accepted | ConvertTo-Json -Depth 5 | Set-Content $receipt
if ($env:GITHUB_STEP_SUMMARY) {
    Add-Content $env:GITHUB_STEP_SUMMARY 'Native workflows, restart and uninstall retention are checked independently. Tray action acceptance remains UNVERIFIED unless explicitly recorded; see docs/companion-v2-windows-manual-acceptance.md. This is a candidate, not a signed stable release.'
}
Write-Output 'NSIS per-user install, native-window launch and uninstall retention verified. See separate tray acceptance status.'
