# Test-only native PE and shell interactions, restricted to disposable CI fixtures.
param([Parameter(Mandatory=$true)][ValidateSet('Setup','Register','RegisterSecond','ClearRegistry','StartGame','StopGame','ChooseFolder','CancelFolder')][string]$Action,[string]$GamePath)
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') { throw 'Disposable Windows CI only' }
$base=Join-Path $env:MARKET_TEST_APP_DATA 'workshop-summary-fixtures'
$keys=@('HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\TwichUI-Workshop-Automatic-Fixture-A','HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\TwichUI-Workshop-Automatic-Fixture-B')
if ($Action -eq 'Setup') {
    if(Test-Path $base){throw 'Summary fixture must start fresh'}
    $null=New-Item -ItemType Directory -Path $base
    $sid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
    & icacls $base /inheritance:r /grant:r "*$($sid):(OI)(CI)F" '*S-1-5-18:(OI)(CI)F' '*S-1-5-32-544:(OI)(CI)F' | Out-Null
    if($LASTEXITCODE -ne 0){throw 'Private fixture ACL failed'}
    $source=Join-Path $base 'SyntheticWow.cs'
    @'
using System;
using System.Reflection;
[assembly: AssemblyFileVersion("1.60.1.12345")]
[assembly: AssemblyVersion("1.60.1.12345")]
[assembly: AssemblyDescription("TwichUI synthetic CI executable; not World of Warcraft")]
class SyntheticWow { static void Main() { System.Threading.Thread.Sleep(30000); } }
'@ | Set-Content $source
    $compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
    $addon=Join-Path (Get-Location) 'coordinated-addon'
    if(-not(Test-Path (Join-Path $addon 'TwichUI_Workshop\Summary.lua'))){throw 'Pinned coordinated addon checkout required'}
    foreach($name in @('Forever-A','Forever-B')) {
        $game=Join-Path $base $name
        $addons=Join-Path $game 'Interface\AddOns'
        $null=New-Item -ItemType Directory -Path $addons -Force
        & $compiler /nologo /target:winexe "/out:$game\Wow.exe" $source
        if($LASTEXITCODE -ne 0){throw 'Synthetic versioned PE compilation failed'}
        foreach($folder in @('!!!TwichUI','TwichUI_Workshop')) { Copy-Item (Join-Path $addon $folder) $addons -Recurse }
        $saved=Join-Path $game 'WTF\Account\SyntheticOnly\SavedVariables'
        $null=New-Item -ItemType Directory -Path $saved -Force
        'SYNTHETIC_SAVED_VARIABLES_SENTINEL' | Set-Content (Join-Path $saved 'TwichUIWorkshop.lua')
    }
    @{base=$base;first=(Join-Path $base 'Forever-A');second=(Join-Path $base 'Forever-B');synthetic=$true;real_game=$false} | ConvertTo-Json -Compress
    exit
}
if($Action -in @('Register','RegisterSecond')) {
    $index=if($Action -eq 'Register'){0}else{1}
    $path=Join-Path $base $(if($index -eq 0){'Forever-A'}else{'Forever-B'})
    if(Test-Path $keys[$index]){throw 'Refusing existing test registry key'}
    $null=New-Item $keys[$index] -Force
    $null=New-ItemProperty $keys[$index] -Name DisplayName -Value 'Synthetic Forever CI fixture' -PropertyType String
    $null=New-ItemProperty $keys[$index] -Name InstallLocation -Value $path -PropertyType String
    $null=New-ItemProperty $keys[$index] -Name TwichUIFixtureOwned -Value $base -PropertyType String
    @{registered=$true}|ConvertTo-Json -Compress;exit
}
if($Action -eq 'ClearRegistry') {
    foreach($key in $keys){if((Get-ItemProperty -Path $key -Name TwichUIFixtureOwned -ErrorAction SilentlyContinue).TwichUIFixtureOwned -eq $base){Remove-Item $key -Recurse}}
    @{cleared=$true}|ConvertTo-Json -Compress;exit
}
if($Action -in @('StartGame','StopGame')) {
    $exe=Join-Path $base 'Forever-A\Wow.exe'
    if($Action -eq 'StartGame') {$p=Start-Process $exe -PassThru;@{pid=$p.Id;synthetic=$true}|ConvertTo-Json -Compress}
    else {Get-Process -Name Wow -ErrorAction SilentlyContinue|Where-Object{$_.Path -eq $exe}|Stop-Process;@{stopped=$true}|ConvertTo-Json -Compress}
    exit
}
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$condition=[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ClassNameProperty,'#32770')
$dialog=$null
for($i=0;$i -lt 200;$i++) {
    $all=[System.Windows.Automation.AutomationElement]::RootElement.FindAll([System.Windows.Automation.TreeScope]::Children,$condition)
    foreach($candidate in $all) {if($candidate.Current.ProcessId -eq [int]$env:MARKET_TEST_PRIMARY_PID){$dialog=$candidate;break}}
    if($dialog){break};Start-Sleep -Milliseconds 100
}
if(-not $dialog){throw 'Actual Companion folder dialog not found'}
# Classic shell controls do not always implement UIA Invoke/Value on the runner.
# Use actual, process-checked native controls, never a mocked picker/IPC result.
# BM_CLICK: https://learn.microsoft.com/windows/win32/controls/bm-click
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class SummaryPickerControls {
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr window);
 [DllImport("user32.dll")] public static extern IntPtr GetDlgItem(IntPtr window,int id);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr window,out uint pid);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern IntPtr SendMessageTimeoutW(IntPtr window,uint message,IntPtr w,IntPtr l,uint flags,uint milliseconds,out IntPtr result);
 [DllImport("user32.dll",CharSet=CharSet.Unicode,EntryPoint="SendMessageTimeoutW")] public static extern IntPtr SetText(IntPtr window,uint message,IntPtr w,string text,uint flags,uint milliseconds,out IntPtr result);
}
'@
$dialogWindow=[IntPtr]$dialog.Current.NativeWindowHandle
$null=[SummaryPickerControls]::SetForegroundWindow($dialogWindow)
function CheckedWindow($element) {
    $window=[IntPtr]$element.Current.NativeWindowHandle
    [uint32]$owner=0
    $null=[SummaryPickerControls]::GetWindowThreadProcessId($window,[ref]$owner)
    if($window -eq [IntPtr]::Zero -or $owner -ne [uint32]$env:MARKET_TEST_PRIMARY_PID){throw 'Native control process identity changed'}
    return $window
}
function ClickButton($element) {
    $pattern=$null
    if($element.TryGetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern,[ref]$pattern)){$pattern.Invoke();return}
    $window=CheckedWindow $element
    $result=[IntPtr]::Zero
    if([SummaryPickerControls]::SendMessageTimeoutW($window,0x00F5,[IntPtr]::Zero,[IntPtr]::Zero,2,3000,[ref]$result) -eq [IntPtr]::Zero){throw 'Actual native button click timed out'}
}
if($Action -eq 'CancelFolder') {
    $button=$dialog.FindFirst([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::AutomationIdProperty,'2'))
    if(-not $button){throw 'Native cancel button unavailable'}
    ClickButton $button
} else {
    $resolved=[IO.Path]::GetFullPath($GamePath)
    if(-not $resolved.StartsWith([IO.Path]::GetFullPath($base)+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Picker fixture path escaped'}
    $edit=$dialog.FindFirst([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::Edit))
    if(-not $edit){throw 'Actual native folder edit unavailable'}
    $pattern=$null
    if($edit.TryGetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern,[ref]$pattern)){$pattern.SetValue($resolved)}
    else {
        $window=CheckedWindow $edit;$result=[IntPtr]::Zero
        if([SummaryPickerControls]::SetText($window,0x000C,[IntPtr]::Zero,$resolved,2,3000,[ref]$result) -eq [IntPtr]::Zero){throw 'Actual native edit timed out'}
    }
    $button=$dialog.FindFirst([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::AutomationIdProperty,'1'))
    if(-not $button){throw 'Native folder confirmation unavailable'}
    ClickButton $button
}
@{native_dialog=$true;cancelled=($Action -eq 'CancelFolder')}|ConvertTo-Json -Compress
