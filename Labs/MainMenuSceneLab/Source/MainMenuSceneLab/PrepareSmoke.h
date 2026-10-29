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
#include "NiagaraNodeFunctionCall.h"
#include "NiagaraScriptVariable.h"
#include "NiagaraVolumeRendererProperties.h"
#include "ViewModels/Stack/NiagaraParameterHandle.h"
#include "ViewModels/Stack/NiagaraStackGraphUtilities.h"
#include "Materials/MaterialInterface.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "Misc/App.h"
#include "UObject/SavePackage.h"
#include "UObject/UnrealType.h"

namespace SceneSmokePreparation
{
 template<class T>
 FNiagaraVariable User(UNiagaraSystem* System,const TCHAR* Name,const FNiagaraTypeDefinition& Type,const T& Value)
 {
  FNiagaraVariable Variable(Type,FName(Name));
  System->GetExposedParameters().SetParameterValue(Value,Variable,true);
  return Variable;
 }

 // Check the called version's real input metadata before adding an override.
 // The shipped module graph itself remains read-only.
 UNiagaraScriptVariable* Input(UNiagaraNodeFunctionCall* Call,const TCHAR* Name)
 {
  auto Graph=Call->GetCalledGraph();
  return Graph?Graph->GetScriptVariable(FName(*(FString(TEXT("Module."))+Name))):nullptr;
 }

 bool Set(UNiagaraNodeFunctionCall* Call,const TCHAR* Name,const TCHAR* Literal,const FNiagaraVariable* UserParameter=nullptr)
 {
  auto Variable=Input(Call,Name);
  if(!Variable){UE_LOG(LogTemp,Error,TEXT("SMOKE_INPUT_MISSING module=%s input=%s"),*Call->FunctionScript->GetName(),Name);return false;}
  const auto Type=Variable->Variable.GetType();
  if(UserParameter&&Type!=UserParameter->GetType())
  {
   UE_LOG(LogTemp,Error,TEXT("SMOKE_INPUT_TYPE module=%s input=%s actual=%s requested=%s"),*Call->FunctionScript->GetName(),Name,*Type.GetName(),*UserParameter->GetType().GetName());return false;
  }
  if(Variable->GetIsStaticSwitch())
  {
   UEdGraphPin* Pin=Call->FindPin(FName(Name),EGPD_Input);
   if(!Pin||UserParameter)return false;
   Pin->Modify();Pin->DefaultValue=Literal;
  }
  else
  {
   const FNiagaraParameterHandle Handle(FName(*Call->GetFunctionName()),FName(Name));
   auto& Pin=FNiagaraStackGraphUtilities::GetOrCreateStackFunctionInputOverridePin(*Call,Handle,Type,Variable->Metadata.GetVariableGuid(),FGuid());
   Pin.Modify();Pin.BreakAllPinLinks(true);
   if(UserParameter)
   {
    TSet<FNiagaraVariableBase> Known;Known.Add(*UserParameter);
    FNiagaraStackGraphUtilities::SetLinkedParameterValueForFunctionInput(Pin,*UserParameter,Known);
   }
   else Pin.DefaultValue=Literal;
  }
  Call->MarkNodeRequiresSynchronization(TEXT("Lab cold smoke controls"),true);
  UE_LOG(LogTemp,Display,TEXT("SMOKE_INPUT module=%s input=%s type=%s static=%d value=%s"),*Call->FunctionScript->GetName(),Name,*Type.GetName(),Variable->GetIsStaticSwitch(),UserParameter?*UserParameter->GetName().ToString():Literal);
  return true;
 }

 void MaterialBinding(UNiagaraVolumeRendererProperties* Renderer,const TCHAR* Name,const FNiagaraVariable& Variable)
 {
  Renderer->MaterialParameters.AttributeBindings.RemoveAll([Name](const FNiagaraMaterialAttributeBinding& Binding){return Binding.MaterialParameterName==FName(Name);});
  auto& Binding=Renderer->MaterialParameters.AttributeBindings.AddDefaulted_GetRef();
  Binding.MaterialParameterName=FName(Name);Binding.NiagaraVariable=Variable;
 }
}

// Must run after M_GasSmoke is prepared. It reuses Epic's real gas solver and
// native volume renderer; only this lab's duplicate and its call overrides change.
static bool PrepareSceneSmoke()
{
 using namespace SceneSmokePreparation;
 if(FPaths::GetBaseFilename(FPaths::GetProjectFilePath())!=TEXT("MainMenuSceneLab"))return false;
 auto System=LoadObject<UNiagaraSystem>(nullptr,TEXT("/Game/MenuScene/NS_UpperGasSmoke.NS_UpperGasSmoke"));
 if(!System)
 {
  auto Original=LoadObject<UNiagaraSystem>(nullptr,TEXT("/NiagaraFluids/Templates/Gas/3D/Systems/Grid3D_Gas_Smoke.Grid3D_Gas_Smoke"));
  if(!Original)return false;
  auto& Assets=FModuleManager::LoadModuleChecked<FAssetToolsModule>(TEXT("AssetTools")).Get();
  System=Cast<UNiagaraSystem>(Assets.DuplicateAsset(TEXT("NS_UpperGasSmoke"),TEXT("/Game/MenuScene"),Original));
 }
 if(!System)return false;
 System->Modify();
 // Use the engine's fixed-step scheduler and seed for reproducible cache input.
 // These UPROPERTY fields are protected in the installed public C++ header.
 auto Determinism=FindFProperty<FBoolProperty>(UNiagaraSystem::StaticClass(),TEXT("bDeterminism"));
 auto Seed=FindFProperty<FIntProperty>(UNiagaraSystem::StaticClass(),TEXT("RandomSeed"));
 auto Fixed=FindFProperty<FBoolProperty>(UNiagaraSystem::StaticClass(),TEXT("bFixedTickDelta"));
 auto Delta=FindFProperty<FFloatProperty>(UNiagaraSystem::StaticClass(),TEXT("FixedTickDeltaTime"));
 if(!Determinism||!Seed||!Fixed||!Delta)return false;
 Determinism->SetPropertyValue_InContainer(System,true);Seed->SetPropertyValue_InContainer(System,41);
 Fixed->SetPropertyValue_InContainer(System,true);Delta->SetPropertyValue_InContainer(System,1.f/60.f);
 auto Density=User(System,TEXT("User.SmokeSourceDensity"),FNiagaraTypeDefinition::GetFloatDef(),1.f);
 auto Radius=User(System,TEXT("User.SmokeSourceRadius"),FNiagaraTypeDefinition::GetFloatDef(),150.f);
 auto SourceScale=User(System,TEXT("User.SmokeSourceScale"),FNiagaraTypeDefinition::GetVec3Def(),FVector3f(1,1,1));
 auto Velocity=User(System,TEXT("User.SmokeVelocity"),FNiagaraTypeDefinition::GetVec3Def(),FVector3f(0,0,-80));
 auto Lift=User(System,TEXT("User.SmokeDensityBuoyancy"),FNiagaraTypeDefinition::GetFloatDef(),-.025f);
 auto Roll=User(System,TEXT("User.SmokeVorticity"),FNiagaraTypeDefinition::GetFloatDef(),2.f);
 auto RenderDensity=User(System,TEXT("User.SmokeRenderDensity"),FNiagaraTypeDefinition::GetFloatDef(),1.f);
 auto CropPlane=User(System,TEXT("User.SmokeCropPlane"),FNiagaraTypeDefinition::GetVec4Def(),FVector4f(0,0,1,-300));
 auto CropFeather=User(System,TEXT("User.SmokeCropFeather"),FNiagaraTypeDefinition::GetFloatDef(),65.f);
 auto Material=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/MenuScene/M_GasSmoke.M_GasSmoke"));
 bool OK=Material!=nullptr;int32 Sources=0,Vorticity=0,Buoyancy=0,Volumes=0,Boundaries=0,Pivots=0;
 FString Audit;
 TArray<FNiagaraVariable> Exposed;System->GetExposedParameters().GetParameters(Exposed);
 for(const auto& Var:Exposed)Audit+=FString::Printf(TEXT("USER %s : %s\n"),*Var.GetName().ToString(),*Var.GetType().GetName());
 for(auto& Handle:System->GetEmitterHandles())
 {
  if(!Handle.GetIsEnabled())continue;
  auto Data=Handle.GetEmitterData();if(!Data)continue;
  auto Source=Cast<UNiagaraScriptSource>(Data->GraphSource);
  if(!Source||!Source->NodeGraph||Source->GetOutermost()!=System->GetOutermost()||Source->NodeGraph->GetOutermost()!=System->GetOutermost())return false;
  Audit+=TEXT("EMITTER ")+Handle.GetName().ToString()+TEXT("\n");
  const auto Nodes=Source->NodeGraph->Nodes;
  for(auto Node:Nodes)
  {
   auto Call=Cast<UNiagaraNodeFunctionCall>(Node);
   if(!Call||!Call->FunctionScript||!Call->IsNodeEnabled())continue;
   const FString Script=Call->FunctionScript->GetName();
   if(!Script.StartsWith(TEXT("Grid3D_")))continue;
   Audit+=TEXT("MODULE ")+Script+TEXT(" alias=")+Call->GetFunctionName()+TEXT("\n");
   if(auto Called=Call->GetCalledGraph())for(const auto& Pair:Called->GetAllMetaData())
    if(Pair.Key.GetName().ToString().StartsWith(TEXT("Module.")))
     Audit+=FString::Printf(TEXT("  %s : %s static=%d\n"),*Pair.Key.GetName().ToString(),*Pair.Key.GetType().GetName(),Pair.Value?Pair.Value->GetIsStaticSwitch():false);
   if(Script==TEXT("Grid3D_Gas_SphereSource"))
   {
    ++Sources;
    OK=Set(Call,TEXT("Density"),nullptr,&Density)&&OK;
    OK=Set(Call,TEXT("Emit Radius"),nullptr,&Radius)&&OK;
    OK=Set(Call,TEXT("Non Uniform Scale"),nullptr,&SourceScale)&&OK;
    OK=Set(Call,TEXT("Velocity"),nullptr,&Velocity)&&OK;
    OK=Set(Call,TEXT("Temperature"),TEXT("0"))&&OK;
    // The original User.Emit Position remains the source position binding.
    if(Input(Call,TEXT("Local Emit Position")))OK=Set(Call,TEXT("Local Emit Position"),TEXT("false"))&&OK;
    if(Input(Call,TEXT("Local Velocity")))OK=Set(Call,TEXT("Local Velocity"),TEXT("false"))&&OK;
   }
   else if(Script==TEXT("Grid3D_Gas_Buoyancy"))
   {
    ++Buoyancy;
    // Stock HLSL: Force=(DensityBuoyancy*Density-TemperatureBuoyancy*Temperature)*g.
    // With explicit downward gravity, a negative density coefficient lifts the
    // downward-injected smoke back up. Temperature stays zero: no fire emission.
    OK=Set(Call,TEXT("g"),TEXT("0.000,0.000,-980.000"))&&OK;
    OK=Set(Call,TEXT("DensityBuoyancy"),nullptr,&Lift)&&OK;
    OK=Set(Call,TEXT("TemperatureBuoyancy"),TEXT("0"))&&OK;
   }
   else if(Script==TEXT("Grid3D_VorticityConfinementForce"))
   {
    ++Vorticity;OK=Set(Call,TEXT("VorticityMult"),nullptr,&Roll)&&OK;
    if(Input(Call,TEXT("Calculate Vorticity Confinement")))OK=Set(Call,TEXT("Calculate Vorticity Confinement"),TEXT("true"))&&OK;
   }
   else if(Script==TEXT("Grid3D_ComputeBoundary"))
   {
    ++Boundaries;
    // These verified static switches prune scene collision DI calls at compile
    // time. Upper ambient gas needs only its open simulation-grid boundaries.
    for(const TCHAR* Name:{TEXT("Use Mesh Distance Fields"),TEXT("Use Global Distance Field Collisions"),TEXT("Use Mesh Collisions"),TEXT("Use Geometry Collection Collisions"),TEXT("Use Landscape Collisions"),TEXT("Use Depth Map Collisions"),TEXT("Use Particle Collisions"),TEXT("Use GBuffer Velocity")})
     OK=Set(Call,Name,TEXT("false"))&&OK;
   }
   else if(Script==TEXT("Grid3D_RigidMesh_FindColliders"))
    OK=Set(Call,TEXT("FindColliders"),TEXT("false"))&&OK;
   else if(Script==TEXT("Grid3D_Gas_UpdateEmitter"))
   {
    ++Pivots;
    // Shipped Smoke uses (0,0,.5), putting an upright plume above the actor.
    // A zero pivot makes the lab's height refer to the cloud-bank center.
    OK=Set(Call,TEXT("Local Pivot"),TEXT("0.000,0.000,0.000"))&&OK;
    OK=Set(Call,TEXT("Compensate For Actor Motion"),TEXT("false"))&&OK;
   }
   else if(Script==TEXT("Grid3D_ActorMotionForce"))
    OK=Set(Call,TEXT("Calculate Actor Motion Force"),TEXT("false"))&&OK;
  }
  for(auto Renderer:Data->GetRenderers())
  {
   if(Renderer->GetOutermost()!=System->GetOutermost())return false;
   if(auto Volume=Cast<UNiagaraVolumeRendererProperties>(Renderer))
   {
    ++Volumes;Volume->Modify();Volume->SetIsEnabled(true);
    if(Material){Volume->Material=Material;Volume->MICMaterial=nullptr;}
    else UE_LOG(LogTemp,Error,TEXT("SMOKE_MATERIAL_MISSING composition material must be prepared before the system"));
    MaterialBinding(Volume,TEXT("CropPlane"),CropPlane);
    MaterialBinding(Volume,TEXT("CropFeather"),CropFeather);
    MaterialBinding(Volume,TEXT("SmokeRenderDensity"),RenderDensity);
    Volume->StepFactor=1.f;Volume->LightingDownsampleFactor=2.f;
   }
   else Renderer->SetIsEnabled(false); // Debug meshes and obsolete raymarch renderer.
  }
 }
 FFileHelper::SaveStringToFile(Audit,*(FPaths::ProjectSavedDir()/TEXT("Validation/smoke-template-audit.txt")));
 UE_LOG(LogTemp,Display,TEXT("SMOKE_PREPARE sources=%d vorticity=%d buoyancy=%d nativeVolumes=%d boundaries=%d centeredPivots=%d inputsOK=%d"),Sources,Vorticity,Buoyancy,Volumes,Boundaries,Pivots,OK);
 if(!OK||Sources==0||Vorticity==0||Buoyancy==0||Volumes==0||Boundaries==0||Pivots==0)return false;
 // Native Niagara Volume Renderer uses the proxy's bounds for ray integration,
 // not just visibility culling. Runtime sets these to its exact chosen grid size.
 System->SetFixedBounds(FBox(FVector(-650,-1680,-350),FVector(650,1680,350)));
 System->MarkPackageDirty();System->RequestCompile(true);System->WaitForCompilationComplete(true,false);
 // A completed compile can still have failed: Niagara logs these as warnings,
 // and package saving alone happily succeeds. Validate CPU and GPU executables.
 TArray<UNiagaraScript*> Scripts;
 Scripts.Add(System->GetSystemSpawnScript());Scripts.Add(System->GetSystemUpdateScript());
 // Null-RHI preparation deliberately cannot render; IsReadyToRun() rejects that
 // environment before examining any script. Validate its executables below.
 bool Compiled=(!FApp::CanEverRender()||System->IsReadyToRun())&&!System->HasOutstandingCompilationRequests(true);
 for(const auto& Handle:System->GetEmitterHandles())
 {
  if(!Handle.GetIsEnabled())continue;
  const auto Data=Handle.GetEmitterData();if(!Data){Compiled=false;continue;}
  const bool Valid=Data->IsValid()&&Data->IsReadyToRun();
  Compiled=Valid&&Compiled;
  Data->GetScripts(Scripts,false,true);
  if(Data->SimTarget==ENiagaraSimTarget::GPUComputeSim)
  {
   const auto GPU=Data->GetGPUComputeScript();
   const bool GPUOK=GPU&&!GPU->IsScriptCompilationPending(true)&&GPU->DidScriptCompilationSucceed(true);
   Compiled=GPUOK&&Compiled;
   Audit+=FString::Printf(TEXT("GPU %s success=%d emitterValid=%d\n"),*Handle.GetName().ToString(),GPUOK,Valid);
   UE_LOG(LogTemp,Display,TEXT("SMOKE_GPU_COMPILE emitter=%s success=%d valid=%d"),*Handle.GetName().ToString(),GPUOK,Valid);
  }
 }
 for(const auto Script:Scripts)
 {
  if(!Script){Compiled=false;continue;}
  const auto Status=Script->GetLastCompileStatus();
  if(Status==ENiagaraScriptCompileStatus::NCS_Error||Status==ENiagaraScriptCompileStatus::NCS_Dirty||Status==ENiagaraScriptCompileStatus::NCS_BeingCreated)
  {
   Compiled=false;
   UE_LOG(LogTemp,Error,TEXT("SMOKE_COMPILE_FAILED script=%s status=%d %s"),*Script->GetPathName(),int32(Status),*Script->GetVMExecutableData().ErrorMsg);
  }
  Audit+=FString::Printf(TEXT("COMPILE %s status=%d\n"),*Script->GetPathName(),int32(Status));
 }
 Audit+=FString::Printf(TEXT("CAN_RENDER %d\nSYSTEM_READY %d\nCOMPILE_SUCCESS %d\n"),FApp::CanEverRender(),System->IsReadyToRun(),Compiled);
 FFileHelper::SaveStringToFile(Audit,*(FPaths::ProjectSavedDir()/TEXT("Validation/smoke-template-audit.txt")));
 if(!Compiled){UE_LOG(LogTemp,Error,TEXT("SMOKE_COMPILE_FAILED refusing to save a non-runnable system"));return false;}
 const FString Filename=FPackageName::LongPackageNameToFilename(System->GetOutermost()->GetName(),FPackageName::GetAssetPackageExtension());
 FSavePackageArgs Args;Args.TopLevelFlags=RF_Public|RF_Standalone;Args.SaveFlags=SAVE_NoError;
 return UPackage::SavePackage(System->GetOutermost(),System,*Filename,Args);
}
static void FinalizeSceneSmoke()
{
 const bool OK=PrepareSceneSmoke();
 FFileHelper::SaveStringToFile(OK?TEXT("{\"saved\":true}"):TEXT("{\"saved\":false}"),*(FPaths::ProjectSavedDir()/TEXT("Validation/smoke-system.json")));
 UE_LOG(LogTemp,Display,TEXT("SMOKE_SYSTEM_SAVED=%d"),OK);
}
static void RegisterSmokePreparation()
{
 static FAutoConsoleCommand Command(TEXT("Scene.FinalizeSmoke"),TEXT("Bind and save the isolated cold smoke system."),FConsoleCommandDelegate::CreateStatic(&FinalizeSceneSmoke));
}
#endif
