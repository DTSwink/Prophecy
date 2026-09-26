// Explicit editor command only. Playback is ordinary Blueprint nodes, not a native tick scheduler.
#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CallFunction.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_Event.h"
#include "K2Node_GetArrayItem.h"
#include "K2Node_IfThenElse.h"
#include "K2Node_VariableGet.h"
#include "K2Node_VariableSet.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Kismet/KismetMathLibrary.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Components/SceneComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "ScopedTransaction.h"
#include "ProphecyAgent.h"
#include "ProphecyAttackCheckpointLibrary.h"
#include "ProphecyAttackTrimLibrary.h"

namespace ProphecySlashTrainBlueprint
{
void Build()
{
    if (!GEditor || GEditor->PlayWorld)
    { UE_LOG(LogTemp,Warning,TEXT("Slash train: editor must be outside Play; no changes."));return; }
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP) return;
    UEdGraph* Graph=nullptr;
    for (UEdGraph* G:BP->FunctionGraphs) if (G->GetFName()==TEXT("codex slash train")) Graph=G;
    auto* Entry=Graph && Graph->Nodes.Num()==1 ? Cast<UK2Node_FunctionEntry>(Graph->Nodes[0]) : nullptr;
    if (!Entry || !Entry->FindPin(UEdGraphSchema_K2::PN_Then) || !Entry->FindPin(UEdGraphSchema_K2::PN_Then)->LinkedTo.IsEmpty())
    { UE_LOG(LogTemp,Warning,TEXT("Slash train: expected user's empty function; refusing to overwrite edits."));return; }

    FString Text;
    TSharedPtr<FJsonObject> Data;
    if (!FFileHelper::LoadFileToString(Text,*(FPaths::ProjectDir()/TEXT("Tools/NN/Fixtures/SlashTrain2026092223.json"))) ||
        !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Data) || !Data.IsValid()) return;
    const auto& Rows=Data->GetArrayField(TEXT("rows"));
    if (Rows.Num()!=30 || Data->GetIntegerField(TEXT("seed"))!=2026092223) return;
    FString Names=TEXT("("), Targets=TEXT("(");
    for (int32 I=0; I<Rows.Num(); ++I)
    {
        const auto Row=Rows[I]->AsObject();const auto& V=Row->GetArrayField(TEXT("targetLocalCm"));
        if (Row->GetIntegerField(TEXT("index"))!=I+1 || V.Num()!=3) return;
        if (I) { Names+=TEXT(",");Targets+=TEXT(","); }
        Names+=FString::Printf(TEXT("\"%s\""),*Row->GetStringField(TEXT("attack")));
        Targets+=FString::Printf(TEXT("(X=%.12f,Y=%.12f,Z=%.12f)"),V[0]->AsNumber(),V[1]->AsNumber(),V[2]->AsNumber());
    }
    Names+=TEXT(")");Targets+=TEXT(")");
    const FName IndexName(TEXT("Codex Slash Train Index")), NamesName(TEXT("Codex Slash Train Attacks")),
        TargetsName(TEXT("Codex Slash Train Local Targets")), TargetName(TEXT("Codex Slash Train World Target"));
    for (const FName Name:{IndexName,NamesName,TargetsName,TargetName})
        if (FBlueprintEditorUtils::FindNewVariableIndex(BP,Name)!=INDEX_NONE)
        { UE_LOG(LogTemp,Warning,TEXT("Slash train: variable already exists; no changes."));return; }
    // Resolve all existing nodes before modifying the user's Blueprint.
    TMap<FName,UFunction*> Functions;
    auto Resolve=[&](UClass* Class,FName Name)
    { UFunction* Function=Class->FindFunctionByName(Name);Functions.Add(Name,Function);return Function!=nullptr; };
    bool Good=true;
    for (FName Name:{FName(TEXT("GetNNAttackState")),FName(TEXT("TriggerNNAttack")),
        FName(TEXT("GetAuthoredBodyWorldTarget")),FName(TEXT("GetAgentMesh"))}) Good &= Resolve(AProphecyAgent::StaticClass(),Name);
    for (FName Name:{FName(TEXT("Less_IntInt")),FName(TEXT("EqualEqual_IntInt")),FName(TEXT("Add_IntInt")),
        FName(TEXT("TransformLocation"))}) Good &= Resolve(UKismetMathLibrary::StaticClass(),Name);
    Good &= Resolve(USceneComponent::StaticClass(),TEXT("K2_GetComponentToWorld"));
    Good &= Resolve(UProphecyAttackCheckpointLibrary::StaticClass(),TEXT("SetAttackCheckpoint"));
    Good &= Resolve(UKismetSystemLibrary::StaticClass(),TEXT("PrintString"));
    if (!Good) { UE_LOG(LogTemp,Error,TEXT("Slash train: missing existing function; no changes."));return; }

    const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","WireSlashTrain","Wire seed 2026092223 slash train"));
    BP->Modify();Graph->Modify();Entry->Modify();
    TArray<FName> AddedVariables;
    auto Variable=[&](FName Name,FEdGraphPinType Type,const FString& Default)
    {
        if (!FBlueprintEditorUtils::AddMemberVariable(BP,Name,Type,Default)) { Good=false;return; }
        AddedVariables.Add(Name);
        FBlueprintEditorUtils::SetBlueprintVariableCategory(BP,Name,nullptr,FText::FromString(TEXT("Codex Slash Train")),true);
    };
    FEdGraphPinType IntType;IntType.PinCategory=UEdGraphSchema_K2::PC_Int;
    FEdGraphPinType NameArray;NameArray.PinCategory=UEdGraphSchema_K2::PC_Name;NameArray.ContainerType=EPinContainerType::Array;
    FEdGraphPinType VectorType;VectorType.PinCategory=UEdGraphSchema_K2::PC_Struct;VectorType.PinSubCategoryObject=TBaseStructure<FVector>::Get();
    FEdGraphPinType VectorArray=VectorType;VectorArray.ContainerType=EPinContainerType::Array;
    Variable(IndexName,IntType,TEXT("0"));Variable(NamesName,NameArray,Names);
    Variable(TargetsName,VectorArray,Targets);Variable(TargetName,VectorType,TEXT("(X=0,Y=0,Z=0)"));
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    TArray<UEdGraphNode*> AddedNodes;
    auto Call=[&](FName Name,int32 X,int32 Y)
    {
        FGraphNodeCreator<UK2Node_CallFunction> Creator(*Graph);auto* N=Creator.CreateNode();
        N->SetFromFunction(Functions[Name]);N->NodePosX=X;N->NodePosY=Y;Creator.Finalize();AddedNodes.Add(N);return N;
    };
    auto Get=[&](FName Name,int32 X,int32 Y)
    {
        FGraphNodeCreator<UK2Node_VariableGet> Creator(*Graph);auto* N=Creator.CreateNode();
        N->VariableReference.SetSelfMember(Name);N->NodePosX=X;N->NodePosY=Y;Creator.Finalize();AddedNodes.Add(N);return N;
    };
    auto Set=[&](FName Name,int32 X,int32 Y)
    {
        FGraphNodeCreator<UK2Node_VariableSet> Creator(*Graph);auto* N=Creator.CreateNode();
        N->VariableReference.SetSelfMember(Name);N->NodePosX=X;N->NodePosY=Y;Creator.Finalize();AddedNodes.Add(N);return N;
    };
    auto Branch=[&](int32 X,int32 Y)
    {
        FGraphNodeCreator<UK2Node_IfThenElse> Creator(*Graph);auto* N=Creator.CreateNode();
        N->NodePosX=X;N->NodePosY=Y;Creator.Finalize();AddedNodes.Add(N);return N;
    };
    const auto* Schema=GetDefault<UEdGraphSchema_K2>();
    auto Link=[&](UEdGraphNode* A,FName AP,UEdGraphNode* B,FName BPName)
    {
        auto* P=A?A->FindPin(AP):nullptr;auto* Q=B?B->FindPin(BPName):nullptr;
        if (!P || !Q || !Schema->TryCreateConnection(P,Q))
        { Good=false;UE_LOG(LogTemp,Error,TEXT("Slash train connection failed: %s.%s -> %s.%s"),*GetNameSafe(A),*AP.ToString(),*GetNameSafe(B),*BPName.ToString()); }
    };
    auto Default=[&](UEdGraphNode* N,FName Pin,const FString& Value)
    { if (auto* P=N->FindPin(Pin)) Schema->TrySetDefaultValue(*P,Value);else Good=false; };
    auto ArrayItem=[&](FName VariableName,UEdGraphNode* Index,int32 X,int32 Y)
    {
        auto* Array=Get(VariableName,X-280,Y);
        FGraphNodeCreator<UK2Node_GetArrayItem> Creator(*Graph);auto* Item=Creator.CreateNode();
        Item->NodePosX=X;Item->NodePosY=Y;Creator.Finalize();AddedNodes.Add(Item);
        if (!Schema->TryCreateConnection(Array->FindPin(VariableName),Item->GetTargetArrayPin())) Good=false;
        if (!Schema->TryCreateConnection(Index->FindPin(IndexName),Item->GetIndexPin())) Good=false;
        return Item;
    };

    Entry->NodePosX=0;Entry->NodePosY=0;
    Entry->NodeComment=TEXT("Seed 2026092223, complete 30-attack chain. Existing possessed/tick>=30 caller retained. Advance on actual NN completion, never a timer. Index 30 = finished; reset Index to 0 to replay.");
    Entry->bCommentBubbleVisible=true;
    auto* Index=Get(IndexName,0,180);
    auto* Less=Call(TEXT("Less_IntInt"),230,180);Default(Less,TEXT("B"),TEXT("30"));Link(Index,IndexName,Less,TEXT("A"));
    auto* HasNext=Branch(260,0);Link(Entry,TEXT("then"),HasNext,TEXT("execute"));Link(Less,TEXT("ReturnValue"),HasNext,TEXT("Condition"));
    auto* State=Call(TEXT("GetNNAttackState"),520,180);
    auto* Busy=Branch(530,0);Link(HasNext,TEXT("then"),Busy,TEXT("execute"));Link(State,TEXT("ReturnValue"),Busy,TEXT("Condition"));
    Busy->NodeComment=TEXT("While attacking: do nothing. First tick after natural completion starts next request; no Stop/retrigger while active.");Busy->bCommentBubbleVisible=true;
    auto* First=Call(TEXT("EqualEqual_IntInt"),810,180);Link(Index,IndexName,First,TEXT("A"));Default(First,TEXT("B"),TEXT("0"));
    auto* FirstBranch=Branch(820,0);Link(Busy,TEXT("else"),FirstBranch,TEXT("execute"));Link(First,TEXT("ReturnValue"),FirstBranch,TEXT("Condition"));
    auto* LocalTarget=ArrayItem(TargetsName,Index,1170,940);
    auto* Attack=ArrayItem(NamesName,Index,2280,730);
    auto* Checkpoint=Call(TEXT("SetAttackCheckpoint"),1100,-250);Default(Checkpoint,TEXT("Checkpoint"),TEXT("PredictivePin184064"));
    Link(FirstBranch,TEXT("then"),Checkpoint,TEXT("execute"));
    auto* CheckpointOK=Branch(1460,-250);Link(Checkpoint,TEXT("then"),CheckpointOK,TEXT("execute"));Link(Checkpoint,TEXT("ReturnValue"),CheckpointOK,TEXT("Condition"));
    auto* Mesh=Call(TEXT("GetAgentMesh"),1100,-610);
    auto* Carrier=Call(TEXT("K2_GetComponentToWorld"),1400,-610);Link(Mesh,TEXT("ReturnValue"),Carrier,TEXT("self"));
    auto* FirstTarget=Call(TEXT("TransformLocation"),1690,-540);Link(Carrier,TEXT("ReturnValue"),FirstTarget,TEXT("T"));
    Link(LocalTarget,LocalTarget->GetResultPin()->PinName,FirstTarget,TEXT("Location"));
    auto* SetFirst=Set(TargetName,1980,-250);Link(CheckpointOK,TEXT("then"),SetFirst,TEXT("execute"));Link(FirstTarget,TEXT("ReturnValue"),SetFirst,TargetName);
    SetFirst->NodeComment=TEXT("First request uses the source attack root frame, mapped onto this agent's initial mesh carrier.");SetFirst->bCommentBubbleVisible=true;

    auto* Pelvis=Call(TEXT("GetAuthoredBodyWorldTarget"),1080,520);Default(Pelvis,TEXT("BoneName"),TEXT("pelvis"));
    auto* PelvisOK=Branch(1460,330);Link(FirstBranch,TEXT("else"),PelvisOK,TEXT("execute"));Link(Pelvis,TEXT("ReturnValue"),PelvisOK,TEXT("Condition"));
    auto* NextTarget=Call(TEXT("TransformLocation"),1700,590);Link(Pelvis,TEXT("CurrentWorldTransform"),NextTarget,TEXT("T"));
    Link(LocalTarget,LocalTarget->GetResultPin()->PinName,NextTarget,TEXT("Location"));
    auto* SetNext=Set(TargetName,1980,330);Link(PelvisOK,TEXT("then"),SetNext,TEXT("execute"));Link(NextTarget,TEXT("ReturnValue"),SetNext,TargetName);
    SetNext->NodeComment=TEXT("Same mapped_target rule as training: source initial-pelvis-local request on the final published pelvis. Target is sampled once, then held for the attack.");SetNext->bCommentBubbleVisible=true;
    auto* Target=Get(TargetName,2300,510);
    auto* Trigger=Call(TEXT("TriggerNNAttack"),2600,0);Link(SetFirst,TEXT("then"),Trigger,TEXT("execute"));Link(SetNext,TEXT("then"),Trigger,TEXT("execute"));
    Link(Attack,Attack->GetResultPin()->PinName,Trigger,TEXT("Attack"));Link(Target,TargetName,Trigger,TEXT("TargetWorldLocation"));
    Default(Trigger,TEXT("bHalfAttack"),TEXT("false"));
    auto* Success=Branch(2950,0);Link(Trigger,TEXT("then"),Success,TEXT("execute"));Link(Trigger,TEXT("ReturnValue"),Success,TEXT("Condition"));
    auto* Add=Call(TEXT("Add_IntInt"),3000,250);Link(Index,IndexName,Add,TEXT("A"));Default(Add,TEXT("B"),TEXT("1"));
    auto* Advance=Set(IndexName,3310,0);Link(Success,TEXT("then"),Advance,TEXT("execute"));Link(Add,TEXT("ReturnValue"),Advance,IndexName);
    auto* Halt=Set(IndexName,2970,1080);Default(Halt,IndexName,TEXT("30"));
    Link(Success,TEXT("else"),Halt,TEXT("execute"));Link(CheckpointOK,TEXT("else"),Halt,TEXT("execute"));Link(PelvisOK,TEXT("else"),Halt,TEXT("execute"));
    auto* Error=Call(TEXT("PrintString"),3310,1080);Link(Halt,TEXT("then"),Error,TEXT("execute"));
    Default(Error,TEXT("InString"),TEXT("Codex slash train stopped: checkpoint selection, pelvis read or Trigger NN Attack failed. No request skipped/retried."));
    Default(Error,TEXT("Duration"),TEXT("15.0"));
    if (!Good)
    {
        for (auto* N:AddedNodes) FBlueprintEditorUtils::RemoveNode(BP,N,true);
        for (FName Name:AddedVariables) FBlueprintEditorUtils::RemoveMemberVariable(BP,Name);
        UE_LOG(LogTemp,Error,TEXT("Slash train: could not wire existing nodes; removed additions."));return;
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP);
    UE_LOG(LogTemp,Display,TEXT("Slash train: populated %s with %d existing nodes, 30 source requests, actual-completion progression; BP status=%d; not saved."),*Graph->GetName(),AddedNodes.Num(),int32(BP->Status));
}
FAutoConsoleCommand Command(TEXT("Prophecy.Editor.BuildSlashTrain"),
    TEXT("Fill the empty codex slash train function with existing nodes for seed 2026092223. Undoable, no Play, no save."),
    FConsoleCommandDelegate::CreateStatic(&Build));

void AddInitialPose()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP) return;
    UEdGraph* Graph=nullptr;
    for (UEdGraph* G:BP->FunctionGraphs) if (G->GetFName()==TEXT("codex slash train")) Graph=G;
    if (!Graph) { UE_LOG(LogTemp,Warning,TEXT("Slash seed: graph missing"));return; }
    UK2Node_CallFunction* Checkpoint=nullptr;
    for (UEdGraphNode* N:Graph->Nodes) if (auto* Call=Cast<UK2Node_CallFunction>(N))
    {
        if (Call->FunctionReference.GetMemberName()==TEXT("SetSlashTrainStartingPose")) return;
        if (Call->FunctionReference.GetMemberName()==TEXT("SetAttackCheckpoint")) Checkpoint=Call;
    }
    if (!Checkpoint) { UE_LOG(LogTemp,Warning,TEXT("Slash seed: checkpoint node missing"));return; }
    auto* Next=Checkpoint->FindPin(TEXT("then"));
    auto* Branch=Next && Next->LinkedTo.Num()==1?Cast<UK2Node_IfThenElse>(Next->LinkedTo[0]->GetOwningNode()):nullptr;
    if (!Branch || Branch->GetThenPin()->LinkedTo.Num()!=1 || Branch->GetElsePin()->LinkedTo.Num()!=1)
    { UE_LOG(LogTemp,Warning,TEXT("Slash seed: checkpoint branch is not the expected shape"));return; }
    auto* Destination=Branch->GetThenPin()->LinkedTo[0];
    auto* Failure=Branch->GetElsePin()->LinkedTo[0];
    auto* SeedClass=FindObject<UClass>(nullptr,TEXT("/Script/GameAnimationSample3.ProphecySlashTrainDebugLibrary"));
    auto* Function=SeedClass?SeedClass->FindFunctionByName(TEXT("SetSlashTrainStartingPose")):nullptr;
    if (!Function) { UE_LOG(LogTemp,Warning,TEXT("Slash seed: function missing"));return; }
    const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","SeedSlashTrain","Seed slash train from viewer history"));
    BP->Modify();Graph->Modify();Branch->Modify();Destination->GetOwningNode()->Modify();Failure->GetOwningNode()->Modify();
    FGraphNodeCreator<UK2Node_CallFunction> Creator(*Graph);auto* Seed=Creator.CreateNode();
    Seed->SetFromFunction(Function);Seed->NodePosX=Branch->NodePosX+240;Seed->NodePosY=Branch->NodePosY-350;Creator.Finalize();
    FGraphNodeCreator<UK2Node_IfThenElse> BC(*Graph);auto* OK=BC.CreateNode();
    OK->NodePosX=Seed->NodePosX+350;OK->NodePosY=Seed->NodePosY;BC.Finalize();
    const auto* Schema=GetDefault<UEdGraphSchema_K2>();
    Branch->GetThenPin()->BreakLinkTo(Destination);
    const bool Good=Schema->TryCreateConnection(Branch->GetThenPin(),Seed->FindPin(TEXT("execute"))) &&
        Schema->TryCreateConnection(Seed->FindPin(TEXT("then")),OK->GetExecPin()) &&
        Schema->TryCreateConnection(Seed->FindPin(TEXT("ReturnValue")),OK->GetConditionPin()) &&
        Schema->TryCreateConnection(OK->GetThenPin(),Destination) && Schema->TryCreateConnection(OK->GetElsePin(),Failure);
    if (!Good)
    {
        FBlueprintEditorUtils::RemoveNode(BP,Seed,true);FBlueprintEditorUtils::RemoveNode(BP,OK,true);
        Schema->TryCreateConnection(Branch->GetThenPin(),Destination);
    }
    else
    {
        // The train intentionally uses the complete reference tails. Override
        // the user's ordinary per-tick trim setter while this debug graph runs.
        UK2Node_FunctionEntry* Entry=nullptr;
        for (UEdGraphNode* N:Graph->Nodes) if (auto* E=Cast<UK2Node_FunctionEntry>(N)) Entry=E;
        if (Entry)
        {
            FGraphNodeCreator<UK2Node_CallFunction> TC(*Graph);auto* Trim=TC.CreateNode();
            Trim->SetFromFunction(UProphecyAttackTrimLibrary::StaticClass()->FindFunctionByName(TEXT("SetTrimAttack")));
            Trim->NodePosX=Entry->NodePosX+220;Trim->NodePosY=Entry->NodePosY-600;TC.Finalize();
            const auto Outgoing=Entry->FindPin(TEXT("then"))->LinkedTo;
            Entry->Modify();
            for (auto* Pin:Outgoing) { Pin->GetOwningNode()->Modify();Entry->FindPin(TEXT("then"))->BreakLinkTo(Pin);Schema->TryCreateConnection(Trim->FindPin(TEXT("then")),Pin); }
            Schema->TryCreateConnection(Entry->FindPin(TEXT("then")),Trim->FindPin(TEXT("execute")));
            Trim->NodeComment=TEXT("Reference comparison: complete attacks, all trims zero. Regular settings outside this train are preserved.");
            Trim->bCommentBubbleVisible=true;
        }
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);FKismetEditorUtilities::CompileBlueprint(BP);
    UE_LOG(LogTemp,Display,TEXT("Slash train seed node: wired=%d status=%d; all existing nodes preserved, not saved."),Good,int32(BP->Status));
}
FAutoConsoleCommand SeedCommand(TEXT("Prophecy.Editor.SeedSlashTrain"),TEXT("Insert initial-history debug node on the first request only; preserve existing graph."),FConsoleCommandDelegate::CreateStatic(&AddInitialPose));

void ChainAtEnd()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP) return;
    UK2Node_Event* Event=nullptr;UEdGraph* Graph=nullptr;UEdGraph* Train=nullptr;
    for (UEdGraph* G:BP->FunctionGraphs) if (G->GetFName()==TEXT("codex slash train")) Train=G;
    for (UEdGraph* G:BP->UbergraphPages) for (UEdGraphNode* N:G->Nodes)
        if (auto* E=Cast<UK2Node_Event>(N);E && E->EventReference.GetMemberName()==TEXT("OnNNAttackEnded")) { Event=E;Graph=G; }
    if (!Event || !Train || !Event->FindPin(TEXT("then"))->LinkedTo.IsEmpty())
    { UE_LOG(LogTemp,Warning,TEXT("Slash chain: expected unused Attack Ended event; nothing overwritten."));return; }
    const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","ChainSlashAtEnd","Continue debug slash train on Attack Ended"));
    BP->Modify();Graph->Modify();Event->Modify();
    auto Call=[&](UFunction* F,int X,int Y)
    { FGraphNodeCreator<UK2Node_CallFunction> C(*Graph);auto* N=C.CreateNode();N->SetFromFunction(F);N->NodePosX=X;N->NodePosY=Y;C.Finalize();return N; };
    const int X=Event->NodePosX,Y=Event->NodePosY;
    auto* Player=Call(APawn::StaticClass()->FindFunctionByName(TEXT("IsPlayerControlled")),X,Y+180);
    FGraphNodeCreator<UK2Node_VariableGet> VC(*Graph);auto* Index=VC.CreateNode();
    Index->VariableReference.SetSelfMember(TEXT("Codex Slash Train Index"));Index->NodePosX=X;Index->NodePosY=Y+320;VC.Finalize();
    auto* Greater=Call(UKismetMathLibrary::StaticClass()->FindFunctionByName(TEXT("Greater_IntInt")),X+240,Y+320);
    auto* And=Call(UKismetMathLibrary::StaticClass()->FindFunctionByName(TEXT("BooleanAND")),X+490,Y+190);
    FGraphNodeCreator<UK2Node_IfThenElse> BC(*Graph);auto* Branch=BC.CreateNode();Branch->NodePosX=X+720;Branch->NodePosY=Y;BC.Finalize();
    auto* Continue=Call(BP->GeneratedClass->FindFunctionByName(Train->GetFName()),X+960,Y);
    Continue->NodeComment=TEXT("Comparison train only: continue at the real attack end, before an intervening locomotion prediction changes both input frames.");Continue->bCommentBubbleVisible=true;
    const auto* S=GetDefault<UEdGraphSchema_K2>();
    bool Good=S->TryCreateConnection(Event->FindPin(TEXT("then")),Branch->GetExecPin());
    Good &= S->TryCreateConnection(Index->FindPin(TEXT("Codex Slash Train Index")),Greater->FindPin(TEXT("A")));
    Good &= S->TryCreateConnection(Player->FindPin(TEXT("ReturnValue")),And->FindPin(TEXT("A")));
    Good &= S->TryCreateConnection(Greater->FindPin(TEXT("ReturnValue")),And->FindPin(TEXT("B")));
    Good &= S->TryCreateConnection(And->FindPin(TEXT("ReturnValue")),Branch->GetConditionPin());
    Good &= S->TryCreateConnection(Branch->GetThenPin(),Continue->FindPin(TEXT("execute")));
    if (!Good) Event->FindPin(TEXT("then"))->BreakAllPinLinks();
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);FKismetEditorUtilities::CompileBlueprint(BP);
    UE_LOG(LogTemp,Display,TEXT("Slash chain event: wired=%d status=%d not saved."),Good,int32(BP->Status));
}
FAutoConsoleCommand ChainCommand(TEXT("Prophecy.Editor.ChainSlashTrainAtEnd"),TEXT("Wire the comparison train into unused Attack Ended, for the possessed agent with an active train only."),FConsoleCommandDelegate::CreateStatic(&ChainAtEnd));
}
