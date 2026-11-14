# Runs only on the disposable Windows CI runner; no server or addon files involved.
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
    $app = Start-Process -FilePath $executable -PassThru
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Seconds 1
        $app.Refresh()
        if ($app.HasExited) { throw "Installed application exited early: $($app.ExitCode)" }
        if ($app.MainWindowHandle -ne 0 -and $app.MainWindowTitle -eq 'TwichUI Market Companion') {
            $ready = $true
            break
        }
    }
    if (-not $ready) { throw 'Installed application did not create its expected native window' }
    Write-Output 'Installed release executable created the expected native window.'
    python scripts/verify-companion-http.py --ui
    if ($LASTEXITCODE -ne 0) { throw 'Native WebView2 workflow failed' }
} finally {
    Remove-ItemProperty -Path $policy -Name $policyName -ErrorAction SilentlyContinue
    if ($null -ne $app -and -not $app.HasExited) {
        $null = $app.CloseMainWindow()
        if (-not $app.WaitForExit(10000)) { $app.Kill(); $app.WaitForExit() }
    }
}
$uninstaller = Join-Path $installPath 'uninstall.exe'
if (-not (Test-Path $uninstaller)) { throw 'Uninstaller is missing' }
$remove = Start-Process -FilePath $uninstaller -ArgumentList @('/S', "_?=$installPath") -Wait -PassThru
if ($remove.ExitCode -ne 0) { throw "Uninstaller failed: $($remove.ExitCode)" }
if (Test-Path $executable) { throw 'Uninstall left the application executable behind' }
Write-Output 'NSIS per-user install, native-window launch and uninstall verified.'
