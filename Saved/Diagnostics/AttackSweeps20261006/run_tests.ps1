$ErrorActionPreference='Stop'
$taskRoot=(Get-Location).Path
$taskReport=Join-Path $taskRoot 'Saved/Diagnostics/AttackSweeps20261006/tests'
New-Item -ItemType Directory -Force $taskReport | Out-Null
$taskArgs='"'+(Join-Path $taskRoot 'GameAnimationSample3.uproject')+'" /Engine/Maps/Entry -unattended -nop4 -nosplash -nosound -nullrhi -NoLiveCoding -ExecCmds="Automation RunTests Prophecy.Jolt.ContactShapes+Prophecy.Jolt.HitEvents" -TestExit="Automation Test Queue Empty" -ReportExportPath="'+$taskReport+'" -abslog="'+$taskReport+'/Unreal.log"'
$taskProcess=Start-Process 'C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe' -ArgumentList $taskArgs -WindowStyle Hidden -PassThru
$taskProcess.WaitForExit()
Write-Output "Exit: $($taskProcess.ExitCode)"
Get-Content (Join-Path $taskReport 'index.json') -Raw
