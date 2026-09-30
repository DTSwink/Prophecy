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
        if(FunctionName==TEXT("SetAttackStartPelvisInertia"))
            for(const TCHAR* Name:{TEXT("LeftFootTranslationWindowFrames"),TEXT("LeftFootTranslationInertia"),
                TEXT("LeftFootRotationWindowFrames"),TEXT("LeftFootRotationInertia"),
                TEXT("RightFootTranslationWindowFrames"),TEXT("RightFootTranslationInertia"),
                TEXT("RightFootRotationWindowFrames"),TEXT("RightFootRotationInertia")})
                if(auto* P=N->FindPin(Name)) {P->BreakAllPinLinks();N->RemovePin(P);}
        const bool HadDistanceToLimit=N->FindPin(TEXT("DistanceToLimit"))!=nullptr;
        const bool HadLerpTarget=N->FindPin(TEXT("LerpTarget"))!=nullptr;
        const bool HadPositionCompensation=N->FindPin(TEXT("CompensatePosition"))!=nullptr;
        const bool HadNonKicking=N->FindPin(TEXT("NonKickingFootTranslationXY"))!=nullptr;
        const bool HadAttackReachFamilies=N->FindPin(TEXT("SlashR"))!=nullptr;
        FString OldKickGraph;
        const FString Diagnostics=FPaths::ProjectSavedDir()/TEXT("Diagnostics");
        FFileHelper::LoadFileToString(OldKickGraph,*(Diagnostics/TEXT("KickRolePinsBefore.txt")));
        const FString NodeKey=TEXT(" | ")+Graph->GetName()+TEXT(" | ")+N->GetName()+TEXT(" | ");
        FString OldReachGraph;
        if (FunctionName==TEXT("SetAttackTargetExtraReach"))
            FFileHelper::LoadFileToString(OldReachGraph,*(Diagnostics/TEXT("AttackTargetExtraReachBefore.txt")));
        const bool MigrateReach=FunctionName==TEXT("SetAttackTargetExtraReach")
            && (!HadAttackReachFamilies || (!IFileManager::Get().FileExists(*(Diagnostics/ReportName)) && OldReachGraph.Contains(NodeKey)));
        const bool MigrateFeet=FunctionName==TEXT("SetKickLocomotionLowerBodyTempering")
            && (!HadNonKicking || (!IFileManager::Get().FileExists(*(Diagnostics/TEXT("KickTemperingRoles.txt")))
                && OldKickGraph.Contains(NodeKey)));
        auto Before=PinValues(N);
        N->Modify();N->ReconstructNode();++Count;
        const TCHAR* ReachPins[]={TEXT("SlashR"),TEXT("SlashLD"),TEXT("SlashRD"),TEXT("SlashLU"),TEXT("SlashRU"),TEXT("Pike"),
            TEXT("JabL"),TEXT("JabR"),TEXT("HookL"),TEXT("HookR"),TEXT("OverL"),TEXT("OverR"),TEXT("Headbutt"),TEXT("KickL"),TEXT("KickR")};
        if (MigrateReach)
        {
            // ExtraReachCm retains its old pin identity and now displays slashL.
            // Copy the old common setting to every added family; keep explicit
            // edits made to new pins after Live Coding reconstructed the node.
            auto* Src=N->FindPin(TEXT("ExtraReachCm"));
            if (!Src) Preserved=false;
            else for (const TCHAR* Name:ReachPins)
            {
                auto* Dst=N->FindPin(Name);
                if (!Dst) { Preserved=false;continue; }
                if (!Dst->LinkedTo.IsEmpty() || FCString::Atof(*Dst->DefaultValue)!=50.f) continue;
                Dst->DefaultValue=Src->DefaultValue;Dst->DefaultObject=Src->DefaultObject;Dst->DefaultTextValue=Src->DefaultTextValue;
                for (auto* Link:Src->LinkedTo) if (!Graph->GetSchema()->TryCreateConnection(Link,Dst)) Preserved=false;
            }
        }
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
        if (!HadPositionCompensation && FunctionName==TEXT("EnableSpine01CompensationHalfAttack"))
        {
            const auto* Position=N->FindPin(TEXT("CompensatePosition"));
            Preserved&=Position && Position->LinkedTo.IsEmpty() && Position->DefaultValue==TEXT("false");
            After.RemoveAll([](const FString& Row) { return Row.StartsWith(TEXT("CompensatePosition=")); });
        }
        if (!HadLerpTarget && FunctionName==TEXT("SetWalkPinningBackwardBound"))
        {
            const auto* Lerp=N->FindPin(TEXT("LerpTarget"));
            Preserved&=Lerp && Lerp->LinkedTo.IsEmpty() && FCString::Atof(*Lerp->DefaultValue)==0.f;
            After.RemoveAll([](const FString& Row) { return Row.StartsWith(TEXT("LerpTarget=")) || Row.StartsWith(TEXT("LerpTarget->")); });
        }
        if (MigrateReach)
        {
            auto IsAddedReachPin=[&](const FString& Row)
            {
                for (const TCHAR* Name:ReachPins) if (Row.StartsWith(FString(Name)+TEXT("=")) || Row.StartsWith(FString(Name)+TEXT("->"))) return true;
                return false;
            };
            Before.RemoveAll(IsAddedReachPin);After.RemoveAll(IsAddedReachPin);
        }
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
        if(FunctionName==TEXT("SetArmRepellantCone"))
        {
            auto NewPin=[](const FString& Row)
            { return Row.StartsWith(TEXT("EnableWristTwistRecoil=")) || Row.StartsWith(TEXT("TwistLimitDegrees=")) || Row.StartsWith(TEXT("TwistRecoilStrength=")) || Row.StartsWith(TEXT("TwistDamping=")); };
            // Compare all original pins; the new pins are intentionally added with defaults.
            Before.RemoveAll(NewPin);After.RemoveAll(NewPin);
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
static void RefreshSpinePosition() { RefreshOrderFor(TEXT("EnableSpine01CompensationHalfAttack"),TEXT("SpinePositionPins.txt")); }
static FAutoConsoleCommand SpinePositionCommand(TEXT("Prophecy.Editor.RefreshSpinePosition"),TEXT("Add position compensation checkbox; preserve existing values and links, leave unsaved."),FConsoleCommandDelegate::CreateStatic(&RefreshSpinePosition));
static void RefreshTemperingOrder() { RefreshOrderFor(TEXT("SetLocomotionLowerBodyTempering"),TEXT("TemperingPinOrder.txt")); }
static void RefreshAttackTargetMargin() { RefreshOrderFor(TEXT("GetValidAttackTarget"),TEXT("AttackTargetMarginPins.txt")); }
static void RefreshAttackTargetExtraReach() { RefreshOrderFor(TEXT("SetAttackTargetExtraReach"),TEXT("AttackTargetExtraReachPins.txt")); }
static void RefreshWalkBoundTarget() { RefreshOrderFor(TEXT("SetWalkPinningBackwardBound"),TEXT("WalkBoundTargetPins.txt")); }
static void RestorePelvisOnlyInertia() { RefreshOrderFor(TEXT("SetAttackStartPelvisInertia"),TEXT("RestorePelvisOnlyPins.txt")); }
static FAutoConsoleCommand RestorePelvisOnlyCommand(TEXT("Prophecy.Editor.RestorePelvisOnlyInertia"),TEXT("Remove discarded foot-entry controls; retain pelvis values and wiring."),FConsoleCommandDelegate::CreateStatic(&RestorePelvisOnlyInertia));
static void RemoveWalkLimitNodes()
{
    if(!GEditor || GEditor->PlayWorld)return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if(!BP)return;
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","RemoveWalkLimit","Remove obsolete raw Walk pinning limit"));
    BP->Modify();TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);int32 Removed=0;bool OK=true;
    for(auto* Graph:Graphs)
    {
        const auto Nodes=Graph->Nodes;
        for(UEdGraphNode* Base:Nodes)
        {
            auto* N=Cast<UK2Node_CallFunction>(Base);if(!N)continue;
            const auto Name=N->FunctionReference.GetMemberName();
            const bool Setter=Name==TEXT("SetWalkPinningLimit");
            if(!Setter && Name!=TEXT("GetWalkPinningLimit"))continue;
            Graph->Modify();N->Modify();
            TArray<UEdGraphPin*> Incoming,Outgoing,Results;
            if(auto* P=N->FindPin(TEXT("execute")))Incoming=P->LinkedTo;
            if(auto* P=N->FindPin(TEXT("then")))Outgoing=P->LinkedTo;
            if(auto* P=N->FindPin(TEXT("ReturnValue")))Results=P->LinkedTo;
            N->BreakAllNodeLinks();
            for(auto* From:Incoming)for(auto* To:Outgoing)OK&=Graph->GetSchema()->TryCreateConnection(From,To);
            // Remove obsolete readbacks without leaving dangling data pins.
            for(auto* Result:Results)Graph->GetSchema()->TrySetDefaultValue(*Result,Setter?TEXT("true"):TEXT("2.0"));
            FBlueprintEditorUtils::RemoveNode(BP,N,true);++Removed;
        }
    }
    const FString Report=FString::Printf(TEXT("removed=%d execution_reconnected=%d asset_saved=0\n"),Removed,int32(OK));
    FFileHelper::SaveStringToFile(Report,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/RemoveWalkPinLimit.txt")));
    UE_LOG(LogTemp,Display,TEXT("Walk pin limit removal: %s"),*Report);
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
}
static FAutoConsoleCommand RemoveWalkLimitCommand(TEXT("Prophecy.Editor.RemoveWalkPinningLimit"),TEXT("Remove obsolete Walk raw-limit calls and reconnect execution; leaves Blueprint unsaved."),FConsoleCommandDelegate::CreateStatic(&RemoveWalkLimitNodes));
static FAutoConsoleCommand WalkBoundTargetCommand(TEXT("Prophecy.Editor.RefreshWalkBoundTarget"),TEXT("Add the default-zero Lerp Target pin to backward pin bound nodes; preserve existing values/wiring, leave unsaved."),FConsoleCommandDelegate::CreateStatic(&RefreshWalkBoundTarget));
static FAutoConsoleCommand AttackTargetExtraReachCommand(TEXT("Prophecy.Editor.RefreshAttackTargetExtraReach"),TEXT("Expand existing extra reach nodes to all attack families, preserving prior common values/connections; leave unsaved."),FConsoleCommandDelegate::CreateStatic(&RefreshAttackTargetExtraReach));
static void RefreshKickRoles()
{
    RefreshOrderFor(TEXT("SetKickToLocomotionBlend"),TEXT("KickRecoveryRoles.txt"));
    RefreshOrderFor(TEXT("SetKickLocomotionLowerBodyTempering"),TEXT("KickTemperingRoles.txt"));
}
static FAutoConsoleCommand KickRolesCommand(TEXT("Prophecy.Editor.RefreshKickRoles"),TEXT("Refresh kicking/non-kicking roles and copy old shared foot values to both roles; leave unsaved."),FConsoleCommandDelegate::CreateStatic(&RefreshKickRoles));
static FAutoConsoleCommand AttackTargetMarginCommand(TEXT("Prophecy.Editor.RefreshAttackTargetMargin"),TEXT("Add the distance-to-limit output on existing target queries; preserve values and links, leave unsaved."),FConsoleCommandDelegate::CreateStatic(&RefreshAttackTargetMargin));
static FAutoConsoleCommand OrderCommand(TEXT("Prophecy.Editor.RefreshRecoveryPinOrder"),TEXT("Refresh recovery pin order while retaining named pins and their connections; leaves Blueprint unsaved."),FConsoleCommandDelegate::CreateStatic(&RefreshOrder));
static FAutoConsoleCommand TemperingOrderCommand(TEXT("Prophecy.Editor.RefreshTemperingPinOrder"),TEXT("Group tempering pins by feet/pelvis and XY/Z/rotation; retains values and connections, leaves Blueprint unsaved."),FConsoleCommandDelegate::CreateStatic(&RefreshTemperingOrder));
static void RefreshBothArmReturn()
{
    if(!GEditor || GEditor->PlayWorld) return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    auto* Class=LoadObject<UClass>(nullptr,TEXT("/Script/GameAnimationSample3.ProphecySlashReturnLibrary"));
    auto* Function=Class?Class->FindFunctionByName(TEXT("SetAttackBothArmsReturnToNeutral")):nullptr;
    if(!BP || !Function) return;
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","BothArmReturnCheckboxes","Replace attack selector with return checkboxes"));
    BP->Modify();int32 Count=0;bool Preserved=true,DefaultsOff=true;FString Prior;
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
    for(auto* Graph:Graphs) for(UEdGraphNode* Base:Graph->Nodes)
    {
        auto* N=Cast<UK2Node_CallFunction>(Base);
        if(!N || N->FunctionReference.GetMemberName()!=TEXT("SetAttackBothArmsReturnToNeutral")) continue;
        if(!N->FindPin(TEXT("Attack")) && !N->FindPin(TEXT("Enabled"))) continue;
        Graph->Modify();N->Modify();
        for(auto* P:N->Pins) if(P) Prior+=Graph->GetName()+TEXT("/")+N->GetName()+TEXT("/")+P->PinName.ToString()+TEXT("=")+P->DefaultValue+TEXT("\n");
        for(const TCHAR* Name:{TEXT("Attack"),TEXT("Enabled")}) if(auto* P=N->FindPin(Name))
        { P->BreakAllPinLinks();N->RemovePin(P); }
        const auto Before=PinValues(N);
        N->SetFromFunction(Function);N->ReconstructNode();++Count;
        const auto After=PinValues(N);for(const auto& Row:Before) if(!After.Contains(Row)) Preserved=false;
        int32 Bools=0;
        for(auto* P:N->Pins) if(P && P->Direction==EGPD_Input && P->PinType.PinCategory==UEdGraphSchema_K2::PC_Boolean)
        { ++Bools;DefaultsOff&=P->DefaultValue==TEXT("false") && P->LinkedTo.IsEmpty(); }
        DefaultsOff&=Bools==16;
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    const FString Report=FString::Printf(TEXT("nodes=%d existing_connections_and_values_preserved=%d all16_defaults_off=%d status=%d asset_saved=0\n"),Count,int32(Preserved),int32(DefaultsOff),int32(BP->Status))+Prior;
    FFileHelper::SaveStringToFile(Report,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/BothArmReturnCheckboxes.txt")));
    UE_LOG(LogTemp,Display,TEXT("Both-arm return checkbox upgrade: %s"),*Report);
}
static FAutoConsoleCommand BothArmReturnCommand(TEXT("Prophecy.Editor.RefreshBothArmReturn"),TEXT("Replace the old attack-name/enable selector pins with16 unchecked attack inputs. Preserve execution/Agent/output wiring; leave Blueprint unsaved."),FConsoleCommandDelegate::CreateStatic(&RefreshBothArmReturn));
static void RefreshFootLocomotionHandoff()
{
    if(!GEditor || GEditor->PlayWorld)return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if(!BP)return;
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","FootLocomotionHandoff","Add foot rotation and independent handoff durations"));
    BP->Modify();int32 Count=0;bool Preserved=true,Defaults=true;
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
    const FName Pins[]={TEXT("AlphaRotation"),TEXT("LeftBlendDurationSeconds"),TEXT("RightBlendDurationSeconds"),TEXT("KneePoleBlendDurationSeconds")};
    for(auto* G:Graphs)for(UEdGraphNode* Base:G->Nodes)
    {
        auto* N=Cast<UK2Node_CallFunction>(Base);if(!N || N->FunctionReference.GetMemberName()!=TEXT("SetAttackFootLocomotion"))continue;
        bool Had[UE_ARRAY_COUNT(Pins)];for(int32 I=0;I<UE_ARRAY_COUNT(Pins);++I)Had[I]=N->FindPin(Pins[I])!=nullptr;
        const auto Before=PinValues(N);G->Modify();N->Modify();N->ReconstructNode();++Count;
        const auto After=PinValues(N);for(const auto& Row:Before)Preserved&=After.Contains(Row);
        for(int32 I=0;I<UE_ARRAY_COUNT(Pins);++I)if(!Had[I])
        {const auto* P=N->FindPin(Pins[I]);Defaults&=P && P->LinkedTo.IsEmpty() && FCString::Atof(*P->DefaultValue)==(I==0?1.f:0.f);}
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    const FString Report=FString::Printf(TEXT("nodes=%d values_and_links_preserved=%d new_defaults_correct=%d status=%d asset_saved=0\n"),Count,int32(Preserved),int32(Defaults),int32(BP->Status));
    FFileHelper::SaveStringToFile(Report,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootLocomotionHandoffPins.txt")));
    UE_LOG(LogTemp,Display,TEXT("Foot locomotion handoff pins: %s"),*Report);
}
static FAutoConsoleCommand FootLocomotionHandoffCommand(TEXT("Prophecy.Editor.RefreshFootLocomotionHandoff"),TEXT("Add foot rotation/handoff pins on existing loco-drag nodes, preserve values/wiring and leave unsaved."),FConsoleCommandDelegate::CreateStatic(&RefreshFootLocomotionHandoff));
static void DisableOverriddenUpperReturn()
{
    if(!GEditor || GEditor->PlayWorld)return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if(!BP)return;
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
    TArray<UK2Node_CallFunction*> Nodes;
    for(auto* G:Graphs)if(G->GetFName()==TEXT("EventGraph"))for(UEdGraphNode* N:G->Nodes)
    {
        auto* C=Cast<UK2Node_CallFunction>(N);if(!C)continue;
        if((C->GetFName()==TEXT("K2Node_CallFunction_203") && C->FunctionReference.GetMemberName()==TEXT("SetLocomotionHandTempering")) ||
            (C->GetFName()==TEXT("K2Node_CallFunction_157") && C->FunctionReference.GetMemberName()==TEXT("SetSlashRightArmReturnToNeutral")))Nodes.Add(C);
    }
    if(Nodes.Num()!=2)return;
    for(auto* N:Nodes)if(!N->FindPin(TEXT("Enabled")) || !N->FindPin(TEXT("Enabled"))->LinkedTo.IsEmpty())return;
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","UpperInertiaControls","Keep upper exit tempering and neutral return disabled"));
    BP->Modify();
    for(auto* N:Nodes){N->Modify();N->GetGraph()->Modify();N->FindPin(TEXT("Enabled"))->DefaultValue=TEXT("false");}
    FBlueprintEditorUtils::MarkBlueprintAsModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    UE_LOG(LogTemp,Display,TEXT("Upper exit overrides: two Enabled pins set false, links unchanged, BP status=%d, asset_saved=0"),int32(BP->Status));
}
static FAutoConsoleCommand UpperReturnOverrideCommand(TEXT("Prophecy.Editor.DisableOverriddenUpperReturn"),TEXT("Explicitly disable the two stale upper-exit control setters; preserve wiring and leave unsaved."),FConsoleCommandDelegate::CreateStatic(&DisableOverriddenUpperReturn));
static void RefreshUpperInertiaSpace()
{
    if(!GEditor || GEditor->PlayWorld)return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if(!BP)return;
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","UpperInertiaSpace","Add hand inertia reference space"));
    BP->Modify();int32 Count=0;bool Preserved=true,Defaults=true;
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
    for(auto* G:Graphs)for(UEdGraphNode* Base:G->Nodes)
    {
        auto* N=Cast<UK2Node_CallFunction>(Base);if(!N || N->FunctionReference.GetMemberName()!=TEXT("SetAttackUpperBodyInertia"))continue;
        const bool Had=N->FindPin(TEXT("HandInertiaSpace"))!=nullptr;
        const bool HadAlpha=N->FindPin(TEXT("Alpha"))!=nullptr;
        const auto Before=PinValues(N);G->Modify();N->Modify();N->ReconstructNode();++Count;
        const auto After=PinValues(N);for(const auto& Row:Before)Preserved&=After.Contains(Row);
        if(!Had){const auto* P=N->FindPin(TEXT("HandInertiaSpace"));Defaults&=P && P->LinkedTo.IsEmpty() && P->DefaultValue==TEXT("RootLocal");}
        if(!HadAlpha){const auto* P=N->FindPin(TEXT("Alpha"));Defaults&=P && P->LinkedTo.IsEmpty() && FCString::Atof(*P->DefaultValue)==1.f;}
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    UE_LOG(LogTemp,Display,TEXT("Upper inertia space pins: nodes=%d preserved=%d defaults=%d status=%d asset_saved=0"),Count,int32(Preserved),int32(Defaults),int32(BP->Status));
}
static FAutoConsoleCommand UpperInertiaSpaceCommand(TEXT("Prophecy.Editor.RefreshUpperInertiaSpace"),TEXT("Add Root Local/Spine Local selector to existing upper inertia nodes; preserve wiring and leave unsaved."),FConsoleCommandDelegate::CreateStatic(&RefreshUpperInertiaSpace));
}

namespace ProphecyBlendNodeUpgrade
{
static void RefreshArmConeTwist(){RefreshOrderFor(TEXT("SetArmRepellantCone"),TEXT("ArmConeTwistPins.txt"));}
static FAutoConsoleCommand ArmConeTwistCommand(TEXT("Prophecy.Editor.RefreshArmConeTwist"),TEXT("Add optional wrist recoil pins; preserve existing values and wiring, leave unsaved."),FConsoleCommandDelegate::CreateStatic(&RefreshArmConeTwist));
}
namespace ProphecyBlendNodeUpgrade
{
// Explicit diagnostic preview; never saves. Restore exact prior pin literals afterwards.
static TMap<FGuid,TArray<FString>> WristPreviewPins;
static void PreviewArmConeTwist(const TArray<FString>& Args)
{
    if(!GEditor || GEditor->PlayWorld || Args.Num()!=1)return;
    const bool On=Args[0]==TEXT("on"),Off=Args[0]==TEXT("restore");
    if((!On&&!Off) || (On&&!WristPreviewPins.IsEmpty()))return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if(!BP)return;
    const TCHAR* Pins[]={TEXT("EnableWristTwistRecoil"),TEXT("TwistLimitDegrees"),TEXT("TwistRecoilStrength"),TEXT("TwistDamping")};
    const TCHAR* Values[]={TEXT("true"),TEXT("60"),TEXT("1000000"),TEXT("20")};
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);int32 Count=0;
    for(auto* G:Graphs)for(UEdGraphNode* Base:G->Nodes)
    {
        auto* N=Cast<UK2Node_CallFunction>(Base);
        if(!N || N->FunctionReference.GetMemberName()!=TEXT("SetArmRepellantCone"))continue;
        bool OK=true;for(const TCHAR* P:Pins)if(!N->FindPin(P)||!N->FindPin(P)->LinkedTo.IsEmpty())OK=false;
        if(!OK)continue;
        if(On)
        {
            TArray<FString> Old;for(const TCHAR* P:Pins)Old.Add(N->FindPin(P)->DefaultValue);
            WristPreviewPins.Add(N->NodeGuid,MoveTemp(Old));
            for(int32 I=0;I<4;++I)N->FindPin(Pins[I])->DefaultValue=Values[I];++Count;
        }
        else if(const auto* Old=WristPreviewPins.Find(N->NodeGuid))
        {for(int32 I=0;I<4;++I)N->FindPin(Pins[I])->DefaultValue=(*Old)[I];++Count;}
    }
    if(Off)WristPreviewPins.Reset();
    if(Count){FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);}
    UE_LOG(LogTemp,Display,TEXT("ArmCone twist preview %s nodes=%d status=%d saved=0"),*Args[0],Count,int32(BP->Status));
}
static FAutoConsoleCommand WristPreviewCommand(TEXT("Prophecy.Editor.PreviewArmConeTwist"),TEXT("Diagnostic on/restore of wrist recoil pins; preserves prior literals; never saves."),FConsoleCommandWithArgsDelegate::CreateStatic(&PreviewArmConeTwist));
}
