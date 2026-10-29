#pragma once
#if WITH_EDITOR
#include "AssetToolsModule.h"
#include "IAssetTools.h"
#include "NiagaraSystem.h"
#include "NiagaraEmitter.h"
#include "NiagaraEmitterHandle.h"
#include "NiagaraScript.h"
#include "NiagaraScriptSource.h"
#include "NiagaraGraph.h"
#include "NiagaraNode.h"
#include "NiagaraNodeFunctionCall.h"
#include "NiagaraScriptVariable.h"
#include "ViewModels/Stack/NiagaraParameterHandle.h"
#include "ViewModels/Stack/NiagaraStackGraphUtilities.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Misc/App.h"
#include "UObject/SavePackage.h"

namespace SceneWaterPreparation
{
 static bool SetInput(UNiagaraSystem* System,UNiagaraNodeFunctionCall* Call,const TCHAR* Name,const TCHAR* Parameter,float Default,bool IsBool=false)
 {
  auto Type=IsBool?FNiagaraTypeDefinition::GetBoolDef():FNiagaraTypeDefinition::GetFloatDef();
  auto Graph=Call->GetCalledGraph();
  const FName ModuleName(*(FString(TEXT("Module."))+Name));
  UNiagaraScriptVariable* Variable=nullptr;bool Found=false;
  if(Graph)for(const auto& Item:Graph->GetAllMetaData())if(Item.Key.GetName()==ModuleName&&(Item.Key.GetType()==Type||(IsBool&&Item.Key.GetType()==Type.ToStaticDef()))){Found=true;Variable=Item.Value;Type=Item.Key.GetType();break;}
  // Some shipped inputs have a typed graph entry but no metadata UObject.
  // Use the graph's authoritative typed key and leave the engine graph untouched.
  if(!Found||(Variable&&Variable->GetIsStaticSwitch()))
  {UE_LOG(LogTemp,Error,TEXT("WATER_INPUT_INVALID module=%s input=%s expected=%s"),*Call->FunctionScript->GetName(),Name,*Type.GetName());return false;}
  const FNiagaraParameterHandle Input(FName(*Call->GetFunctionName()),FName(Name));
  auto& Pin=FNiagaraStackGraphUtilities::GetOrCreateStackFunctionInputOverridePin(*Call,Input,Type,Variable?Variable->Metadata.GetVariableGuid():FGuid(),FGuid());
  // Only the isolated lab call overrides are changed; engine modules stay intact.
  Pin.Modify();Pin.BreakAllPinLinks(true);
  if(Type.IsStatic()){
   Pin.DefaultValue=Default>.5f?TEXT("true"):TEXT("false");
   CastChecked<UNiagaraNode>(Pin.GetOwningNode())->MarkNodeRequiresSynchronization(TEXT("Lab resting depth variant"),true);
   Call->MarkNodeRequiresSynchronization(TEXT("Lab resting depth variant"),true);
   UE_LOG(LogTemp,Display,TEXT("WATER_STATIC_INPUT %s=%s"),Name,*Pin.DefaultValue);return true;
  }
  FNiagaraVariable User(Type,FName(Parameter));
  if(IsBool)System->GetExposedParameters().SetParameterValue(FNiagaraBool(Default>.5f),User,true);
  else System->GetExposedParameters().SetParameterValue(Default,User,true);
  TSet<FNiagaraVariableBase> Known;Known.Add(User);
  FNiagaraStackGraphUtilities::SetLinkedParameterValueForFunctionInput(Pin,User,Known);
  CastChecked<UNiagaraNode>(Pin.GetOwningNode())->MarkNodeRequiresSynchronization(TEXT("Lab shallow puddle contact and dissipation"),true);
  Call->MarkNodeRequiresSynchronization(TEXT("Lab shallow puddle contact and dissipation"),true);
  UE_LOG(LogTemp,Display,TEXT("WATER_INPUT module=%s input=%s value=%s"),*Call->FunctionScript->GetName(),Name,Parameter);
  return true;
 }
}

// Keep the shipping engine templates untouched; only tune this lab's module call.
static bool PrepareSceneWater(){
 if(!FPaths::GetBaseFilename(FPaths::GetProjectFilePath()).Equals(TEXT("MainMenuSceneLab")))return false;
 const FString AssetName=TEXT("NS_CrimsonShallowWater");
 const FString AssetPath=TEXT("/Game/MenuScene/")+AssetName+TEXT(".")+AssetName;
 auto Copy=LoadObject<UNiagaraSystem>(nullptr,*AssetPath);
 if(!Copy){
  auto Original=LoadObject<UNiagaraSystem>(nullptr,TEXT("/WaterAdvanced/Niagara/Systems/Grid2D_SW_WaterBody.Grid2D_SW_WaterBody"));
  if(!Original)return false;
  auto& AssetTools=FModuleManager::LoadModuleChecked<FAssetToolsModule>(TEXT("AssetTools")).Get();
  Copy=Cast<UNiagaraSystem>(AssetTools.DuplicateAsset(AssetName,TEXT("/Game/MenuScene"),Original));
 }
 if(!Copy)return false;
 Copy->Modify();bool OK=true;int32 CollisionCalls=0,VelocityCalls=0;
 for(auto& Handle:Copy->GetEmitterHandles()){
  if(!Handle.GetIsEnabled())continue;
  auto Data=Handle.GetEmitterData();if(!Data)continue;
  auto Source=Cast<UNiagaraScriptSource>(Data->GraphSource);
  if(!Source||!Source->NodeGraph)continue;
  if(Source->GetOutermost()!=Copy->GetOutermost()||Source->NodeGraph->GetOutermost()!=Copy->GetOutermost())return false;
  const auto Nodes=Source->NodeGraph->Nodes;
  for(auto Node:Nodes){
   auto Call=Cast<UNiagaraNodeFunctionCall>(Node);
   if(!Call||!Call->FunctionScript||!Call->IsNodeEnabled())continue;
   const auto Script=Call->FunctionScript->GetName();
   if(Script==TEXT("Grid2D_SW_UpdateCollisions"))
   {
    ++CollisionCalls;
    OK=SceneWaterPreparation::SetInput(Copy,Call,TEXT("CollisionVelocityMult"),TEXT("User.ContactStrength"),1.f)&&OK;
    OK=SceneWaterPreparation::SetInput(Copy,Call,TEXT("MinVelocityForCollision"),TEXT("User.ContactMinSpeed"),1.f)&&OK;
    OK=SceneWaterPreparation::SetInput(Copy,Call,TEXT("SDFSoftCollisionFalloff"),TEXT("User.ContactSoftness"),4.f)&&OK;
   }
   else if(Script==TEXT("Grid2D_SW_UpdateDepthGrid"))
   {
    OK=SceneWaterPreparation::SetInput(Copy,Call,TEXT("KeepWaterDepthInsideColliders"),TEXT("User.KeepRestingDepth"),0.f,true)&&OK;
   }
   else if(Script==TEXT("Grid2D_SW_UpdateVelocity"))
   {
    ++VelocityCalls;
    // The stock friction divides by depth_m^(4/3). At this puddle's 3.5 cm
    // depth it rapidly erases contact wakes; reduce drag, not the solver steps.
    OK=SceneWaterPreparation::SetInput(Copy,Call,TEXT("Friction"),TEXT("User.WaterFriction"),.00025f)&&OK;
    OK=SceneWaterPreparation::SetInput(Copy,Call,TEXT("VelocityDissipation"),TEXT("User.WaterDissipation"),.0003f)&&OK;
   }
  }
 }
 UE_LOG(LogTemp,Display,TEXT("WATER_PREPARE collisionCalls=%d velocityCalls=%d inputsOK=%d"),CollisionCalls,VelocityCalls,OK);
 if(!OK||CollisionCalls==0||VelocityCalls==0)return false;
 Copy->MarkPackageDirty();Copy->RequestCompile(true);Copy->WaitForCompilationComplete(true,false);
 // Null-RHI preparation cannot satisfy system runtime readiness. Its CPU and
 // GPU executables still must compile successfully before the package is saved.
 bool Compiled=(!FApp::CanEverRender()||Copy->IsReadyToRun())&&!Copy->HasOutstandingCompilationRequests(true);
 TArray<UNiagaraScript*> Scripts;
 Scripts.Add(Copy->GetSystemSpawnScript());Scripts.Add(Copy->GetSystemUpdateScript());
 for(const auto& Handle:Copy->GetEmitterHandles())
 {
  if(!Handle.GetIsEnabled())continue;
  const auto Data=Handle.GetEmitterData();if(!Data){Compiled=false;continue;}
  const bool Valid=Data->IsValid()&&Data->IsReadyToRun();
  Compiled=Valid&&Compiled;Data->GetScripts(Scripts,false,true);
  if(Data->SimTarget==ENiagaraSimTarget::GPUComputeSim)
  {
   const auto GPU=Data->GetGPUComputeScript();
   const bool GPUOK=GPU&&!GPU->IsScriptCompilationPending(true)&&GPU->DidScriptCompilationSucceed(true);
   Compiled=GPUOK&&Compiled;
   UE_LOG(LogTemp,Display,TEXT("WATER_GPU_COMPILE emitter=%s success=%d valid=%d"),*Handle.GetName().ToString(),GPUOK,Valid);
  }
 }
 for(const auto Script:Scripts)
 {
  if(!Script){Compiled=false;continue;}
  const auto Status=Script->GetLastCompileStatus();
  if(Status==ENiagaraScriptCompileStatus::NCS_Error||Status==ENiagaraScriptCompileStatus::NCS_Dirty||Status==ENiagaraScriptCompileStatus::NCS_BeingCreated)
  {
   Compiled=false;
   UE_LOG(LogTemp,Error,TEXT("WATER_COMPILE_FAILED script=%s status=%d %s"),*Script->GetPathName(),int32(Status),*Script->GetVMExecutableData().ErrorMsg);
  }
 }
 UE_LOG(LogTemp,Display,TEXT("WATER_COMPILE_SUCCESS=%d CAN_RENDER=%d SYSTEM_READY=%d"),Compiled,FApp::CanEverRender(),Copy->IsReadyToRun());
 if(!Compiled){UE_LOG(LogTemp,Error,TEXT("WATER_COMPILE_FAILED refusing to save a non-runnable system"));return false;}
 const FString Filename=FPackageName::LongPackageNameToFilename(Copy->GetOutermost()->GetName(),FPackageName::GetAssetPackageExtension());
 FSavePackageArgs Args;Args.TopLevelFlags=RF_Public|RF_Standalone;Args.SaveFlags=SAVE_NoError;
 return UPackage::SavePackage(Copy->GetOutermost(),Copy,*Filename,Args);
}
#endif
