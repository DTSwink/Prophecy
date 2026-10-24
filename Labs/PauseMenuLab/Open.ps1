param([switch]$Capture,[switch]$StayOpen)
$ErrorActionPreference='Stop'
$exe='C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor.exe'
$labArgs=@(('"{0}/PauseMenuLab.uproject"' -f $PSScriptRoot),'/Engine/Maps/Entry','-game','-windowed','-ResX=1672','-ResY=941','-WinX=90','-WinY=35','-NoSplash','-NoSound','-NoLiveCoding')
if($Capture) {
 $labArgs+=@('-PauseVerify',('-PauseCapture="{0}/Saved/Captures/checkpoint-01.png"' -f $PSScriptRoot))
 if(-not $StayOpen) {$labArgs+='-PauseExitAfterCapture'}
}
Start-Process -FilePath $exe -ArgumentList $labArgs -PassThru | Select-Object Id,ProcessName

