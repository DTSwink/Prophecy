param([switch]$Capture, [switch]$StayOpen)
$ErrorActionPreference = 'Stop'
$project = Join-Path $PSScriptRoot 'WeaponWheelLab.uproject'
$exe = 'C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe'
$argsForLab = @(('"{0}"' -f $project), '/Engine/Maps/Entry', '-game', '-windowed', '-ResX=1024', '-ResY=949', '-WinX=448', '-WinY=30', '-NoSplash', '-NoSound', '-NoLiveCoding')
if ($Capture) {
    $output = Join-Path $PSScriptRoot 'Saved\Captures\checkpoint-03.png'
    $argsForLab += @('-WheelPresent', '-WheelVerify', ('-WheelCapture="{0}"' -f $output))
    $argsForLab += $(if ($StayOpen) { '-WheelReview' } else { '-WheelExitAfterCapture' })
}
# This is the user-facing review window, not a background service.
Start-Process -FilePath $exe -ArgumentList $argsForLab -PassThru | Select-Object Id, ProcessName
