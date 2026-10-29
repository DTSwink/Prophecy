#pragma once
#include "CoreMinimal.h"
#include "Engine/World.h"
#include "NiagaraComponent.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraSystem.h"

// A real Epic 3D gas simulation with its native heterogeneous volume renderer.
// Runtime names below are either audited stock users or explicitly created and
// linked to typed module inputs by PrepareSceneSmoke().
struct FSceneGasSmoke
{
 UNiagaraComponent* Component=nullptr;
 UNiagaraSystem* System=nullptr;
 bool bVisible=false,bPaused=false,bStopped=false;
 FVector GridDimensions=FVector::ZeroVector,PendingDimensions=FVector::ZeroVector;
 int32 PendingResolution=224;float ResizeDelay=-1;
 FVector4 CutoffPlane=FVector4(0,0,1,-300);
 float CutoffFeather=65.f;

 bool Has(const TCHAR* Name,const FNiagaraTypeDefinition& Type) const
 {
  if(!System)return false;
  const bool Found=System->GetExposedParameters().IndexOf(FNiagaraVariable(Type,FName(Name)))!=INDEX_NONE;
  if(!Found)UE_LOG(LogTemp,Error,TEXT("SMOKE_RUNTIME_PARAMETER missing/wrong type %s (%s)"),Name,*Type.GetName());
  return Found;
 }

 bool Build(UWorld* World)
 {
  if(Component)return true;
  System=LoadObject<UNiagaraSystem>(nullptr,TEXT("/Game/MenuScene/NS_UpperGasSmoke.NS_UpperGasSmoke"));
  if(!World||!System){UE_LOG(LogTemp,Error,TEXT("SMOKE_SYSTEM_MISSING run scene preparation"));return false;}
  System->WaitForCompilationComplete(true,false);
  bool Ready=Has(TEXT("User.DrawBounds"),FNiagaraTypeDefinition::GetBoolDef())&&
   Has(TEXT("User.ResolutionMaxAxis"),FNiagaraTypeDefinition::GetIntDef())&&
   Has(TEXT("User.WorldSpaceSize"),FNiagaraTypeDefinition::GetVec3Def());
  for(const TCHAR* Name:{TEXT("User.SmokeSourceDensity"),TEXT("User.SmokeSourceRadius"),TEXT("User.SmokeVorticity"),TEXT("User.SmokeDensityBuoyancy"),TEXT("User.SmokeRenderDensity"),TEXT("User.SmokeCropFeather")})Ready=Has(Name,FNiagaraTypeDefinition::GetFloatDef())&&Ready;
  Ready=Has(TEXT("User.SmokeSourceScale"),FNiagaraTypeDefinition::GetVec3Def())&&Ready;
  Ready=Has(TEXT("User.SmokeVelocity"),FNiagaraTypeDefinition::GetVec3Def())&&Ready;
  Ready=Has(TEXT("User.SmokeCropPlane"),FNiagaraTypeDefinition::GetVec4Def())&&Ready;
  const auto& Users=System->GetExposedParameters();
  const bool SourcePosition=Users.IndexOf(FNiagaraVariable(FNiagaraTypeDefinition::GetPositionDef(),TEXT("User.Emit Position")))!=INDEX_NONE||Users.IndexOf(FNiagaraVariable(FNiagaraTypeDefinition::GetVec3Def(),TEXT("User.Emit Position")))!=INDEX_NONE;
  if(!SourcePosition)UE_LOG(LogTemp,Error,TEXT("SMOKE_RUNTIME_PARAMETER missing/wrong type User.Emit Position"));
  Ready=SourcePosition&&Ready;
  if(!Ready)return false;
  Component=UNiagaraFunctionLibrary::SpawnSystemAtLocation(World,System,FVector(850,140,600),FRotator::ZeroRotator,FVector::OneVector,false,false,ENCPoolMethod::None,false);
  if(!Component)return false;
  Component->SetCastShadow(true);
  Component->SetVariableBool(TEXT("User.DrawBounds"),false);
  Component->SetVariableInt(TEXT("User.ResolutionMaxAxis"),224);
  Apply(.25f,600.f,1.4f,.6f,.15f);
  Component->Activate(true);
  Component->SetPaused(bPaused||bStopped||!bVisible);
  UE_LOG(LogTemp,Display,TEXT("SMOKE_GAS_READY source=Epic_Grid3D_Gas_Smoke resolutionMaxAxis=224 nativeVolume=1"));
  return true;
 }

 void Apply(float Amount,float Height,float Spread,float Roll,float Speed,float Shift=200.f,float HorizontalWidth=1.f)
 {
  if(!Component)return;
  bVisible=Amount>.0001f;bStopped=Speed<=.0001f;
  const float Width=FMath::Clamp(Spread,.35f,3.f);
  const FVector Center(850,140+Shift,FMath::Clamp(Height,100.f,1500.f));
  const float Stretch=FMath::Clamp(HorizontalWidth,.25f,8.f);
  const float Radius=FMath::Clamp(180.f*FMath::Sqrt(Width),105.f,240.f);
  // Preserve old source depth/height. Only its world-Y axis (screen horizontal) widens.
  // Leave 450cm of return-flow space at each end of the enlarged source.
  const FVector Dimensions(1000,FMath::Max(1800*Width,2*Radius*Stretch+900),650);
  const float OriginalCellSize=FMath::Max(1000.f,1800*Width)/224.f;
  const int32 Resolution=FMath::Clamp(FMath::CeilToInt(Dimensions.GetMax()/OriginalCellSize),224,512);
  Component->SetWorldLocation(Center);
  // Native volume integration uses these bounds as the actual sampling box.
  if(GridDimensions.IsNearlyZero()){
   GridDimensions=Dimensions;Component->SetSystemFixedBounds(FBox(-Dimensions*.5,Dimensions*.5));
   Component->SetVariableVec3(TEXT("User.WorldSpaceSize"),Dimensions);
   Component->SetVariableInt(TEXT("User.ResolutionMaxAxis"),Resolution);
  }else if(!Dimensions.Equals(PendingDimensions,.1)){
   PendingDimensions=Dimensions;PendingResolution=Resolution;
   ResizeDelay=Dimensions.Equals(GridDimensions,.1)?-1.f:.3f;
  }
  // Feed downward near the center. The smaller source leaves surrounding
  // cells free for the solver's return flow instead of forcing the whole bank.
  // Its maximum radius plus this offset fits inside the 650 cm grid height.
  const FVector Source=Center+FVector(0,0,20);
  if(System->GetExposedParameters().IndexOf(FNiagaraVariable(FNiagaraTypeDefinition::GetPositionDef(),TEXT("User.Emit Position")))!=INDEX_NONE)
   Component->SetVariablePosition(TEXT("User.Emit Position"),Source);
  else if(System->GetExposedParameters().IndexOf(FNiagaraVariable(FNiagaraTypeDefinition::GetVec3Def(),TEXT("User.Emit Position")))!=INDEX_NONE)
   Component->SetVariableVec3(TEXT("User.Emit Position"),Source);
  else UE_LOG(LogTemp,Error,TEXT("SMOKE_RUNTIME_PARAMETER missing/wrong type User.Emit Position"));
  const float Drift=FMath::Clamp(Speed/.15f,0.f,6.f);
  Component->SetVariableFloat(TEXT("User.SmokeSourceDensity"),1.f);
  Component->SetVariableFloat(TEXT("User.SmokeSourceRadius"),Radius);
  Component->SetVariableVec3(TEXT("User.SmokeSourceScale"),FVector(1,Stretch,1));
  Component->SetVariableVec3(TEXT("User.SmokeVelocity"),FVector(0,0,-80)*Drift);
  // Epic applies (density * coefficient) * gravity. A negative coefficient
  // gives this cold-looking gas an art-directed upward return without heat.
  // Scaling acceleration with speed squared keeps the approximate roll depth
  // steady while Drift changes its pace (about 131 cm at unit density).
  Component->SetVariableFloat(TEXT("User.SmokeDensityBuoyancy"),-.025f*Drift*Drift);
  Component->SetVariableFloat(TEXT("User.SmokeVorticity"),FMath::Lerp(.25f,4.f,FMath::Clamp(Roll,0.f,1.f)));
  // Stock density is sized for compact plumes; this broad bank needs a much
  // thinner optical range so most of the slider does not become opaque.
  Component->SetVariableFloat(TEXT("User.SmokeRenderDensity"),.08f*FMath::Square(FMath::Clamp(Amount,0.f,1.f)));
  Component->SetVariableVec4(TEXT("User.SmokeCropPlane"),CutoffPlane);
  Component->SetVariableFloat(TEXT("User.SmokeCropFeather"),CutoffFeather);
  Component->SetVisibility(bVisible);
  Component->SetPaused(bPaused||bStopped||!bVisible);
 }

 // Resize only after a brief pause in dragging, not on every slider event.
 void Tick(float Delta){
  if(!Component||ResizeDelay<0)return;
  ResizeDelay-=Delta;if(ResizeDelay>0)return;
  GridDimensions=PendingDimensions;ResizeDelay=-1;
  Component->SetSystemFixedBounds(FBox(-GridDimensions*.5,GridDimensions*.5));
  Component->SetVariableVec3(TEXT("User.WorldSpaceSize"),GridDimensions);
  Component->SetVariableInt(TEXT("User.ResolutionMaxAxis"),PendingResolution);
  Component->ReinitializeSystem();Component->SetPaused(bPaused||bStopped||!bVisible);
 }

 void SetCutoffPlane(const FVector4& Plane,float Feather)
 {
  CutoffPlane=Plane;CutoffFeather=FMath::Max(1.f,Feather);
  if(Component)
  {
   Component->SetVariableVec4(TEXT("User.SmokeCropPlane"),CutoffPlane);
   Component->SetVariableFloat(TEXT("User.SmokeCropFeather"),CutoffFeather);
  }
 }

 void SetPaused(bool Paused)
 {
  bPaused=Paused;if(Component)Component->SetPaused(bPaused||bStopped||!bVisible);
 }
 bool IsVisible() const { return Component&&bVisible; }
};
