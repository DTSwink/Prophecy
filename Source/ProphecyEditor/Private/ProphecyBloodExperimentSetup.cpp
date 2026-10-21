#include "CoreMinimal.h"
#include "HAL/IConsoleManager.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CallFunction.h"
#include "K2Node_DynamicCast.h"
#include "K2Node_Select.h"
#include "K2Node_PromotableOperator.h"
#include "K2Node_VariableGet.h"
#include "Components/SkeletalMeshComponent.h"
#include "Kismet/GameplayStatics.h"
#include "ScopedTransaction.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "Editor.h"
#include "NiagaraSystem.h"
#include "NiagaraEmitter.h"
#include "NiagaraScript.h"
#include "NiagaraScriptSource.h"
#include "NiagaraGraph.h"
#include "NiagaraNodeFunctionCall.h"
#include "NiagaraDataInterfaceCollisionQuery.h"

namespace
{
void SetWoundSynchronousCollision(UNiagaraSystem* System)
{
    auto* Query=LoadObject<UNiagaraScript>(nullptr,TEXT("/Game/Prophecy/BloodTexturePainting/Modules/WoundQuerySync"));
    auto* Collision=LoadObject<UNiagaraScript>(nullptr,TEXT("/Game/Prophecy/BloodTexturePainting/Modules/WoundCollisionSync"));
    if(!System || !Query || !Collision)return;
    TArray<FNiagaraFunctionSignature> Signatures;
    GetDefault<UNiagaraDataInterfaceCollisionQuery>()->GetFunctionSignatures(Signatures);
    const auto* Sync=Signatures.FindByPredicate([](const auto& S){return S.Name==TEXT("PerformCollisionQuerySyncCPU");});
    if(!Sync)return;
    for(auto* Script:{Query,Collision})
    {
        Script->Modify();
        for(const auto& Version:Script->GetAllAvailableVersions())
        {
            auto* Source=Cast<UNiagaraScriptSource>(Script->GetSource(Version.VersionGuid));
            if(!Source || !Source->NodeGraph)continue;
            Source->Modify();Source->NodeGraph->Modify();
            for(UEdGraphNode* N:Source->NodeGraph->Nodes)if(auto* Call=Cast<UNiagaraNodeFunctionCall>(N))
            {
                if(Script==Query && Call->Signature.Name==TEXT("PerformCollisionQueryAsyncCPU"))
                {
                    Call->Modify();
                    for(auto* Pin:Call->Pins)if(Pin->PinName==TEXT("PreviousFrameQueryID") || Pin->PinName==TEXT("NextFrameQueryID"))Pin->BreakAllPinLinks();
                    Call->Signature=*Sync;
                    Call->RefreshFromExternalChanges();
                }
                if(Script==Collision && Call->FunctionScript && Call->FunctionScript->GetName()==TEXT("CollisionQueryAndResponse"))
                {Call->Modify();Call->FunctionScript=Query;}
            }
            Script->GetSource(Version.VersionGuid)->MarkNotSynchronized(TEXT("Wound synchronous collision"));
            Source->NodeGraph->NotifyGraphChanged();
        }
        Script->MarkPackageDirty();
    }
    for(const auto& H:System->GetEmitterHandles())if(H.GetName()==TEXT("Fountain001"))
    {
        auto* Data=H.GetEmitterData();
        auto* Source=Data?Cast<UNiagaraScriptSource>(Data->GraphSource):nullptr;
        if(!Source || !Source->NodeGraph)continue;
        System->Modify();Source->Modify();Source->NodeGraph->Modify();
        for(UEdGraphNode* N:Source->NodeGraph->Nodes)if(auto* Call=Cast<UNiagaraNodeFunctionCall>(N))
            if(Call->FunctionScript && Call->FunctionScript->GetPathName()==TEXT("/Niagara/Modules/Collision/Collision.Collision"))
            {Call->Modify();Call->FunctionScript=Collision;}
        Data->GraphSource->MarkNotSynchronized(TEXT("Wound synchronous collision"));
        Source->NodeGraph->NotifyGraphChanged();
    }
    System->RequestCompile(false);System->MarkPackageDirty();
    UE_LOG(LogTemp,Display,TEXT("Wound first emitter synchronous collision installed."));
}
void SetWoundRayLookahead()
{
    if(GEditor && GEditor->PlayWorld)return;
    auto* System=LoadObject<UNiagaraSystem>(nullptr,TEXT("/Game/_mygame/blood2/NS_bloodwound"));
    if(!System)return;
    // Already installed: preserve later user edits to module inputs and copies.
    for(const auto& H:System->GetEmitterHandles())if(H.GetName()==TEXT("Fountain001"))
        if(auto* Data=H.GetEmitterData())if(auto* Source=Cast<UNiagaraScriptSource>(Data->GraphSource))
            if(Source->NodeGraph)for(UEdGraphNode* N:Source->NodeGraph->Nodes)
                if(auto* Call=Cast<UNiagaraNodeFunctionCall>(N))
                    if(Call->FunctionScript && Call->FunctionScript->GetPathName()==TEXT("/Game/Prophecy/BloodTexturePainting/Modules/WoundCollisionSync.WoundCollisionSync"))return;
    SetWoundSynchronousCollision(System);
    TArray<UNiagaraScript*> Scripts;
    for(const auto& H:System->GetEmitterHandles())if(auto* D=H.GetEmitterData())D->GetScripts(Scripts,false,false);
    Scripts.Add(System->GetSystemSpawnScript());Scripts.Add(System->GetSystemUpdateScript());
    const FNiagaraVariable Parameter(FNiagaraTypeDefinition::GetFloatDef(),TEXT("Constants.Fountain001.Collision.CPU Trace Vector Length Multiplier"));
    const FScopedTransaction Tx(NSLOCTEXT("Prophecy","WoundRayLookahead","Limit wound ray collision lookahead to one step"));
    int32 Changed=0;
    for(auto* Script:Scripts)if(Script && Script->RapidIterationParameters.IndexOf(Parameter)!=INDEX_NONE)
    {
        const float Old=Script->RapidIterationParameters.GetParameterValue<float>(Parameter);
        if(Old==1.f)continue;
        System->Modify();Script->Modify();
        Script->RapidIterationParameters.SetParameterValue<float>(1.f,Parameter);
        ++Changed;
    }
    if(Changed){System->RequestCompile(false);System->MarkPackageDirty();}
    UE_LOG(LogTemp,Display,TEXT("Wound ray first-emitter lookahead: updated %d parameter stores to 1."),Changed);
}
void WireWoundProjectionTolerance(UBlueprint* BP)
{
    if (!BP || (GEditor && GEditor->PlayWorld)) return;
    UEdGraph* Graph=nullptr;
    for (UEdGraph* G:BP->FunctionGraphs) if (G && G->GetFName()==TEXT("NewFunction")) Graph=G;
    if (!Graph) return;
    auto Find=[Graph](const TCHAR* Name)->UEdGraphNode*
    { for(UEdGraphNode* N:Graph->Nodes) if(N && N->GetName()==Name)return N; return nullptr; };
    if (auto* Old=Find(TEXT("ProphecyWoundRetraceDistance")))
    {
        BP->Modify();Graph->Modify();
        FBlueprintEditorUtils::RemoveNode(BP,Old,true);
    }
    if(auto* Scale=Cast<UK2Node_PromotableOperator>(Find(TEXT("K2Node_PromotableOperator_2"))))
        if(auto* Factor=Scale->FindPin(TEXT("B"));Factor && Factor->LinkedTo.IsEmpty() &&
           Factor->PinType.PinCategory==UEdGraphSchema_K2::PC_Struct && Factor->DefaultValue==TEXT("1.000000"))
        {
            BP->Modify();Scale->Modify();
            FEdGraphPinType Scalar;Scalar.PinCategory=UEdGraphSchema_K2::PC_Real;Scalar.PinSubCategory=UEdGraphSchema_K2::PC_Double;
            Scale->ConvertPinType(Factor,Scalar);
            Factor=Scale->FindPin(TEXT("B"));Factor->DefaultValue=TEXT("1.000000");
            FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
            FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
        }
}
// Idempotent, additive setup. Preserve the user's current execution paths.
void WireBloodExperiment()
{
    SetWoundRayLookahead();
    UBlueprint* BP = LoadObject<UBlueprint>(nullptr,
        TEXT("/Game/_mygame/blood2/A_DecalManager"));
    if (!BP) return;
    WireWoundProjectionTolerance(BP);
    UEdGraph* Graph = nullptr;
    for (UEdGraph* G : BP->FunctionGraphs)
        if (G && G->GetFName() == TEXT("NewFunction")) Graph = G;
    if (!Graph) return;
    auto Node = [Graph](const TCHAR* Name) -> UEdGraphNode*
    {
        for (UEdGraphNode* N : Graph->Nodes)
            if (N && N->GetName() == Name) return N;
        return nullptr;
    };
    // Ordinary receivers (including skeletal meshes) use this path. The
    // separate floor and instanced-mesh paths retain their existing radii.
    UK2Node_CallFunction* PaintNode = Cast<UK2Node_CallFunction>(Node(TEXT("K2Node_CallFunction_6")));
    if (!PaintNode || PaintNode->FunctionReference.GetMemberName() != TEXT("TryPaintFromHit"))
    {
        UE_LOG(LogTemp, Error, TEXT("Blood experiment: unexpected graph; left unchanged."));
        return;
    }
    const FName RadiusName(TEXT("Skeletal Brush Radius"));
    if (Node(TEXT("ProphecySkeletalBrushSelect")))
    {
        UE_LOG(LogTemp, Display, TEXT("Blood skeletal brush control already installed; unchanged."));
        return;
    }
    auto* Radius = PaintNode->FindPin(TEXT("BrushRadiusWorld"));
    auto* Hit = PaintNode->FindPin(TEXT("Hit"));
    if (!Radius || Radius->LinkedTo.Num() != 1 || !Hit || Hit->LinkedTo.Num() != 1 ||
        FBlueprintEditorUtils::FindNewVariableIndex(BP, RadiusName) != INDEX_NONE) return;
    UEdGraphPin* PreviousRadius = Radius->LinkedTo[0];
    UEdGraphPin* HitSource = Hit->LinkedTo[0];
    const FScopedTransaction Transaction(NSLOCTEXT("Prophecy", "SkeletalBrush", "Add separate skeletal blood brush radius"));
    BP->Modify(); Graph->Modify(); PaintNode->Modify(); PreviousRadius->GetOwningNode()->Modify();
    if (!FBlueprintEditorUtils::AddMemberVariable(BP, RadiusName, Radius->PinType, TEXT("3.0"))) return;
    FBlueprintEditorUtils::SetBlueprintOnlyEditableFlag(BP, RadiusName, false);
    FBlueprintEditorUtils::SetBlueprintVariableCategory(BP, RadiusName, nullptr, FText::FromString(TEXT("Blood Paint")), true);

    FGraphNodeCreator<UK2Node_CallFunction> BreakCreator(*Graph);
    auto* Break = BreakCreator.CreateNode();
    Break->SetFromFunction(UGameplayStatics::StaticClass()->FindFunctionByName(TEXT("BreakHitResult")));
    Break->NodePosX=PaintNode->NodePosX-1000; Break->NodePosY=PaintNode->NodePosY+900;
    BreakCreator.Finalize();
    FGraphNodeCreator<UK2Node_DynamicCast> CastCreator(*Graph);
    auto* Cast = CastCreator.CreateNode();
    Cast->TargetType = USkeletalMeshComponent::StaticClass();
    Cast->NodePosX=PaintNode->NodePosX-700; Cast->NodePosY=PaintNode->NodePosY+900;
    CastCreator.Finalize(); Cast->SetPurity(true);
    FGraphNodeCreator<UK2Node_VariableGet> GetCreator(*Graph);
    auto* Get = GetCreator.CreateNode(); Get->VariableReference.SetSelfMember(RadiusName);
    Get->NodePosX=PaintNode->NodePosX-700; Get->NodePosY=PaintNode->NodePosY+1150;
    GetCreator.Finalize();
    FGraphNodeCreator<UK2Node_Select> SelectCreator(*Graph);
    auto* Select = SelectCreator.CreateNode();
    Select->Rename(TEXT("ProphecySkeletalBrushSelect"), Graph);
    Select->NodePosX=PaintNode->NodePosX-350; Select->NodePosY=PaintNode->NodePosY+1050;
    SelectCreator.Finalize();
    FEdGraphPinType Bool; Bool.PinCategory=UEdGraphSchema_K2::PC_Boolean;
    Select->GetIndexPin()->PinType=Bool; Select->ChangePinType(Select->GetIndexPin());
    Select->GetReturnValuePin()->PinType=Radius->PinType; Select->ChangePinType(Select->GetReturnValuePin());
    TArray<UEdGraphPin*> Options; Select->GetOptionPins(Options);
    Select->NodeComment=TEXT("Skeletal meshes use Skeletal Brush Radius (cm); all other receivers retain Brush Radius.");
    Select->bCommentBubbleVisible=true;
    const UEdGraphSchema_K2* Schema = GetDefault<UEdGraphSchema_K2>();
    auto Link=[Schema](UEdGraphPin* A, UEdGraphPin* B) { return A && B && Schema->TryCreateConnection(A,B); };
    bool bOK = Options.Num()==2 &&
        Link(HitSource, Break->FindPin(TEXT("Hit"))) &&
        Link(Break->FindPin(TEXT("HitComponent")), Cast->GetCastSourcePin()) &&
        Link(Cast->GetBoolSuccessPin(), Select->GetIndexPin()) &&
        Link(PreviousRadius, Options[0]) &&
        Link(Get->FindPin(RadiusName), Options[1]);
    if (bOK)
    {
        Radius->BreakAllPinLinks();
        bOK = Link(Select->GetReturnValuePin(), Radius);
    }
    if (!bOK)
    {
        for (UEdGraphNode* Added : TArray<UEdGraphNode*>{Break,Cast,Get,Select})
            FBlueprintEditorUtils::RemoveNode(BP,Added,true);
        FBlueprintEditorUtils::RemoveMemberVariable(BP,RadiusName);
        Link(PreviousRadius,Radius);
    }
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);
    FKismetEditorUtilities::CompileBlueprint(BP);
    UE_LOG(LogTemp, Display, TEXT("Blood skeletal brush wiring: %s, Blueprint status=%d"),
        bOK ? TEXT("connected") : TEXT("FAILED"), int32(BP->Status));
}
FAutoConsoleCommand BloodExperimentCommand(
    TEXT("Prophecy.Blood.WireExperiment"),
    TEXT("Wire floor and ordinary mesh staining on the shared A_DecalManager Blueprint."),
    FConsoleCommandDelegate::CreateStatic(&WireBloodExperiment));
}
