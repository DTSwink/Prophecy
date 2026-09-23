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

namespace ProphecyBlendNodeUpgrade
{
// Explicit one-shot editor migration. No startup/game hook and no asset save.
static void Run()
{
    if (!GEditor || GEditor->PlayWorld) return;
    const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics");
    const FString ReportPath=Dir/TEXT("FineGrainedBlends-Upgrade.txt");
    if (IFileManager::Get().FileExists(*ReportPath))
    { UE_LOG(LogTemp,Warning,TEXT("Blend node upgrade already ran; inspect %s"),*ReportPath);return; }
    FString Before;
    if (!FFileHelper::LoadFileToString(Before,*(Dir/TEXT("FineGrainedBlends-Before.txt")))) return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP) return;
    FSavePackageArgs Save;Save.TopLevelFlags=RF_Public|RF_Standalone;Save.SaveFlags=SAVE_KeepDirty;
    if (!UPackage::SavePackage(BP->GetOutermost(),BP,*(Dir/TEXT("FineGrainedBlends-BeforeUpgrade.uasset")),Save)) return;
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","FineGrainedBlends","Split translation and regional recovery pins"));
    BP->Modify();int32 Nodes=0,Pins=0;bool OK=true;
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
    for (auto* Graph:Graphs) for (UEdGraphNode* Base:Graph->Nodes)
    {
        auto* Node=Cast<UK2Node_CallFunction>(Base);if (!Node) continue;
        const FName Name=Node->FunctionReference.GetMemberName();
        const bool Temper=Name==TEXT("SetLocomotionLowerBodyTempering");
        if (!Temper && Name!=TEXT("SetAttackToLocomotionBlend")) continue;
        const FString Key=TEXT(" | ")+Graph->GetName()+TEXT(" | ")+Node->GetName()+TEXT(" | ");
        if (!Before.Contains(Key)) continue; // Only nodes present before this update.
        Graph->Modify();Node->Modify();Node->ReconstructNode();++Nodes;
        auto Copy=[&](const TCHAR* From,const TCHAR* To)
        {
            auto* Src=Node->FindPin(From);auto* Dst=Node->FindPin(To);
            if (!Src || !Dst || !Dst->LinkedTo.IsEmpty()) { OK=false;return; }
            Dst->DefaultValue=Src->DefaultValue;Dst->DefaultObject=Src->DefaultObject;Dst->DefaultTextValue=Src->DefaultTextValue;
            for (auto* Link:Src->LinkedTo) if (!Graph->GetSchema()->TryCreateConnection(Link,Dst)) OK=false;
            ++Pins;
        };
        if (Temper)
        { Copy(TEXT("FeetTranslation"),TEXT("FeetTranslationZ"));Copy(TEXT("PelvisTranslation"),TEXT("PelvisTranslationZ")); }
        else
        {
            Copy(TEXT("DurationSeconds"),TEXT("LeftLegDurationSeconds"));Copy(TEXT("DurationSeconds"),TEXT("RightLegDurationSeconds"));
            Copy(TEXT("HoldDurationSeconds"),TEXT("LeftLegHoldDurationSeconds"));Copy(TEXT("HoldDurationSeconds"),TEXT("RightLegHoldDurationSeconds"));
        }
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    const FString Report=FString::Printf(TEXT("nodes=%d new_pins=%d connections_ok=%d status=%d asset_saved=0\n"),Nodes,Pins,int32(OK),int32(BP->Status));
    FFileHelper::SaveStringToFile(Report,*ReportPath);UE_LOG(LogTemp,Display,TEXT("Blend node upgrade: %s"),*Report);
}
static FAutoConsoleCommand Command(TEXT("Prophecy.Editor.UpgradeFineGrainedBlends"),TEXT("Explicitly extend old pose-agent blend nodes, preserving old values for both XY/Z and all regions; leaves asset unsaved."),FConsoleCommandDelegate::CreateStatic(&Run));

static TArray<FString> PinValues(const UK2Node_CallFunction* Node)
{
    TArray<FString> Rows;
    for (auto* P:Node->Pins) if (P)
    {
        Rows.Add(P->PinName.ToString()+TEXT("=")+P->DefaultValue+TEXT("|")+P->DefaultTextValue.ToString());
        for (auto* L:P->LinkedTo) if (L)
            Rows.Add(P->PinName.ToString()+TEXT("->")+L->GetOwningNode()->NodeGuid.ToString()+TEXT(":")+L->PinName.ToString());
    }
    Rows.Sort();return Rows;
}
static void RefreshOrderFor(FName FunctionName,const TCHAR* ReportName)
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP) return;
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","RecoveryPinOrder","Order recovery controls by region"));
    BP->Modify();int32 Count=0;bool Preserved=true;
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
    for (auto* Graph:Graphs) for (UEdGraphNode* Base:Graph->Nodes)
    {
        auto* N=Cast<UK2Node_CallFunction>(Base);
        if (!N || N->FunctionReference.GetMemberName()!=FunctionName) continue;
        N->Modify();
        if (FunctionName==TEXT("SetAttackToLocomotionBlend")) if (auto* Force=N->FindPin(TEXT("bForceRun")))
        {
            Force->BreakAllPinLinks();N->RemovePin(Force);
        }
        const bool HadDistanceToLimit=N->FindPin(TEXT("DistanceToLimit"))!=nullptr;
        const bool HadNonKicking=N->FindPin(TEXT("NonKickingFootTranslationXY"))!=nullptr;
        FString OldKickGraph;
        const FString Diagnostics=FPaths::ProjectSavedDir()/TEXT("Diagnostics");
        FFileHelper::LoadFileToString(OldKickGraph,*(Diagnostics/TEXT("KickRolePinsBefore.txt")));
        const FString NodeKey=TEXT(" | ")+Graph->GetName()+TEXT(" | ")+N->GetName()+TEXT(" | ");
        const bool MigrateFeet=FunctionName==TEXT("SetKickLocomotionLowerBodyTempering")
            && (!HadNonKicking || (!IFileManager::Get().FileExists(*(Diagnostics/TEXT("KickTemperingRoles.txt")))
                && OldKickGraph.Contains(NodeKey)));
        auto Before=PinValues(N);
        N->Modify();N->ReconstructNode();++Count;
        if (MigrateFeet)
        {
            const TCHAR* Sources[]={TEXT("FeetTranslation"),TEXT("FeetTranslationZ"),TEXT("FeetRotation")};
            const TCHAR* Targets[]={TEXT("NonKickingFootTranslationXY"),TEXT("NonKickingFootTranslationZ"),TEXT("NonKickingFootRotation")};
            for (int32 I=0;I<3;++I)
            {
                auto* Src=N->FindPin(Sources[I]);auto* Dst=N->FindPin(Targets[I]);
                if (!Src || !Dst) { Preserved=false;continue; }
                // New pins inherit the old shared feet values/connections. Preserve
                // any explicit new-pin edit made after a Live Coding reconstruction.
                if (Dst->LinkedTo.IsEmpty() && FCString::Atof(*Dst->DefaultValue)==1.f)
                {
                    Dst->DefaultValue=Src->DefaultValue;Dst->DefaultObject=Src->DefaultObject;Dst->DefaultTextValue=Src->DefaultTextValue;
                    for (auto* Link:Src->LinkedTo) if (!Graph->GetSchema()->TryCreateConnection(Link,Dst)) Preserved=false;
                }
            }
        }
        auto After=PinValues(N);
        if (MigrateFeet)
        {
            Before.RemoveAll([](const FString& Row) { return Row.StartsWith(TEXT("NonKickingFoot")); });
            After.RemoveAll([](const FString& Row) { return Row.StartsWith(TEXT("NonKickingFoot")); });
        }
        if (!HadDistanceToLimit && FunctionName==TEXT("GetValidAttackTarget"))
        {
            const auto* Margin=N->FindPin(TEXT("DistanceToLimit"));
            Preserved&=Margin && Margin->Direction==EGPD_Output && Margin->LinkedTo.IsEmpty();
            After.RemoveAll([](const FString& Row) { return Row.StartsWith(TEXT("DistanceToLimit=")); });
        }
        Preserved&=Before==After;
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    const FString Report=FString::Printf(TEXT("nodes=%d values_and_links_preserved=%d status=%d asset_saved=0\n"),Count,int32(Preserved),int32(BP->Status));
    FFileHelper::SaveStringToFile(Report,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics")/ReportName));
    UE_LOG(LogTemp,Display,TEXT("Recovery pin order: %s"),*Report);
}
static void RefreshOrder() { RefreshOrderFor(TEXT("SetAttackToLocomotionBlend"),TEXT("RecoveryPinOrder.txt")); }
static void RefreshTemperingOrder() { RefreshOrderFor(TEXT("SetLocomotionLowerBodyTempering"),TEXT("TemperingPinOrder.txt")); }
static void RefreshAttackTargetMargin() { RefreshOrderFor(TEXT("GetValidAttackTarget"),TEXT("AttackTargetMarginPins.txt")); }
static void RefreshKickRoles()
{
    RefreshOrderFor(TEXT("SetKickToLocomotionBlend"),TEXT("KickRecoveryRoles.txt"));
    RefreshOrderFor(TEXT("SetKickLocomotionLowerBodyTempering"),TEXT("KickTemperingRoles.txt"));
}
static FAutoConsoleCommand KickRolesCommand(TEXT("Prophecy.Editor.RefreshKickRoles"),TEXT("Refresh kicking/non-kicking roles and copy old shared foot values to both roles; leave unsaved."),FConsoleCommandDelegate::CreateStatic(&RefreshKickRoles));
static FAutoConsoleCommand AttackTargetMarginCommand(TEXT("Prophecy.Editor.RefreshAttackTargetMargin"),TEXT("Add the distance-to-limit output on existing target queries; preserve values and links, leave unsaved."),FConsoleCommandDelegate::CreateStatic(&RefreshAttackTargetMargin));
static FAutoConsoleCommand OrderCommand(TEXT("Prophecy.Editor.RefreshRecoveryPinOrder"),TEXT("Refresh recovery pin order while retaining named pins and their connections; leaves Blueprint unsaved."),FConsoleCommandDelegate::CreateStatic(&RefreshOrder));
static FAutoConsoleCommand TemperingOrderCommand(TEXT("Prophecy.Editor.RefreshTemperingPinOrder"),TEXT("Group tempering pins by feet/pelvis and XY/Z/rotation; retains values and connections, leaves Blueprint unsaved."),FConsoleCommandDelegate::CreateStatic(&RefreshTemperingOrder));
}
