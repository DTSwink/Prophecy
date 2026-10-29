$ErrorActionPreference='Stop'
& 'C:/Program Files/Epic Games/UE_5.7/Engine/Build/BatchFiles/Build.bat' MainMenuSceneLabEditor Win64 Development "-Project=$PSScriptRoot/MainMenuSceneLab.uproject" -WaitMutex -FromMsBuild -NoHotReloadFromIDE
exit $LASTEXITCODE
