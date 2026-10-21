#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraphSchema_K2.h"
#include "HAL/IConsoleManager.h"
#include "K2Node_CallFunction.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"

// Explicit migration of the user's bomb only; never runs at startup or saves.
static FAutoConsoleCommand StaticBombFuse(TEXT("Prophecy.Editor.StaticBombFuse"),
    TEXT("Remove retired fuse-physics nodes, wire current Niagara, and refresh upright fuse pins on A_Bomb. Does not save."),
    FConsoleCommandDelegate::CreateLambda([]
    {
        if(!GEditor || GEditor->PlayWorld)return;
        auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/bomb/A_Bomb.A_Bomb"));
        auto* Effect=LoadObject<UObject>(nullptr,TEXT("/Game/_mygame/bomb/NewNiagaraSystem1.NewNiagaraSystem1"));
        if(!BP || !Effect)return;
        TArray<UEdGraph*> Graphs;BP->GetAllGraphs(Graphs);
        // Validate before modifying: no hidden dependency on the retired result.
        for(auto* G:Graphs)for(UEdGraphNode* N:G->Nodes)if(auto* Call=Cast<UK2Node_CallFunction>(N))
        {
            const FName Function=Call->FunctionReference.GetMemberName();
            if(Function==TEXT("SetBombFuseStiffness"))
                if(auto* Result=Call->FindPin(TEXT("ReturnValue"));Result && !Result->LinkedTo.IsEmpty())
                {UE_LOG(LogTemp,Error,TEXT("StaticBombFuse: retired result has consumers; migration stopped"));return;}
            if(Function==TEXT("LightBombFuse"))
                if(auto* Pin=Call->FindPin(TEXT("FuseSparks"));Pin && !Pin->LinkedTo.IsEmpty())
                {UE_LOG(LogTemp,Error,TEXT("StaticBombFuse: emitter pin is wired; migration stopped"));return;}
        }
        BP->Modify();int32 Removed=0,Assigned=0;
        for(auto* G:Graphs)
        {
            const auto Nodes=G->Nodes;
            for(UEdGraphNode* N:Nodes)if(auto* Call=Cast<UK2Node_CallFunction>(N))
            {
                const FName Function=Call->FunctionReference.GetMemberName();
                if(Function==TEXT("SetBombFuseStiffness"))
                {
                    auto* In=Call->FindPin(UEdGraphSchema_K2::PN_Execute);
                    auto* Out=Call->FindPin(UEdGraphSchema_K2::PN_Then);
                    const TArray<UEdGraphPin*> Before=In?In->LinkedTo:TArray<UEdGraphPin*>();
                    const TArray<UEdGraphPin*> After=Out?Out->LinkedTo:TArray<UEdGraphPin*>();
                    FBlueprintEditorUtils::RemoveNode(BP,Call,true);
                    for(auto* A:Before)for(auto* B:After)A->MakeLinkTo(B);
                    ++Removed;
                }
                else if(Function==TEXT("LightBombFuse"))
                {
                    Call->Modify();Call->ReconstructNode();
                    if(auto* Old=Call->FindPin(TEXT("SparkRotationOffset")))
                    {Old->BreakAllPinLinks();Call->RemovePin(Old);}
                    if(auto* Pin=Call->FindPin(TEXT("FuseSparks")))
                    {G->GetSchema()->TrySetDefaultObject(*Pin,Effect);++Assigned;}
                }
            }
        }
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
        FKismetEditorUtilities::CompileBlueprint(BP);
        UE_LOG(LogTemp,Display,TEXT("StaticBombFuse: removed=%d assigned=%d status=%d; not saved"),Removed,Assigned,int32(BP->Status));
    }));
