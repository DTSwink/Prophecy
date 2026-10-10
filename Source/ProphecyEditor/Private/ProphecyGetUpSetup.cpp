#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CallFunction.h"
#include "K2Node_IfThenElse.h"
#include "K2Node_VariableGet.h"
#include "Kismet/KismetMathLibrary.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ScopedTransaction.h"
#include "UObject/UnrealType.h"
#include "ProphecyGetUpLibrary.h"

namespace ProphecyGetUpSetup
{
// Migration for the removed floor-correction API; preserve the surrounding flow.
static void RemoveFloorCorrectionCalls()
{
    if(!GEditor || GEditor->PlayWorld)return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if(!BP)return;
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
    TArray<UK2Node_CallFunction*> Calls;
    const auto* Schema=GetDefault<UEdGraphSchema_K2>();
    for(auto* G:Graphs)for(UEdGraphNode* N:G->Nodes)
        if(auto* C=Cast<UK2Node_CallFunction>(N))if(C->FunctionReference.GetMemberName()==TEXT("SetGetUpFloorCorrection"))Calls.Add(C);
    for(auto* C:Calls)
    {
        auto* In=C->GetExecPin();auto* Out=C->GetThenPin();auto* Result=C->FindPin(TEXT("ReturnValue"));
        if(!In || !Out || In->LinkedTo.Num()!=1 || Out->LinkedTo.Num()!=1 || (Result && !Result->LinkedTo.IsEmpty()) ||
            Schema->CanCreateConnection(In->LinkedTo[0],Out->LinkedTo[0]).Response==CONNECT_RESPONSE_DISALLOW)
        { UE_LOG(LogTemp,Error,TEXT("Floor correction removal: unexpected links; no changes."));return; }
    }
    const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","RemoveGetUpFloorCorrection","Remove get-up floor correction"));
    BP->Modify();
    for(auto* C:Calls)
    {
        C->GetGraph()->Modify();C->Modify();
        auto* From=C->GetExecPin()->LinkedTo[0];auto* To=C->GetThenPin()->LinkedTo[0];
        From->GetOwningNode()->Modify();To->GetOwningNode()->Modify();
        if(!Schema->TryCreateConnection(From,To))
        { UE_LOG(LogTemp,Error,TEXT("Floor correction removal: could not reconnect execution."));return; }
        FBlueprintEditorUtils::RemoveNode(BP,C,true);
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    FFileHelper::SaveStringToFile(FString::Printf(TEXT("removed=%d status=%d saved=0\n"),Calls.Num(),int32(BP->Status)),
        *(FPaths::ProjectSavedDir()/TEXT("Diagnostics/GetUpFloorRemoval20261010/migration.txt")));
}
static FAutoConsoleCommand RemoveCommand(TEXT("Prophecy.Editor.RemoveGetUpFloorCorrection"),TEXT("Remove obsolete floor-correction calls, reconnect execution, compile without saving."),FConsoleCommandDelegate::CreateStatic(&RemoveFloorCorrectionCalls));
static void WireTick30()
{
    if(!GEditor || GEditor->PlayWorld)return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if(!BP || !BP->GeneratedClass)return;
    UEdGraph* Graph=nullptr;
    for(UEdGraph* G:BP->FunctionGraphs)if(G->GetFName()==TEXT("tick debugging"))Graph=G;
    if(!Graph)return;
    UK2Node_IfThenElse* Knockdown=nullptr;UK2Node_CallFunction* Player=nullptr;
    int32 Bottom=0;
    for(UEdGraphNode* N:Graph->Nodes)
    {
        Bottom=FMath::Max(Bottom,N->NodePosY);
        if(N->GetFName()==TEXT("K2Node_IfThenElse_5"))Knockdown=Cast<UK2Node_IfThenElse>(N);
        if(N->GetFName()==TEXT("K2Node_CallFunction_101"))Player=Cast<UK2Node_CallFunction>(N);
        if(auto* C=Cast<UK2Node_CallFunction>(N))if(C->FunctionReference.GetMemberName()==TEXT("GetUp"))
        { UE_LOG(LogTemp,Warning,TEXT("Get Up tick30: a call already exists; no changes."));return; }
    }
    auto* Count=FindFProperty<FIntProperty>(BP->GeneratedClass,TEXT("absolute tick debug"));
    auto* Equal=UKismetMathLibrary::StaticClass()->FindFunctionByName(TEXT("EqualEqual_IntInt"));
    auto* GetUp=UProphecyGetUpLibrary::StaticClass()->FindFunctionByName(TEXT("GetUp"));
    auto* Tail=Knockdown?Knockdown->GetElsePin():nullptr;
    auto* Possessed=Player?Player->FindPin(TEXT("b")):nullptr;
    auto* Condition=Knockdown?Knockdown->GetConditionPin():nullptr;
    auto* Tick=Condition && Condition->LinkedTo.Num()==1?Cast<UK2Node_CallFunction>(Condition->LinkedTo[0]->GetOwningNode()):nullptr;
    if(!Count || !Equal || !GetUp || !Tail || !Tail->LinkedTo.IsEmpty() || !Possessed ||
        Player->FunctionReference.GetMemberName()!=TEXT("is player possssessed") || !Tick ||
        Tick->FunctionReference.GetMemberName()!=TEXT("is tick") || !Tick->FindPin(TEXT("i")) ||
        Tick->FindPin(TEXT("i"))->DefaultValue!=TEXT("10"))
    { UE_LOG(LogTemp,Error,TEXT("Get Up tick30: audited knockdown graph changed; no changes."));return; }
    const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","GetUpTick30","Get Up at absolute tick 30"));
    BP->Modify();Graph->Modify();Knockdown->Modify();Player->Modify();
    const auto* Schema=GetDefault<UEdGraphSchema_K2>();TArray<UEdGraphNode*> Added;
    const int32 X=Knockdown->NodePosX,Y=Bottom+480;
    auto Call=[&](UFunction* Function,int32 DX,int32 DY)
    {
        FGraphNodeCreator<UK2Node_CallFunction> C(*Graph);auto* N=C.CreateNode();
        N->SetFromFunction(Function);N->NodePosX=X+DX;N->NodePosY=Y+DY;C.Finalize();Added.Add(N);return N;
    };
    auto Branch=[&](int32 DX)
    {
        FGraphNodeCreator<UK2Node_IfThenElse> C(*Graph);auto* N=C.CreateNode();
        N->NodePosX=X+DX;N->NodePosY=Y;C.Finalize();Added.Add(N);return N;
    };
    FGraphNodeCreator<UK2Node_VariableGet> Getter(*Graph);auto* Absolute=Getter.CreateNode();
    Absolute->VariableReference.SetSelfMember(TEXT("absolute tick debug"));
    Absolute->NodePosX=X;Absolute->NodePosY=Y+240;Getter.Finalize();Added.Add(Absolute);
    auto* Compare=Call(Equal,260,240);auto* AtThirty=Branch(540);auto* IsPlayer=Branch(800);auto* Rise=Call(GetUp,1060,0);
    Schema->TrySetDefaultValue(*Compare->FindPinChecked(TEXT("B")),TEXT("30"));
    Schema->TrySetDefaultValue(*Rise->FindPinChecked(TEXT("PlayRateMultiplier")),TEXT("1.0"));
    Rise->NodeComment=TEXT("Player get-up at absolute tick 30, after the existing tick-10 knockdown.");Rise->bCommentBubbleVisible=true;
    bool OK=true;
    auto Link=[&](UEdGraphPin* From,UEdGraphPin* To){OK&=From && To && Schema->TryCreateConnection(From,To);};
    Link(Tail,AtThirty->GetExecPin());
    Link(Absolute->FindPin(TEXT("absolute tick debug")),Compare->FindPin(TEXT("A")));
    Link(Compare->FindPin(TEXT("ReturnValue")),AtThirty->GetConditionPin());
    Link(AtThirty->GetThenPin(),IsPlayer->GetExecPin());Link(Possessed,IsPlayer->GetConditionPin());
    Link(IsPlayer->GetThenPin(),Rise->GetExecPin());
    if(!OK)
    {
        for(auto* N:Added)FBlueprintEditorUtils::RemoveNode(BP,N,true);
        UE_LOG(LogTemp,Error,TEXT("Get Up tick30: connection failed; additions removed."));return;
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    const FString Report=FString::Printf(TEXT("connections_ok=1 status=%d absolute_tick=30 rate=1 player_only=1 added_nodes=%d asset_saved=0\n"),int32(BP->Status),Added.Num());
    FFileHelper::SaveStringToFile(Report,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/GetUpTick30/wiring.txt")));
    UE_LOG(LogTemp,Display,TEXT("Get Up tick30: %s"),*Report);
}
static FAutoConsoleCommand Command(TEXT("Prophecy.Editor.WireGetUpTick30"),TEXT("Add Get Up to the audited knockdown branch at absolute tick30, player only; compile without saving."),FConsoleCommandDelegate::CreateStatic(&WireTick30));
}
