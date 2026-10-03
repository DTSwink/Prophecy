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
#include "ProphecyAttackFootLocomotionLibrary.h"

namespace
{
void WireGhostLocoDrag()
{
    if(!GEditor || GEditor->PlayWorld)return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if(!BP)return;
    TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
    UK2Node_CallFunction* Drag=nullptr;UK2Node_CallFunction* Draw=nullptr;
    for(auto* G:Graphs)for(UEdGraphNode* Base:G->Nodes)if(auto* N=Cast<UK2Node_CallFunction>(Base))
    {
        const FName Name=N->FunctionReference.GetMemberName();
        if(Name==TEXT("SetGhostLocoDrag"))return; // Explicit, idempotent editor action.
        auto* Exec=N->FindPin(TEXT("execute"));if(!Exec || Exec->LinkedTo.IsEmpty())continue;
        if(Name==TEXT("SetAttackFootLocomotion")){if(Drag)return;Drag=N;}
        if(Name==TEXT("DrawAttackFootLocomotion")){if(Draw)return;Draw=N;}
    }
    if(!Drag || !Draw)return;
    const FString Dir=FPaths::ProjectSavedDir()/TEXT("Diagnostics/GhostLocoDrag20261003");
    IFileManager::Get().MakeDirectory(*Dir,true);
    FSavePackageArgs Save;Save.TopLevelFlags=RF_Public|RF_Standalone;Save.SaveFlags=SAVE_KeepDirty;
    if(!UPackage::SavePackage(BP->GetOutermost(),BP,*(Dir/TEXT("BP-live-before.uasset")),Save))return;
    FScopedTransaction Tx(NSLOCTEXT("Prophecy","GhostLocoDrag","Enable ghost loco drag and its visualization"));
    BP->Modify();bool OK=true;
    auto Insert=[&](UK2Node_CallFunction* Before,FName Function)
    {
        auto* Graph=Before->GetGraph();Graph->Modify();Before->Modify();
        auto* Func=UProphecyAttackFootLocomotionLibrary::StaticClass()->FindFunctionByName(Function);
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
    Insert(Drag,TEXT("SetGhostLocoDrag"));Insert(Draw,TEXT("DrawGhostLocoDrag"));
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    const FString Report=FString::Printf(TEXT("connections_ok=%d status=%d asset_saved=0\n"),int32(OK),int32(BP->Status));
    FFileHelper::SaveStringToFile(Report,*(Dir/TEXT("wiring.txt")));
    UE_LOG(LogTemp,Display,TEXT("Ghost loco drag: %s"),*Report);
}
FAutoConsoleCommand GhostLocoDragSetup(TEXT("Prophecy.Editor.WireGhostLocoDrag"),TEXT("Back up, insert ghost loco drag and draw after the active drag nodes, compile without saving."),FConsoleCommandDelegate::CreateStatic(&WireGhostLocoDrag));
}
