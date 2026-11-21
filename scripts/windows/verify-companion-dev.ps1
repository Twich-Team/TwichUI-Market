# Minimal smoke, restricted to disposable Windows Actions machines.
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') { throw 'Disposable Windows CI only' }
$installers=@(Get-ChildItem 'desktop/src-tauri/target/release/bundle/nsis/*-setup.exe')
if($installers.Count -ne 1){throw 'Expected one real NSIS installer'}
$installPath=Join-Path $env:RUNNER_TEMP 'TwichMarket-DEV'
$p=Start-Process $installers[0].FullName -ArgumentList @('/S',"/D=$installPath") -Wait -PassThru
if($p.ExitCode -ne 0){throw 'DEV installer failed'}
$exe=Join-Path $installPath 'twichui-market-companion-dev.exe'
if(!(Test-Path $exe)){throw 'Distinct installed DEV executable missing'}
$production=Join-Path $env:APPDATA 'team.twich.market'
$null=New-Item $production -ItemType Directory -Force
$sentinel=Join-Path $production 'dev-smoke-preservation.txt'
'Production state preservation fixture' | Set-Content $sentinel
$before=(Get-FileHash $sentinel).Hash
$probe=[System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback,0)
$probe.Start();$env:DEV_CDP_PORT=$probe.LocalEndpoint.Port.ToString();$probe.Stop()
$policy='HKLM:\SOFTWARE\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments'
$name='twichui-market-companion-dev.exe'
$null=New-Item $policy -Force
if($null -ne (Get-ItemProperty $policy -Name $name -ErrorAction SilentlyContinue)){throw 'Existing WebView policy refused'}
$null=New-ItemProperty $policy -Name $name -PropertyType String -Value "--remote-debugging-port=$env:DEV_CDP_PORT --remote-debugging-address=127.0.0.1"
$app=$null
try {
  $app=Start-Process $exe -PassThru
  $ready=$false
  for($i=0;$i -lt 150;$i++){
    Start-Sleep -Milliseconds 200;$app.Refresh()
    if($app.HasExited){throw 'Installed DEV exited early'}
    if($app.MainWindowHandle -ne 0 -and $app.MainWindowTitle.Contains('Companion DEV')){$ready=$true;break}
  }
  if(!$ready){throw 'DEV native window did not start'}
  node scripts/verify-companion-dev.cjs
  if($LASTEXITCODE -ne 0){throw 'Installed native/frontend smoke failed'}
} finally {
  Remove-ItemProperty $policy -Name $name -ErrorAction SilentlyContinue
  if($null -ne $app -and !$app.HasExited){$app.Kill();$app.WaitForExit()}
}
$uninstaller=Join-Path $installPath 'uninstall.exe'
$p=Start-Process $uninstaller -ArgumentList @('/S',"_?=$installPath") -Wait -PassThru
if($p.ExitCode -ne 0 -or (Test-Path $exe)){throw 'DEV uninstall failed'}
if((Get-FileHash $sentinel).Hash -ne $before){throw 'DEV changed production storage'}
Write-Output 'Minimal installed Windows DEV smoke passed; production storage sentinel preserved.'
