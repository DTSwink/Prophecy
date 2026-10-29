param([switch]$Wait)
$ErrorActionPreference='Stop'
$labRoot=$PSScriptRoot.Replace('\','/')
$labArgs=@(('"'+$labRoot+'/MainMenuSceneLab.uproject"'),'-run=pythonscript',('-script="'+$labRoot+'/Tools/prepare_materials.py"'),'-WaterPrepare','-nullrhi','-unattended','-NoSound','-NoSplash','-NoCef',('-abslog="'+$labRoot+'/Saved/materials.log"'))
$labProc=Start-Process 'C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor-Cmd.exe' -ArgumentList $labArgs -WindowStyle Hidden -PassThru
$labProc.PriorityClass='BelowNormal'
$labProc.Id
if($Wait){
 $labProc.WaitForExit()
 if($labProc.ExitCode -ne 0){throw "Scene material preparation failed (exit $($labProc.ExitCode)); inspect Saved/materials.log"}
}
