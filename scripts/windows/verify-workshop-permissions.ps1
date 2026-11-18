# Real NTFS/token checks, with a synthetic versioned PE and pinned addon source.
# A limited-token child is mandatory; elevated runner success is insufficient.
param([switch]$Worker,[string]$Plan)
$ErrorActionPreference='Stop'
if($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows'){throw 'Disposable Windows CI only'}
if($Worker){
    try {
        $planData=Get-Content $Plan -Raw|ConvertFrom-Json
        $results=@()
        foreach($case in $planData.cases){
            $before=@{}
            Get-ChildItem $case.path -File -Recurse|ForEach-Object{
                if($_.FullName -eq $case.unreadable){$before[$_.FullName]=@{length=$_.Length;modified=$_.LastWriteTimeUtc.Ticks}}
                else{$before[$_.FullName]=(Get-FileHash $_.FullName -Algorithm SHA256).Hash}
            }
            $native=(& $planData.exe inspect $case.path)|ConvertFrom-Json
            if($LASTEXITCODE -ne 0 -or $native.elevated){throw "Non-elevated native execution required: $($case.name) $($native|ConvertTo-Json -Compress -Depth 8)"}
            if($native.accepted -ne $case.accepted){throw "Unexpected acceptance: $($case.name) $($native|ConvertTo-Json -Compress -Depth 8)"}
            if(-not $case.accepted -and $native.failure.code -ne $case.code){throw "Wrong failure code: $($case.name) $($native|ConvertTo-Json -Compress -Depth 8)"}
            foreach($file in $before.Keys){
                if($file -eq $case.unreadable){
                    $info=Get-Item $file
                    if($info.Length -ne $before[$file].length -or $info.LastWriteTimeUtc.Ticks -ne $before[$file].modified){throw 'Read-only preflight changed inaccessible file metadata'}
                } elseif((Get-FileHash $file -Algorithm SHA256).Hash -ne $before[$file]){throw 'Read-only preflight changed prior data'}
            }
            $after=@(Get-ChildItem $case.path -File -Recurse)
            if($after.Count -ne $before.Count){throw 'Read-only preflight changed the file inventory'}
            $results+=@{name=$case.name;native=$native;prior_files_unchanged=$true}
        }
        @{synthetic_executable=$true;genuine_forever_binary=$false;non_elevated=$true;results=$results}|ConvertTo-Json -Depth 12|Set-Content $planData.report
    } catch {
        $_.ToString()|Set-Content ($Plan+'.error')
        exit 1
    }
    exit
}
$taskName='TwichUI-Workshop-NTFS-'+$env:GITHUB_RUN_ID+'-'+$env:GITHUB_RUN_ATTEMPT
# Inherit the real user's LocalAppData permissions. No private fixture ACL reset.
$base=Join-Path $env:LOCALAPPDATA $taskName
if(Test-Path $base){throw 'NTFS fixture must begin empty'}
$null=New-Item $base -ItemType Directory
$addon=Join-Path (Get-Location) 'coordinated-addon'
$compiler=Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
function MakeGame($name,$version='1.60.1.12345'){
    $game=Join-Path $base $name
    $addons=Join-Path $game 'Interface\AddOns'
    $null=New-Item $addons -ItemType Directory -Force
    $source=Join-Path $base ($name+'.cs')
    "using System.Reflection; [assembly: AssemblyFileVersion(`"$version`")] class Fixture { static void Main() {} }"|Set-Content $source
    & $compiler /nologo /target:winexe "/out:$game\Wow.exe" $source
    if($LASTEXITCODE -ne 0){throw 'Synthetic PE compilation failed'}
    foreach($folder in @('!!!TwichUI','TwichUI_Workshop')){Copy-Item (Join-Path $addon $folder) $addons -Recurse}
    return $game
}
$cases=@()
$normal=MakeGame 'normal-inheritance'
$cases+=@{name='normal inherited permissions';path=$normal;accepted=$true}
$admin=MakeGame 'administrator-installed'
# Installation inputs and parent may have a trusted administrator owner. The
# limited player still inherits its own write grant for new addon data.
& icacls $admin /setowner '*S-1-5-32-544' /T /Q|Out-Null
if($LASTEXITCODE -ne 0){throw 'Administrator owner fixture failed'}
$cases+=@{name='administrator owned installed files';path=$admin;accepted=$true}
$missing=MakeGame 'missing-workshop'
Remove-Item (Join-Path $missing 'Interface\AddOns\TwichUI_Workshop\Summary.lua')
$cases+=@{name='missing Workshop file';path=$missing;accepted=$false;code='workshop_addon'}
$denied=MakeGame 'unreadable-addon'
$unreadable=Join-Path $denied 'Interface\AddOns\TwichUI_Workshop\Summary.lua'
$userSid=[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
& icacls $unreadable /deny "*$($userSid):R" /Q|Out-Null
if($LASTEXITCODE -ne 0){throw 'Unreadable addon fixture failed'}
$cases+=@{name='Windows refuses installed addon read';path=$denied;unreadable=$unreadable;accepted=$false;code='access_denied'}
$wrong=MakeGame 'wrong-folder'
Remove-Item (Join-Path $wrong 'Wow.exe')
$cases+=@{name='wrong game folder';path=$wrong;accepted=$false;code='wrong_folder'}
$unsupported=MakeGame 'unsupported-version' '1.12.1.5875'
$cases+=@{name='unsupported native version resource';path=$unsupported;accepted=$false;code='unsupported_client'}
$conflict=MakeGame 'unowned-market-data'
$data=Join-Path $conflict 'Interface\AddOns\TwichUI_MarketData'
$null=New-Item $data -ItemType Directory
'existing unrelated player file'|Set-Content (Join-Path $data 'unrelated.lua')
$cases+=@{name='unowned existing Market data';path=$conflict;accepted=$false;code='ownership_conflict'}
$broad=MakeGame 'unsafe-output-permissions'
& icacls (Join-Path $broad 'Interface\AddOns') /grant '*S-1-1-0:(OI)(CI)M' /Q|Out-Null
if($LASTEXITCODE -ne 0){throw 'Unsafe ACL fixture failed'}
$cases+=@{name='unrelated principals may modify output';path=$broad;accepted=$false;code='access_denied'}
$inherited=MakeGame 'unsafe-inheritable-output'
& icacls (Join-Path $inherited 'Interface\AddOns') /grant '*S-1-1-0:(OI)(CI)(IO)M' /Q|Out-Null
if($LASTEXITCODE -ne 0){throw 'Unsafe inheritable ACL fixture failed'}
$cases+=@{name='unrelated principals may modify future output';path=$inherited;accepted=$false;code='access_denied'}
$junction=MakeGame 'junction-parent'
$addons=Join-Path $junction 'Interface\AddOns'
$target=Join-Path $junction 'OriginalAddOns'
Move-Item $addons $target
$null=New-Item $addons -ItemType Junction -Value $target
$cases+=@{name='junction in installed path';path=$junction;accepted=$false;code='unsafe_path'}
$report=Join-Path (Get-Location) 'artifacts\companion-v2\workshop-permissions.json'
$null=New-Item (Split-Path $report) -ItemType Directory -Force
& icacls (Split-Path $report) /grant "*$($userSid):(OI)(CI)M" /Q|Out-Null
if($LASTEXITCODE -ne 0){throw 'Limited worker report grant failed'}
$planFile=Join-Path $base 'plan.json'
@{exe=(Join-Path (Get-Location) 'desktop\target\debug\examples\installation_smoke.exe');report=$report;cases=$cases}|ConvertTo-Json -Depth 8|Set-Content $planFile
$script=(Resolve-Path $PSCommandPath).Path
# The restricted process receives only disposable markers and OS/profile paths.
$launcher=Join-Path $base 'limited-worker.ps1'
@("`$env:GITHUB_ACTIONS='true'", "`$env:RUNNER_OS='Windows'", ("& '"+$script.Replace("'","''")+"' -Worker -Plan '"+$planFile.Replace("'","''")+"'"))|Set-Content $launcher
$arguments='-NoProfile -File "'+$launcher+'"'
# This runner's Limited scheduled task still produced an elevated native token. Use Windows SAFER's NormalUser restriction instead
# of changing UAC, users, registry or host policies. The child proves its token.
Add-Type @'
using System;
using System.Text;
using System.Runtime.InteropServices;
using System.ComponentModel;
public static class WorkshopLimitedProcess {
 [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
 struct Startup { public int cb; public string reserved, desktop, title; public int x,y,cx,cy,charsX,charsY,fill,flags; public short show,reservedBytes; public IntPtr reservedData,input,output,error; }
 [StructLayout(LayoutKind.Sequential)] struct ProcessInfo { public IntPtr process,thread; public int pid,tid; }
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool OpenProcessToken(IntPtr process,uint access,out IntPtr token);
 [DllImport("kernel32.dll")] static extern IntPtr GetCurrentProcess();
 [DllImport("kernel32.dll")] static extern bool CloseHandle(IntPtr handle);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool SaferCreateLevel(uint scope,uint level,uint flags,out IntPtr handle,IntPtr reserved);
 [DllImport("advapi32.dll",SetLastError=true)] static extern bool SaferComputeTokenFromLevel(IntPtr level,IntPtr token,out IntPtr result,uint flags,IntPtr reserved);
 [DllImport("advapi32.dll")] static extern bool SaferCloseLevel(IntPtr level);
 [DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool CreateProcessAsUserW(IntPtr token,string app,StringBuilder command,IntPtr processAttributes,IntPtr threadAttributes,bool inherit,uint flags,IntPtr environment,string directory,ref Startup startup,out ProcessInfo info);
 public static int Start(string app,string args,string directory,string environment) {
  IntPtr token=IntPtr.Zero,level=IntPtr.Zero,restricted=IntPtr.Zero,env=IntPtr.Zero;
  try {
   if(!OpenProcessToken(GetCurrentProcess(),0x0002|0x0008,out token))throw new Win32Exception();
   if(!SaferCreateLevel(1,0x20000,1,out level,IntPtr.Zero))throw new Win32Exception();
   if(!SaferComputeTokenFromLevel(level,token,out restricted,0,IntPtr.Zero))throw new Win32Exception();
   env=Marshal.StringToHGlobalUni(environment);
   Startup startup=new Startup();startup.cb=Marshal.SizeOf(typeof(Startup));ProcessInfo info;
   if(!CreateProcessAsUserW(restricted,app,new StringBuilder("\""+app+"\" "+args),IntPtr.Zero,IntPtr.Zero,false,0x400,env,directory,ref startup,out info))throw new Win32Exception();
   CloseHandle(info.process);CloseHandle(info.thread);return info.pid;
  } finally {
   if(env!=IntPtr.Zero)Marshal.FreeHGlobal(env);
   if(restricted!=IntPtr.Zero)CloseHandle(restricted);
   if(level!=IntPtr.Zero)SaferCloseLevel(level);
   if(token!=IntPtr.Zero)CloseHandle(token);
  }
 }
}
'@
$workerProcess=$null
try {
    # Pass only OS/profile paths and disposable markers, with no credentials.
    $environment=@('GITHUB_ACTIONS=true','RUNNER_OS=Windows',('SystemRoot='+$env:SystemRoot),('WINDIR='+$env:WINDIR),('USERPROFILE='+$env:USERPROFILE),('LOCALAPPDATA='+$env:LOCALAPPDATA),('TEMP='+$env:TEMP),('TMP='+$env:TMP),('PATH='+$env:WINDIR+'\System32;'+$env:WINDIR)) -join "`0"
    $environment+="`0`0"
    $workerId=[WorkshopLimitedProcess]::Start((Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'),$arguments,(Get-Location).Path,$environment)
    $workerProcess=Get-Process -Id $workerId
    if(-not $workerProcess.WaitForExit(90000)){throw 'Limited-token Windows acceptance did not complete'}
    if(Test-Path ($planFile+'.error')){throw (Get-Content ($planFile+'.error') -Raw)}
    if(-not(Test-Path $report)){throw 'Limited-token worker did not produce acceptance'}
    Get-Content $report -Raw|Write-Output
} finally {
    if($workerProcess -and -not $workerProcess.HasExited){$workerProcess.Kill();$workerProcess.WaitForExit()}
    # Retain fixture files on the disposable runner for failure inspection.
}
