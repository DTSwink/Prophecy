// Explicit editor action: fill the user's debug function with ordinary Blueprint flow.
#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CallFunction.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_ExecutionSequence.h"
#include "K2Node_IfThenElse.h"
#include "K2Node_VariableGet.h"
#include "K2Node_VariableSet.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Kismet/KismetMathLibrary.h"
#include "Kismet/KismetSystemLibrary.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ScopedTransaction.h"
#include "UObject/SavePackage.h"
#include "ProphecyAgent.h"
#include "ProphecySlashTrainDebugLibrary.h"

namespace ProphecyGTAttackIdleBlueprint
{
static void Build()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP) return;
    UEdGraph* Graph=nullptr;
    for (UEdGraph* G:BP->FunctionGraphs) if (G->GetFName()==TEXT("codex GT slash")) Graph=G;
    auto* Entry=Graph && Graph->Nodes.Num()==1?Cast<UK2Node_FunctionEntry>(Graph->Nodes[0]):nullptr;
    if (!Entry || !Entry->UserDefinedPins.IsEmpty() || !Entry->FindPinChecked(TEXT("then"))->LinkedTo.IsEmpty())
    { UE_LOG(LogTemp,Warning,TEXT("GT idle loop: expected the user's empty function; no changes."));return; }

    const FName Was(TEXT("Codex GT Was Attacking")),Next(TEXT("Codex GT Next Time")),
        Failed(TEXT("Codex GT Failed")),Target(TEXT("Codex GT World Target")),HasTarget(TEXT("Codex GT Has Target"));
    for (FName Name:{Was,Next,Failed,Target,HasTarget})
        if (FBlueprintEditorUtils::FindNewVariableIndex(BP,Name)!=INDEX_NONE) return;
    TMap<FName,UFunction*> Functions;
    auto Resolve=[&](UClass* Class,FName Name)
    { auto* F=Class->FindFunctionByName(Name);Functions.Add(Name,F);return F!=nullptr; };
    bool OK=Resolve(AProphecyAgent::StaticClass(),TEXT("GetNNAttackState")) &&
        Resolve(AProphecyAgent::StaticClass(),TEXT("TriggerNNAttack")) &&
        Resolve(UProphecySlashTrainDebugLibrary::StaticClass(),TEXT("PrepareGTAttackFromIdle"));
    for (FName Name:{FName(TEXT("GetGameTimeInSeconds")),FName(TEXT("DrawDebugSphere")),FName(TEXT("PrintString"))})
        OK&=Resolve(UKismetSystemLibrary::StaticClass(),Name);
    for (FName Name:{FName(TEXT("Add_DoubleDouble")),FName(TEXT("GreaterEqual_DoubleDouble")),FName(TEXT("FMax")),FName(TEXT("BooleanAND"))})
        OK&=Resolve(UKismetMathLibrary::StaticClass(),Name);
    if (!OK) { UE_LOG(LogTemp,Error,TEXT("GT idle loop: missing function."));return; }
    const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/GTAttackIdle20260930");
    IFileManager::Get().MakeDirectory(*(Dir/TEXT("Before")),true);
    const FString Backup=Dir/TEXT("Before/BP_ProphecyManualPoseAgent-live.uasset");
    FSavePackageArgs Save;Save.TopLevelFlags=RF_Public|RF_Standalone;Save.SaveFlags=SAVE_KeepDirty;
    if (!IFileManager::Get().FileExists(*Backup) && !UPackage::SavePackage(BP->GetOutermost(),BP,*Backup,Save)) return;
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","GTIdleLoop","Wire original GT target attack loop"));
    BP->Modify();Graph->Modify();Entry->Modify();
    const auto* Schema=GetDefault<UEdGraphSchema_K2>();
    FEdGraphPinType Bool;Bool.PinCategory=UEdGraphSchema_K2::PC_Boolean;
    FEdGraphPinType Number;Number.PinCategory=UEdGraphSchema_K2::PC_Real;Number.PinSubCategory=UEdGraphSchema_K2::PC_Double;
    FEdGraphPinType NameType;NameType.PinCategory=UEdGraphSchema_K2::PC_Name;
    FEdGraphPinType Vector;Vector.PinCategory=UEdGraphSchema_K2::PC_Struct;Vector.PinSubCategoryObject=TBaseStructure<FVector>::Get();
    TArray<FName> Variables;
    auto Var=[&](FName Name,const FEdGraphPinType& Type,const TCHAR* Default)
    {
        if (!FBlueprintEditorUtils::AddMemberVariable(BP,Name,Type,Default)) { OK=false;return; }
        Variables.Add(Name);
        FBlueprintEditorUtils::SetBlueprintVariableCategory(BP,Name,nullptr,FText::FromString(TEXT("Codex GT Slash")),true);
    };
    Var(Was,Bool,TEXT("false"));Var(Next,Number,TEXT("0"));Var(Failed,Bool,TEXT("false"));
    Var(Target,Vector,TEXT("(X=0,Y=0,Z=0)"));Var(HasTarget,Bool,TEXT("false"));
    auto Input=[&](FName Name,const FEdGraphPinType& Type,const TCHAR* Default)
    {
        if (auto* P=Entry->CreateUserDefinedPin(Name,Type,EGPD_Output))
        {
            P->DefaultValue=Default;
            for (auto& D:Entry->UserDefinedPins) if (D->PinName==Name) D->PinDefaultValue=Default;
        }
        else OK=false;
    };
    Input(TEXT("Attack"),NameType,TEXT("slashR"));
    Input(TEXT("CoolOutSeconds"),Number,TEXT("1.0"));
    Input(TEXT("ShowTarget"),Bool,TEXT("true"));
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    TArray<UEdGraphNode*> Added;
    auto Call=[&](FName Name,int32 X,int32 Y)
    { FGraphNodeCreator<UK2Node_CallFunction> C(*Graph);auto* N=C.CreateNode();N->SetFromFunction(Functions[Name]);N->NodePosX=X;N->NodePosY=Y;C.Finalize();Added.Add(N);return N; };
    auto Get=[&](FName Name,int32 X,int32 Y)
    { FGraphNodeCreator<UK2Node_VariableGet> C(*Graph);auto* N=C.CreateNode();N->VariableReference.SetSelfMember(Name);N->NodePosX=X;N->NodePosY=Y;C.Finalize();Added.Add(N);return N; };
    auto Set=[&](FName Name,int32 X,int32 Y)
    { FGraphNodeCreator<UK2Node_VariableSet> C(*Graph);auto* N=C.CreateNode();N->VariableReference.SetSelfMember(Name);N->NodePosX=X;N->NodePosY=Y;C.Finalize();Added.Add(N);return N; };
    auto Branch=[&](int32 X,int32 Y)
    { FGraphNodeCreator<UK2Node_IfThenElse> C(*Graph);auto* N=C.CreateNode();N->NodePosX=X;N->NodePosY=Y;C.Finalize();Added.Add(N);return N; };
    auto Link=[&](UEdGraphNode* A,FName AP,UEdGraphNode* B,FName BPName)
    {
        auto* P=A->FindPin(AP);auto* Q=B->FindPin(BPName);
        if (!P || !Q || !Schema->TryCreateConnection(P,Q))
        { OK=false;UE_LOG(LogTemp,Error,TEXT("GT idle link failed: %s.%s -> %s.%s"),*A->GetName(),*AP.ToString(),*B->GetName(),*BPName.ToString()); }
    };
    auto Default=[&](UEdGraphNode* N,FName Pin,const TCHAR* Value)
    { if (auto* P=N->FindPin(Pin)) Schema->TrySetDefaultValue(*P,Value);else OK=false; };
    Entry->NodePosX=0;Entry->NodePosY=0;
    Entry->NodeComment=TEXT("Called by your existing tick>=30 branch. Each repeat seeds BOTH NN histories with idle frame 0, then attacks the original GT target. Cool Out Seconds starts after actual attack completion; zero repeats immediately. Full attacks, current checkpoint/tuning. Cyan sphere = original world target. Set Codex GT Failed=false to retry after an error.");
    Entry->bCommentBubbleVisible=true;
    FGraphNodeCreator<UK2Node_ExecutionSequence> SeqCreator(*Graph);auto* Seq=SeqCreator.CreateNode();
    Seq->NodePosX=260;Seq->NodePosY=0;SeqCreator.Finalize();Added.Add(Seq);
    Link(Entry,TEXT("then"),Seq,TEXT("execute"));
    auto* DrawAllowed=Call(TEXT("BooleanAND"),310,-460);
    auto* Has=Get(HasTarget,0,-330);Link(Entry,TEXT("ShowTarget"),DrawAllowed,TEXT("A"));Link(Has,HasTarget,DrawAllowed,TEXT("B"));
    auto* DrawBranch=Branch(550,-240);Link(Seq,TEXT("then_0"),DrawBranch,TEXT("execute"));Link(DrawAllowed,TEXT("ReturnValue"),DrawBranch,TEXT("Condition"));
    auto* Draw=Call(TEXT("DrawDebugSphere"),820,-300);Link(DrawBranch,TEXT("then"),Draw,TEXT("execute"));
    auto* WorldTarget=Get(Target,540,-610);Link(WorldTarget,Target,Draw,TEXT("Center"));
    Default(Draw,TEXT("Radius"),TEXT("5.0"));Default(Draw,TEXT("Segments"),TEXT("12"));
    Default(Draw,TEXT("LineColor"),TEXT("(R=0.0,G=1.0,B=1.0,A=1.0)"));Default(Draw,TEXT("Duration"),TEXT("0.0"));Default(Draw,TEXT("Thickness"),TEXT("1.0"));
    auto* Halted=Get(Failed,300,300);auto* HaltBranch=Branch(540,0);
    Link(Seq,TEXT("then_1"),HaltBranch,TEXT("execute"));Link(Halted,Failed,HaltBranch,TEXT("Condition"));
    auto* Active=Call(TEXT("GetNNAttackState"),570,220);auto* ActiveBranch=Branch(810,0);
    Link(HaltBranch,TEXT("else"),ActiveBranch,TEXT("execute"));Link(Active,TEXT("ReturnValue"),ActiveBranch,TEXT("Condition"));
    auto* WasGet=Get(Was,850,240);auto* EndedBranch=Branch(1090,0);
    Link(ActiveBranch,TEXT("else"),EndedBranch,TEXT("execute"));Link(WasGet,Was,EndedBranch,TEXT("Condition"));
    auto* Ended=Set(Was,1330,-40);Default(Ended,Was,TEXT("false"));Link(EndedBranch,TEXT("then"),Ended,TEXT("execute"));
    auto* Now=Call(TEXT("GetGameTimeInSeconds"),1160,630);
    auto* Cool=Call(TEXT("FMax"),850,500);Link(Entry,TEXT("CoolOutSeconds"),Cool,TEXT("A"));Default(Cool,TEXT("B"),TEXT("0"));
    auto* Deadline=Call(TEXT("Add_DoubleDouble"),1420,420);Link(Now,TEXT("ReturnValue"),Deadline,TEXT("A"));Link(Cool,TEXT("ReturnValue"),Deadline,TEXT("B"));
    auto* SetNext=Set(Next,1650,-40);Link(Ended,TEXT("then"),SetNext,TEXT("execute"));Link(Deadline,TEXT("ReturnValue"),SetNext,Next);
    SetNext->NodeComment=TEXT("Capture the cooldown once on the first call after the NN attack ends, never during the swing.");SetNext->bCommentBubbleVisible=true;
    auto* NextGet=Get(Next,1680,370);auto* Ready=Call(TEXT("GreaterEqual_DoubleDouble"),1960,330);
    Link(Now,TEXT("ReturnValue"),Ready,TEXT("A"));Link(NextGet,Next,Ready,TEXT("B"));
    auto* ReadyBranch=Branch(1940,0);Link(EndedBranch,TEXT("else"),ReadyBranch,TEXT("execute"));Link(SetNext,TEXT("then"),ReadyBranch,TEXT("execute"));Link(Ready,TEXT("ReturnValue"),ReadyBranch,TEXT("Condition"));
    auto* Seed=Call(TEXT("PrepareGTAttackFromIdle"),2210,0);Link(ReadyBranch,TEXT("then"),Seed,TEXT("execute"));Link(Entry,TEXT("Attack"),Seed,TEXT("Attack"));
    auto* SeedOK=Branch(2580,0);Link(Seed,TEXT("then"),SeedOK,TEXT("execute"));Link(Seed,TEXT("ReturnValue"),SeedOK,TEXT("Condition"));
    auto* StoreTarget=Set(Target,2850,-40);Link(SeedOK,TEXT("then"),StoreTarget,TEXT("execute"));Link(Seed,TEXT("TargetWorldLocation"),StoreTarget,Target);
    auto* Trigger=Call(TEXT("TriggerNNAttack"),3200,-40);Link(StoreTarget,TEXT("then"),Trigger,TEXT("execute"));Link(Entry,TEXT("Attack"),Trigger,TEXT("Attack"));Link(Seed,TEXT("TargetWorldLocation"),Trigger,TEXT("TargetWorldLocation"));Default(Trigger,TEXT("bHalfAttack"),TEXT("false"));
    auto* TriggerOK=Branch(3560,-40);Link(Trigger,TEXT("then"),TriggerOK,TEXT("execute"));Link(Trigger,TEXT("ReturnValue"),TriggerOK,TEXT("Condition"));
    auto* Started=Set(Was,3830,-80);Default(Started,Was,TEXT("true"));Link(TriggerOK,TEXT("then"),Started,TEXT("execute"));
    auto* Visible=Set(HasTarget,4140,-80);Default(Visible,HasTarget,TEXT("true"));Link(Started,TEXT("then"),Visible,TEXT("execute"));
    auto* SeedError=Call(TEXT("PrintString"),2850,800);Link(SeedOK,TEXT("else"),SeedError,TEXT("execute"));Link(Seed,TEXT("OutError"),SeedError,TEXT("InString"));Default(SeedError,TEXT("Duration"),TEXT("15"));
    auto* TriggerError=Call(TEXT("PrintString"),3830,540);Link(TriggerOK,TEXT("else"),TriggerError,TEXT("execute"));Default(TriggerError,TEXT("InString"),TEXT("Codex GT slash stopped: Trigger NN Attack failed."));Default(TriggerError,TEXT("Duration"),TEXT("15"));
    auto* Fail=Set(Failed,4180,660);Default(Fail,Failed,TEXT("true"));Link(SeedError,TEXT("then"),Fail,TEXT("execute"));Link(TriggerError,TEXT("then"),Fail,TEXT("execute"));
    if (!OK)
    {
        for (auto* N:Added) FBlueprintEditorUtils::RemoveNode(BP,N,true);
        for (FName Name:Variables) FBlueprintEditorUtils::RemoveMemberVariable(BP,Name);
        Entry->UserDefinedPins.Reset();Entry->ReconstructNode();
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
        UE_LOG(LogTemp,Error,TEXT("GT idle loop: wiring failed, additions rolled back."));return;
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);int32 Callers=0;
    for (auto* G:Graphs) for (UEdGraphNode* Base:G->Nodes) if (auto* N=Cast<UK2Node_CallFunction>(Base))
        if (N->FunctionReference.GetMemberName()==TEXT("codex GT slash"))
        {
            N->Modify();N->ReconstructNode();
            Default(N,TEXT("Attack"),TEXT("slashR"));Default(N,TEXT("CoolOutSeconds"),TEXT("1.0"));Default(N,TEXT("ShowTarget"),TEXT("true"));++Callers;
        }
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    const FString Report=FString::Printf(TEXT("nodes=%d callers=%d links_ok=%d status=%d saved=0\n"),Added.Num(),Callers,int32(OK),int32(BP->Status));
    FFileHelper::SaveStringToFile(Report,*(Dir/TEXT("BlueprintBuild.txt")));
    UE_LOG(LogTemp,Display,TEXT("GT idle loop: %s"),*Report);
}
static FAutoConsoleCommand Command(TEXT("Prophecy.Editor.BuildGTAttackIdle"),
    TEXT("Fill the empty codex GT slash function with a looping original-target NN comparison. Back up live BP; preserve caller, no save."),
    FConsoleCommandDelegate::CreateStatic(&Build));
}
