$ErrorActionPreference = 'Stop'
$engine = 'C:\Program Files\Epic Games\UE_5.7'
# This distinct DLL/project is not loaded in the main editor. Do not request hot
# reload into another project's active Live Coding session (the engine mutex is global).
& "$engine\Engine\Build\BatchFiles\Build.bat" WeaponWheelLabEditor Win64 Development "-Project=$PSScriptRoot\WeaponWheelLab.uproject" -WaitMutex -FromMsBuild -NoHotReloadFromIDE
exit $LASTEXITCODE
