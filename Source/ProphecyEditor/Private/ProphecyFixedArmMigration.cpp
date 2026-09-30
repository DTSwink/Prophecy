#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "K2Node_CallFunction.h"
#include "EdGraph/EdGraph.h"
#include "EdGraphSchema_K2.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ScopedTransaction.h"
#include "UObject/SavePackage.h"
#include "HAL/IConsoleManager.h"

namespace ProphecyFixedArmMigration
{
static void Run()
{
    if(!GEditor || GEditor->PlayWorld)return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if(!BP)return;
    const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/FixedArms20260930");
    IFileManager::Get().MakeDirectory(*Dir,true);
    const FString Backup=Dir/TEXT("Before/BP_ProphecyManualPoseAgent-live.uasset");
    FSavePackageArgs Save;Save.TopLevelFlags=RF_Public|RF_Standalone;Save.SaveFlags=SAVE_KeepDirty;
    if(!IFileManager::Get().FileExists(*Backup) && !UPackage::SavePackage(BP->GetOutermost(),BP,*Backup,Save))return;
    const TSet<FName> RemovedFunctions={TEXT("SetAttackHandClamp"),TEXT("SetLocomotionHandClamp"),TEXT("SetLocomotionForearmClamp"),
        TEXT("SetParryHandClamp"),TEXT("SetParryForearmClamp"),TEXT("SetDodgeHandClamp"),TEXT("SetDodgeForearmClamp")};
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","FixedForearms","Remove obsolete hand and forearm length allowance nodes"));
    BP->Modify();TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);int32 Removed=0;bool OK=true;FString Report;
    for(auto* Graph:Graphs)
    {
        const auto Nodes=Graph->Nodes;
        for(UEdGraphNode* Base:Nodes)
        {
            auto* N=Cast<UK2Node_CallFunction>(Base);if(!N)continue;
            const FName Name=N->FunctionReference.GetMemberName();
            bool Remove=RemovedFunctions.Contains(Name);
            if(Name==TEXT("BlendClampToSnapshot"))if(auto* P=N->FindPin(TEXT("Clamp")))
                Remove=P->LinkedTo.IsEmpty() && (P->DefaultValue==TEXT("Hand") || P->DefaultValue==TEXT("Forearm"));
            if(!Remove)continue;
            Graph->Modify();N->Modify();TArray<UEdGraphPin*> In,Out,Results;
            if(auto* P=N->FindPin(TEXT("execute")))In=P->LinkedTo;
            if(auto* P=N->FindPin(TEXT("then")))Out=P->LinkedTo;
            if(auto* P=N->FindPin(TEXT("ReturnValue")))Results=P->LinkedTo;
            Report+=Graph->GetName()+TEXT(" / ")+N->GetName()+TEXT(" / ")+Name.ToString()+TEXT("\n");
            N->BreakAllNodeLinks();
            for(auto* From:In)for(auto* To:Out)OK&=Graph->GetSchema()->TryCreateConnection(From,To);
            for(auto* P:Results)Graph->GetSchema()->TrySetDefaultValue(*P,TEXT("true"));
            FBlueprintEditorUtils::RemoveNode(BP,N,true);++Removed;
        }
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    Report+=FString::Printf(TEXT("removed=%d connections_ok=%d status=%d saved=0\n"),Removed,int32(OK),int32(BP->Status));
    FFileHelper::SaveStringToFile(Report,*(Dir/TEXT("BlueprintMigration.txt")));
    UE_LOG(LogTemp,Display,TEXT("Fixed arm migration: %s"),*Report);
}
static FAutoConsoleCommand Command(TEXT("Prophecy.Editor.RemoveArmLeeway"),TEXT("Explicitly remove obsolete arm leeway calls; back up live Blueprint, reconnect execution, compile without saving."),FConsoleCommandDelegate::CreateStatic(&Run));

// Explicit diagnostic preview only, so the same rollout can exercise simulation
// without its per-tick Kinematic literal immediately undoing the selected mode.
static TMap<FGuid,FString> ModePins;
static bool WasDirty=false;
static void PreviewMode(const TArray<FString>& Args)
{
    if(!GEditor || GEditor->PlayWorld || Args.Num()!=1)return;
    const bool Restore=Args[0]==TEXT("restore");
    if((Restore && ModePins.IsEmpty()) || (!Restore && (Args[0]!=TEXT("Physical") || !ModePins.IsEmpty())))return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if(!BP)return;
    if(!Restore)WasDirty=BP->GetOutermost()->IsDirty();
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
    for(auto* Graph:Graphs)for(UEdGraphNode* Base:Graph->Nodes)
    {
        auto* N=Cast<UK2Node_CallFunction>(Base);
        if(!N || N->FunctionReference.GetMemberName()!=TEXT("SetSimulationMode"))continue;
        auto* Pin=N->FindPin(TEXT("NewMode"));if(!Pin || !Pin->LinkedTo.IsEmpty())continue;
        if(Restore)
        {
            if(const auto* Old=ModePins.Find(N->NodeGuid))Pin->DefaultValue=*Old;
        }
        else {ModePins.Add(N->NodeGuid,Pin->DefaultValue);Pin->DefaultValue=TEXT("Physical");}
    }
    const int32 Count=ModePins.Num();
    FBlueprintEditorUtils::MarkBlueprintAsModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    if(Restore){ModePins.Reset();BP->GetOutermost()->SetDirtyFlag(WasDirty);}
    UE_LOG(LogTemp,Display,TEXT("Fixed-arm mode preview %s pins=%d status=%d saved=0"),*Args[0],Count,int32(BP->Status));
}
static FAutoConsoleCommand ModeCommand(TEXT("Prophecy.Editor.PreviewFixedArmMode"),TEXT("Physical/restore current graph mode literals for bounded verification; never saves."),FConsoleCommandWithArgsDelegate::CreateStatic(&PreviewMode));
}
