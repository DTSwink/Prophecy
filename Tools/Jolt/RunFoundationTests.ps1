[CmdletBinding()]
param(
    [string]$Engine = 'C:/Program Files/Epic Games/UE_5.7',
    [string]$Project = '',
    [switch]$NoLockIdleReads,
    [ValidatePattern('^Prophecy\.(?:Jolt|NN\.PhysicalTargets|NN\.PhysicalFeedback(?:Tolerance)?|Fists\.Cache|Crowd\.NameLookup)(?:\.[A-Za-z0-9]+)*$')][string]$Filter = 'Prophecy.Jolt',
    [ValidateRange(30, 1800)][int]$TimeoutSeconds = 300
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$joltProjectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$joltProject = if ($Project) { (Resolve-Path -LiteralPath $Project).Path } else { Join-Path $joltProjectRoot 'GameAnimationSample3.uproject' }
if ([IO.Path]::GetExtension($joltProject) -ne '.uproject') { throw 'Project must resolve to a .uproject file.' }
$joltEditor = Join-Path $Engine 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe'
if (-not (Test-Path -LiteralPath $joltEditor)) { throw "Editor executable not found: $joltEditor" }
$joltActiveEditors = @(Get-Process -Name UnrealEditor,UnrealEditor-Cmd -ErrorAction SilentlyContinue)
if ($joltActiveEditors.Count) { throw 'An editor process is already running. This isolated runner will not close it.' }
$joltReport = Join-Path $joltProjectRoot ('Saved/JoltMigration/Foundation-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Path $joltReport | Out-Null
$joltLog = Join-Path $joltReport 'Unreal.log'
$joltArguments = '"' + $joltProject + '" /Engine/Maps/Entry -unattended -nop4 -nosplash -nosound -nullrhi -NoLiveCoding -NoScreenMessages -LogCmds="LogWindows Verbose"' +
    ' -ExecCmds="Module List,Automation RunTests ' + $Filter + '" -TestExit="Automation Test Queue Empty" -ReportExportPath="' + $joltReport + '" -abslog="' + $joltLog + '"'
if ($NoLockIdleReads) { $joltArguments += ' -ProphecyJoltNoLockIdleReads' }
$joltProcess = Start-Process -FilePath $joltEditor -ArgumentList $joltArguments -WindowStyle Hidden -PassThru
$joltProcess.PriorityClass = 'BelowNormal'
Write-Output "Jolt foundation process $($joltProcess.Id); report $joltReport"
$joltDeadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
while (-not $joltProcess.WaitForExit(1000)) {
    if ([DateTime]::UtcNow -gt $joltDeadline) {
        # This Process object belongs only to the hidden test child launched above.
        $joltProcess.Kill()
        throw "Owned test child exceeded $TimeoutSeconds seconds. See $joltLog"
    }
}
$joltResultPath = Join-Path $joltReport 'index.json'
if (-not (Test-Path -LiteralPath $joltResultPath)) { throw "Automation report missing. Exit $($joltProcess.ExitCode); see $joltLog" }
$joltResult = Get-Content -Raw -LiteralPath $joltResultPath | ConvertFrom-Json
$joltBadTests = @($joltResult.tests | Where-Object { $_.state -ne 'Success' -or $_.errors -gt 0 -or $_.warnings -gt 0 })
if ($joltProcess.ExitCode -ne 0 -or $joltResult.succeeded -eq 0 -or $joltResult.failed -ne 0 -or $joltResult.notRun -ne 0 -or $joltBadTests.Count) {
    throw "Jolt automation did not pass cleanly. Exit $($joltProcess.ExitCode); see $joltResultPath"
}
[pscustomobject]@{ Success = $true; Tests = $joltResult.succeeded; ExitCode = $joltProcess.ExitCode; Report = $joltResultPath } | ConvertTo-Json
