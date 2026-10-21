#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraphSchema_K2.h"
#include "HAL/IConsoleManager.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"

// Explicit, narrowly guarded repair of the death branch; no startup mutation or save.
static FAutoConsoleCommand SwordDeathDrop(TEXT("Prophecy.Editor.RepairSwordDeathDrop"),
    TEXT("Drop owned equipment before testing the result and setting its material. Does not save."),
    FConsoleCommandDelegate::CreateLambda([]
    {
        if(!GEditor || GEditor->PlayWorld)return;
        auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
        if(!BP)return;
        TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
        for(auto* G:Graphs)if(G->GetFName()==TEXT("die revive"))
        {
            auto Pin=[&](const TCHAR* Node,const TCHAR* Name)->UEdGraphPin*
            {for(UEdGraphNode* N:G->Nodes)if(N->GetFName()==Node)return N->FindPin(Name);return nullptr;};
            auto* Before=Pin(TEXT("K2Node_CallFunction_109"),TEXT("then"));
            auto* Guard=Pin(TEXT("K2Node_IfThenElse_2"),TEXT("execute"));
            auto* GuardOut=Pin(TEXT("K2Node_IfThenElse_2"),TEXT("then"));
            auto* DropIn=Pin(TEXT("K2Node_CallFunction_169"),TEXT("execute"));
            auto* DropOut=Pin(TEXT("K2Node_CallFunction_169"),TEXT("then"));
            auto* Result=Pin(TEXT("K2Node_CallFunction_169"),TEXT("ReturnValue"));
            auto* GuardObject=Pin(TEXT("K2Node_PromotableOperator_1"),TEXT("A"));
            auto* Object=Pin(TEXT("K2Node_DynamicCast_0"),TEXT("Object"));
            auto* Sword=Pin(TEXT("K2Node_DynamicCast_0"),TEXT("AsA Sword"));
            auto* MeshOwner=Pin(TEXT("K2Node_VariableGet_1"),TEXT("self"));
            auto* MaterialIn=Pin(TEXT("K2Node_CallFunction_5"),TEXT("execute"));
            auto* MaterialOut=Pin(TEXT("K2Node_CallFunction_5"),TEXT("then"));
            const TArray<UEdGraphPin*> Pins={Before,Guard,GuardOut,DropIn,DropOut,Result,GuardObject,Object,Sword,MeshOwner,MaterialIn,MaterialOut};
            for(auto* P:Pins)if(!P){UE_LOG(LogTemp,Error,TEXT("SwordDeathDrop: expected pin missing; no edits"));return;}
            if(!Before->LinkedTo.Contains(Guard)||!GuardOut->LinkedTo.Contains(MaterialIn)||!MaterialOut->LinkedTo.Contains(DropIn)
                ||!DropOut->LinkedTo.IsEmpty()||!Sword->LinkedTo.IsEmpty())
            {UE_LOG(LogTemp,Error,TEXT("SwordDeathDrop: wiring differs from inspected graph; no edits"));return;}
            BP->Modify();G->Modify();for(auto* P:Pins)P->GetOwningNode()->Modify();
            Before->BreakLinkTo(Guard);MaterialOut->BreakLinkTo(DropIn);
            Object->BreakAllPinLinks();MeshOwner->BreakAllPinLinks();GuardObject->BreakAllPinLinks();
            Before->MakeLinkTo(DropIn);DropOut->MakeLinkTo(Guard);Result->MakeLinkTo(Object);
            Result->MakeLinkTo(GuardObject);Sword->MakeLinkTo(MeshOwner);
            FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
            FKismetEditorUtilities::CompileBlueprint(BP);
            UE_LOG(LogTemp,Display,TEXT("SwordDeathDrop: repaired status=%d; not saved"),int32(BP->Status));
            return;
        }
    }));
