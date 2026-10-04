#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "K2Node_CallFunction.h"
#include "EdGraph/EdGraph.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ScopedTransaction.h"

// Explicit migration of this test harness, never a startup or gameplay hook.
static void UseAcceptedFKLabProfiles()
{
    if(!GEditor || GEditor->PlayWorld)return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if(!BP)return;
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","FKLabProfiles","Use accepted lab return profiles"));
    BP->Modify();TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);int32 Refreshed=0,Disconnected=0;
    for(auto* Graph:Graphs)for(UEdGraphNode* Base:Graph->Nodes)
    {
        auto* Node=Cast<UK2Node_CallFunction>(Base);
        if(!Node || Node->FunctionReference.GetMemberName()!=TEXT("SetAttackFKReturnProfile"))continue;
        Graph->Modify();Node->Modify();Node->ReconstructNode();++Refreshed;
        // This old family loop overwrites every imported profile. Retain the
        // experimental node and its values for reference, but stop executing it.
        if(Graph->GetName()==TEXT("tick debugging") && Node->GetName()==TEXT("K2Node_CallFunction_224"))
        {
            if(auto* Pin=Node->FindPin(TEXT("execute"))) {Disconnected+=Pin->LinkedTo.Num();Pin->BreakAllPinLinks();}
            Node->NodeComment=TEXT("Old overrides disabled: using the accepted per-attack lab profiles built into Set Attack FK Return.");
            Node->bCommentBubbleVisible=true;
        }
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    const FString Report=FString::Printf(TEXT("refreshed=%d disconnected_old_profile_exec=%d status=%d saved=0"),Refreshed,Disconnected,int32(BP->Status));
    FFileHelper::SaveStringToFile(Report,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/FKLabPort20261004/profile-setup.txt")));
    UE_LOG(LogTemp,Display,TEXT("FK lab profiles: %s"),*Report);
}
static FAutoConsoleCommand FKLabProfilesCommand(TEXT("Prophecy.Editor.UseAcceptedFKLabProfiles"),
    TEXT("Refresh FK profile pins and disable the old test-harness profile override. Does not save."),
    FConsoleCommandDelegate::CreateStatic(&UseAcceptedFKLabProfiles));

static void UpgradeFKPerAttackTiming()
{
    if(!GEditor || GEditor->PlayWorld)return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if(!BP)return;
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","FKPerAttackTiming","Upgrade per-attack FK Hold / Trim"));
    BP->Modify();TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);int32 Refreshed=0,Removed=0;
    for(auto* Graph:Graphs)for(UEdGraphNode* Base:Graph->Nodes)
    {
        auto* Node=Cast<UK2Node_CallFunction>(Base);
        if(!Node || Node->FunctionReference.GetMemberName()!=TEXT("SetAttackFKReturn"))continue;
        Graph->Modify();Node->Modify();
        // Replaced scalar controls are intentionally superseded by per-family defaults.
        for(const TCHAR* Name:{TEXT("AlphaHold"),TEXT("Trim")})
            if(auto* Pin=Node->FindPin(Name)){Pin->BreakAllPinLinks();Node->RemovePin(Pin);++Removed;}
        Node->ReconstructNode();++Refreshed;
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    const FString Report=FString::Printf(TEXT("refreshed=%d removed_old_scalars=%d status=%d saved=0"),Refreshed,Removed,int32(BP->Status));
    FFileHelper::SaveStringToFile(Report,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/FKPerAttackTiming20261004/upgrade.txt")));
    UE_LOG(LogTemp,Display,TEXT("FK per-attack timing: %s"),*Report);
}
static FAutoConsoleCommand FKPerAttackTimingCommand(TEXT("Prophecy.Editor.UpgradeFKPerAttackTiming"),
    TEXT("Replace FK Hold/Trim scalars with 16 per-family vectors; preserve other wiring. Does not save."),
    FConsoleCommandDelegate::CreateStatic(&UpgradeFKPerAttackTiming));
