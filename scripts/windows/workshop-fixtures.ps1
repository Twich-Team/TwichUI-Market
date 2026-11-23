# Test-only native PE and shell interactions, restricted to disposable CI fixtures.
param([Parameter(Mandatory=$true)][ValidateSet('Setup','Register','RegisterSecond','ClearRegistry','StartGame','StopGame','GameRunning','ChooseFolder','CancelFolder')][string]$Action,[string]$GamePath,[string]$AddonRoot)
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
[assembly: AssemblyFileVersion("160.1.7095.9")]
[assembly: AssemblyInformationalVersion("Version 1.60.1.70959")]
[assembly: AssemblyProduct("World of Warcraft")]
[assembly: AssemblyVersion("1.60.1.0")]
[assembly: AssemblyDescription("TwichUI synthetic CI executable; not World of Warcraft")]
class SyntheticWow { static void Main() { System.Threading.Thread.Sleep(180000); } }
'@ | Set-Content $source
    $compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
    $addon=if($AddonRoot){(Resolve-Path $AddonRoot).Path}else{Join-Path (Get-Location) 'coordinated-addon'}
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
if($Action -in @('StartGame','StopGame','GameRunning')) {
    $exe=Join-Path $base 'Forever-A\Wow.exe'
    if($Action -eq 'StartGame') {$p=Start-Process $exe -PassThru;@{pid=$p.Id;synthetic=$true}|ConvertTo-Json -Compress}
    elseif($Action -eq 'GameRunning') {@{running=@(Get-Process -Name Wow -ErrorAction SilentlyContinue|Where-Object{$_.Path -eq $exe}).Count -gt 0;synthetic=$true}|ConvertTo-Json -Compress}
    else {Get-Process -Name Wow -ErrorAction SilentlyContinue|Where-Object{$_.Path -eq $exe}|Stop-Process;@{stopped=$true}|ConvertTo-Json -Compress}
    exit
}
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms
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
using System.Text;
using System.Collections.Generic;
public static class SummaryPickerControls {
 public delegate bool EnumChild(IntPtr window,IntPtr data);
 [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr window,EnumChild callback,IntPtr data);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetClassNameW(IntPtr window,StringBuilder name,int size);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr window);
 public static IntPtr FindEdit(IntPtr parent) {
  IntPtr found=IntPtr.Zero;int count=0;
  EnumChildWindows(parent,delegate(IntPtr w,IntPtr data) {
   if(++count>512)return false;
   var name=new StringBuilder(256);GetClassNameW(w,name,256);
   if(IsWindowVisible(w)&&name.ToString().Equals("Edit",StringComparison.OrdinalIgnoreCase)){found=w;return false;}
   return true;
  },IntPtr.Zero);return found;
 }
 public static string Classes(IntPtr parent) {
  var items=new List<string>();
  EnumChildWindows(parent,delegate(IntPtr w,IntPtr data) {
   if(items.Count>=128)return false;
   var name=new StringBuilder(256);GetClassNameW(w,name,256);items.Add(name.ToString());return true;
  },IntPtr.Zero);return String.Join(",",items.ToArray());
 }
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr window);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern IntPtr GetDlgItem(IntPtr window,int id);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr window,out uint pid);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern IntPtr SendMessageTimeoutW(IntPtr window,uint message,IntPtr w,IntPtr l,uint flags,uint milliseconds,out IntPtr result);
 [DllImport("user32.dll",CharSet=CharSet.Unicode,EntryPoint="SendMessageTimeoutW")] public static extern IntPtr SetText(IntPtr window,uint message,IntPtr w,string text,uint flags,uint milliseconds,out IntPtr result);
}
'@
$dialogWindow=[IntPtr]$dialog.Current.NativeWindowHandle
$null=[SummaryPickerControls]::SetForegroundWindow($dialogWindow)
function CheckedWindow($element) {
    if($element -is [IntPtr]){$window=$element}else{$window=[IntPtr]$element.Current.NativeWindowHandle}
    [uint32]$owner=0
    $null=[SummaryPickerControls]::GetWindowThreadProcessId($window,[ref]$owner)
    if($window -eq [IntPtr]::Zero -or $owner -ne [uint32]$env:MARKET_TEST_PRIMARY_PID){throw 'Native control process identity changed'}
    return $window
}
function ClickButton($element) {
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
    $edit=[SummaryPickerControls]::FindEdit((CheckedWindow $dialogWindow))
    if($edit -eq [IntPtr]::Zero){throw ('Actual native folder edit unavailable; classes: '+[SummaryPickerControls]::Classes($dialogWindow))}
    $window=CheckedWindow $edit;$result=[IntPtr]::Zero
    # Focus via scalar WM_NEXTDLGCTL and type through the real keyboard so the
    # shell observes edit notifications. A local WM_USER string pointer is not
    # marshaled across processes, and WM_SETTEXT alone can leave a stale PIDL.
    if([SummaryPickerControls]::SendMessageTimeoutW((CheckedWindow $dialogWindow),0x0028,$window,[IntPtr]1,2,3000,[ref]$result) -eq [IntPtr]::Zero){throw 'Actual native edit focus timed out'}
    if([SummaryPickerControls]::GetForegroundWindow() -ne $dialogWindow){throw 'Refusing keyboard input outside the checked folder dialog'}
    $keys=[Text.StringBuilder]::new()
    foreach($character in $resolved.ToCharArray()) {
        if('+^%~()[]{}'.Contains([string]$character)){$null=$keys.Append('{').Append($character).Append('}')}
        else{$null=$keys.Append($character)}
    }
    # Classic Edit controls need not implement Ctrl+A. EM_SETSEL selects the
    # complete old path using scalar offsets, including on repeated dialogs.
    if([SummaryPickerControls]::SendMessageTimeoutW($window,0x00B1,[IntPtr]::Zero,[IntPtr](-1),2,3000,[ref]$result) -eq [IntPtr]::Zero){throw 'Actual native edit selection timed out'}
    [System.Windows.Forms.SendKeys]::SendWait($keys.ToString())
    [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
}
@{native_dialog=$true;cancelled=($Action -eq 'CancelFolder')}|ConvertTo-Json -Compress
