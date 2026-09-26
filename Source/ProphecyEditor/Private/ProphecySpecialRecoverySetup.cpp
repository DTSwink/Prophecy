#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "EdGraphSchema_K2.h"
#include "EdGraphUtilities.h"
#include "K2Node_Event.h"
#include "K2Node_IfThenElse.h"
#include "K2Node_CallFunction.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ScopedTransaction.h"

namespace ProphecySpecialRecoverySetup
{
void Install(const TArray<FString>& Args)
{
    if(!GEditor || GEditor->PlayWorld) { UE_LOG(LogTemp,Warning,TEXT("SpecialRecovery: stop Play before graph migration"));return; }
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    auto* Interface=FindObject<UClass>(nullptr,TEXT("/Script/GameAnimationSample3.ProphecySpecialRecoveryEvents"));
    if(!BP || !Interface) return;
    UEdGraph* Graph=nullptr;UK2Node_Event* Old=nullptr;UK2Node_Event* Event=nullptr;
    for(UEdGraph* G:BP->UbergraphPages) for(UEdGraphNode* N:G->Nodes) if(auto* E=Cast<UK2Node_Event>(N))
    {
        if(E->EventReference.GetMemberName()==TEXT("OnNNAttackEnded")) { Old=E;Graph=G; }
        if(E->EventReference.GetMemberName()==TEXT("OnNNSpecialEnded")) Event=E;
    }
    if(!Graph || !Old) { UE_LOG(LogTemp,Error,TEXT("SpecialRecovery: expected attack end event missing; no edits"));return; }
    const bool Move=Args.Contains(TEXT("MoveRecovery"));
    TSet<UObject*> Nodes;for(UEdGraphNode* N:Graph->Nodes) Nodes.Add(N);
    FString Backup;FEdGraphUtilities::ExportNodesToText(Nodes,Backup);
    FFileHelper::SaveStringToFile(Backup,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/BeforeSpecialRecovery-")+FDateTime::Now().ToString(TEXT("%Y%m%d-%H%M%S"))+TEXT(".txt")));
    FScopedTransaction Transaction(NSLOCTEXT("Prophecy","SpecialRecovery","Expose shared Special Ended recovery"));
    BP->Modify();Graph->Modify();Old->Modify();
    bool HasInterface=false;for(const auto& D:BP->ImplementedInterfaces) HasInterface|=D.Interface==Interface;
    if(!HasInterface && !FBlueprintEditorUtils::ImplementNewInterface(BP,FTopLevelAssetPath(TEXT("/Script/GameAnimationSample3"),TEXT("ProphecySpecialRecoveryEvents")))) return;
    if(!Event)
    {
        FGraphNodeCreator<UK2Node_Event> C(*Graph);Event=C.CreateNode();
        Event->EventReference.SetExternalMember(TEXT("OnNNSpecialEnded"),Interface);Event->bOverrideFunction=true;
        Event->NodePosX=Old->NodePosX;Event->NodePosY=Old->NodePosY+300;C.Finalize();
    }
    bool OK=true;auto* Schema=GetDefault<UEdGraphSchema_K2>();
    if(Move && Old->FindPinChecked(TEXT("then"))->LinkedTo.Num())
    {
        FGraphNodeCreator<UK2Node_IfThenElse> C(*Graph);auto* Gate=C.CreateNode();Gate->NodePosX=Event->NodePosX+250;Gate->NodePosY=Event->NodePosY;C.Finalize();
        auto* From=Old->FindPinChecked(TEXT("then"));const auto Links=From->LinkedTo;
        OK&=Schema->TryCreateConnection(Event->FindPinChecked(TEXT("then")),Gate->GetExecPin());
        OK&=Schema->TryCreateConnection(Event->FindPinChecked(TEXT("ReturningToLocomotion")),Gate->GetConditionPin());
        for(auto* P:Links) { From->BreakLinkTo(P);OK&=Schema->TryCreateConnection(Gate->GetThenPin(),P); }
        for(auto Pair:{TPair<FName,FName>(TEXT("Attack"),TEXT("Attack")),TPair<FName,FName>(TEXT("bHalfAttack"),TEXT("HalfAttack"))})
        {
            auto* Source=Old->FindPin(Pair.Key);auto* Dest=Event->FindPin(Pair.Value);if(!Source || !Dest)continue;
            const auto Pins=Source->LinkedTo;for(auto* P:Pins) { Source->BreakLinkTo(P);OK&=Schema->TryCreateConnection(Dest,P); }
        }
        Gate->NodeComment=TEXT("Recovery runs only when returning to locomotion, not when one special replaces another.");Gate->bCommentBubbleVisible=true;
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    UE_LOG(LogTemp,Display,TEXT("SpecialRecovery: shared_event=1 moved=%d connections_ok=%d status=%d asset_saved=0"),Move,OK,int32(BP->Status));
}
FAutoConsoleCommand Command(TEXT("Prophecy.Editor.SpecialRecovery"),TEXT("Expose Special Ended; optional MoveRecovery migrates the existing end chain without saving."),FConsoleCommandWithArgsDelegate::CreateStatic(&Install));

void SplitRegions()
{
    UE_LOG(LogTemp,Display,TEXT("Regional recovery: checking graph"));
    if (!GEditor || GEditor->PlayWorld) { UE_LOG(LogTemp,Warning,TEXT("Regional recovery: editor unavailable or Play active"));return; }
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    auto* Interface=FindObject<UClass>(nullptr,TEXT("/Script/GameAnimationSample3.ProphecySpecialRecoveryEvents"));
    if (!BP || !Interface || !Interface->FindFunctionByName(TEXT("OnNNUpperSpecialEnded"))
        || !Interface->FindFunctionByName(TEXT("OnNNLowerSpecialEnded"))) { UE_LOG(LogTemp,Error,TEXT("Regional recovery: missing Blueprint/interface/functions"));return; }
    UK2Node_Event* Event=nullptr;
    for (UEdGraph* G:BP->UbergraphPages) for (UEdGraphNode* N:G->Nodes) if (auto* E=Cast<UK2Node_Event>(N))
    {
        if (E->EventReference.GetMemberName()==TEXT("OnNNUpperSpecialEnded"))
        { UE_LOG(LogTemp,Display,TEXT("Regional recovery already installed; no edits"));return; }
        if (E->EventReference.GetMemberName()==TEXT("OnNNSpecialEnded")) Event=E;
    }
    if (!Event) { UE_LOG(LogTemp,Error,TEXT("Regional recovery: combined event missing"));return; }
    auto* Graph=Event->GetGraph();
    auto Find=[&](FName Name)->UEdGraphNode* { for (UEdGraphNode* N:Graph->Nodes) if(N && N->GetFName()==Name)return N;return nullptr; };
    auto* Arm=Cast<UK2Node_CallFunction>(Find(TEXT("K2Node_CallFunction_157")));
    auto* Lower=Cast<UK2Node_CallFunction>(Find(TEXT("K2Node_CallFunction_206")));
    auto* EndLower=Cast<UK2Node_CallFunction>(Find(TEXT("K2Node_CallFunction_209")));
    auto* Hand=Cast<UK2Node_CallFunction>(Find(TEXT("K2Node_CallFunction_203")));
    auto* HandEnd=Cast<UK2Node_CallFunction>(Find(TEXT("K2Node_CallFunction_204")));
    auto* TimerBranch=Cast<UK2Node_IfThenElse>(Find(TEXT("K2Node_IfThenElse_20")));
    if(!Arm || !Lower || !EndLower || !Hand || !HandEnd || !TimerBranch
        || Arm->FunctionReference.GetMemberName()!=TEXT("SetSlashRightArmReturnToNeutral")
        || Lower->FunctionReference.GetMemberName()!=TEXT("SetLocomotionLowerBodyTempering")
        || EndLower->FunctionReference.GetMemberName()!=TEXT("SetAttackToLocomotionBlend")
        || Hand->FunctionReference.GetMemberName()!=TEXT("SetLocomotionHandTempering"))
    { UE_LOG(LogTemp,Error,TEXT("Regional recovery: functions differ from the current audited graph; no edits"));return; }
    auto* ArmIn=Arm->FindPinChecked(TEXT("execute"));auto* ArmOut=Arm->FindPinChecked(TEXT("then"));
    auto* HandIn=Hand->FindPinChecked(TEXT("execute"));auto* HandOut=HandEnd->FindPinChecked(TEXT("then"));
    auto* TimerIn=TimerBranch->GetExecPin();
    // The user has already separated the current lower and hand/arm chains.
    // Preserve that newer layout rather than restoring the earlier mixed chain.
    if(HandIn->LinkedTo.Num()!=0 || ArmIn->LinkedTo.Num()!=1 || ArmIn->LinkedTo[0]!=HandOut
        || HandOut->LinkedTo.Num()!=1 || ArmOut->LinkedTo.Num()!=0
        || EndLower->FindPinChecked(TEXT("then"))->LinkedTo.Num()!=0 || TimerIn->LinkedTo.Num()!=1)
    { UE_LOG(LogTemp,Error,TEXT("Regional recovery: prepared chain links changed; no edits"));return; }
    TSet<UObject*> Nodes;for(UEdGraphNode* N:Graph->Nodes) Nodes.Add(N);
    FString Backup;FEdGraphUtilities::ExportNodesToText(Nodes,Backup);
    FFileHelper::SaveStringToFile(Backup,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/BeforeRegionalRecovery-")+FDateTime::Now().ToString(TEXT("%Y%m%d-%H%M%S"))+TEXT(".txt")));
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","SplitRegionalRecovery","Split upper and lower special recovery"));
    BP->Modify();Graph->Modify();for(UEdGraphNode* N:Graph->Nodes) N->Modify();
    Event->EventReference.SetExternalMember(TEXT("OnNNLowerSpecialEnded"),Interface);Event->ReconstructNode();
    FGraphNodeCreator<UK2Node_Event> EC(*Graph);auto* Upper=EC.CreateNode();
    Upper->EventReference.SetExternalMember(TEXT("OnNNUpperSpecialEnded"),Interface);Upper->bOverrideFunction=true;
    Upper->NodePosX=Event->NodePosX;Upper->NodePosY=Event->NodePosY-450;EC.Finalize();
    FGraphNodeCreator<UK2Node_IfThenElse> GC(*Graph);auto* Gate=GC.CreateNode();
    Gate->NodePosX=Upper->NodePosX+300;Gate->NodePosY=Upper->NodePosY;GC.Finalize();
    Upper->FindPinChecked(TEXT("then"))->MakeLinkTo(Gate->GetExecPin());
    Upper->FindPinChecked(TEXT("ReturningToLocomotion"))->MakeLinkTo(Gate->GetConditionPin());
    Gate->GetThenPin()->MakeLinkTo(HandIn);
    // Cleanup of the ongoing attack timer belongs to upper completion.
    TimerIn->BreakAllPinLinks();ArmOut->MakeLinkTo(TimerIn);
    Event->NodeComment=TEXT("Lower-body ownership ended: leg, pelvis and foot recovery only.");Event->bCommentBubbleVisible=true;
    Upper->NodeComment=TEXT("Upper-body ownership ended: arm return and hand recovery only.");Upper->bCommentBubbleVisible=true;
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    UE_LOG(LogTemp,Display,TEXT("Regional recovery installed: upper/lower separated, BP status=%d, asset_saved=0"),int32(BP->Status));
}
FAutoConsoleCommand SplitCommand(TEXT("Prophecy.Editor.SplitSpecialRecovery"),TEXT("Split the audited recovery graph into upper/lower events; undoable, no save."),FConsoleCommandDelegate::CreateStatic(&SplitRegions));
}
