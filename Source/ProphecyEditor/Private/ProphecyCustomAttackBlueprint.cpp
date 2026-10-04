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

namespace ProphecyCustomAttackBlueprint
{
static void Build()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP) return;
    UEdGraph* Graph=nullptr;
    for (UEdGraph* G:BP->FunctionGraphs) if (G->GetFName()==TEXT("codex custom attack")) Graph=G;
    auto* Entry=Graph && Graph->Nodes.Num()==1?Cast<UK2Node_FunctionEntry>(Graph->Nodes[0]):nullptr;
    if (!Entry || !Entry->UserDefinedPins.IsEmpty() || !Entry->FindPinChecked(TEXT("then"))->LinkedTo.IsEmpty())
    { UE_LOG(LogTemp,Warning,TEXT("Custom attack loop: expected the user's empty function; no changes."));return; }

    const FName Was(TEXT("Codex Custom Was Attacking")),Next(TEXT("Codex Custom Next Time")),
        Failed(TEXT("Codex Custom Failed")),Target(TEXT("Codex Custom World Target")),HasTarget(TEXT("Codex Custom Has Target"));
    for (FName Name:{Was,Next,Failed,Target,HasTarget})
        if (FBlueprintEditorUtils::FindNewVariableIndex(BP,Name)!=INDEX_NONE) return;
    TMap<FName,UFunction*> Functions;
    auto Resolve=[&](UClass* Class,FName Name)
    { auto* F=Class->FindFunctionByName(Name);Functions.Add(Name,F);return F!=nullptr; };
    bool OK=Resolve(AProphecyAgent::StaticClass(),TEXT("GetNNAttackState")) &&
        Resolve(AProphecyAgent::StaticClass(),TEXT("TriggerNNAttack")) &&
        Resolve(UProphecySlashTrainDebugLibrary::StaticClass(),TEXT("PrepareProblemSlash"));
    for (FName Name:{FName(TEXT("GetGameTimeInSeconds")),FName(TEXT("DrawDebugSphere")),FName(TEXT("PrintString"))})
        OK&=Resolve(UKismetSystemLibrary::StaticClass(),Name);
    for (FName Name:{FName(TEXT("Add_DoubleDouble")),FName(TEXT("GreaterEqual_DoubleDouble")),FName(TEXT("FMax")),FName(TEXT("BooleanAND"))})
        OK&=Resolve(UKismetMathLibrary::StaticClass(),Name);
    if (!OK) { UE_LOG(LogTemp,Error,TEXT("Custom attack loop: missing function."));return; }
    const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/CustomAttack20261003");
    IFileManager::Get().MakeDirectory(*(Dir/TEXT("Before")),true);
    const FString Backup=Dir/TEXT("Before/BP_ProphecyManualPoseAgent-live.uasset");
    FSavePackageArgs Save;Save.TopLevelFlags=RF_Public|RF_Standalone;Save.SaveFlags=SAVE_KeepDirty;
    if (!IFileManager::Get().FileExists(*Backup) && !UPackage::SavePackage(BP->GetOutermost(),BP,*Backup,Save)) return;
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","CustomAttackLoop","Wire captured problem slashL loop"));
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
        FBlueprintEditorUtils::SetBlueprintVariableCategory(BP,Name,nullptr,FText::FromString(TEXT("Codex Custom Slash")),true);
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
        { OK=false;UE_LOG(LogTemp,Error,TEXT("Custom attack link failed: %s.%s -> %s.%s"),*A->GetName(),*AP.ToString(),*B->GetName(),*BPName.ToString()); }
    };
    auto Default=[&](UEdGraphNode* N,FName Pin,const TCHAR* Value)
    { if (auto* P=N->FindPin(Pin)) Schema->TrySetDefaultValue(*P,Value);else OK=false; };
    Entry->NodePosX=0;Entry->NodePosY=0;
    Entry->NodeComment=TEXT("Called by your existing tick debugging branch. Each repeat restores the captured starting pose and BOTH NN histories from the problematic sixth slashL, then attacks its captured target. Cool Out Seconds starts after actual attack completion; zero repeats immediately. Full slashL, current checkpoint/tuning. Original checkpoint: Predictive Pin 184064. Physical rig/sword are explicitly placed at the captured pose; live inference follows. Cyan sphere = captured target. Set Codex Custom Failed=false to retry after an error.");
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
    auto* Seed=Call(TEXT("PrepareProblemSlash"),2210,0);Link(ReadyBranch,TEXT("then"),Seed,TEXT("execute"));
    auto* SeedOK=Branch(2580,0);Link(Seed,TEXT("then"),SeedOK,TEXT("execute"));Link(Seed,TEXT("ReturnValue"),SeedOK,TEXT("Condition"));
    auto* StoreTarget=Set(Target,2850,-40);Link(SeedOK,TEXT("then"),StoreTarget,TEXT("execute"));Link(Seed,TEXT("TargetWorldLocation"),StoreTarget,Target);
    auto* Trigger=Call(TEXT("TriggerNNAttack"),3200,-40);Link(StoreTarget,TEXT("then"),Trigger,TEXT("execute"));Default(Trigger,TEXT("Attack"),TEXT("slashL"));Link(Seed,TEXT("TargetWorldLocation"),Trigger,TEXT("TargetWorldLocation"));Default(Trigger,TEXT("bHalfAttack"),TEXT("false"));
    auto* TriggerOK=Branch(3560,-40);Link(Trigger,TEXT("then"),TriggerOK,TEXT("execute"));Link(Trigger,TEXT("ReturnValue"),TriggerOK,TEXT("Condition"));
    auto* Started=Set(Was,3830,-80);Default(Started,Was,TEXT("true"));Link(TriggerOK,TEXT("then"),Started,TEXT("execute"));
    auto* Visible=Set(HasTarget,4140,-80);Default(Visible,HasTarget,TEXT("true"));Link(Started,TEXT("then"),Visible,TEXT("execute"));
    auto* SeedError=Call(TEXT("PrintString"),2850,800);Link(SeedOK,TEXT("else"),SeedError,TEXT("execute"));Link(Seed,TEXT("OutError"),SeedError,TEXT("InString"));Default(SeedError,TEXT("Duration"),TEXT("15"));
    auto* TriggerError=Call(TEXT("PrintString"),3830,540);Link(TriggerOK,TEXT("else"),TriggerError,TEXT("execute"));Default(TriggerError,TEXT("InString"),TEXT("Codex Custom slash stopped: Trigger NN Attack failed."));Default(TriggerError,TEXT("Duration"),TEXT("15"));
    auto* Fail=Set(Failed,4180,660);Default(Fail,Failed,TEXT("true"));Link(SeedError,TEXT("then"),Fail,TEXT("execute"));Link(TriggerError,TEXT("then"),Fail,TEXT("execute"));
    if (!OK)
    {
        for (auto* N:Added) FBlueprintEditorUtils::RemoveNode(BP,N,true);
        for (FName Name:Variables) FBlueprintEditorUtils::RemoveMemberVariable(BP,Name);
        Entry->UserDefinedPins.Reset();Entry->ReconstructNode();
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
        UE_LOG(LogTemp,Error,TEXT("Custom attack loop: wiring failed, additions rolled back."));return;
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);int32 Callers=0;
    for (auto* G:Graphs) for (UEdGraphNode* Base:G->Nodes) if (auto* N=Cast<UK2Node_CallFunction>(Base))
        if (N->FunctionReference.GetMemberName()==TEXT("codex custom attack"))
        {
            N->Modify();N->ReconstructNode();
            Default(N,TEXT("CoolOutSeconds"),TEXT("1.0"));Default(N,TEXT("ShowTarget"),TEXT("true"));++Callers;
        }
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    const FString Report=FString::Printf(TEXT("nodes=%d callers=%d links_ok=%d status=%d saved=0\n"),Added.Num(),Callers,int32(OK),int32(BP->Status));
    FFileHelper::SaveStringToFile(Report,*(Dir/TEXT("BlueprintBuild.txt")));
    UE_LOG(LogTemp,Display,TEXT("Custom attack loop: %s"),*Report);
}
static FAutoConsoleCommand Command(TEXT("Prophecy.Editor.BuildCustomAttack"),
    TEXT("Fill the empty codex custom attack function with a looping captured slashL comparison. Back up live BP; preserve caller, no save."),
    FConsoleCommandDelegate::CreateStatic(&Build));

// Narrow repair of the captured harness caller; never changes runtime blend algorithms.
static void MatchCapturedPhase()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP) return;
    UEdGraph* Graph=nullptr;
    for (UEdGraph* G:BP->FunctionGraphs) if(G->GetFName()==TEXT("tick debugging"))Graph=G;
    if (!Graph) return;
    auto Find=[&](const TCHAR* Name)->UEdGraphNode* { for(UEdGraphNode* N:Graph->Nodes)if(N->GetName()==Name)return N;return nullptr; };
    auto* Tick=Find(TEXT("K2Node_CallFunction_115"));
    auto* Selection=Find(TEXT("K2Node_CallFunction_150"));
    auto* Half=Find(TEXT("K2Node_IfThenElse_13"));
    if(!Tick || !Selection || !Half)return;
    auto* Offset=Tick->FindPin(TEXT("i"));auto* Selected=Selection->FindPin(TEXT("ReturnValue"));
    auto* Condition=Half->FindPin(TEXT("Condition"));
    if(!Offset || !Selected || !Condition || !Offset->LinkedTo.IsEmpty() || Offset->DefaultValue!=TEXT("0")
        || Condition->LinkedTo.Num()!=1 || Condition->LinkedTo[0]!=Selected)
    { UE_LOG(LogTemp,Warning,TEXT("Captured phase repair: unexpected graph or already repaired; no changes."));return; }
    auto* Function=UKismetMathLibrary::StaticClass()->FindFunctionByName(TEXT("SelectInt"));if(!Function)return;
    const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/CustomAttackParity20261003");
    IFileManager::Get().MakeDirectory(*Dir,true);
    FSavePackageArgs Save;Save.TopLevelFlags=RF_Public|RF_Standalone;Save.SaveFlags=SAVE_KeepDirty;
    const FString Backup=Dir/TEXT("BeforePhaseRepair.uasset");
    if(IFileManager::Get().FileExists(*Backup) || !UPackage::SavePackage(BP->GetOutermost(),BP,*Backup,Save))return;
    FScopedTransaction Transaction(NSLOCTEXT("Prophecy","CapturedAttackPhase","Match captured attack inference phase"));
    BP->Modify();Graph->Modify();Tick->Modify();Half->Modify();Selection->Modify();
    FGraphNodeCreator<UK2Node_CallFunction> Creator(*Graph);auto* Pick=Creator.CreateNode();
    Pick->SetFromFunction(Function);Pick->NodePosX=Tick->NodePosX-280;Pick->NodePosY=Tick->NodePosY+150;Creator.Finalize();
    const auto* Schema=GetDefault<UEdGraphSchema_K2>();
    Schema->TrySetDefaultValue(*Pick->FindPinChecked(TEXT("A")),TEXT("0"));
    Schema->TrySetDefaultValue(*Pick->FindPinChecked(TEXT("B")),TEXT("59"));
    const bool OK=Schema->TryCreateConnection(Selected,Pick->FindPinChecked(TEXT("bPickA")))
        && Schema->TryCreateConnection(Pick->FindPinChecked(TEXT("ReturnValue")),Offset);
    if(!OK){FBlueprintEditorUtils::RemoveNode(BP,Pick,true);return;}
    Pick->NodeComment=TEXT("Original/random mode keeps tick % 60 == 0. Captured custom slash uses == 59: exactly one game tick before its first 30 Hz prediction, matching original trigger731 -> prediction732. Existing entry inertia weights feed back into the NN, so this phase matters.");
    Pick->bCommentBubbleVisible=true;
    Schema->BreakSinglePinLink(Selected,Condition);Schema->TrySetDefaultValue(*Condition,TEXT("true"));
    Half->NodeComment=TEXT("Keep the original Armed-to-half logic in both selected harnesses. Selecting the custom attack must not silently disable this transition.");Half->bCommentBubbleVisible=true;
    for(UEdGraph* G:BP->FunctionGraphs)if(G->GetFName()==TEXT("codex custom attack"))for(UEdGraphNode* N:G->Nodes)
        if(auto* Entry=Cast<UK2Node_FunctionEntry>(N))Entry->NodeComment=TEXT("Captured sixth slashL entry and target, current checkpoint/tuning. Caller preserves original 30 Hz phase and Armed-to-half transition. Both NN histories are restored each repeat; live inference follows.");
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    const FString Report=FString::Printf(TEXT("phase_links=%d status=%d saved=0\n"),int32(OK),int32(BP->Status));
    FFileHelper::SaveStringToFile(Report,*(Dir/TEXT("phase-repair.txt")));
    UE_LOG(LogTemp,Display,TEXT("Captured phase repair: %s"),*Report);
}
static FAutoConsoleCommand PhaseCommand(TEXT("Prophecy.Editor.MatchCustomAttackPhase"),
    TEXT("Preserve the captured slash inference phase and original Armed-to-half switch in the custom harness."),
    FConsoleCommandDelegate::CreateStatic(&MatchCapturedPhase));

}
