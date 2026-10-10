#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CallFunction.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_IfThenElse.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "ScopedTransaction.h"

namespace ProphecySwordHolsterSetup
{
static void Wire()
{
    if(!GEditor || GEditor->PlayWorld)return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if(!BP)return;
    auto* Library=FindObject<UClass>(nullptr,TEXT("/Script/GameAnimationSample3.ProphecySwordHolsterLibrary"));
    if(!Library)return;
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
    UEdGraph* Tick=nullptr;UK2Node_IfThenElse* Branch=nullptr;
    TArray<UK2Node_FunctionEntry*> Entries;
    for(auto* G:Graphs)
    {
        if(G->GetFName()==TEXT("tick debugging"))Tick=G;
        for(UEdGraphNode* N:G->Nodes)
        {
            if(auto* Call=Cast<UK2Node_CallFunction>(N))if(Call->FunctionReference.GetMemberName()==TEXT("DrawSword"))
            {UE_LOG(LogTemp,Warning,TEXT("Sword holster wiring already exists; no changes."));return;}
            if(G->GetFName()==TEXT("begin_f") || G->GetFName()==TEXT("UserConstructionScript"))
                if(auto* E=Cast<UK2Node_FunctionEntry>(N))Entries.Add(E);
            if(G==Tick && N->GetFName()==TEXT("K2Node_IfThenElse_5"))Branch=Cast<UK2Node_IfThenElse>(N);
        }
    }
    auto* Condition=Branch?Branch->GetConditionPin():nullptr;
    auto* At=Condition && Condition->LinkedTo.Num()==1?Cast<UK2Node_CallFunction>(Condition->LinkedTo[0]->GetOwningNode()):nullptr;
    if(!Branch || !Branch->GetThenPin()->LinkedTo.IsEmpty() || Entries.Num()!=2 || !At ||
        At->FunctionReference.GetMemberName()!=TEXT("is tick") || !At->FindPin(TEXT("i")) || At->FindPin(TEXT("i"))->DefaultValue!=TEXT("25"))
    {UE_LOG(LogTemp,Error,TEXT("Sword holster: expected unused tick25 branch and construction/begin entries; no changes."));return;}
    for(auto* E:Entries)if(!E->FindPin(UEdGraphSchema_K2::PN_Then) || E->FindPin(UEdGraphSchema_K2::PN_Then)->LinkedTo.Num()>1)return;
    const FScopedTransaction Transaction(NSLOCTEXT("Prophecy","SwordHolster","Wire procedural sword holster"));
    BP->Modify();Tick->Modify();Branch->Modify();
    const auto* Schema=GetDefault<UEdGraphSchema_K2>();
    auto Call=[&](UEdGraph* G,FName Function,int32 X,int32 Y)
    {
        FGraphNodeCreator<UK2Node_CallFunction> C(*G);auto* N=C.CreateNode();
        N->SetFromFunction(Library->FindFunctionByName(Function));
        N->NodePosX=X;N->NodePosY=Y;C.Finalize();return N;
    };
    bool OK=true;
    auto Link=[&](UEdGraphPin* A,UEdGraphPin* B){OK&=A && B && Schema->TryCreateConnection(A,B);};
    for(auto* E:Entries)
    {
        E->GetGraph()->Modify();E->Modify();auto* Out=E->FindPinChecked(UEdGraphSchema_K2::PN_Then);
        auto* Next=Out->LinkedTo.IsEmpty()?nullptr:Out->LinkedTo[0];
        if(Next)Next->GetOwningNode()->Modify();
        auto* Capture=Call(E->GetGraph(),TEXT("CaptureSwordHolsterReference"),E->NodePosX+250,E->NodePosY-180);
        Out->BreakAllPinLinks();Link(Out,Capture->GetExecPin());if(Next)Link(Capture->GetThenPin(),Next);
    }
    auto* Profile=Call(Tick,TEXT("SetSwordHolsterProfile"),Branch->NodePosX+300,Branch->NodePosY+130);
    auto* Draw=Call(Tick,TEXT("DrawSword"),Branch->NodePosX+640,Branch->NodePosY+130);
    Schema->TrySetDefaultValue(*Draw->FindPinChecked(TEXT("Sheathe")),TEXT("true"));
    Link(Branch->GetThenPin(),Profile->GetExecPin());Link(Profile->GetThenPin(),Draw->GetExecPin());
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    FFileHelper::SaveStringToFile(FString::Printf(TEXT("connections=%d status=%d saved=0 added=4\n"),OK,int32(BP->Status)),
        *(FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordDraw20261010/wiring.txt")));
}
static FAutoConsoleCommand Command(TEXT("Prophecy.Editor.WireSwordHolster"),TEXT("Wire audited tick25 sword holster and capture reference; compile without saving."),FConsoleCommandDelegate::CreateStatic(&Wire));
}
