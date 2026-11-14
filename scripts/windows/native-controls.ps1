# Actual OS interactions, restricted to this installed app on a disposable runner.
param([ValidateSet('Capture','Open','Settings','Sync','Pause','Quit','Minimize','Close')][string]$Action)
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') { throw 'Disposable Windows CI only' }
$apps = @(Get-Process -Name 'twichui-market-companion' -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $env:MARKET_TEST_INSTALLED_EXE })
if ($apps.Count -ne 1) { throw 'Expected one exact installed companion process' }
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes,System.Drawing,System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class CompanionNativeInput {
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
$icon=$elements | Where-Object { $_.Current.Name -like 'TwichUI Market Companion*' -and -not $_.Current.IsOffscreen } | Select-Object -First 1
if ($null -eq $icon) {
    $chevron=$elements | Where-Object { $_.Current.Name -match 'Show hidden icons|Notification Chevron' -and -not $_.Current.IsOffscreen } | Select-Object -First 1
    if ($null -eq $chevron) { throw 'Companion icon and notification overflow control unavailable' }
    Click-Element $chevron
    Start-Sleep -Milliseconds 300
    $icon=@(Tray-Elements) | Where-Object { $_.Current.Name -like 'TwichUI Market Companion*' -and -not $_.Current.IsOffscreen } | Select-Object -First 1
}
if ($null -eq $icon) { throw 'Actual companion tray icon unavailable' }
Click-Element $icon $true
$condition=[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::MenuItem)
$items=@()
for ($attempt=0;$attempt -lt 20;$attempt++) {
    $items=@(foreach ($menu in $root.FindAll([System.Windows.Automation.TreeScope]::Children,$trueCondition)) {
        if ($menu.Current.ProcessId -eq $apps[0].Id -and ($menu.Current.ClassName -eq '#32768' -or $menu.Current.ControlType -eq [System.Windows.Automation.ControlType]::Menu)) {
            foreach ($item in $menu.FindAll($scope,$condition)) { $item }
        }
    })
    if (@($items | Where-Object { $_.Current.Name -eq 'Open companion' }).Count -eq 1) { break }
    Start-Sleep -Milliseconds 100
}
$names=@($items | ForEach-Object { $_.Current.Name })
foreach ($expected in @('Open companion','Sync now','Settings…','Quit')) {
    if ($names -notcontains $expected) { throw "Actual tray menu missing $expected" }
}
if ($Action -eq 'Capture') {
    $screen=[System.Windows.Forms.SystemInformation]::VirtualScreen
    $bitmap=[System.Drawing.Bitmap]::new($screen.Width,$screen.Height)
    $graphics=[System.Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CopyFromScreen($screen.Location,[System.Drawing.Point]::Empty,$screen.Size)
        $file=Join-Path (Get-Location) 'artifacts/companion-v2/native-tray.png'
        $bitmap.Save($file,[System.Drawing.Imaging.ImageFormat]::Png)
    } finally { $graphics.Dispose();$bitmap.Dispose() }
    # Dismiss only this popup through Escape after capturing the actual Windows menu.
    [System.Windows.Forms.SendKeys]::SendWait('{ESC}')
} else {
    $match=switch ($Action) { 'Open' {'^Open companion$'} 'Settings' {'^Settings'} 'Sync' {'^Sync now$'} 'Pause' {'^(Pause|Resume) automatic sync$'} 'Quit' {'^Quit$'} }
    $item=$items | Where-Object { $_.Current.Name -match $match } | Select-Object -First 1
    if ($null -eq $item -or -not $item.Current.IsEnabled) { throw 'Requested native tray action unavailable' }
    Click-Element $item
}
@{ action=$Action; actual_tray=$true; items=$names } | ConvertTo-Json -Compress
