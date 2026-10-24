$ErrorActionPreference='Stop'
& 'C:/Program Files/Epic Games/UE_5.7/Engine/Build/BatchFiles/Build.bat' PauseMenuLabEditor Win64 Development "-Project=$PSScriptRoot/PauseMenuLab.uproject" -WaitMutex -FromMsBuild -NoHotReloadFromIDE
exit $LASTEXITCODE

