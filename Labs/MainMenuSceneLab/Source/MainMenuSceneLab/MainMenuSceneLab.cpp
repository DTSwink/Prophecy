
#include "Modules/ModuleManager.h"
#include "Containers/Ticker.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "Engine/GameViewportClient.h"
#include "Engine/StaticMeshActor.h"
#include "Engine/StaticMesh.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/Texture2D.h"
#include "Engine/PlanarReflection.h"
#include "Engine/PostProcessVolume.h"
#include "Engine/DirectionalLight.h"
#include "Engine/RectLight.h"
#include "Engine/PointLight.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/RectLightComponent.h"
#include "Components/PointLightComponent.h"
#include "Components/DirectionalLightComponent.h"
#include "Components/PlanarReflectionComponent.h"
#include "Animation/AnimSequence.h"
#include "Animation/AnimSingleNodeInstance.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "ProceduralMeshComponent.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "Framework/Application/SlateApplication.h"
#include "Framework/Application/IInputProcessor.h"
#include "Widgets/SWindow.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/Parse.h"
#include "Misc/CommandLine.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Math/Float16Color.h"
#include "TextureResource.h"
#include "UnrealClient.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "NiagaraSystem.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/TextureRenderTargetVolume.h"
#include "UObject/UObjectIterator.h"
#include "ShallowWaterSubsystem.h"
#include "NiagaraDataInterfaceRigidMeshCollisionQuery.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "PrepareWater.h"
#include "SceneControls.h"
#include "SceneGizmo.h"
#include "SceneVolume.h"
#include "SceneGasSmoke.h"
#include "PrepareSmoke.h"
#include "PrepareWetMaterial.h"
#include "ShaderCompiler.h"

class FSceneInput:public IInputProcessor {
public:
 TFunction<void(FKey)> Press;
 TSet<FKey> Held;
 virtual void Tick(const float,FSlateApplication&,TSharedRef<ICursor>)override{}
 virtual bool HandleKeyDownEvent(FSlateApplication&,const FKeyEvent& E)override{
  Held.Add(E.GetKey());if(!E.IsRepeat()&&Press)Press(E.GetKey());return E.GetKey()==EKeys::Tab||E.GetKey()==EKeys::SpaceBar||E.GetKey()==EKeys::P||E.GetKey()==EKeys::R||E.GetKey()==EKeys::F12||E.GetKey()==EKeys::W||E.GetKey()==EKeys::A||E.GetKey()==EKeys::S||E.GetKey()==EKeys::D;
 }
 virtual bool HandleKeyUpEvent(FSlateApplication&,const FKeyEvent& E)override{Held.Remove(E.GetKey());return false;}
};

class FMainMenuSceneModule:public FDefaultGameModuleImpl {
 FTSTicker::FDelegateHandle Handle;
 TSharedPtr<FSceneInput> Input;
 UWorld* World=nullptr;USkeletalMeshComponent* Body=nullptr;
 UMaterialInstanceDynamic* WaterMID=nullptr;ACameraActor* Camera=nullptr;
 UMaterialInstanceDynamic* BedMID=nullptr;UMaterialInstanceDynamic* RainMID=nullptr;UMaterialInstanceDynamic* BodyMID=nullptr;
 UInstancedStaticMeshComponent* RainMesh=nullptr;
 FSceneVolume SceneVolume;
 FSceneGasSmoke Smoke;
 TSharedPtr<SSceneGizmo> Gizmo;bool bValidateGizmo=false,bGizmoValidated=false;
 TSharedPtr<SWidget> ControlsRoot;bool bControlsVisible=true,bCaptureUI=false;
 FString SettingsPath,SceneStatus=TEXT("Live changes recover automatically. Save look sets the revert point.");
 float RainClock=0,HazeClock=0,WetClock=0;
 float RecoveryDelay=-1;
 bool bValidateControls=false,bControlsValidated=false;
 UNiagaraComponent* WaterSim=nullptr;UTextureRenderTarget2D* NormalRT=nullptr;
 TArray<FTransform> PreviousContactBones;bool bWaterContactActive=false;float ContactHold=0,ContactSpeed=0,PeakContactSpeed=0;int32 ContactFrames=0;
 bool bMoveTest=false,bNoCollision=false;FVector ManualOffset=FVector::ZeroVector;
 UAnimSequence* Idle=nullptr;UAnimSequence* StepClip=nullptr;UAnimSequence* WalkClip=nullptr;UAnimSequence* ActiveClip=nullptr;


 FVector2D FieldOrigin=FVector2D(0,140);
 float Accumulator=0,Time=0,AnimTime=0,Alive=0,ShadersStable=0;
 bool bDemo=false,bPaused=false,bBuilt=false,bCaptureRequested=false,bBodyCloseup=false;
 FString CapturePath;int32 CapturePhase=0;double ExitAt=0;
 TSharedPtr<FJsonObject> Settings;
 float PoseTime=-1,MoveSpeed=90;

 float Setting(const TCHAR* Name,float Default)const {double Value=0;return Settings&&Settings->TryGetNumberField(Name,Value)&&FMath::IsFinite(Value)?float(Value):Default;}

 void LoadSettings(bool Recover=false){
  FString Json;TSharedPtr<FJsonObject> Read;
  if(FFileHelper::LoadFileToString(Json,*SettingsPath)&&FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Json),Read)&&Read)Settings=Read;
  if(Recover){
   FString RecoveryJson,Base;TSharedPtr<FJsonObject> Recovered;const TSharedPtr<FJsonObject>* Live=nullptr;
   if(FFileHelper::LoadFileToString(RecoveryJson,*(SettingsPath+TEXT(".recovery")))&&FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(RecoveryJson),Recovered)&&Recovered&&Recovered->TryGetStringField(TEXT("saved_snapshot"),Base)&&Base==Json&&Recovered->TryGetObjectField(TEXT("settings"),Live)&&Live&&Live->IsValid())Settings=*Live;
  }
  if(!Settings)Settings=MakeShared<FJsonObject>();
  const TPair<const TCHAR*,float> Defaults[]={
   {TEXT("collision_strength"),1},{TEXT("collision_min_speed"),1},{TEXT("collision_softness"),4},{TEXT("water_damping"),0},{TEXT("water_resting_contact"),0},
   {TEXT("body_offset_x"),0},{TEXT("body_offset_y"),0},{TEXT("body_offset_z"),0},
   {TEXT("wind_strength"),.16f},{TEXT("ground_scale"),1},{TEXT("ground_shape"),1},{TEXT("ground_darkness"),1},{TEXT("ground_contrast"),1},
   {TEXT("rain_amount"),.35f},{TEXT("rain_speed"),1},{TEXT("rain_slant"),.08f},{TEXT("rain_ripple_strength"),.35f},{TEXT("rain_ripple_size"),1},
   {TEXT("rain_width"),.12f},{TEXT("rain_length"),18},{TEXT("rain_gust"),.65f},{TEXT("rain_brightness"),2.4f},
   {TEXT("haze_amount"),.65f},{TEXT("haze_height"),350},{TEXT("haze_spread"),1},{TEXT("haze_speed"),.12f},{TEXT("fog_amount"),0},
   {TEXT("smoke_lower_edge"),.28f},{TEXT("smoke_edge_softness"),.06f},{TEXT("smoke_roll"),.65f},
   {TEXT("smoke_horizontal_width"),1},{TEXT("smoke_horizontal_shift"),200},
   {TEXT("wet_amount"),.65f},{TEXT("bead_density"),.55f},{TEXT("bead_size"),1},{TEXT("bead_strength"),.65f},{TEXT("runoff_speed"),.3f},{TEXT("trail_amount"),.45f}};
  for(auto Pair:Defaults)if(!Settings->HasField(Pair.Key))Settings->SetNumberField(Pair.Key,Pair.Value);
  ManualOffset=ClampBodyOffset(FVector(Setting(TEXT("body_offset_x"),0),Setting(TEXT("body_offset_y"),0),Setting(TEXT("body_offset_z"),0)));
 }
 static FVector ClampBodyOffset(FVector P){
  const FVector XY=FVector(P.X,P.Y,0).GetClampedToMaxSize(450);
  return FVector(XY.X,XY.Y,FMath::Clamp(P.Z,-30.,400.));
 }
 void SetBodyOffset(FVector P){
  if(P.ContainsNaN())return;
  ManualOffset=ClampBodyOffset(P);
  Settings->SetNumberField(TEXT("body_offset_x"),ManualOffset.X);Settings->SetNumberField(TEXT("body_offset_y"),ManualOffset.Y);Settings->SetNumberField(TEXT("body_offset_z"),ManualOffset.Z);
  if(Body)Body->SetWorldLocation(FVector(0,140,0)+ManualOffset);
  RecoveryDelay=.25f;SceneStatus=TEXT("Position updated. Recovery saves automatically.");
 }
 void ResetBodyPosition(){
  if(Gizmo)Gizmo->Finish(false);
  SetBodyOffset(FVector::ZeroVector);
  if(Body)Body->SetWorldRotation(FRotator(0,Setting(TEXT("mannequin_yaw"),205),0));
  if(bBodyCloseup)UpdateCamera();
 }
 void WriteRecovery(){
  if(!Settings||SettingsPath.IsEmpty())return;
  FString Json,Base;FFileHelper::LoadFileToString(Base,*SettingsPath);
  TSharedPtr<FJsonObject> Snapshot=MakeShared<FJsonObject>();Snapshot->SetStringField(TEXT("saved_snapshot"),Base);Snapshot->SetObjectField(TEXT("settings"),Settings);
  FJsonSerializer::Serialize(Snapshot.ToSharedRef(),TJsonWriterFactory<>::Create(&Json));
  const FString Path=SettingsPath+TEXT(".recovery"),Pending=Path+TEXT(".pending");
  if(FFileHelper::SaveStringToFile(Json,*Pending,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))IFileManager::Get().Move(*Path,*Pending,true,true,false,true);
  RecoveryDelay=-1;
 }
 void SaveSettings(){
  FString Json;FJsonSerializer::Serialize(Settings.ToSharedRef(),TJsonWriterFactory<>::Create(&Json));
  const FString Pending=SettingsPath+TEXT(".pending");
  if(FPaths::FileExists(SettingsPath))IFileManager::Get().Copy(*(SettingsPath+TEXT(".previous")),*SettingsPath);
  const bool OK=FFileHelper::SaveStringToFile(Json,*Pending,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM)&&IFileManager::Get().Move(*SettingsPath,*Pending,true,true,false,true);
  WriteRecovery();
  SceneStatus=OK?TEXT("Saved. This look will load next time."):TEXT("Save failed; your live settings are still here.");
 }
 void SetStudioParameter(FName Key,float Value){
  if(!FMath::IsFinite(Value))return;
  Settings->SetNumberField(Key.ToString(),Value);RecoveryDelay=.25f;ApplyWeatherSettings();SceneStatus=TEXT("Unsaved changes - live preview.");
 }
 void ValidateControls(){
  bControlsValidated=true;
  if(!FPaths::IsUnderDirectory(FPaths::ConvertRelativePathToFull(SettingsPath),FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir())))return;
  FString Original;FJsonSerializer::Serialize(Settings.ToSharedRef(),TJsonWriterFactory<>::Create(&Original));
  SetStudioParameter(TEXT("rain_amount"),0);SetStudioParameter(TEXT("haze_amount"),0);
  float RainUniform=-1;WaterMID->GetScalarParameterValue(TEXT("RainAmount"),RainUniform);
  SetStudioParameter(TEXT("wind_strength"),0);float AmbientUniform=-1;WaterMID->GetScalarParameterValue(TEXT("WindStrength"),AmbientUniform);
  SetStudioParameter(TEXT("wet_amount"),0);float WetUniform=-1;BodyMID->GetScalarParameterValue(TEXT("WetAmount"),WetUniform);
  const bool Disabled=!RainMesh->IsVisible()&&!Smoke.IsVisible()&&RainUniform==0&&WetUniform==0&&AmbientUniform==0;
  SetStudioParameter(TEXT("rain_amount"),3.27f);SetStudioParameter(TEXT("haze_amount"),.54f);
  SetStudioParameter(TEXT("wind_strength"),.37f);
  SetStudioParameter(TEXT("ground_scale"),1.27f);SetStudioParameter(TEXT("ground_darkness"),.31f);
  SetStudioParameter(TEXT("wet_amount"),.67f);SetStudioParameter(TEXT("rain_width"),.08f);SetStudioParameter(TEXT("bead_size"),1.4f);
  SetStudioParameter(TEXT("smoke_lower_edge"),.21f);SetStudioParameter(TEXT("smoke_roll"),.82f);SetStudioParameter(TEXT("smoke_edge_softness"),.04f);
  SetStudioParameter(TEXT("smoke_horizontal_shift"),-260.f);
  SetStudioParameter(TEXT("smoke_horizontal_width"),1);Smoke.Tick(.31f);
  bool RadiusValid=false,ScaleValid=false,SizeValid=false;
  const float OldRadius=Smoke.Component->GetVariableFloat(TEXT("User.SmokeSourceRadius"),RadiusValid);
  const FVector OldDimensions=Smoke.Component->GetVariableVec3(TEXT("User.WorldSpaceSize"),SizeValid);
  SetStudioParameter(TEXT("smoke_horizontal_width"),8);Smoke.Tick(.31f);
  const FVector WideScale=Smoke.Component->GetVariableVec3(TEXT("User.SmokeSourceScale"),ScaleValid);
  const FVector WideDimensions=Smoke.Component->GetVariableVec3(TEXT("User.WorldSpaceSize"),SizeValid);
  const bool WidthOK=RadiusValid&&ScaleValid&&SizeValid&&WideScale.Equals(FVector(1,8,1),.001)&&FMath::IsNearlyEqual(Smoke.Component->GetVariableFloat(TEXT("User.SmokeSourceRadius"),RadiusValid),OldRadius)&&WideDimensions.X==OldDimensions.X&&WideDimensions.Z==OldDimensions.Z&&WideDimensions.Y>=2*OldRadius*8+899;
  SetStudioParameter(TEXT("smoke_horizontal_width"),3.25f);Smoke.Tick(.31f);
  bool PlaneValid=false,RollValid=false,VelocityValid=false,BuoyancyValid=false;
  const FVector4 ExpectedPlane=Smoke.CutoffPlane;
  const FVector4 BoundPlane=Smoke.Component?Smoke.Component->GetVariableVec4(TEXT("User.SmokeCropPlane"),PlaneValid):FVector4();
  const float BoundRoll=Smoke.Component?Smoke.Component->GetVariableFloat(TEXT("User.SmokeVorticity"),RollValid):0;
  const FVector BoundVelocity=Smoke.Component?Smoke.Component->GetVariableVec3(TEXT("User.SmokeVelocity"),VelocityValid):FVector::ZeroVector;
  const float BoundBuoyancy=Smoke.Component?Smoke.Component->GetVariableFloat(TEXT("User.SmokeDensityBuoyancy"),BuoyancyValid):0;
  const float ExpectedDrift=FMath::Clamp(Setting(TEXT("haze_speed"),.12f)/.15f,0.f,6.f);
  const bool SmokeBindings=PlaneValid&&RollValid&&VelocityValid&&BuoyancyValid&&BoundPlane.Equals(ExpectedPlane,.001)&&FMath::IsNearlyEqual(BoundRoll,FMath::Lerp(.25f,4.f,.82f))&&FMath::IsNearlyEqual(Smoke.Component->GetComponentLocation().Y,-120.,.001)&&BoundVelocity.Equals(FVector(0,0,-80)*ExpectedDrift,.001)&&FMath::IsNearlyEqual(BoundBuoyancy,-.025f*ExpectedDrift*ExpectedDrift);
  SetStudioParameter(TEXT("collision_strength"),0);
  bool StrengthValid=false,ThresholdValid=false;
  const bool WaterOff=WaterSim&&WaterSim->GetVariableFloat(TEXT("User.ContactStrength"),StrengthValid)==0&&WaterSim->GetVariableFloat(TEXT("User.ContactMinSpeed"),ThresholdValid)>1.e8f&&StrengthValid&&ThresholdValid;
  SetStudioParameter(TEXT("collision_strength"),.6f);SetStudioParameter(TEXT("collision_min_speed"),5);
  SetStudioParameter(TEXT("collision_softness"),7);SetStudioParameter(TEXT("water_damping"),.3f);SetStudioParameter(TEXT("interaction_strength"),.8f);
  SaveSettings();
  FString Saved;FFileHelper::LoadFileToString(Saved,*SettingsPath);TSharedPtr<FJsonObject> Disk;
  const bool Parsed=FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Saved),Disk)&&Disk;
  SetStudioParameter(TEXT("rain_amount"),.11f);SetStudioParameter(TEXT("haze_amount"),.09f);
  SetStudioParameter(TEXT("wind_strength"),.81f);WriteRecovery();LoadSettings(true);
  const bool RecoveryOK=FMath::IsNearlyEqual(Setting(TEXT("wind_strength"),0),.81f);
  LoadSettings();ApplyWeatherSettings();
  WaterMID->GetScalarParameterValue(TEXT("WindStrength"),AmbientUniform);
  const bool WidthSaved=FMath::IsNearlyEqual(Setting(TEXT("smoke_horizontal_width"),0),3.25f);
  const FString WidthResult=FString::Printf(TEXT("{\"passed\":%s,\"source_scale_y\":%.1f,\"radius_cm\":%.3f,\"grid_y_cm\":%.3f,\"height_and_depth_unchanged\":%s,\"save_reload\":%s}"),WidthOK&&WidthSaved?TEXT("true"):TEXT("false"),WideScale.Y,OldRadius,WideDimensions.Y,WidthOK?TEXT("true"):TEXT("false"),WidthSaved?TEXT("true"):TEXT("false"));
  FFileHelper::SaveStringToFile(WidthResult,*(FPaths::ProjectSavedDir()/TEXT("Validation/smoke-width.json")));
  const bool SmokeSaved=WidthOK&&WidthSaved&&FMath::IsNearlyEqual(Setting(TEXT("smoke_lower_edge"),0),.21f)&&FMath::IsNearlyEqual(Setting(TEXT("smoke_roll"),0),.82f)&&FMath::IsNearlyEqual(Setting(TEXT("smoke_edge_softness"),0),.04f)&&FMath::IsNearlyEqual(Setting(TEXT("smoke_horizontal_shift"),0),-260.f);
  float GroundUniform=-1;BedMID->GetScalarParameterValue(TEXT("GroundScale"),GroundUniform);WaterMID->GetScalarParameterValue(TEXT("RainAmount"),RainUniform);
  float StreakAmount=-1;RainMID->GetScalarParameterValue(TEXT("RainAmount"),StreakAmount);
  const bool RoundTrip=RecoveryOK&&FMath::IsNearlyEqual(AmbientUniform,.37f)&&Parsed&&FMath::IsNearlyEqual(Setting(TEXT("rain_amount"),0),3.27f)&&FMath::IsNearlyEqual(Setting(TEXT("haze_amount"),0),.54f)&&FMath::IsNearlyEqual(GroundUniform,1.27f)&&FMath::IsNearlyEqual(RainUniform,3.27f)&&FMath::IsNearlyEqual(StreakAmount,3.27f);
  float WidthUniform=-1,SizeUniform=-1;BodyMID->GetScalarParameterValue(TEXT("WetAmount"),WetUniform);BodyMID->GetScalarParameterValue(TEXT("BeadSize"),SizeUniform);RainMID->GetScalarParameterValue(TEXT("RainWidth"),WidthUniform);
  bool SoftValid=false,FrictionValid=false,DissipationValid=false;
  SetStudioParameter(TEXT("water_resting_contact"),1);
  auto CollisionDI=UNiagaraFunctionLibrary::GetDataInterface<UNiagaraDataInterfaceRigidMeshCollisionQuery>(WaterSim,TEXT("User.Collide_Meshes"));
  const bool RestingEnabled=CollisionDI&&CollisionDI->SourceActors.Num()==1;
  SetStudioParameter(TEXT("water_resting_contact"),0);SetWaterContact(false);
  const bool DepthBinding=RestingEnabled&&CollisionDI&&CollisionDI->SourceActors.IsEmpty();
  float Relief=-1;WaterMID->GetScalarParameterValue(TEXT("InteractionStrength"),Relief);
  const bool WaterBindings=DepthBinding&&WaterOff&&FMath::IsNearlyEqual(WaterSim->GetVariableFloat(TEXT("User.ContactStrength"),StrengthValid),.6f)&&StrengthValid
   &&FMath::IsNearlyEqual(WaterSim->GetVariableFloat(TEXT("User.ContactMinSpeed"),ThresholdValid),5.f)&&ThresholdValid
   &&FMath::IsNearlyEqual(WaterSim->GetVariableFloat(TEXT("User.ContactSoftness"),SoftValid),7.f)&&SoftValid
   &&FMath::IsNearlyEqual(WaterSim->GetVariableFloat(TEXT("User.WaterFriction"),FrictionValid),FMath::Lerp(.00025f,.01f,.09f))&&FrictionValid
   &&FMath::IsNearlyEqual(WaterSim->GetVariableFloat(TEXT("User.WaterDissipation"),DissipationValid),FMath::Lerp(.0003f,.05f,.09f))&&DissipationValid&&FMath::IsNearlyEqual(Relief,.8f);
  const FVector BeforeClear=Body->GetComponentLocation();ClearWaterWaves();
  const bool ClearPreserves=Body->GetComponentLocation().Equals(BeforeClear,.001)&&FMath::IsNearlyEqual(Setting(TEXT("collision_min_speed"),0),5.f);
  const FString WaterResult=FString::Printf(TEXT("{\"passed\":%s,\"zero_push_gates_forcing\":%s,\"live_parameters_and_round_trip\":%s,\"clear_preserves_placement\":%s}"),WaterBindings&&ClearPreserves?TEXT("true"):TEXT("false"),WaterOff?TEXT("true"):TEXT("false"),WaterBindings?TEXT("true"):TEXT("false"),ClearPreserves?TEXT("true"):TEXT("false"));
  FFileHelper::SaveStringToFile(WaterResult,*(FPaths::ProjectSavedDir()/TEXT("Validation/collision-controls.json")));
  UE_LOG(LogTemp,Display,TEXT("COLLISION_CONTROLS %s"),*WaterResult);
  const bool Visible=WaterBindings&&ClearPreserves&&RainMesh->IsVisible()&&Smoke.IsVisible()&&SmokeBindings&&SmokeSaved&&FMath::IsNearlyEqual(WetUniform,.67f)&&FMath::IsNearlyEqual(WidthUniform,.08f)&&FMath::IsNearlyEqual(SizeUniform,1.4f);
  const FString Result=FString::Printf(TEXT("{\"passed\":%s,\"disabled_effects_hidden\":%s,\"save_revert_round_trip\":%s,\"enabled_effects_visible\":%s,\"method\":\"Native shared UI callbacks, saved JSON reload and live material readback; no OS mouse injection\"}"),Disabled&&RoundTrip&&Visible?TEXT("true"):TEXT("false"),Disabled?TEXT("true"):TEXT("false"),RoundTrip?TEXT("true"):TEXT("false"),Visible?TEXT("true"):TEXT("false"));
  FFileHelper::SaveStringToFile(Result,*(FPaths::ProjectSavedDir()/TEXT("Validation/weather-controls.json")));
  FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Original),Settings);ApplyWeatherSettings();FFileHelper::SaveStringToFile(Original,*SettingsPath,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
  WriteRecovery();
  SceneStatus=TEXT("Live changes recover automatically. Save look sets the revert point.");
  UE_LOG(LogTemp,Display,TEXT("WEATHER_CONTROLS %s"),*Result);
 }
 void ValidateGizmo(){
  bGizmoValidated=true;
  if(!Gizmo||!FPaths::IsUnderDirectory(FPaths::ConvertRelativePathToFull(SettingsPath),FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir())))return;
  FString Original;FJsonSerializer::Serialize(Settings.ToSharedRef(),TJsonWriterFactory<>::Create(&Original));
  const FVector OriginalOffset=ManualOffset;const FRotator OriginalRotation=Body->GetComponentRotation();
  const bool WasPaused=bPaused;bPaused=true;
  const FGeometry G=Gizmo->GetCachedGeometry();FVector2D BodyPoint;
  ResetBodyPosition();Gizmo->Select(false);
  const bool Projected=Gizmo->Project(G,Body->GetSocketLocation(TEXT("spine_03")),BodyPoint);
  const bool Picked=Projected&&Gizmo->Begin(G,BodyPoint)&&Gizmo->IsSelected();
  bool AxesOK=Picked,CancelOK=false;
  for(int I=0;I<3;++I){
   SetBodyOffset(FVector::ZeroVector);Gizmo->Select(true);
   FVector2D O,E[3],Target;float Lengths[3];
   if(!Gizmo->Handles(G,O,E,Lengths)){AxesOK=false;continue;}
   const FVector A=SSceneGizmo::Axis(I);
   const FVector Start=Gizmo->Anchor();
   FVector2D Press;Gizmo->Project(G,Start+A*(Lengths[I]*.8f),Press);
   const bool Began=Gizmo->Begin(G,Press)&&Gizmo->IsDragging();
   Gizmo->Project(G,Start+A*(Lengths[I]*.8f+40),Target);Gizmo->Move(G,Target);
   UE_LOG(LogTemp,Display,TEXT("GIZMO_AXIS test=%d active=%d began=%d offset=%s start=%s target=%s"),I,Gizmo->ActiveAxis(),Began,*ManualOffset.ToString(),*Press.ToString(),*Target.ToString());
   AxesOK=Began&&ManualOffset.Equals(A*40,.15)&&Body->GetComponentLocation().Equals(FVector(0,140,0)+A*40,.15)&&AxesOK;
   Gizmo->Finish(false);
   if(I==2){
    Gizmo->Handles(G,O,E,Lengths);Gizmo->Begin(G,O+(E[2]-O)*.8);Gizmo->Move(G,O+(E[2]-O)*1.2);Gizmo->Finish(true);
    CancelOK=ManualOffset.Equals(FVector(0,0,40),.15);
   }
  }
  const bool Lifted=Body->GetSocketLocation(TEXT("foot_l")).Z>3.5&&Body->GetSocketLocation(TEXT("foot_r")).Z>3.5;
  // Exercise logical-coordinate scaling independently of the host desktop DPI.
  const FGeometry Scaled=FGeometry::MakeRoot(G.GetLocalSize()*.5,FSlateLayoutTransform(2.f));
  FVector2D SO,SE[3],SP,ST;float SL[3];const FVector BeforeScale=ManualOffset;
  Gizmo->Handles(Scaled,SO,SE,SL);Gizmo->Project(Scaled,Gizmo->Anchor()+FVector(0,0,SL[2]*.8),SP);
  Gizmo->Project(Scaled,Gizmo->Anchor()+FVector(0,0,SL[2]*.8+20),ST);
  const bool ScaleBegin=Gizmo->Begin(Scaled,SP);Gizmo->Move(Scaled,ST);
  AxesOK=AxesOK&&ScaleBegin&&ManualOffset.Equals(BeforeScale+FVector(0,0,20),.15);Gizmo->Finish(true);
  SaveSettings();SetBodyOffset(FVector::ZeroVector);LoadSettings();ApplyWeatherSettings();
  const bool Saved=ManualOffset.Equals(FVector(0,0,40),.15)&&Body->GetComponentLocation().Equals(FVector(0,140,40),.15);
  ResetBodyPosition();const bool Reset=ManualOffset.IsNearlyZero()&&Body->GetComponentLocation().Equals(FVector(0,140,0),.01);
  Gizmo->Select(false);const bool Miss=!Gizmo->Begin(G,FVector2D(G.GetLocalSize().X*.5,25))&&!Gizmo->IsSelected();
  const bool Passed=Picked&&AxesOK&&CancelOK&&Lifted&&Saved&&Reset&&Miss;
  const FString Result=FString::Printf(TEXT("{\"passed\":%s,\"body_pick\":%s,\"xyz_drags\":%s,\"escape_restore\":%s,\"feet_above_water\":%s,\"save_reload\":%s,\"reset_position\":%s,\"empty_click\":%s,\"method\":\"Native shared pick/drag callbacks with actual camera projection and mannequin collision queries; no desktop input\"}"),Passed?TEXT("true"):TEXT("false"),Picked?TEXT("true"):TEXT("false"),AxesOK?TEXT("true"):TEXT("false"),CancelOK?TEXT("true"):TEXT("false"),Lifted?TEXT("true"):TEXT("false"),Saved?TEXT("true"):TEXT("false"),Reset?TEXT("true"):TEXT("false"),Miss?TEXT("true"):TEXT("false"));
  FFileHelper::SaveStringToFile(Result,*(FPaths::ProjectSavedDir()/TEXT("Validation/mannequin-gizmo.json")));UE_LOG(LogTemp,Display,TEXT("GIZMO_VALIDATION %s"),*Result);
  FFileHelper::SaveStringToFile(Original,*SettingsPath,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);LoadSettings();ApplyWeatherSettings();Body->SetWorldRotation(OriginalRotation);WriteRecovery();
  if(FParse::Param(FCommandLine::Get(),TEXT("SceneGizmoPreview"))){SetBodyOffset(OriginalOffset+FVector(0,0,12));Gizmo->Select(true);}
  bPaused=WasPaused;
 }
 void ApplyWaterSettings(){
  if(WaterMID)WaterMID->SetScalarParameterValue(TEXT("InteractionStrength"),FMath::Clamp(Setting(TEXT("interaction_strength"),1),0.f,3.f));
  if(!WaterSim)return;
  const float Strength=FMath::Clamp(Setting(TEXT("collision_strength"),1),0.f,3.f);
  WaterSim->SetVariableFloat(TEXT("User.ContactStrength"),Strength);
  WaterSim->SetVariableFloat(TEXT("User.ContactMinSpeed"),Strength<=0?1.e9f:FMath::Clamp(Setting(TEXT("collision_min_speed"),1),0.f,20.f));
  WaterSim->SetVariableFloat(TEXT("User.ContactSoftness"),FMath::Clamp(Setting(TEXT("collision_softness"),4),.5f,20.f));
  const float Damping=FMath::Clamp(Setting(TEXT("water_damping"),0),0.f,1.f);
  WaterSim->SetVariableFloat(TEXT("User.WaterFriction"),FMath::Lerp(.00025f,.01f,Damping*Damping));
  WaterSim->SetVariableFloat(TEXT("User.WaterDissipation"),FMath::Lerp(.0003f,.05f,Damping*Damping));
  if(Strength<=0||bNoCollision)SetWaterContact(false);
  else if(Setting(TEXT("water_resting_contact"),0)>.5f)SetWaterContact(true);
 }
 void ClearWaterWaves(){if(NormalRT)NormalRT->UpdateResourceImmediate(true);if(WaterSim){WaterSim->ReinitializeSystem();ApplyWaterSettings();WaterSim->SetPaused(bPaused);}SceneStatus=TEXT("Waves cleared. Position and settings retained.");}
 void ApplyWeatherSettings(){
  ApplyWaterSettings();
  if(Body)Body->SetWorldLocation(FVector(0,140,0)+ManualOffset);
  if(WaterMID)WaterMID->SetScalarParameterValue(TEXT("WindStrength"),Setting(TEXT("wind_strength"),.16f));
  if(BedMID){
   BedMID->SetScalarParameterValue(TEXT("GroundScale"),Setting(TEXT("ground_scale"),1));
   BedMID->SetScalarParameterValue(TEXT("GroundShape"),Setting(TEXT("ground_shape"),1));
   BedMID->SetScalarParameterValue(TEXT("GroundDarkness"),Setting(TEXT("ground_darkness"),1));
   BedMID->SetScalarParameterValue(TEXT("GroundContrast"),Setting(TEXT("ground_contrast"),1));
  }
  const float Amount=FMath::Clamp(Setting(TEXT("rain_amount"),.35f),0.f,4.f);
  if(WaterMID){WaterMID->SetScalarParameterValue(TEXT("RainAmount"),Amount);WaterMID->SetScalarParameterValue(TEXT("RainStrength"),Setting(TEXT("rain_ripple_strength"),.35f));WaterMID->SetScalarParameterValue(TEXT("RainSize"),Setting(TEXT("rain_ripple_size"),1));}
  if(RainMID){RainMID->SetScalarParameterValue(TEXT("RainAmount"),Amount);RainMID->SetScalarParameterValue(TEXT("RainSlant"),Setting(TEXT("rain_slant"),.08f));
   RainMID->SetScalarParameterValue(TEXT("RainWidth"),Setting(TEXT("rain_width"),.12f));RainMID->SetScalarParameterValue(TEXT("RainLength"),Setting(TEXT("rain_length"),18));
   RainMID->SetScalarParameterValue(TEXT("RainGust"),Setting(TEXT("rain_gust"),.65f));RainMID->SetScalarParameterValue(TEXT("RainBrightness"),Setting(TEXT("rain_brightness"),2.4f));}
  if(RainMesh)RainMesh->SetVisibility(Amount>.0001f);
  Smoke.Apply(Setting(TEXT("haze_amount"),.65f),Setting(TEXT("haze_height"),350),Setting(TEXT("haze_spread"),1),Setting(TEXT("smoke_roll"),.65f),Setting(TEXT("haze_speed"),.12f),Setting(TEXT("smoke_horizontal_shift"),200),Setting(TEXT("smoke_horizontal_width"),1));
  SceneVolume.ApplyAtmosphere(Setting(TEXT("fog_amount"),0));
  UpdateSmokeBoundary();
  if(BodyMID){
   BodyMID->SetScalarParameterValue(TEXT("WetAmount"),Setting(TEXT("wet_amount"),.65f));BodyMID->SetScalarParameterValue(TEXT("BeadDensity"),Setting(TEXT("bead_density"),.55f));
   BodyMID->SetScalarParameterValue(TEXT("BeadSize"),Setting(TEXT("bead_size"),1));BodyMID->SetScalarParameterValue(TEXT("BeadStrength"),Setting(TEXT("bead_strength"),.65f));
   BodyMID->SetScalarParameterValue(TEXT("RunoffSpeed"),Setting(TEXT("runoff_speed"),.3f));BodyMID->SetScalarParameterValue(TEXT("TrailAmount"),Setting(TEXT("trail_amount"),.45f));
  }
 }
 static float RainHash(int32 X,int32 Y,uint32 Salt){uint32 H=uint32(X)*374761393u+uint32(Y)*668265263u+Salt*1442695041u;H=(H^(H>>13))*1274126177u;H=H^(H>>16);return float(H&0x00ffffffu)/16777216.f;}
 void MakeWeather(){
  auto RainActor=World->SpawnActor<AActor>();RainActor->SetActorLabel(TEXT("Deterministic rain streaks - paired with surface impacts"));
  RainMesh=NewObject<UInstancedStaticMeshComponent>(RainActor);RainActor->SetRootComponent(RainMesh);RainMesh->RegisterComponent();
  RainMesh->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Plane.Plane")));
  RainMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);RainMesh->SetCastShadow(false);RainMesh->SetBoundsScale(3);RainMesh->NumCustomDataFloats=3;
  RainMID=UMaterialInstanceDynamic::Create(Mat(TEXT("M_RainStreak")),RainMesh);RainMesh->SetMaterial(0,RainMID);
  TArray<FTransform> Instances;TArray<FVector> Seeds;
  // Four independently jittered layers; layer zero preserves existing looks.
  for(int Layer=0;Layer<4;++Layer)for(int Y=-80;Y<=80;++Y)for(int X=-17;X<=135;++X){
   const uint32 Salt=97*Layer;
   const FVector Point((X+.1f+.8f*RainHash(X,Y,1+Salt))*22,(Y+.1f+.8f*RainHash(X,Y,2+Salt))*22,3.5f);
   Instances.Add(FTransform(FRotator(90,0,0),Point,FVector(.075f,.004f,1)));
   Seeds.Add(FVector(RainHash(X,Y,3+Salt),Layer+RainHash(X,Y,5+Salt),Point.Y));
  }
  RainMesh->AddInstances(Instances,false,false,false);
  for(int I=0;I<Seeds.Num();++I){RainMesh->SetCustomDataValue(I,0,Seeds[I].X,false);RainMesh->SetCustomDataValue(I,1,Seeds[I].Y,false);RainMesh->SetCustomDataValue(I,2,Seeds[I].Z,false);}
  RainMesh->MarkRenderStateDirty();
  SceneVolume.Build(World,nullptr);Smoke.Build(World);
  ApplyWeatherSettings();
 }
 void SetControlsVisible(bool Visible){
  bControlsVisible=Visible;
  if(Gizmo){Gizmo->Finish(false);Gizmo->SetVisibility(Visible?EVisibility::Visible:EVisibility::Collapsed);}
  if(auto PC=World->GetFirstPlayerController()){
   PC->bShowMouseCursor=Visible;
   if(Visible){FInputModeGameAndUI Mode;Mode.SetHideCursorDuringCapture(false);Mode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);PC->SetInputMode(Mode);}
   else PC->SetInputMode(FInputModeGameOnly());
  }
 }
 void MakeControls(){
  FSceneControlsCallbacks C;
  C.InitialTab=FParse::Param(FCommandLine::Get(),TEXT("SceneWaterTab"))?4:bBodyCloseup?3:FParse::Param(FCommandLine::Get(),TEXT("SceneGroundTab"))?0:(FParse::Param(FCommandLine::Get(),TEXT("SceneAirTab"))?2:1);
  C.Get=[this](FName Key,float Default){return Setting(*Key.ToString(),Default);};
  C.Set=[this](FName Key,float Value){SetStudioParameter(Key,Value);};
  C.ResetPosition=[this](){ResetBodyPosition();};C.ClearWaves=[this](){ClearWaterWaves();};
  C.Save=[this](){SaveSettings();};C.Revert=[this](){LoadSettings();ApplyWeatherSettings();WriteRecovery();SceneStatus=TEXT("Restored the saved look.");};
  C.StatusText=[this](){return FText::FromString(SceneStatus);};
  C.BodyView=[this](){return bBodyCloseup;};C.ToggleBodyView=[this](){bBodyCloseup=!bBodyCloseup;UpdateCamera();};
  Gizmo=SNew(SSceneGizmo).Controller(World->GetFirstPlayerController()).Body(Body)
   .GetOffset([this](){return ManualOffset;}).SetOffset([this](FVector P){SetBodyOffset(P);});
  GEngine->GameViewport->AddViewportWidgetContent(Gizmo.ToSharedRef(),10);
  ControlsRoot=SNew(SBox).Padding(16).Visibility_Lambda([this](){return bControlsVisible?EVisibility::SelfHitTestInvisible:EVisibility::Collapsed;})[MakeSceneControls(MoveTemp(C))];
  GEngine->GameViewport->AddViewportWidgetContent(ControlsRoot.ToSharedRef(),20);SetControlsVisible(bControlsVisible);
 }
 void UpdateCamera(){
  if(!Camera)return;
  if(bBodyCloseup){Camera->SetActorLocationAndRotation(FVector(-185,140,135)+ManualOffset,FRotator::ZeroRotator);Camera->GetCameraComponent()->SetFieldOfView(42);}
  else{Camera->SetActorLocationAndRotation(FVector(Setting(TEXT("camera_x"),-465),Setting(TEXT("camera_y"),35),Setting(TEXT("camera_z"),64)),FRotator(Setting(TEXT("camera_pitch"),1.3f),0,0));Camera->GetCameraComponent()->SetFieldOfView(Setting(TEXT("camera_fov"),51));}
  UpdateSmokeBoundary();
 }
 void UpdateSmokeBoundary(){
  if(!Camera)return;
  const float HalfV=FMath::Tan(FMath::DegreesToRadians(Camera->GetCameraComponent()->FieldOfView*.5f))/(16.f/9.f);
  const float Edge=FMath::Clamp(Setting(TEXT("smoke_lower_edge"),.28f),.05f,.65f);
  const FVector N=(Camera->GetActorUpVector()-Camera->GetActorForwardVector()*((1-2*Edge)*HalfV)).GetSafeNormal();
  const FVector Eye=Camera->GetActorLocation();
  const float Distance=FMath::Max(300.f,float(FVector::DotProduct(FVector(850,140,Setting(TEXT("haze_height"),350))-Eye,Camera->GetActorForwardVector())));
  Smoke.SetCutoffPlane(FVector4(N,-FVector::DotProduct(N,Eye)),2*Distance*HalfV*Setting(TEXT("smoke_edge_softness"),.06f));
 }

 UMaterialInterface* Mat(const TCHAR* Name){return LoadObject<UMaterialInterface>(nullptr,*FString::Printf(TEXT("/Game/MenuScene/%s.%s"),Name,Name));}
 AStaticMeshActor* Static(const FString& Name,FVector P,FVector Scale,UMaterialInterface* M,const TCHAR* Mesh=TEXT("/Engine/BasicShapes/Plane.Plane")){
  auto A=World->SpawnActor<AStaticMeshActor>(P,FRotator::ZeroRotator);A->SetActorLabel(Name);
  auto C=A->GetStaticMeshComponent();C->SetMobility(EComponentMobility::Movable);C->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,Mesh));C->SetMaterial(0,M);C->SetCollisionEnabled(ECollisionEnabled::NoCollision);A->SetActorScale3D(Scale);return A;
 }
 void Rect(const FString& Name,FVector P,FVector Target,FLinearColor Color,float Intensity,float Width,float Height){
  auto A=World->SpawnActor<ARectLight>(P,(Target-P).Rotation());A->SetActorLabel(Name);
  auto L=Cast<URectLightComponent>(A->GetLightComponent());L->SetMobility(EComponentMobility::Movable);L->SetIntensityUnits(ELightUnits::Lumens);L->SetIntensity(Intensity*Setting(TEXT("light_gain"),1));L->SetLightColor(Color);L->SetSourceWidth(Width);L->SetSourceHeight(Height);L->SetAttenuationRadius(4000);L->SetCastShadows(true);
 }
 void MakeWater(){
  auto A=World->SpawnActor<AActor>();A->SetActorLabel(TEXT("Shallow crimson water - live height field"));
  auto Mesh=NewObject<UProceduralMeshComponent>(A);A->SetRootComponent(Mesh);Mesh->RegisterComponent();Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);Mesh->SetCastShadow(false);
  TArray<float> Axis;Axis.Add(-20000);Axis.Add(-6000);Axis.Add(-2000);
  for(int I=0;I<=160;++I)Axis.Add(-1000.f+I*12.5f);
  Axis.Add(2000);Axis.Add(6000);Axis.Add(20000);
  const int N=Axis.Num();TArray<FVector> V,Normals;TArray<int32> Tris;TArray<FVector2D> UV;TArray<FProcMeshTangent> Tangents;
  for(int Y=0;Y<N;++Y)for(int X=0;X<N;++X){V.Add(FVector(Axis[X],Axis[Y],3.5));Normals.Add(FVector::UpVector);UV.Add(FVector2D(Axis[X]/100,Axis[Y]/100));Tangents.Add(FProcMeshTangent(1,0,0));}
  for(int Y=0;Y<N-1;++Y)for(int X=0;X<N-1;++X){int I=Y*N+X;Tris.Append({I,I+N,I+1,I+1,I+N,I+N+1});}
  Mesh->CreateMeshSection_LinearColor(0,V,Tris,Normals,UV,TArray<FLinearColor>(),Tangents,false);
  WaterMID=UMaterialInstanceDynamic::Create(Mat(TEXT("M_Water")),Mesh);Mesh->SetMaterial(0,WaterMID);
  WaterMID->SetScalarParameterValue(TEXT("WaterRoughness"),Setting(TEXT("water_roughness"),.115f));
  WaterMID->SetScalarParameterValue(TEXT("WindStrength"),Setting(TEXT("wind_strength"),.16f));
  WaterMID->SetScalarParameterValue(TEXT("InteractionStrength"),Setting(TEXT("interaction_strength"),1));
  WaterMID->SetVectorParameterValue(TEXT("FieldOrigin"),FLinearColor(FieldOrigin.X,FieldOrigin.Y,0,0));
  auto Reflect=World->SpawnActor<APlanarReflection>(FVector(0,0,3.5),FRotator::ZeroRotator);
  Reflect->SetActorLabel(TEXT("Live reflected mannequin and offscreen studio lights"));Reflect->SetActorScale3D(FVector(200,200,1));
  auto R=Reflect->GetPlanarReflectionComponent();R->NormalDistortionStrength=Setting(TEXT("reflection_distortion"),140);R->PrefilterRoughness=.025f;R->PrefilterRoughnessDistance=500;R->ScreenPercentage=100;R->ExtraFOV=0;R->DistanceFromPlaneFadeoutStart=50;R->DistanceFromPlaneFadeoutEnd=150;R->AngleFromPlaneFadeStart=45;R->AngleFromPlaneFadeEnd=85;R->bShowPreviewPlane=false;R->bRenderSceneTwoSided=true;R->HiddenActors.Add(A);R->ShowFlags.SetSkeletalMeshes(true);R->MarkRenderStateDirty();
 }
 void SetWaterContact(bool Active){
  if(!WaterSim||!Body||Active==bWaterContactActive)return;
  bWaterContactActive=Active;
  UNiagaraDIRigidMeshCollisionFunctionLibrary::SetSourceActors(WaterSim,TEXT("User.Collide_Meshes"),Active?TArray<AActor*>{Body->GetOwner()}:TArray<AActor*>{});
 }
 void UpdateWaterContact(float Delta){
  if(!Body||!WaterSim||!Body->GetPhysicsAsset()||Delta<=1.e-6f||bPaused)return;
  const auto& Setups=Body->GetPhysicsAsset()->SkeletalBodySetups;
  const bool HavePrevious=PreviousContactBones.Num()==Setups.Num();
  PreviousContactBones.SetNum(Setups.Num());ContactSpeed=0;
  for(int32 I=0;I<Setups.Num();++I){
   const auto Setup=Setups[I];if(!Setup)continue;
   const int32 Bone=Body->GetBoneIndex(Setup->BoneName);if(Bone==INDEX_NONE)continue;
   const FTransform Current=Body->GetBoneTransform(Bone);
   const FBox Bounds=Setup->AggGeom.CalcAABB(Current);
   if(HavePrevious&&Bounds.IsValid&&Bounds.Min.Z<=3.5){
    const FBox Local=Setup->AggGeom.CalcAABB(FTransform::Identity);
    const FVector Center=Local.GetCenter(),Extent=Local.GetExtent();
    const FVector Points[]={Center,Center+FVector(Extent.X,0,0),Center-FVector(Extent.X,0,0),Center+FVector(0,Extent.Y,0),Center-FVector(0,Extent.Y,0),Center+FVector(0,0,Extent.Z),Center-FVector(0,0,Extent.Z)};
    for(const FVector& P:Points){const FVector V=(Current.TransformPosition(P)-PreviousContactBones[I].TransformPosition(P))/Delta;ContactSpeed=FMath::Max(ContactSpeed,float(V.Size2D()));}
   }
   PreviousContactBones[I]=Current;
  }
  PeakContactSpeed=FMath::Max(PeakContactSpeed,ContactSpeed);
  const float Threshold=FMath::Max(.01f,Setting(TEXT("collision_min_speed"),1));
  if(ContactSpeed>Threshold)ContactHold=.08f;else ContactHold=FMath::Max(0.f,ContactHold-Delta);
  SetWaterContact(!bNoCollision&&Setting(TEXT("collision_strength"),1)>0&&(Setting(TEXT("water_resting_contact"),0)>.5f||ContactHold>0));
  if(bWaterContactActive)++ContactFrames;
 }
 void ConfigureWaterProviders(){
  WaterSim->SetVariableVec2(TEXT("WorldGridSize"),FVector2D(1000,1000));
  WaterSim->SetVariableInt(TEXT("ResolutionMaxAxis"),512);
  WaterSim->SetVariableTextureRenderTarget(TEXT("NormalRT"),NormalRT);
  WaterSim->SetVariableFloat(TEXT("BottomDepth"),-3.5f);
  WaterSim->SetVariableFloat(TEXT("WaterHeightAtParent"),3.5f);
  WaterSim->SetVariableFloat(TEXT("SecondsUntilDestroyed"),36000);
  WaterSim->SetVariableBool(TEXT("UseBakedSim"),false);
  WaterSim->SetVariableBool(TEXT("UseWaterInfoTexture"),false);
  WaterSim->SetVariableBool(TEXT("UseDebugRender"),false);
  WaterSim->SetVariableBool(TEXT("PlayerIsInWater"),true);
  Body->ComponentTags.AddUnique(TEXT("RigidMesh_ShallowWaterCollider"));
  // Explicit providers avoid relying on overlap discovery: the copied PHAT supplies the shapes.
  UNiagaraDIRigidMeshCollisionFunctionLibrary::SetSourceActors(WaterSim,TEXT("User.Collide_Meshes"),bNoCollision||!bWaterContactActive?TArray<AActor*>{}:TArray<AActor*>{Body->GetOwner()});
  if(auto DI=UNiagaraFunctionLibrary::GetDataInterface<UNiagaraDataInterfaceRigidMeshCollisionQuery>(WaterSim,TEXT("User.Collide_Meshes"))){DI->ComponentTags={TEXT("RigidMesh_ShallowWaterCollider")};DI->ActorTags.Empty();UE_LOG(LogTemp,Display,TEXT("WATER_PHAT asset=%s actors=%d ownerComponents=%d"),*GetNameSafe(Body->GetPhysicsAsset()),DI->SourceActors.Num(),Body->GetOwner()->GetComponents().Num());}
 }
 void MakeSimulation(){
  NormalRT=NewObject<UTextureRenderTarget2D>(WaterMID);NormalRT->RenderTargetFormat=RTF_RGBA16f;
  NormalRT->ClearColor=FLinearColor(0,0,0,0);NormalRT->bAutoGenerateMips=false;NormalRT->bCanCreateUAV=true;
  NormalRT->InitAutoFormat(512,512);NormalRT->UpdateResourceImmediate(true);
  auto Template=LoadObject<UNiagaraSystem>(nullptr,TEXT("/Game/MenuScene/NS_CrimsonShallowWater.NS_CrimsonShallowWater"));
  if(!Template)return;
  Template->WaitForCompilationComplete(true,false);
  WaterSim=UNiagaraFunctionLibrary::SpawnSystemAtLocation(World,Template,FVector(FieldOrigin,0),FRotator::ZeroRotator,FVector::OneVector,false,false,ENCPoolMethod::None,false);
  if(!WaterSim){UE_LOG(LogTemp,Error,TEXT("Epic shallow water could not initialize"));return;}
  ConfigureWaterProviders();
  WaterMID->SetTextureParameterValue(TEXT("WaterField"),NormalRT);
  ApplyWaterSettings();WaterSim->Activate(true);
 }
 void Build(){
  LoadSettings(true);
  IFileManager::Get().MakeDirectory(*(FPaths::ProjectSavedDir()/TEXT("Validation")),true);
  auto Ground=Static(TEXT("Crimson mineral bed below 3.5cm water"),FVector(0,0,0),FVector(400,400,1),Mat(TEXT("M_Ground")));
  BedMID=UMaterialInstanceDynamic::Create(Mat(TEXT("M_Ground")),Ground);BedMID->SetScalarParameterValue(TEXT("BedGlow"),Setting(TEXT("bed_glow"),.32f));Ground->GetStaticMeshComponent()->SetMaterial(0,BedMID);
  MakeWater();
  auto Actor=World->SpawnActor<AActor>();Actor->SetActorLabel(TEXT("Animated UEFN mannequin - read-only copied assets"));
  Body=NewObject<USkeletalMeshComponent>(Actor);Actor->SetRootComponent(Body);Body->RegisterComponent();
  Body->SetSkeletalMesh(LoadObject<USkeletalMesh>(nullptr,TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin")));
  Body->SetCollisionResponseToAllChannels(ECR_Ignore);Body->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);Body->SetCollisionEnabled(ECollisionEnabled::QueryOnly);Body->SetDisablePostProcessBlueprint(true);Body->SetComponentTickEnabled(false);
  Body->SetWorldLocationAndRotation(FVector(0,140,0)+ManualOffset,FRotator(0,Setting(TEXT("mannequin_yaw"),25),0));
  Body->SetWorldScale3D(FVector(Setting(TEXT("mannequin_scale"),1.12f)));
  BodyMID=UMaterialInstanceDynamic::Create(Mat(TEXT("M_Mannequin")),Body);BodyMID->SetScalarParameterValue(TEXT("BodyRoughness"),Setting(TEXT("body_roughness"),.3f));
  for(int I=0;I<Body->GetNumMaterials();++I)Body->SetMaterial(I,FParse::Param(FCommandLine::Get(),TEXT("SceneReflectionProbe"))?Mat(TEXT("M_Softbox")):BodyMID);
  Idle=LoadObject<UAnimSequence>(nullptr,TEXT("/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Neutral_Stand_Idle_Loop.M_Neutral_Stand_Idle_Loop"));
  StepClip=LoadObject<UAnimSequence>(nullptr,TEXT("/Game/Characters/UEFN_Mannequin/Animations/Avoidance/M_Neutral_avoid_idle_move_1_0m_RR_Rfoot.M_Neutral_avoid_idle_move_1_0m_RR_Rfoot"));
  WalkClip=LoadObject<UAnimSequence>(nullptr,TEXT("/Game/Characters/UEFN_Mannequin/Animations/Walk/M_Neutral_Walk_Loop_F.M_Neutral_Walk_Loop_F"));
  if(Idle)Idle->AddToRoot();if(StepClip)StepClip->AddToRoot();if(WalkClip)WalkClip->AddToRoot();
  ActiveClip=bDemo?StepClip:Idle;Body->PlayAnimation(ActiveClip,true);Body->SetPosition(0,false);Body->TickAnimation(0,false);Body->RefreshBoneTransforms();
  MakeSimulation();
  Camera=World->SpawnActor<ACameraActor>(FVector(Setting(TEXT("camera_x"),-465),Setting(TEXT("camera_y"),35),Setting(TEXT("camera_z"),64)),FRotator(Setting(TEXT("camera_pitch"),1.3f),0,0));
  Camera->GetCameraComponent()->SetFieldOfView(Setting(TEXT("camera_fov"),51));Camera->GetCameraComponent()->SetConstraintAspectRatio(true);Camera->GetCameraComponent()->SetAspectRatio(16.f/9);
  if(auto PC=World->GetFirstPlayerController()){PC->SetViewTarget(Camera);PC->bShowMouseCursor=false;if(auto Pawn=PC->GetPawn())Pawn->SetActorHiddenInGame(true);}
  auto PP=World->SpawnActor<APostProcessVolume>();PP->bUnbound=true;
  auto& S=PP->Settings;S.bOverride_AutoExposureMethod=true;S.AutoExposureMethod=AEM_Manual;
  S.bOverride_AutoExposureBias=true;S.AutoExposureBias=Setting(TEXT("exposure_bias"),0);S.bOverride_AutoExposureApplyPhysicalCameraExposure=true;S.AutoExposureApplyPhysicalCameraExposure=false;
  S.bOverride_BloomIntensity=true;S.BloomIntensity=.3f;S.bOverride_BloomThreshold=true;S.BloomThreshold=.8f;
  S.bOverride_VignetteIntensity=true;S.VignetteIntensity=.24f;S.bOverride_MotionBlurAmount=true;S.MotionBlurAmount=0;
  S.bOverride_AmbientOcclusionIntensity=true;S.AmbientOcclusionIntensity=.65f;S.bOverride_AmbientOcclusionRadius=true;S.AmbientOcclusionRadius=20;
  Rect(TEXT("Pearl rim - crown and right shoulder"),FVector(80,270,380),FVector(0,140,100),FLinearColor(1,.88f,.81f),24000,65,180);
  Rect(TEXT("Cool silver edge - left arm"),FVector(-120,-70,200),FVector(0,140,95),FLinearColor(.78f,.85f,1),5000,75,160);
  Rect(TEXT("Soft frontal shape"),FVector(-310,160,280),FVector(0,140,100),FLinearColor(1,.95f,.9f),2800,210,200);
  Rect(TEXT("Crimson bounce"),FVector(70,80,30),FVector(0,140,110),FLinearColor(1,.012f,.008f),100,140,60);
  Rect(TEXT("Low silver edge and its water reflection"),FVector(-120,310,75),FVector(0,140,55),FLinearColor(1,.92f,.87f),1300,35,110);
  Rect(TEXT("Soft upper volume backlight"),FVector(500,-650,1000),FVector(950,150,450),FLinearColor(.75f,.83f,1),90000,700,500);
  // Visible only in the reflection: actual emissive studio strips above the frame.
  const float Ys[]={-3870,-3055,-1070,142,886,2935,3869};
  for(int I=0;I<7;++I){
   auto Card=Static(FString::Printf(TEXT("Reflected softbox %d"),I+1),FVector(8000,Ys[I],1500),FVector(30.f,1.8f+I%3*.4f,1),Mat(TEXT("M_Softbox")));
   Card->SetActorRotation(FRotator(90,0,0));
   Card->GetStaticMeshComponent()->SetVisibleInSceneCaptureOnly(true);
  }
  auto Fill=World->SpawnActor<ADirectionalLight>(FVector(0,0,800),FRotator(-72,20,0));Fill->GetLightComponent()->SetIntensity(.025f);Fill->GetLightComponent()->SetLightColor(FLinearColor(1,.7f,.6f));Fill->GetLightComponent()->SetCastShadows(false);
  MakeWeather();MakeControls();UpdateCamera();
  GEngine->SetMaxFPS(60);
  UE_LOG(LogTemp,Display,TEXT("SCENE_READY mesh=%s idle=%s step=%s"),*GetNameSafe(Body->GetSkeletalMeshAsset()),*GetNameSafe(Idle),*GetNameSafe(StepClip));
  bBuilt=true;
 }
 void FixedTick(){
  Time+=1.f/60.f;AnimTime+=1.f/60.f;
  if(Body&&Idle&&StepClip){
   float T=0;
   if(bDemo){const float Len=StepClip->GetPlayLength();const float Cycle=2*Len+3;const float Q=FMath::Fmod(AnimTime,Cycle);T=Q<Len?Q:Q<Len+1.5f?Len:Q<2*Len+1.5f?2*Len+1.5f-Q:0;}
   else T=FMath::Fmod(AnimTime,Idle->GetPlayLength());
   FVector Direction=FVector::ZeroVector;
   if(Input){Direction.X=float(Input->Held.Contains(EKeys::W))-float(Input->Held.Contains(EKeys::S));Direction.Y=float(Input->Held.Contains(EKeys::D))-float(Input->Held.Contains(EKeys::A));}
   if(bMoveTest&&Time>2&&Time<3)Direction.Y=-1;
   if(Gizmo&&Gizmo->IsDragging())Direction=FVector::ZeroVector;
   if(!Direction.IsNearlyZero())SetBodyOffset(ManualOffset+Direction.GetClampedToMaxSize(1)*(bMoveTest?MoveSpeed/60.f:1.5f));
   Body->SetWorldLocation(FVector(0,140,0)+ManualOffset);
   UAnimSequence* DesiredClip=bDemo?StepClip:Idle;
   if(!Direction.IsNearlyZero()&&!bMoveTest&&WalkClip){DesiredClip=WalkClip;T=FMath::Fmod(AnimTime,WalkClip->GetPlayLength());Body->SetWorldRotation(Direction.Rotation());}
   if(DesiredClip!=ActiveClip){ActiveClip=DesiredClip;Body->PlayAnimation(ActiveClip,true);}
   if(FParse::Param(FCommandLine::Get(),TEXT("SceneFreezeBody")))T=0;
   Body->SetPosition(T,false);Body->TickAnimation(0,false);Body->RefreshBoneTransforms();
  }
  WaterMID->SetScalarParameterValue(TEXT("SceneTime"),Time);
  if(bBodyCloseup&&(!Gizmo||!Gizmo->IsDragging()))UpdateCamera();
  if(Setting(TEXT("rain_amount"),.35f)>.0001f){RainClock+=Setting(TEXT("rain_speed"),1)/60.f;WaterMID->SetScalarParameterValue(TEXT("RainTime"),RainClock);if(RainMID)RainMID->SetScalarParameterValue(TEXT("RainTime"),RainClock);}
  if(Setting(TEXT("haze_amount"),.65f)>.0001f)HazeClock+=Setting(TEXT("haze_speed"),.12f)/60.f;
  if(Setting(TEXT("wet_amount"),.65f)>.0001f&&Setting(TEXT("runoff_speed"),.3f)>.0001f){WetClock+=1.f/60.f;if(BodyMID)BodyMID->SetScalarParameterValue(TEXT("WetTime"),WetClock);}
 }
 void Report(){
  TArray<FLinearColor> Pixels;if(NormalRT)NormalRT->GameThread_GetRenderTargetResource()->ReadLinearColorPixels(Pixels,FReadSurfaceDataFlags(RCM_MinMax));
  FLinearColor Min(FLT_MAX,FLT_MAX,FLT_MAX,FLT_MAX),Max(-FLT_MAX,-FLT_MAX,-FLT_MAX,-FLT_MAX),Mean(0,0,0,0);double Energy=0;
  for(const auto& C:Pixels){for(int I=0;I<4;++I){Min.Component(I)=FMath::Min(Min.Component(I),C.Component(I));Max.Component(I)=FMath::Max(Max.Component(I),C.Component(I));Mean.Component(I)+=C.Component(I)/Pixels.Num();}Energy+=C.R*C.R+C.G*C.G;}
  const FString R=FString::Printf(TEXT("{\"framework\":\"Epic WaterAdvanced Niagara\",\"scene_seconds\":%.4f,\"pixels\":%d,\"min\":\"%s\",\"max\":\"%s\",\"mean\":\"%s\",\"rg_energy\":%.9f,\"collision_enabled\":%s,\"manual_offset_cm\":%.4f}"),Time,Pixels.Num(),*Min.ToString(),*Max.ToString(),*Mean.ToString(),Pixels.Num()?Energy/Pixels.Num():0,bNoCollision?TEXT("false"):TEXT("true"),ManualOffset.Size());
  TSharedPtr<FJsonObject> Report;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(R),Report);
  Report->SetNumberField(TEXT("contact_speed_cm_s"),ContactSpeed);Report->SetNumberField(TEXT("peak_contact_speed_cm_s"),PeakContactSpeed);Report->SetNumberField(TEXT("contact_active_frames"),ContactFrames);
  Report->SetObjectField(TEXT("settings"),Settings);Report->SetNumberField(TEXT("rain_clock"),RainClock);Report->SetNumberField(TEXT("haze_clock"),HazeClock);
  Report->SetNumberField(TEXT("rain_instances"),RainMesh?RainMesh->GetInstanceCount():0);Report->SetBoolField(TEXT("controls_visible"),bControlsVisible);
  int32 ActiveRainSeeds=0;const float RainAmount=FMath::Clamp(Setting(TEXT("rain_amount"),.35f),0.f,4.f);
  for(int Layer=0;Layer<4;++Layer)for(int Y=-80;Y<=80;++Y)for(int X=-17;X<=135;++X)
   if(Layer+RainHash(X,Y,5+97*Layer)<RainAmount)++ActiveRainSeeds;
  Report->SetNumberField(TEXT("rain_density_percent"),RainAmount*25);
  Report->SetNumberField(TEXT("rain_active_seeds"),ActiveRainSeeds);
  Report->SetNumberField(TEXT("rain_impacts_per_second_full_field"),ActiveRainSeeds*Setting(TEXT("rain_speed"),1)/1.6);
  if(Smoke.Component){
   bool VelocityValid=false,BuoyancyValid=false;
   const FVector Velocity=Smoke.Component->GetVariableVec3(TEXT("User.SmokeVelocity"),VelocityValid);
   const float Buoyancy=Smoke.Component->GetVariableFloat(TEXT("User.SmokeDensityBuoyancy"),BuoyancyValid);
   bool SourceScaleValid=false,GridSizeValid=false;
   Report->SetStringField(TEXT("smoke_source_scale"),Smoke.Component->GetVariableVec3(TEXT("User.SmokeSourceScale"),SourceScaleValid).ToString());
   Report->SetStringField(TEXT("smoke_grid_size"),Smoke.Component->GetVariableVec3(TEXT("User.WorldSpaceSize"),GridSizeValid).ToString());
   Report->SetStringField(TEXT("smoke_source_velocity"),Velocity.ToString());
   Report->SetNumberField(TEXT("smoke_density_buoyancy"),Buoyancy);
   Report->SetBoolField(TEXT("smoke_flow_bindings_valid"),VelocityValid&&BuoyancyValid);
  }
  Report->SetStringField(TEXT("smoke_framework"),TEXT("Epic NiagaraFluids Grid3D Gas Smoke, native volume renderer"));Report->SetNumberField(TEXT("wet_clock"),WetClock);
  TArray<TSharedPtr<FJsonValue>> VolumeSizes;
  for(TObjectIterator<UTextureRenderTargetVolume> It;It;++It){
   auto Entry=MakeShared<FJsonObject>();Entry->SetStringField(TEXT("name"),It->GetName());
   Entry->SetNumberField(TEXT("x"),It->SizeX);Entry->SetNumberField(TEXT("y"),It->SizeY);Entry->SetNumberField(TEXT("z"),It->SizeZ);
   VolumeSizes.Add(MakeShared<FJsonValueObject>(Entry));
  }
  Report->SetArrayField(TEXT("volume_render_targets"),VolumeSizes);
  if(Body){Report->SetStringField(TEXT("foot_l"),Body->GetSocketLocation(TEXT("foot_l")).ToString());Report->SetStringField(TEXT("foot_r"),Body->GetSocketLocation(TEXT("foot_r")).ToString());}
  if(!CapturePath.IsEmpty()&&!Pixels.IsEmpty())FFileHelper::SaveArrayToFile(TArrayView<const uint8>(reinterpret_cast<const uint8*>(Pixels.GetData()),Pixels.Num()*sizeof(FLinearColor)),*FPaths::ChangeExtension(CapturePath,TEXT("normals.f32")));
  FString Full;FJsonSerializer::Serialize(Report.ToSharedRef(),TJsonWriterFactory<>::Create(&Full));
  FFileHelper::SaveStringToFile(Full,*(FPaths::ProjectSavedDir()/TEXT("Validation/runtime.json")));
  if(!CapturePath.IsEmpty())FFileHelper::SaveStringToFile(Full,*(FPaths::ChangeExtension(CapturePath,TEXT("json"))));
 }
 void Capture(){IFileManager::Get().MakeDirectory(*(FPaths::ProjectSavedDir()/TEXT("Captures")),true);FScreenshotRequest::RequestScreenshot(CapturePath.IsEmpty()?FPaths::ProjectSavedDir()/TEXT("Captures/latest.png"):CapturePath,bCaptureUI,false);Report();}
 bool Tick(float Delta){
  if(!bBuilt){if(!GEngine||!GEngine->GameViewport||!GEngine->GameViewport->GetWorld()||!GEngine->GameViewport->GetWorld()->GetFirstPlayerController())return true;World=GEngine->GameViewport->GetWorld();Build();if(GEngine->GameViewport->GetWindow())GEngine->GameViewport->GetWindow()->SetTitle(FText::FromString(TEXT("Prophecy | Rain and Water Studio - Tab: controls  WASD: walk  P: pause")));}
  Alive+=FMath::Min(Delta,.1f);
  if(RecoveryDelay>=0){RecoveryDelay-=Delta;if(RecoveryDelay<=0)WriteRecovery();}
  // Local IPC lets the build tooling checkpoint the exact live settings without
  // sending desktop input. Implementation-only addition is safe to hot patch.
  if(GFrameCounter%30==0){
   const FString SaveRequest=FPaths::ProjectSavedDir()/TEXT("save-look.request");
   if(FPaths::FileExists(SaveRequest)){SaveSettings();IFileManager::Get().Delete(*SaveRequest);}
  }
  ShadersStable=(!GShaderCompilingManager||!GShaderCompilingManager->IsCompiling())?ShadersStable+FMath::Min(Delta,.1f):0;
  if(bValidateControls&&!bControlsValidated&&Alive>.8f)ValidateControls();
  if(bValidateGizmo&&!bGizmoValidated&&Alive>2)ValidateGizmo();
  if(!bPaused){Accumulator+=FMath::Min(Delta,.1f);int Steps=0;while(Accumulator>=1.f/60.f&&Steps++<6){FixedTick();Accumulator-=1.f/60.f;if(PoseTime>=0&&Time>=PoseTime){bPaused=true;break;}}}
  UpdateWaterContact(Delta);
  if(WaterSim)WaterSim->SetPaused(bPaused);
  Smoke.Tick(Delta);Smoke.SetPaused(bPaused);
  if(!CapturePath.IsEmpty()&&!bCaptureRequested&&Alive>12&&ShadersStable>3&&(PoseTime<0||Time>=PoseTime)){Capture();bCaptureRequested=true;ExitAt=FPlatformTime::Seconds()+2;}
  if(bCaptureRequested&&FPlatformTime::Seconds()>ExitAt&&FParse::Param(FCommandLine::Get(),TEXT("SceneExitAfterCapture")))FPlatformMisc::RequestExit(false);
  return true;
 }
public:
 virtual void StartupModule()override{
#if WITH_EDITOR
  if(FParse::Param(FCommandLine::Get(),TEXT("WaterPrepare"))){RegisterWetPreparation();RegisterSmokePreparation();bool OK=PrepareSceneWater();UE_LOG(LogTemp,Display,TEXT("WATER_PREPARE_SAVED=%d"),OK);return;}
#endif
  if(FParse::Param(FCommandLine::Get(),TEXT("WaterAudit"))){
   FString Out;
   for(const TCHAR* Path:{TEXT("/WaterAdvanced/Niagara/Systems/Grid2D_SW_WaterBody.Grid2D_SW_WaterBody"),TEXT("/NiagaraFluids/Templates/Liquid/2D/Systems/ShallowWater/Grid2D_SW_Pool.Grid2D_SW_Pool")}){
    auto NS=LoadObject<UNiagaraSystem>(nullptr,Path);Out+=FString(Path)+TEXT("\n");
    if(NS){TArray<FNiagaraVariable> Vars;NS->GetExposedParameters().GetParameters(Vars);for(const auto& V:Vars){Out+=V.GetName().ToString()+TEXT(" : ")+V.GetType().GetName()+TEXT("\n");}}
   }
   FFileHelper::SaveStringToFile(Out,*(FPaths::ProjectSavedDir()/TEXT("water-parameters.txt")));
   return;
  }
  if(IsRunningCommandlet()||GIsEditor)return;
  SettingsPath=FPaths::ProjectDir()/TEXT("Resources/scene.json");FParse::Value(FCommandLine::Get(),TEXT("SceneSettings="),SettingsPath);
  bControlsVisible=!FParse::Param(FCommandLine::Get(),TEXT("SceneHideControls"));bCaptureUI=FParse::Param(FCommandLine::Get(),TEXT("SceneCaptureUI"));
  bValidateGizmo=FParse::Param(FCommandLine::Get(),TEXT("SceneValidateGizmo"));
  bValidateControls=FParse::Param(FCommandLine::Get(),TEXT("SceneValidateControls"));
  FParse::Value(FCommandLine::Get(),TEXT("SceneCapture="),CapturePath);bDemo=FParse::Param(FCommandLine::Get(),TEXT("SceneDemo"));
  FParse::Value(FCommandLine::Get(),TEXT("ScenePoseTime="),PoseTime);
  FParse::Value(FCommandLine::Get(),TEXT("SceneMoveSpeed="),MoveSpeed);
  bMoveTest=FParse::Param(FCommandLine::Get(),TEXT("SceneMoveTest"));bNoCollision=FParse::Param(FCommandLine::Get(),TEXT("SceneNoCollision"));
  bBodyCloseup=FParse::Param(FCommandLine::Get(),TEXT("SceneBodyCloseup"));
  Handle=FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateRaw(this,&FMainMenuSceneModule::Tick));
  Input=MakeShared<FSceneInput>();Input->Press=[this](FKey K){
   if(!bBuilt)return;
   if(K==EKeys::Tab)SetControlsVisible(!bControlsVisible);
   if(K==EKeys::SpaceBar){bDemo=!bDemo;AnimTime=0;Body->PlayAnimation(bDemo?StepClip:Idle,true);}
   if(K==EKeys::P)bPaused=!bPaused;
   if(K==EKeys::R){ResetBodyPosition();AnimTime=0;if(WaterSim)WaterSim->ReinitializeSystem();}
   if(K==EKeys::F12)Capture();
  };
  if(FSlateApplication::IsInitialized())FSlateApplication::Get().RegisterInputPreProcessor(Input);
 }
 virtual void ShutdownModule()override{
  if(bBuilt)WriteRecovery();
  FTSTicker::GetCoreTicker().RemoveTicker(Handle);
  if(UObjectInitialized()){if(IsValid(Idle))Idle->RemoveFromRoot();if(IsValid(StepClip))StepClip->RemoveFromRoot();if(IsValid(WalkClip))WalkClip->RemoveFromRoot();}
  if(Input&&FSlateApplication::IsInitialized())FSlateApplication::Get().UnregisterInputPreProcessor(Input);Input.Reset();
 }
};
IMPLEMENT_PRIMARY_GAME_MODULE(FMainMenuSceneModule,MainMenuSceneLab,"MainMenuSceneLab");
