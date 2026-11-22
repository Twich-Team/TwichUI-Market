# Fast real production Rust shell-picker feedback, independent of the web/installer.
$ErrorActionPreference='Stop'
if($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows'){throw 'Disposable Windows only'}
$env:MARKET_TEST_APP_DATA=Join-Path $env:RUNNER_TEMP 'TwichUI-Actual-Picker'
if(Test-Path $env:MARKET_TEST_APP_DATA){throw 'Picker fixture must start fresh'}
$null=New-Item $env:MARKET_TEST_APP_DATA -ItemType Directory
$helper=Join-Path (Get-Location) 'scripts/windows/workshop-fixtures.ps1'
$fixture=(& $helper -Action Setup)|ConvertFrom-Json
$exe=Join-Path (Get-Location) 'desktop/target/debug/examples/installation_smoke.exe'
$p=$null
function BeginPicker($name) {
    $script:output=Join-Path $env:MARKET_TEST_APP_DATA ($name+'.json')
    $script:p=Start-Process $exe -ArgumentList choose -RedirectStandardOutput $script:output -RedirectStandardError ($script:output+'.stderr') -PassThru
    $env:MARKET_TEST_PRIMARY_PID=$script:p.Id.ToString()
}
function ReadPicker() {
    if(-not $script:p.WaitForExit(10000)){throw 'Actual shell picker did not complete'}
    if($script:p.ExitCode -ne 0){throw (Get-Content ($script:output+'.stderr') -Raw)}
    return (Get-Content $script:output -Raw|ConvertFrom-Json)
}
try {
    BeginPicker 'cancel';$null=& $helper -Action CancelFolder
    if($null -ne (ReadPicker).selected){throw 'Native cancellation did not remain empty'}
    BeginPicker 'select';$null=& $helper -Action ChooseFolder -GamePath $fixture.first
    $chosen=ReadPicker
    if($chosen.selected -ne $fixture.first -or -not $chosen.valid){throw 'Real native selection or edition/capability validation failed'}
    # Real shell selection must replace its last PIDL, including when accepting a
    # path whose addon is invalid. Merely changing an edit box can return old data.
    $wrong=Join-Path $fixture.base 'WrongGame';$null=New-Item $wrong -ItemType Directory
    foreach($target in @($fixture.second,$wrong,$fixture.first)) {
        BeginPicker ('replace-'+[IO.Path]::GetFileName($target));$null=& $helper -Action ChooseFolder -GamePath $target
        $chosen=ReadPicker
        if($chosen.selected -ne $target -or $chosen.valid -ne ($target -ne $wrong)){throw 'Native picker reused a stale selection or validation'}
    }
    $null=& $helper -Action Register
    $found=(& $exe discover)|ConvertFrom-Json
    if($found.candidates.Count -ne 1 -or $found.candidates[0] -ne $fixture.first){throw 'Actual registry single discovery failed'}
    $null=& $helper -Action RegisterSecond
    $found=(& $exe discover)|ConvertFrom-Json
    if($found.candidates.Count -ne 2){throw 'Actual registry multiple discovery failed'}
    Write-Output 'Actual Rust native shell cancellation, folder selection, executable/capability validation and single/multiple registry discovery passed. Synthetic versioned PE, not Forever gameplay acceptance.'
} finally {
    if($p -and -not $p.HasExited){$p.Kill();$p.WaitForExit()}
    $null=& $helper -Action ClearRegistry
}
