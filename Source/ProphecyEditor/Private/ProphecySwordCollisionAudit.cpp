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
