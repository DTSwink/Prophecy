#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "EdGraphSchema_K2.h"
#include "EdGraphUtilities.h"
#include "K2Node_CallFunction.h"
#include "K2Node_CommutativeAssociativeBinaryOperator.h"
#include "K2Node_PromotableOperator.h"
#include "K2Node_ExecutionSequence.h"
#include "K2Node_IfThenElse.h"
#include "K2Node_VariableGet.h"
#include "K2Node_VariableSet.h"
#include "Kismet/KismetMathLibrary.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ScopedTransaction.h"
#include "UObject/SavePackage.h"

namespace ProphecyRestoreHalfAttackBranch
{
static void Restore()
{
    if(!GEditor || GEditor->PlayWorld)return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if(!BP)return;
    UEdGraph* G=nullptr;for(UEdGraph* Graph:BP->FunctionGraphs)if(Graph->GetFName()==TEXT("NewFunction"))G=Graph;
    if(!G)return;
    auto Find=[&](const TCHAR* Name)->UEdGraphNode*{for(UEdGraphNode* N:G->Nodes)if(N->GetFName()==Name)return N;return nullptr;};
    auto* Stop=Cast<UK2Node_CallFunction>(Find(TEXT("K2Node_CallFunction_10")));
    auto* Attack=Cast<UK2Node_CallFunction>(Find(TEXT("K2Node_CallFunction_197")));
    if(!Stop || !Attack || Attack->FunctionReference.GetMemberName()!=TEXT("TriggerNNAttack"))return;
    auto* From=Stop->FindPin(TEXT("then"));auto* To=Attack->FindPin(TEXT("execute"));auto* Half=Attack->FindPin(TEXT("bHalfAttack"));
    if(!From || !To || !Half || From->LinkedTo.Num()!=1 || From->LinkedTo[0]!=To || !Half->LinkedTo.IsEmpty())
    {UE_LOG(LogTemp,Warning,TEXT("RestoreHalfAttack: graph differs or branch already exists; no edits"));return;}
    for(const TCHAR* Name:{TEXT("half attack start"),TEXT("dtarget"),TEXT("the victim speed")})
        if(!FBlueprintEditorUtils::FindLocalVariable(BP,G,FName(Name)))
        {UE_LOG(LogTemp,Error,TEXT("RestoreHalfAttack: missing local %s"),Name);return;}
    auto* Math=UKismetMathLibrary::StaticClass();
    const FName Functions[]={TEXT("Not_PreBool"),TEXT("Dot_VectorVector"),TEXT("Greater_DoubleDouble"),TEXT("BooleanOR")};
    for(FName Name:Functions)if(!Math->FindFunctionByName(Name))return;
    const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/FKReturnSplit20261008");
    const FString Backup=Dir/TEXT("BeforeBranchRestore-live.uasset");
    FSavePackageArgs Save;Save.TopLevelFlags=RF_Public|RF_Standalone;Save.SaveFlags=SAVE_KeepDirty;
    if(!IFileManager::Get().FileExists(*Backup) && !UPackage::SavePackage(BP->GetOutermost(),BP,*Backup,Save))return;
    TSet<UObject*> Nodes;for(UEdGraphNode* N:G->Nodes)Nodes.Add(N);FString Text;FEdGraphUtilities::ExportNodesToText(Nodes,Text);
    FFileHelper::SaveStringToFile(Text,*(Dir/TEXT("NewFunction-before.txt")));
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","RestoreHalfAttackBranch","Restore half attack start branch"));
    BP->Modify();G->Modify();Stop->Modify();Attack->Modify();
    const auto* Schema=GetDefault<UEdGraphSchema_K2>();TArray<UEdGraphNode*> Added;
    const int X=Stop->NodePosX+320,Y=Stop->NodePosY;
    auto Call=[&](FName Name,int PX,int PY){FGraphNodeCreator<UK2Node_CallFunction> C(*G);auto* N=C.CreateNode();
        N->SetFromFunction(Math->FindFunctionByName(Name));N->NodePosX=PX;N->NodePosY=PY;C.Finalize();Added.Add(N);return N;};
    auto Get=[&](FName Name,int PX,int PY){FGraphNodeCreator<UK2Node_VariableGet> C(*G);auto* N=C.CreateNode();
        N->VariableReference.SetLocalMember(Name,G->GetName(),FBlueprintEditorUtils::FindLocalVariableGuidByName(BP,G,Name));N->NodePosX=PX;N->NodePosY=PY;C.Finalize();Added.Add(N);return N;};
    FGraphNodeCreator<UK2Node_ExecutionSequence> SC(*G);auto* Seq=SC.CreateNode();Seq->NodePosX=X;Seq->NodePosY=Y;SC.Finalize();Added.Add(Seq);
    FGraphNodeCreator<UK2Node_IfThenElse> BC(*G);auto* Gate=BC.CreateNode();Gate->NodePosX=X+480;Gate->NodePosY=Y-240;BC.Finalize();Added.Add(Gate);
    FGraphNodeCreator<UK2Node_VariableSet> VC(*G);auto* Set=VC.CreateNode();Set->VariableReference.SetLocalMember(TEXT("half attack start"),G->GetName(),FBlueprintEditorUtils::FindLocalVariableGuidByName(BP,G,TEXT("half attack start")));
    Set->NodePosX=X+1100;Set->NodePosY=Y-240;VC.Finalize();Added.Add(Set);
    auto* Prior=Get(TEXT("half attack start"),X,Y-400);auto* Current=Get(TEXT("half attack start"),Attack->NodePosX-250,Attack->NodePosY+200);
    auto* Not=Call(TEXT("Not_PreBool"),X+250,Y-400);
    auto* Speed=Get(TEXT("the victim speed"),X,Y-740);auto* Direction=Get(TEXT("dtarget"),X,Y-630);
    auto* Dot=Call(TEXT("Dot_VectorVector"),X+250,Y-740);
    FGraphNodeCreator<UK2Node_PromotableOperator> PC(*G);auto* Positive=PC.CreateNode();Positive->SetFromFunction(Math->FindFunctionByName(TEXT("Greater_DoubleDouble")));
    Positive->NodePosX=X+510;Positive->NodePosY=Y-740;PC.Finalize();Added.Add(Positive);
    FGraphNodeCreator<UK2Node_CommutativeAssociativeBinaryOperator> OC(*G);auto* Or=OC.CreateNode();Or->SetFromFunction(Math->FindFunctionByName(TEXT("BooleanOR")));
    Or->NodePosX=X+790;Or->NodePosY=Y-610;OC.Finalize();Or->AddInputPin();Added.Add(Or);
    bool OK=true;
    auto Link=[&](UEdGraphNode* A,const TCHAR* AP,UEdGraphNode* B,const TCHAR* BPName){auto* P=A->FindPin(AP);auto* Q=B->FindPin(BPName);
        if(!P || !Q || !Schema->TryCreateConnection(P,Q)){OK=false;UE_LOG(LogTemp,Error,TEXT("RestoreHalfAttack: failed %s -> %s"),AP,BPName);}};
    Link(Seq,TEXT("then_0"),Gate,TEXT("execute"));Link(Prior,TEXT("half attack start"),Not,TEXT("A"));
    Link(Not,TEXT("ReturnValue"),Gate,TEXT("Condition"));Link(Gate,TEXT("then"),Set,TEXT("execute"));
    Link(Speed,TEXT("the victim speed"),Dot,TEXT("A"));Link(Direction,TEXT("dtarget"),Dot,TEXT("B"));
    Link(Dot,TEXT("ReturnValue"),Positive,TEXT("A"));Link(Positive,TEXT("ReturnValue"),Or,TEXT("A"));Link(Or,TEXT("ReturnValue"),Set,TEXT("half attack start"));
    Schema->TrySetDefaultValue(*Positive->FindPinChecked(TEXT("B")),TEXT("0.0"));
    Schema->TrySetDefaultValue(*Or->FindPinChecked(TEXT("B")),TEXT("false"));
    Schema->TrySetDefaultValue(*Or->FindPinChecked(TEXT("C")),TEXT("false"));
    if(OK){From->BreakLinkTo(To);Link(Stop,TEXT("then"),Seq,TEXT("execute"));Link(Seq,TEXT("then_1"),Attack,TEXT("execute"));Link(Current,TEXT("half attack start"),Attack,TEXT("bHalfAttack"));}
    if(!OK)
    {
        for(auto* N:Added)FBlueprintEditorUtils::RemoveNode(BP,N,true);
        Schema->TryCreateConnection(From,To);
        UE_LOG(LogTemp,Error,TEXT("RestoreHalfAttack: restored original connections after failure"));return;
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    FString Report=FString::Printf(TEXT("added=%d status=%d saved=0\n"),Added.Num(),int32(BP->Status));
    for(auto* N:Added)Report+=N->GetName()+TEXT("\n");
    FFileHelper::SaveStringToFile(Report,*(Dir/TEXT("branch-restoration.txt")));
    UE_LOG(LogTemp,Display,TEXT("RestoreHalfAttack: %s"),*Report);
}
static FAutoConsoleCommand Command(TEXT("Prophecy.Editor.RestoreHalfAttackStartBranch"),
    TEXT("Restore the October8 recorded NewFunction half-attack branch; backs up live asset, leaves unsaved."),FConsoleCommandDelegate::CreateStatic(&Restore));
}
