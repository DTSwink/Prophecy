#pragma once
#if WITH_EDITOR
#include "HAL/IConsoleManager.h"
#include "Materials/Material.h"
#include "Materials/MaterialExpression.h"
#include "Misc/FileHelper.h"
#include "Misc/PackageName.h"
#include "Misc/Paths.h"
#include "UObject/SavePackage.h"

// Python's EMaterialProperty wrapper omits the two hidden clearcoat pins.
// This command is registered only by the isolated preparation commandlet.
static void FinalizeSceneWetMaterial()
{
 if(!FPaths::GetBaseFilename(FPaths::GetProjectFilePath()).Equals(TEXT("MainMenuSceneLab")))return;
 auto M=LoadObject<UMaterial>(nullptr,TEXT("/Game/MenuScene/M_Mannequin.M_Mannequin"));
 if(!M)return;
 UMaterialExpression* Coat=nullptr;UMaterialExpression* Roughness=nullptr;
 for(auto Expression:M->GetExpressions())if(Expression){
  if(Expression->Desc==TEXT("WetCoatMask"))Coat=Expression;
  if(Expression->Desc==TEXT("WetCoatRoughness"))Roughness=Expression;
 }
 if(!Coat||!Roughness){UE_LOG(LogTemp,Error,TEXT("WET_MATERIAL missing named coat outputs"));return;}
 M->Modify();auto Data=M->GetEditorOnlyData();
 Data->ClearCoat.Connect(0,Coat);Data->ClearCoatRoughness.Connect(0,Roughness);
 M->PostEditChange();M->MarkPackageDirty();
 const FString Filename=FPackageName::LongPackageNameToFilename(M->GetOutermost()->GetName(),FPackageName::GetAssetPackageExtension());
 FSavePackageArgs Args;Args.TopLevelFlags=RF_Public|RF_Standalone;Args.SaveFlags=SAVE_NoError;
 const bool Saved=UPackage::SavePackage(M->GetOutermost(),M,*Filename,Args);
 const FString Receipt=FString::Printf(TEXT("{\"saved\":%s,\"material\":\"M_Mannequin\",\"shading\":\"clearcoat_dual_normal\",\"coordinates\":\"skeletal_uv_with_tangent_gravity\"}"),Saved?TEXT("true"):TEXT("false"));
 FFileHelper::SaveStringToFile(Receipt,*(FPaths::ProjectSavedDir()/TEXT("Validation/wet-material.json")));
 UE_LOG(LogTemp,Display,TEXT("WET_MATERIAL_SAVED=%d"),Saved);
}

static void RegisterWetPreparation()
{
 static FAutoConsoleCommand Command(TEXT("Scene.FinalizeWetMaterial"),TEXT("Connect and save this lab's wet coating inputs."),FConsoleCommandDelegate::CreateStatic(&FinalizeSceneWetMaterial));
}
#endif
