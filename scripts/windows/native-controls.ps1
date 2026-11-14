# Actual OS interactions, restricted to this installed app on a disposable runner.
param([ValidateSet('Capture','Open','Settings','Sync','Pause','Quit','Minimize','Close','Metrics')][string]$Action)
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') { throw 'Disposable Windows CI only' }
$apps = @(Get-Process -Name 'twichui-market-companion' -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $env:MARKET_TEST_INSTALLED_EXE })
if ($apps.Count -ne 1) { throw 'Expected one exact installed companion process' }
if ($Action -eq 'Metrics') {
    function Owned-Processes {
        $all=@(Get-CimInstance Win32_Process)
        $ids=[System.Collections.Generic.HashSet[int]]::new()
        $null=$ids.Add($apps[0].Id)
        do {
            $added=$false
            foreach ($row in $all) {
                if ($ids.Contains([int]$row.ParentProcessId) -and $ids.Add([int]$row.ProcessId)) { $added=$true }
            }
        } while ($added)
        # The system browser is a separate user application. Include only this
        # app and its WebView2 children, never unrelated Edge/browser processes.
        foreach ($row in $all) {
            if ($ids.Contains([int]$row.ProcessId) -and ($row.ProcessId -eq $apps[0].Id -or $row.Name -eq 'msedgewebview2.exe')) {
                Get-Process -Id $row.ProcessId -ErrorAction SilentlyContinue
            }
        }
    }
    $before=@(Owned-Processes)
    # TimeSpan aggregation is explicit; process CPU is reported as a percent of
    # one logical core, and separately normalized across all host logical cores.
    $cpuBefore=($before | ForEach-Object { $_.TotalProcessorTime.TotalMilliseconds } | Measure-Object -Sum).Sum
    $clock=[System.Diagnostics.Stopwatch]::StartNew()
    Start-Sleep -Seconds 10
    $after=@(Owned-Processes)
    $elapsed=$clock.Elapsed.TotalMilliseconds
    $cpuAfter=($after | ForEach-Object { $_.TotalProcessorTime.TotalMilliseconds } | Measure-Object -Sum).Sum
    $cpu=[math]::Max(0,100*($cpuAfter-$cpuBefore)/$elapsed)
    $connections=@(Get-NetTCPConnection -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -in $after.Id -and $_.State -eq 'Established' })
    @{
        scope='installed native process and owned WebView2 children; browser and test driver excluded'
        sample_ms=[math]::Round($elapsed,2);processes=$after.Count
        working_set_sum_bytes=($after | Measure-Object WorkingSet64 -Sum).Sum
        private_bytes_sum=($after | Measure-Object PrivateMemorySize64 -Sum).Sum
        cpu_one_core_percent=[math]::Round($cpu,4)
        cpu_host_percent=[math]::Round($cpu/[Environment]::ProcessorCount,4)
        established_tcp_connections=$connections.Count
    } | ConvertTo-Json -Compress
    exit
}
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,System.Drawing,System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class CompanionNativeInput {
  [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extra);
  [DllImport("user32.dll")] public static extern bool ShowWindowAsync(IntPtr window, int command);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr window, uint message, IntPtr wParam, IntPtr lParam);
}
'@
if ($Action -in @('Minimize','Close')) {
    $window = $apps[0].MainWindowHandle
    if ($window -eq 0) { throw 'Expected the installed app visible before native window action' }
    if ($Action -eq 'Minimize') { $null = [CompanionNativeInput]::ShowWindowAsync($window,6) }
    else { $null = [CompanionNativeInput]::PostMessage($window,0x0010,[IntPtr]::Zero,[IntPtr]::Zero) }
    @{ action=$Action; exact_installed_process=$true } | ConvertTo-Json -Compress
    exit
}
$null=[CompanionNativeInput]::SetProcessDPIAware()
$root = [System.Windows.Automation.AutomationElement]::RootElement
$scope = [System.Windows.Automation.TreeScope]::Descendants
$trueCondition = [System.Windows.Automation.Condition]::TrueCondition
function Click-Element($element, [bool]$right=$false) {
    $rect = $element.Current.BoundingRectangle
    if ($rect.IsEmpty -or $rect.Width -le 0 -or $rect.Height -le 0) { throw 'Native element is not onscreen' }
    $null = [CompanionNativeInput]::SetCursorPos([int]($rect.X+$rect.Width/2),[int]($rect.Y+$rect.Height/2))
    Start-Sleep -Milliseconds 80
    [CompanionNativeInput]::mouse_event($(if ($right) {8} else {2}),0,0,0,[UIntPtr]::Zero)
    [CompanionNativeInput]::mouse_event($(if ($right) {16} else {4}),0,0,0,[UIntPtr]::Zero)
    Start-Sleep -Milliseconds 200
}
function Tray-Elements {
    $windows=$root.FindAll([System.Windows.Automation.TreeScope]::Children,$trueCondition)
    foreach ($window in $windows) {
        if ($window.Current.ClassName -in @('Shell_TrayWnd','NotifyIconOverflowWindow','TopLevelWindowForOverflowXamlIsland')) {
            foreach ($element in $window.FindAll($scope,$trueCondition)) { $element }
        }
    }
}
$elements=@(Tray-Elements)
$icon=$elements | Where-Object { $_.Current.Name.StartsWith('TwichUI Market Companion ') -and -not $_.Current.IsOffscreen } | Select-Object -First 1
if ($null -eq $icon) {
    $chevron=$elements | Where-Object { $_.Current.Name -match 'Show hidden icons|Notification Chevron' -and -not $_.Current.IsOffscreen } | Select-Object -First 1
    if ($null -eq $chevron) { throw 'Companion icon and notification overflow control unavailable' }
    Click-Element $chevron
    Start-Sleep -Milliseconds 300
    $icon=@(Tray-Elements) | Where-Object { $_.Current.Name.StartsWith('TwichUI Market Companion ') -and -not $_.Current.IsOffscreen } | Select-Object -First 1
}
if ($null -eq $icon) { throw 'Actual companion tray icon unavailable' }
Click-Element $icon $true
$condition=[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::MenuItem)
$items=@()
for ($attempt=0;$attempt -lt 20;$attempt++) {
    $items=@(foreach ($menu in $root.FindAll([System.Windows.Automation.TreeScope]::Children,$trueCondition)) {
        if ($menu.Current.ClassName -eq '#32768' -or $menu.Current.ControlType -eq [System.Windows.Automation.ControlType]::Menu) {
            foreach ($item in $menu.FindAll($scope,$condition)) { $item }
        }
    })
    if (@($items | Where-Object { $_.Current.Name -eq 'Open companion' }).Count -eq 1) { break }
    Start-Sleep -Milliseconds 100
}
$names=@($items | ForEach-Object { $_.Current.Name })
    $screen=[System.Windows.Forms.SystemInformation]::VirtualScreen
    $bitmap=[System.Drawing.Bitmap]::new($screen.Width,$screen.Height)
    $graphics=[System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CopyFromScreen($screen.Location,[System.Drawing.Point]::Empty,$screen.Size)
        $file=Join-Path (Get-Location) 'artifacts/companion-v2/native-tray-attempt.png'
        $bitmap.Save($file,[System.Drawing.Imaging.ImageFormat]::Png)
    } finally { $graphics.Dispose();$bitmap.Dispose() }
$windows=@(foreach ($window in $root.FindAll([System.Windows.Automation.TreeScope]::Children,$trueCondition)) {
    @{name=$window.Current.Name;class=$window.Current.ClassName;process=$window.Current.ProcessId;type=$window.Current.ControlType.ProgrammaticName}
})
@{menus=$names;windows=$windows} | ConvertTo-Json -Depth 4 | Set-Content 'artifacts/companion-v2/tray-discovery.json'
foreach ($expected in @('Open companion','Sync now','Quit')) {
    if ($names -notcontains $expected) { throw "Actual tray menu missing $expected" }
}
if (@($names | Where-Object { $_ -like 'Settings*' }).Count -ne 1) { throw 'Actual tray menu missing Settings' }
if ($Action -eq 'Capture') {
    Copy-Item 'artifacts/companion-v2/native-tray-attempt.png' 'artifacts/companion-v2/native-tray.png'
    # Dismiss only this popup through Escape after capturing the actual Windows menu.
    [System.Windows.Forms.SendKeys]::SendWait('{ESC}')
} else {
    $match=switch ($Action) { 'Open' {'^Open companion$'} 'Settings' {'^Settings'} 'Sync' {'^Sync now$'} 'Pause' {'^(Pause|Resume) automatic sync$'} 'Quit' {'^Quit$'} }
    $item=$items | Where-Object { $_.Current.Name -match $match } | Select-Object -First 1
    if ($null -eq $item -or -not $item.Current.IsEnabled) { throw 'Requested native tray action unavailable' }
    Click-Element $item
}
@{ action=$Action; actual_tray=$true; items=$names } | ConvertTo-Json -Compress
