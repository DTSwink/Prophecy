#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "K2Node_CallFunction.h"
#include "EdGraphSchema_K2.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/Paths.h"
#include "ScopedTransaction.h"
#include "UObject/SavePackage.h"
#include "HAL/IConsoleManager.h"
#include "HAL/FileManager.h"

namespace ProphecyLeftHandAngleSetup
{
static void Run()
{
    if(!GEditor || GEditor->PlayWorld)return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if(!BP)return;
    const FString Backup=FPaths::ProjectSavedDir()/TEXT("Diagnostics/LeftHandAngle20260930/Before/BP_ProphecyManualPoseAgent-live.uasset");
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Backup),true);
    FSavePackageArgs Save;Save.TopLevelFlags=RF_Public|RF_Standalone;Save.SaveFlags=SAVE_KeepDirty;
    if(!IFileManager::Get().FileExists(*Backup) && !UPackage::SavePackage(BP->GetOutermost(),BP,*Backup,Save))return;
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","LeftHandAngle","Expose left-hand angular leeway"));
    BP->Modify();TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);int32 Changed=0;
    for(auto* G:Graphs)for(UEdGraphNode* Base:G->Nodes)if(auto* N=Cast<UK2Node_CallFunction>(Base))
        if(N->FunctionReference.GetMemberName()==TEXT("SetLeftHandConstraint"))
        {
            G->Modify();N->Modify();N->ReconstructNode();
            auto* P=N->FindPin(TEXT("MaxBendDegrees"));
            if(G->GetName()==TEXT("tick debugging") && N->GetFName()==TEXT("K2Node_CallFunction_234") && P &&
                P->LinkedTo.IsEmpty() && FCString::Atof(*P->DefaultValue)==0)
            {G->GetSchema()->TrySetDefaultValue(*P,TEXT("55.0"));++Changed;}
        }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    UE_LOG(LogTemp,Display,TEXT("Left hand angle: zero-lock nodes changed=%d status=%d; not saved."),Changed,int32(BP->Status));
}
static FAutoConsoleCommand Command(TEXT("Prophecy.Editor.LeftHandAngle"),TEXT("Refresh left wrist angle pin; change the audited zero-lock node to55 degrees. Back up live Blueprint; no save."),FConsoleCommandDelegate::CreateStatic(&Run));
}
