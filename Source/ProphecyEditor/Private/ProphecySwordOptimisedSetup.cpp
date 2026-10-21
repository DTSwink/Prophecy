#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CallFunction.h"
#include "K2Node_FunctionEntry.h"
#include "K2Node_IfThenElse.h"
#include "K2Node_Self.h"
#include "K2Node_VariableGet.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "ProphecyPhysicsConstraintBlueprintLibrary.h"
#include "ScopedTransaction.h"
#include "HAL/IConsoleManager.h"

namespace ProphecySwordOptimisedSetup
{
void SkipDuplicateSlashRestore(UBlueprint* BP, UEdGraph* Graph)
{
    UK2Node_IfThenElse* Old = nullptr;
    for (UEdGraphNode* N : Graph->Nodes)
    {
        if (N->GetName() == TEXT("ProphecyOptimisedSkipRestore")) return;
        if (N->GetName() == TEXT("ProphecyPikeSkipRestore")) Old = Cast<UK2Node_IfThenElse>(N);
    }
    if (!Old || Old->GetExecPin()->LinkedTo.Num() != 1 || Old->GetThenPin()->LinkedTo.Num() != 1) return;
    BP->Modify(); Graph->Modify(); Old->Modify();
    FGraphNodeCreator<UK2Node_IfThenElse> B(*Graph); auto* Choice = B.CreateNode();
    Choice->Rename(TEXT("ProphecyOptimisedSkipRestore"), Graph);
    Choice->NodePosX = Old->NodePosX - 280; Choice->NodePosY = Old->NodePosY - 180; B.Finalize();
    FGraphNodeCreator<UK2Node_VariableGet> V(*Graph); auto* Get = V.CreateNode();
    Get->VariableReference.SetSelfMember(TEXT("Optimised")); Get->NodePosX = Choice->NodePosX - 220; Get->NodePosY = Choice->NodePosY + 80; V.Finalize();
    Get->FindPinChecked(TEXT("Optimised"))->MakeLinkTo(Choice->GetConditionPin());
    auto* Before = Old->GetExecPin()->LinkedTo[0]; auto* After = Old->GetThenPin()->LinkedTo[0];
    Before->GetOwningNode()->Modify(); After->GetOwningNode()->Modify();
    Before->BreakLinkTo(Old->GetExecPin()); Before->MakeLinkTo(Choice->GetExecPin());
    Choice->GetElsePin()->MakeLinkTo(Old->GetExecPin()); Choice->GetThenPin()->MakeLinkTo(After);
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
}
void Install()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP = LoadObject<UBlueprint>(nullptr, TEXT("/Game/_mygame/sword/A_Sword.A_Sword"));
    if (!BP) return;
    TArray<UEdGraph*> Graphs; BP->GetAllGraphs(Graphs);
    UEdGraph* Events = nullptr; UEdGraph* Handle = nullptr;
    for (auto* G : Graphs)
    {
        if (G->GetName() == TEXT("EventGraph")) Events = G;
        if (G->GetName() == TEXT("handle cuts f")) Handle = G;
    }
    if (!Events || !Handle) return;
    auto Find = [](UEdGraph* G, const TCHAR* Name) -> UEdGraphNode*
    { for (UEdGraphNode* N : G->Nodes) if (N && N->GetName() == Name) return N; return nullptr; };
    if (Find(Events, TEXT("ProphecyStartOptimisedCut")))
    {
        SkipDuplicateSlashRestore(BP, Events);
        FKismetEditorUtilities::CompileBlueprint(BP);
        UE_LOG(LogTemp, Display, TEXT("Optimised sword wiring verified, status=%d; preserving edits."), int32(BP->Status)); return;
    }
    auto* Init = Find(Events, TEXT("K2Node_CallFunction_50"));
    auto* Made = Find(Events, TEXT("K2Node_AddComponent_0"));
    auto* Correction = Find(Events, TEXT("ProphecyPikeWoundCorrection"));
    auto* Entry = Find(Handle, TEXT("K2Node_FunctionEntry_0"));
    auto* Function = UProphecyPhysicsConstraintBlueprintLibrary::StaticClass()->FindFunctionByName(TEXT("StartOptimisedSwordCut"));
    if (!Init || !Made || !Correction || !Entry || !Function) return;
    auto* Before = Init->FindPin(UEdGraphSchema_K2::PN_Execute);
    auto* EntryThen = Entry->FindPin(UEdGraphSchema_K2::PN_Then);
    if (!Before || Before->LinkedTo.Num() != 1 || !EntryThen || EntryThen->LinkedTo.Num() != 1
        || !Init->FindPinChecked(UEdGraphSchema_K2::PN_Then)->LinkedTo.Contains(Correction->FindPinChecked(UEdGraphSchema_K2::PN_Execute))) return;
    const FScopedTransaction Transaction(NSLOCTEXT("Prophecy", "OptimisedSwordCuts", "Add optimised sword cut mode"));
    BP->Modify(); Events->Modify(); Handle->Modify();
    FEdGraphPinType Boolean; Boolean.PinCategory = UEdGraphSchema_K2::PC_Boolean;
    if (FBlueprintEditorUtils::FindNewVariableIndex(BP, TEXT("Optimised")) == INDEX_NONE)
        FBlueprintEditorUtils::AddMemberVariable(BP, TEXT("Optimised"), Boolean, TEXT("true"));
    FBlueprintEditorUtils::SetBlueprintVariableCategory(BP, TEXT("Optimised"), nullptr, FText::FromString(TEXT("Sword|Cuts")));
    FBlueprintEditorUtils::SetBlueprintVariableMetaData(BP, TEXT("Optimised"), nullptr, TEXT("Tooltip"),
        TEXT("Select before Play. Uses physics travel release, one-time friction and a five-frame solid penetration cap. False keeps the original post-hit Tick path."));
    auto Branch = [&](UEdGraph* G, int32 X, int32 Y, const TCHAR* Name)
    {
        FGraphNodeCreator<UK2Node_IfThenElse> B(*G); auto* N = B.CreateNode();
        N->Rename(Name, G); N->NodePosX = X; N->NodePosY = Y; B.Finalize();
        FGraphNodeCreator<UK2Node_VariableGet> V(*G); auto* Get = V.CreateNode();
        Get->VariableReference.SetSelfMember(TEXT("Optimised")); Get->NodePosX = X - 220; Get->NodePosY = Y + 90; V.Finalize();
        Get->FindPinChecked(TEXT("Optimised"))->MakeLinkTo(N->GetConditionPin());
        return N;
    };
    auto* Choice = Branch(Events, Init->NodePosX - 350, Init->NodePosY - 250, TEXT("ProphecyOptimisedHitMode"));
    auto* Previous = Before->LinkedTo[0]; Previous->GetOwningNode()->Modify(); Init->Modify();
    Previous->BreakLinkTo(Before); Previous->MakeLinkTo(Choice->GetExecPin()); Choice->GetElsePin()->MakeLinkTo(Before);
    FGraphNodeCreator<UK2Node_CallFunction> C(*Events); auto* Start = C.CreateNode();
    Start->Rename(TEXT("ProphecyStartOptimisedCut"), Events); Start->SetFromFunction(Function);
    Start->NodePosX = Choice->NodePosX + 260; Start->NodePosY = Choice->NodePosY - 160; C.Finalize();
    FGraphNodeCreator<UK2Node_Self> S(*Events); auto* Self = S.CreateNode();
    Self->NodePosX = Start->NodePosX - 170; Self->NodePosY = Start->NodePosY - 70; S.Finalize();
    Self->FindPinChecked(UEdGraphSchema_K2::PN_Self)->MakeLinkTo(Start->FindPinChecked(TEXT("SwordActor")));
    Made->FindPinChecked(UEdGraphSchema_K2::PN_ReturnValue)->MakeLinkTo(Start->FindPinChecked(TEXT("Constraint")));
    Choice->GetThenPin()->MakeLinkTo(Start->GetExecPin());
    Start->GetThenPin()->MakeLinkTo(Correction->FindPinChecked(UEdGraphSchema_K2::PN_Execute));
    // Preserve the entire old handler. Only its entry is gated, so the false
    // mode continues to execute the user's original nodes and tuning.
    auto* TickChoice = Branch(Handle, Entry->NodePosX + 200, Entry->NodePosY - 200, TEXT("ProphecyOptimisedSkipTick"));
    auto* OldHandler = EntryThen->LinkedTo[0]; Entry->Modify(); OldHandler->GetOwningNode()->Modify();
    EntryThen->BreakLinkTo(OldHandler); EntryThen->MakeLinkTo(TickChoice->GetExecPin()); TickChoice->GetElsePin()->MakeLinkTo(OldHandler);
    SkipDuplicateSlashRestore(BP, Events);
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP);
    UE_LOG(LogTemp, Display, TEXT("Optimised sword mode installed, status=%d (not saved)."), int32(BP->Status));
}
FAutoConsoleCommand Command(TEXT("Prophecy.Sword.InstallOptimised"), TEXT("Install the optional physics-driven A_Sword lifecycle; preserves legacy graph and does not save."),
    FConsoleCommandDelegate::CreateStatic(&Install));
}
