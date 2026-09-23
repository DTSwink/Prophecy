#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "EdGraphSchema_K2.h"
#include "EdGraphUtilities.h"
#include "K2Node_Event.h"
#include "K2Node_IfThenElse.h"
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
}
