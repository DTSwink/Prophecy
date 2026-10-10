param([int]$TimeoutSeconds = 240, [string]$Tests = "Prophecy.SwordHolster.NativeParity+Prophecy.NN.PhysicalFeedback+Prophecy.Blends.SixtyTickClock")
$ErrorActionPreference = 'Stop'
$holsterRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$holsterOut = Join-Path $holsterRoot 'Saved/Diagnostics/SwordLabPort20261010'
$holsterArgs = '"' + (Join-Path $holsterRoot 'GameAnimationSample3.uproject') + '" /Engine/Maps/Entry -nullrhi -nocef -unattended -nosplash -nosound -nop4 -ExecCmds="Automation RunTests ' + $Tests + '" -TestExit="Automation Test Queue Empty" -ReportExportPath="' + (Join-Path $holsterOut 'automation') + '" -abslog="' + (Join-Path $holsterOut 'automation.log') + '"'
$holsterProcess = Start-Process 'C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe' -ArgumentList $holsterArgs -WindowStyle Hidden -PassThru
$holsterDeadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
while (-not $holsterProcess.WaitForExit(1000)) {
    if ([DateTime]::UtcNow -gt $holsterDeadline) {
        $holsterProcess.Kill()
        throw 'Owned parity test process timed out.'
    }
}
$holsterReport = Get-Content -Raw (Join-Path $holsterOut 'automation/index.json') | ConvertFrom-Json
Get-Content (Join-Path $holsterOut 'native-parity.txt')
if ($holsterProcess.ExitCode -ne 0 -or $holsterReport.failed -ne 0 -or $holsterReport.succeeded -lt 1) { throw 'Native holster parity failed; see automation report.' }
