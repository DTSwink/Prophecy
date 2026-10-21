$ErrorActionPreference = 'Stop'
$bloodRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '../..')).Path
$bloodOut = Join-Path $bloodRoot 'Saved/Diagnostics/BloodRectangleInstall'
$bloodArgs = '"' + (Join-Path $bloodRoot 'GameAnimationSample3.uproject') +
    '" /Engine/Maps/Entry -unattended -nullrhi -nocef -DisablePlugins=Fab -nosound -nosplash -nop4' +
    ' -ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False' +
    ' -ExecCmds="Automation RunTests Prophecy.Blood.RectangleIntegration"' +
    ' -TestExit="Automation Test Queue Empty" -ReportExportPath="' + (Join-Path $bloodOut 'report') +
    '" -abslog="' + (Join-Path $bloodOut 'tests.log') + '"'
$bloodProcess = Start-Process 'C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe' -ArgumentList $bloodArgs -WindowStyle Hidden -PassThru
$bloodProcess.Id | Set-Content (Join-Path $bloodOut 'test.pid')
Write-Output ("Started owned rectangle test process " + $bloodProcess.Id)
