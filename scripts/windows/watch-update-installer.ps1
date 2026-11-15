# Observe only the exact SDK-extracted installer on the disposable runner.
$ErrorActionPreference='Stop'
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_OS -ne 'Windows') { throw 'Disposable Windows runner only' }
$directory=Join-Path (Get-Location) 'artifacts/companion-signed-update-test'
$null=New-Item -ItemType Directory -Path $directory -Force
$ready=Join-Path $directory 'installer-observer.ready'
[IO.File]::WriteAllText($ready,'ready')
$deadline=[DateTime]::UtcNow.AddSeconds(120)
while ([DateTime]::UtcNow -lt $deadline) {
    foreach ($process in [Diagnostics.Process]::GetProcesses()) {
        try {
            if (-not $process.ProcessName.EndsWith('-installer')) { continue }
            $path=$process.MainModule.FileName
            if (-not $path.StartsWith($env:RUNNER_TEMP,[StringComparison]::OrdinalIgnoreCase) -and -not $path.StartsWith([IO.Path]::GetTempPath(),[StringComparison]::OrdinalIgnoreCase)) { continue }
            $hash=(Get-FileHash $path -Algorithm SHA256).Hash.ToLowerInvariant()
            $expected=(Get-FileHash $env:MARKET_TEST_NEW_INSTALLER -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($hash -ne $expected) { continue }
            $started=[DateTime]::UtcNow.ToString('o');$identifier=$process.Id
            $finished=$process.WaitForExit(120000)
            @{observed=$true;pid=$identifier;path=$path;installer_sha256=$hash;observed_at=$started;exited=$finished;exit_code=$(if($finished){$process.ExitCode}else{$null})} |
                ConvertTo-Json | Set-Content (Join-Path $directory 'installer-exit.json')
            exit 0
        } catch { continue } finally { $process.Dispose() }
    }
    Start-Sleep -Milliseconds 25
}
@{observed=$false;reason='No exact SDK installer process observed within the bounded interval'} | ConvertTo-Json | Set-Content (Join-Path $directory 'installer-exit.json')
