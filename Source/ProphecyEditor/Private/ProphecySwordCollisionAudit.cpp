#include "CoreMinimal.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "K2Node_CallFunction.h"
#include "EdGraphSchema_K2.h"
#include "Components/PrimitiveComponent.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "K2Node_GetArrayItem.h"
#include "ScopedTransaction.h"
#include "Editor.h"

namespace ProphecySwordCollisionAudit
{
void Dump()
{
    FString Text;
    for (const TCHAR* Path : {TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"),
        TEXT("/Game/_mygame/sword/A_Sword.A_Sword")})
    {
        auto* BP = LoadObject<UBlueprint>(nullptr,Path);
        if (!BP) continue;
        TArray<UEdGraph*> Graphs;
        BP->GetAllGraphs(Graphs);
        for (UEdGraph* Graph : Graphs) for (UEdGraphNode* Node : Graph->Nodes)
        {
            if (!Node) continue;
            Text += FString::Printf(TEXT("\n%s | %s | %s | %s\n"),Path,*Graph->GetName(),*Node->GetName(),*Node->GetNodeTitle(ENodeTitleType::ListView).ToString());
            for (auto* Pin : Node->Pins)
            {
                if (!Pin) continue;
                Text += FString::Printf(TEXT("  %s=%s %s ->"),*Pin->PinName.ToString(),*Pin->DefaultValue,*GetPathNameSafe(Pin->DefaultObject));
                for (auto* Link : Pin->LinkedTo) if (Link) Text += FString::Printf(TEXT(" %s.%s"),*Link->GetOwningNode()->GetName(),*Link->PinName.ToString());
                Text += TEXT("\n");
            }
        }
    }
    FFileHelper::SaveStringToFile(Text,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/SwordThigh/BlueprintGraph.txt")));
}
FAutoConsoleCommand Cmd(TEXT("Prophecy.Sword.AuditCollisionGraph"),TEXT("Read-only current sword/agent graph audit."),FConsoleCommandDelegate::CreateStatic(&Dump));
// One-shot migration of the user's audited cube follower. Ordinary BP arithmetic
// remains visible/editable; no native runtime component, polling or graph hook.
void FixMagicCubeTime()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP) return;
    UEdGraph* Graph=nullptr;
    for (UEdGraph* G:BP->FunctionGraphs) if (G->GetName()==TEXT("handle magic cube")) Graph=G;
    if (!Graph) return;
    const FString Marker=TEXT("Magic cube uses the continuous window's world-time horizon.");
    for (UEdGraphNode* N:Graph->Nodes) if (N && N->NodeComment==Marker) return;
    auto Pin=[&](const TCHAR* Node,const TCHAR* Name)->UEdGraphPin*
    {
        for (UEdGraphNode* N:Graph->Nodes) if (N && N->GetFName()==Node) return N->FindPin(Name);
        return nullptr;
    };
    auto* Times=Pin(TEXT("K2Node_CallFunction_131"),TEXT("TimeOffsetsSeconds"));
    auto* Half=Pin(TEXT("K2Node_PromotableOperator_0"),TEXT("B"));
    auto* DriveDt=Pin(TEXT("K2Node_PromotableOperator_4"),TEXT("B"));
    auto* FeedbackDt=Pin(TEXT("K2Node_PromotableOperator_5"),TEXT("B"));
    auto FindFunction=[](const TCHAR* Class,const TCHAR* Name)->UFunction*
    { auto* C=FindObject<UClass>(nullptr,Class);return C?C->FindFunctionByName(Name):nullptr; };
    auto* GetRate=FindFunction(TEXT("/Script/GameAnimationSample3.ProphecyAgentTimeLibrary"),TEXT("GetAgentTimeDilation"));
    auto* GetDt=FindFunction(TEXT("/Script/Engine.GameplayStatics"),TEXT("GetWorldDeltaSeconds"));
    auto* Multiply=FindFunction(TEXT("/Script/Engine.KismetMathLibrary"),TEXT("Multiply_DoubleDouble"));
    if (!Times || !Half || !DriveDt || !FeedbackDt || !GetRate || !GetDt || !Multiply ||
        Half->LinkedTo.Num() || DriveDt->LinkedTo.Num() || FeedbackDt->LinkedTo.Num())
    { UE_LOG(LogTemp,Error,TEXT("Magic cube timing: graph differs from audited version; no edits."));return; }
    bool OK=true;
    {
        FScopedTransaction Transaction(NSLOCTEXT("Prophecy","MagicCubeTime","Correct magic cube time units"));
        BP->Modify();Graph->Modify();
        for (UEdGraphNode* N:Graph->Nodes) if (N) N->Modify();
        const auto* Schema=GetDefault<UEdGraphSchema_K2>();
        auto Link=[&](UEdGraphPin* A,UEdGraphPin* B) { OK=Schema->TryCreateConnection(A,B) && OK; };
        auto Call=[&](UFunction* F,int32 X,int32 Y)
        {
            FGraphNodeCreator<UK2Node_CallFunction> C(*Graph);auto* N=C.CreateNode();N->SetFromFunction(F);
            N->NodePosX=X;N->NodePosY=Y;C.Finalize();return N;
        };
        FGraphNodeCreator<UK2Node_GetArrayItem> C(*Graph);auto* Item=C.CreateNode();
        Item->NodePosX=DriveDt->GetOwningNode()->NodePosX-350;Item->NodePosY=DriveDt->GetOwningNode()->NodePosY+160;C.Finalize();
        Item->NodeComment=Marker;Item->bCommentBubbleVisible=true;
        Link(Times,Item->GetTargetArrayPin());Schema->TrySetDefaultValue(*Item->GetIndexPin(),TEXT("1"));
        Schema->TrySetDefaultValue(*Half,TEXT("1.0"));Link(Item->GetResultPin(),DriveDt);
        const int32 X=FeedbackDt->GetOwningNode()->NodePosX-650,Y=FeedbackDt->GetOwningNode()->NodePosY+250;
        auto* Rate=Call(GetRate,X,Y);auto* Dt=Call(GetDt,X,Y+140);auto* Product=Call(Multiply,X+300,Y+70);
        Product->NodeComment=TEXT("Convert world-time cube feedback to agent-local magic velocity: divide by world Delta Seconds * Agent Time Dilation.");
        Product->bCommentBubbleVisible=true;
        Link(Rate->FindPinChecked(TEXT("ReturnValue")),Product->FindPinChecked(TEXT("A")));
        Link(Dt->FindPinChecked(TEXT("ReturnValue")),Product->FindPinChecked(TEXT("B")));
        Link(Product->FindPinChecked(TEXT("ReturnValue")),FeedbackDt);
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
        FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
        OK=OK && BP->Status!=BS_Error;
    }
    if (!OK) { GEditor->UndoTransaction();UE_LOG(LogTemp,Error,TEXT("Magic cube timing migration failed; transaction undone."));return; }
    UE_LOG(LogTemp,Display,TEXT("Magic cube timing corrected and Blueprint compiled; left unsaved."));
    Dump();
}
FAutoConsoleCommand MagicTimeCommand(TEXT("Prophecy.Editor.FixMagicCubeTime"),TEXT("Correct audited magic cube world/local time arithmetic, compile and leave unsaved."),FConsoleCommandDelegate::CreateStatic(&FixMagicCubeTime));
void OrderMagicCubeTime()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP) return;
    for (UEdGraph* G:BP->FunctionGraphs) if (G->GetName()==TEXT("tick debugging"))
    for (UEdGraphNode* N:G->Nodes) if (N && N->GetFName()==TEXT("K2Node_ExecutionSequence_2"))
    {
        auto* First=N->FindPin(TEXT("then_0"));auto* Last=N->FindPin(TEXT("then_2"));
        if (!First || !Last || First->LinkedTo.Num()!=1 || Last->LinkedTo.Num() ||
            First->LinkedTo[0]->GetOwningNode()->GetFName()!=TEXT("K2Node_IfThenElse_15")) return;
        auto* CubeBranch=First->LinkedTo[0];
        FScopedTransaction Tx(NSLOCTEXT("Prophecy","MagicCubeOrder","Update magic cube after tick settings"));
        BP->Modify();G->Modify();N->Modify();CubeBranch->GetOwningNode()->Modify();
        First->BreakLinkTo(CubeBranch);Last->MakeLinkTo(CubeBranch);
        FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
        FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
        UE_LOG(LogTemp,Display,TEXT("Magic cube now runs after tick settings; Blueprint status %d, left unsaved."),int32(BP->Status));
        Dump();return;
    }
}
FAutoConsoleCommand MagicOrderCommand(TEXT("Prophecy.Editor.OrderMagicCubeTime"),TEXT("Move the audited cube branch after tick settings; leave other branches and ordering intact."),FConsoleCommandDelegate::CreateStatic(&OrderMagicCubeTime));
void Repair()
{
    auto* BP = LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent.BP_ProphecyManualPoseAgent"));
    if (!BP) return;
    TArray<UEdGraph*> Graphs; BP->GetAllGraphs(Graphs);
    for (UEdGraph* Graph : Graphs) if (Graph->GetName()==TEXT("tick debugging"))
    {
        for (UEdGraphNode* Node : Graph->Nodes)
        {
            if (Node && Node->NodeComment==TEXT("Attached sword: block PhysicsBody; owner attack filtering is handled natively.")) return;
        }
        for (UEdGraphNode* Node : Graph->Nodes)
        {
            auto* Call=Cast<UK2Node_CallFunction>(Node);
            if (!Call || Call->GetFName()!=TEXT("K2Node_CallFunction_110")
                || Call->FunctionReference.GetMemberName()!=TEXT("SetCollisionResponseToAllChannels")) continue;
            auto* Response=Call->FindPin(TEXT("NewResponse"));
            auto* Then=Call->FindPin(UEdGraphSchema_K2::PN_Then);
            auto* Target=Call->FindPin(UEdGraphSchema_K2::PN_Self);
            if (!Response || Response->DefaultValue!=TEXT("ECR_Ignore") || !Then || !Then->LinkedTo.IsEmpty()
                || !Target || Target->LinkedTo.Num()!=1) return;
            BP->Modify(); Graph->Modify(); Call->Modify();
            FGraphNodeCreator<UK2Node_CallFunction> Creator(*Graph);
            auto* Added=Creator.CreateNode();
            Added->SetFromFunction(UPrimitiveComponent::StaticClass()->FindFunctionByName(TEXT("SetCollisionResponseToChannel")));
            Added->NodePosX=Call->NodePosX+360; Added->NodePosY=Call->NodePosY;
            Added->NodeComment=TEXT("Attached sword: block PhysicsBody; owner attack filtering is handled natively.");
            Creator.Finalize();
            Added->FindPinChecked(TEXT("Channel"))->DefaultValue=TEXT("ECC_PhysicsBody");
            Added->FindPinChecked(TEXT("NewResponse"))->DefaultValue=TEXT("ECR_Block");
            Then->MakeLinkTo(Added->FindPinChecked(UEdGraphSchema_K2::PN_Execute));
            Target->LinkedTo[0]->MakeLinkTo(Added->FindPinChecked(UEdGraphSchema_K2::PN_Self));
            FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
            FKismetEditorUtilities::CompileBlueprint(BP);
            UE_LOG(LogTemp,Display,TEXT("Added the single PhysicsBody Block override after the attached sword's Ignore All node; Blueprint is ready to save."));
            return;
        }
    }
}
FAutoConsoleCommand FixCmd(TEXT("Prophecy.Sword.RepairAttachedCollisionGraph"),TEXT("Add the scoped PhysicsBody Block override to the audited manual agent graph; does not save."),FConsoleCommandDelegate::CreateStatic(&Repair));
}
