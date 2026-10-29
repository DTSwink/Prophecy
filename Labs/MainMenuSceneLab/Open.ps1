param([switch]$Capture,[switch]$Demo,[switch]$Offscreen,[switch]$Visible,[switch]$BodyCloseup,[switch]$Air,[switch]$Ground,[switch]$Water,[switch]$FreezeBody,[switch]$MoveTest,[switch]$NoCollision,[switch]$ReflectionProbe,[switch]$HideControls,[switch]$CaptureUI,[switch]$ValidateControls,[switch]$ValidateGizmo,[switch]$GizmoPreview,[float]$PoseTime=-1,[float]$MoveSpeed=90,[string]$Settings='',[string]$Name='scene')
$ErrorActionPreference='Stop'
$labRoot=$PSScriptRoot.Replace('\','/')
$labArgs=@(('"'+$labRoot+'/MainMenuSceneLab.uproject"'),'/Engine/Maps/Entry','-game','-windowed','-ResX=1280','-ResY=720','-NoSplash','-NoSound',('-abslog="'+$labRoot+'/Saved/scene.log"'))
if($Name -notmatch '^[a-zA-Z0-9_-]+$'){throw 'Capture name must be a simple filename stem'}
if($Capture){$labArgs+=('-SceneCapture="'+$labRoot+'/Saved/Captures/'+$Name+'.png"');$labArgs+='-SceneExitAfterCapture'}
if($Demo){$labArgs+='-SceneDemo'}
if($BodyCloseup){$labArgs+='-SceneBodyCloseup'}
if($Air){$labArgs+='-SceneAirTab'}
if($Water){$labArgs+='-SceneWaterTab'}
if($FreezeBody){$labArgs+='-SceneFreezeBody'}
if($Ground){$labArgs+='-SceneGroundTab'}
if($MoveTest){$labArgs+='-SceneMoveTest';$labArgs+=('-SceneMoveSpeed='+$MoveSpeed.ToString([Globalization.CultureInfo]::InvariantCulture))}
if($NoCollision){$labArgs+='-SceneNoCollision'}
if($ReflectionProbe){$labArgs+='-SceneReflectionProbe'}
if($HideControls){$labArgs+='-SceneHideControls'}
if($CaptureUI){$labArgs+='-SceneCaptureUI'}
if($ValidateControls){$labArgs+='-SceneValidateControls'}
if($ValidateGizmo){$labArgs+='-SceneValidateGizmo'}
if($GizmoPreview){$labArgs+='-SceneGizmoPreview'}
if($Settings){$labArgs+=('-SceneSettings="'+(Resolve-Path -LiteralPath $Settings).Path.Replace('\','/')+'"')}
if($PoseTime -ge 0){$labArgs+=('-ScenePoseTime='+$PoseTime.ToString([Globalization.CultureInfo]::InvariantCulture))}
if($Offscreen){$labArgs+='-RenderOffscreen'}
$labWindowStyle=if($Visible -and -not $Offscreen){'Normal'}else{'Hidden'}
Start-Process -FilePath 'C:/Program Files/Epic Games/UE_5.7/Engine/Binaries/Win64/UnrealEditor.exe' -ArgumentList $labArgs -WindowStyle $labWindowStyle -PassThru | Select-Object Id,ProcessName
