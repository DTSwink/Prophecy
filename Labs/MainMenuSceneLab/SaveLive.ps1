$ErrorActionPreference='Stop'
$sceneProject=(Join-Path $PSScriptRoot 'MainMenuSceneLab.uproject').Replace('\','/')
$sceneProcesses=@(Get-CimInstance Win32_Process | Where-Object {
 $_.Name -eq 'UnrealEditor.exe' -and $_.CommandLine -and
 $_.CommandLine.Replace('\','/').Contains($sceneProject) -and
 $_.CommandLine -notlike '*-SceneCapture=*'
})
if($sceneProcesses.Count -ne 1){throw 'Expected one live Scene Studio review; no save request sent.'}
$sceneSettings=Join-Path $PSScriptRoot 'Resources/scene.json'
if($sceneProcesses[0].CommandLine -match '-SceneSettings="([^"]+)"'){$sceneSettings=$Matches[1]}
$sceneBefore=(Get-Item -LiteralPath $sceneSettings).LastWriteTimeUtc
$sceneRequest=Join-Path $PSScriptRoot 'Saved/save-look.request'
Set-Content -LiteralPath $sceneRequest -Value ('Save before authorized operation: '+[Guid]::NewGuid())
$sceneDeadline=(Get-Date).AddSeconds(15)
while((Test-Path -LiteralPath $sceneRequest) -and (Get-Date) -lt $sceneDeadline){Start-Sleep -Milliseconds 200}
if(Test-Path -LiteralPath $sceneRequest){throw 'Studio did not acknowledge saving. Preserve the running process.'}
if((Get-Item -LiteralPath $sceneSettings).LastWriteTimeUtc -le $sceneBefore){throw 'Saved file was not updated. Preserve the running process.'}
$null=Get-Content -LiteralPath $sceneSettings -Raw | ConvertFrom-Json
Write-Output "Live look saved by Scene Studio PID $($sceneProcesses[0].ProcessId)."
