# Failed signed-upgrade diagnostics on the disposable runner only. No secrets,
# private signing key, live accounts or host security changes are involved.
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') { throw 'Disposable Windows runner only' }
$directory=Join-Path (Get-Location) 'artifacts/companion-signed-update-test'
$null=New-Item -ItemType Directory -Path $directory -Force
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
$bounds=[Windows.Forms.SystemInformation]::VirtualScreen
$image=New-Object Drawing.Bitmap $bounds.Width,$bounds.Height
$graphics=[Drawing.Graphics]::FromImage($image)
try {
    $graphics.CopyFromScreen($bounds.Location,[Drawing.Point]::Empty,$bounds.Size)
    $image.Save((Join-Path $directory 'sdk-installer-desktop.png'),[Drawing.Imaging.ImageFormat]::Png)
} finally { $graphics.Dispose();$image.Dispose() }
$report=@{}
try { $report.windows=@(Get-Process | Where-Object {$_.Name -like '*installer*' -or $_.Name -eq 'twichui-market-companion'} | Select-Object Id,Name,Path,MainWindowTitle) } catch { $report.process_scan_error=$_.Exception.GetType().Name }
try { $report.installer_processes=@(Get-CimInstance Win32_Process | Where-Object {$_.Name -like '*-installer.exe'} | Select-Object Name,ExecutablePath,CommandLine) } catch { $report.cim_error=$_.Exception.GetType().Name }
try {
    $installed=Get-Item $env:MARKET_TEST_INSTALLED_EXE
    $report.installed_version=$installed.VersionInfo.ProductVersion
    $report.installed_sha256=(Get-FileHash $env:MARKET_TEST_INSTALLED_EXE -Algorithm SHA256).Hash.ToLowerInvariant()
} catch { $report.installed_scan_error=$_.Exception.GetType().Name }
$report | ConvertTo-Json -Depth 4 | Set-Content (Join-Path $directory 'sdk-installer-diagnostics.json')
