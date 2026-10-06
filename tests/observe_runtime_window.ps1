# Stage 3G-A Windows observation only. Simulation still runs on its original thread.
param(
    [Parameter(Mandatory=$true)][string]$Fixture,
    [string]$Python='python',
    [ValidatePattern('^[A-Za-z0-9_-]+$')][string]$Tag='observation',
    [ValidateRange(1,600)][int]$Budget=120,
    [ValidateRange(1,1000)][int]$Callbacks=40
)
$auditRepo=Split-Path -Parent $PSScriptRoot
$auditFixture=(Resolve-Path -LiteralPath $Fixture).Path
$env:KIVY_NO_ARGS='1'
$env:KIVY_NO_FILELOG='1'
$env:PYTHONIOENCODING='utf-8'
$auditStart=Get-Date
$auditOut=Join-Path $env:TEMP "at-forensic-native-$Tag.jsonl"
$auditErr=Join-Path $env:TEMP "at-forensic-native-$Tag.err"
$auditArgs=@('-B','-m','tests.profile_runtime_forensics','--fixture',('"'+$auditFixture+'"'),'--native','--budget',$Budget,'--callbacks',$Callbacks)
$auditProc=Start-Process -FilePath $Python -ArgumentList $auditArgs -WorkingDirectory $auditRepo -WindowStyle Hidden -RedirectStandardOutput $auditOut -RedirectStandardError $auditErr -PassThru
$auditRows=[System.Collections.Generic.List[object]]::new()
while (-not $auditProc.HasExited) {
    # The Windows venv launcher can delegate to another python.exe. Inspect only
    # fresh Python window owners, never stop or alter any pre-existing process.
    Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.StartTime -ge $auditStart -and $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -eq 'Airline Tycoon - PH 1.0' } | ForEach-Object {
        $auditRows.Add([pscustomobject]@{ elapsed=((Get-Date)-$auditStart).TotalSeconds; unix_seconds=([DateTimeOffset]::Now.ToUnixTimeMilliseconds()/1000.0); pid=$_.Id; responding=$_.Responding; working=$_.WorkingSet64 })
    }
    Start-Sleep -Milliseconds 250
    $auditProc.Refresh()
}
$auditSummary=[pscustomobject]@{samples=$auditRows.Count;notResponding=(@($auditRows | Where-Object { -not $_.responding })).Count;exitCode=$auditProc.ExitCode;rows=$auditRows}
$auditSummary | ConvertTo-Json -Depth 6 -Compress | Set-Content (Join-Path $env:TEMP "at-forensic-window-$Tag.json")
Write-Output "Native observation finished. Samples $($auditRows.Count), Not Responding $($auditSummary.notResponding), exit $($auditProc.ExitCode)."
Write-Output "TEMP output: $auditOut"
if ($auditProc.ExitCode -ne 0) { Get-Content $auditErr -Tail 12; exit 1 }
