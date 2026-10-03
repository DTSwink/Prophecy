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
#include "ProphecyAttackWristLibrary.h"

namespace
{
void WireForearmStretchReturn()
{
    if(!GEditor || GEditor->PlayWorld)return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if(!BP)return;
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
    UK2Node_CallFunction* Drag=nullptr;bool Existing=false;
    for(auto* G:Graphs)for(UEdGraphNode* Base:G->Nodes)if(auto* N=Cast<UK2Node_CallFunction>(Base))
    {
        const FName Name=N->FunctionReference.GetMemberName();
        if(Name==TEXT("SetAttackForearmStretchReturn"))Existing=true;
        auto* Exec=N->FindPin(TEXT("execute"));if(!Exec || Exec->LinkedTo.IsEmpty())continue;
        if(Name==TEXT("SetAttackFootLocomotion")){if(Drag)return;Drag=N;}
    }
    if(!Drag)return;
    const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/AttackForearmStretch20261003");
    IFileManager::Get().MakeDirectory(*Dir,true);
    FSavePackageArgs Save;Save.TopLevelFlags=RF_Public|RF_Standalone;Save.SaveFlags=SAVE_KeepDirty;
    const FString Backup=Dir/(Existing?TEXT("BP-live-before-final.uasset"):TEXT("BP-live-before.uasset"));
    if(!IFileManager::Get().FileExists(*Backup) && !UPackage::SavePackage(BP->GetOutermost(),BP,*Backup,Save))return;
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","GhostLocoDrag","Enable forearm stretch and captured-length return"));
    BP->Modify();bool OK=true;
    auto Insert=[&](UK2Node_CallFunction* Before,FName Function)
    {
        auto* Graph=Before->GetGraph();Graph->Modify();Before->Modify();
        auto* Func=UProphecyAttackWristLibrary::StaticClass()->FindFunctionByName(Function);
        if(!Func){OK=false;return;}
        auto* N=NewObject<UK2Node_CallFunction>(Graph,NAME_None,RF_Transactional);
        Graph->AddNode(N,true,false);N->CreateNewGuid();N->SetFromFunction(Func);N->AllocateDefaultPins();
        N->NodePosX=Before->NodePosX+440;N->NodePosY=Before->NodePosY;
        const auto* Schema=Graph->GetSchema();Schema->TrySetDefaultValue(*N->FindPin(TEXT("Enabled")),TEXT("true"));
        auto* Agent=Before->FindPin(TEXT("Agent"));auto* Dest=N->FindPin(TEXT("Agent"));
        Dest->DefaultObject=Agent->DefaultObject;Dest->DefaultValue=Agent->DefaultValue;
        for(auto* L:Agent->LinkedTo)OK &= Schema->TryCreateConnection(L,Dest);
        auto* Then=Before->FindPin(TEXT("then"));const auto Next=Then->LinkedTo;
        Then->BreakAllPinLinks();OK &= Schema->TryCreateConnection(Then,N->FindPin(TEXT("execute")));
        for(auto* L:Next){L->GetOwningNode()->Modify();OK &= Schema->TryCreateConnection(N->FindPin(TEXT("then")),L);}
    };
    if(!Existing)Insert(Drag,TEXT("SetAttackForearmStretchReturn"));
    int32 FreedomChanged=0;
    for(auto* G:Graphs)for(UEdGraphNode* Base:G->Nodes)if(auto* N=Cast<UK2Node_CallFunction>(Base))
        if(N->FunctionReference.GetMemberName()==TEXT("SetNNWristFreedom"))
        {
            auto* Exec=N->FindPin(TEXT("execute"));auto* Position=N->FindPin(TEXT("FreePosition"));
            if(Exec && !Exec->LinkedTo.IsEmpty() && Position && Position->LinkedTo.IsEmpty() && Position->DefaultValue==TEXT("true"))
            {G->Modify();N->Modify();G->GetSchema()->TrySetDefaultValue(*Position,TEXT("false"));++FreedomChanged;}
        }
    // The caller now owns simulation mode. The debug GT target helper accepts
    // Sim/Half Sim and does not reset their live physical/NN state.
    int32 Bypassed=0;
    for(auto* G:Graphs)for(UEdGraphNode* Base:G->Nodes)if(auto* N=Cast<UK2Node_CallFunction>(Base))
    {
        if(N->FunctionReference.GetMemberName()!=TEXT("SetSimulationMode"))continue;
        auto* Mode=N->FindPin(TEXT("NewMode"));auto* In=N->FindPin(TEXT("execute"));auto* Out=N->FindPin(TEXT("then"));
        if(!Mode || !In || !Out || !Mode->LinkedTo.IsEmpty() || Mode->DefaultValue!=TEXT("Kinematic") || Out->LinkedTo.Num()!=1)continue;
        auto* Next=Cast<UK2Node_CallFunction>(Out->LinkedTo[0]->GetOwningNode());
        if(!Next || Next->FunctionReference.GetMemberName()!=TEXT("codex GT slash"))continue;
        G->Modify();N->Modify();Next->Modify();const auto From=In->LinkedTo;auto* To=Out->LinkedTo[0];
        In->BreakAllPinLinks();Out->BreakAllPinLinks();
        for(auto* P:From){P->GetOwningNode()->Modify();OK &= G->GetSchema()->TryCreateConnection(P,To);}
        ++Bypassed;
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    const FString Report=FString::Printf(TEXT("connections_ok=%d status=%d asset_saved=0 gt_kinematic_bypassed=%d wrist_free_defaults_changed=%d\n"),int32(OK),int32(BP->Status),Bypassed,FreedomChanged);
    FFileHelper::SaveStringToFile(Report,*(Dir/TEXT("wiring.txt")));
    UE_LOG(LogTemp,Display,TEXT("Forearm stretch: %s"),*Report);
}
FAutoConsoleCommand ForearmStretchSetup(TEXT("Prophecy.Editor.WireForearmStretchReturn"),TEXT("Back up and wire forearm return; bypass forced Kinematic before GT slash; compile without saving."),FConsoleCommandDelegate::CreateStatic(&WireForearmStretchReturn));
}
