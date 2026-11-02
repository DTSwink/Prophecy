#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/SCS_Node.h"
#include "Engine/StaticMesh.h"
#include "Components/StaticMeshComponent.h"
#include "EdGraph/EdGraph.h"
#include "EdGraphSchema_K2.h"
#include "K2Node_CallFunction.h"
#include "K2Node_IfThenElse.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "HAL/IConsoleManager.h"
#include "PhysicsEngine/BodySetup.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "UObject/UnrealType.h"

namespace ProphecySpearSetup
{
void Install()
{
    if (!GEditor || GEditor->PlayWorld) return;
    auto* BP=LoadObject<UBlueprint>(nullptr,TEXT("/Game/_mygame/spear/A_Spear.A_Spear"));
    auto* Mesh=LoadObject<UStaticMesh>(nullptr,TEXT("/Game/_mygame/spear/SM_ImperialSpear.SM_ImperialSpear"));
    if (!BP || !Mesh || !BP->SimpleConstructionScript) return;
    TArray<UEdGraph*> Graphs; BP->GetAllGraphs(Graphs);
    auto Find=[&](const TCHAR* GraphName,const TCHAR* NodeName)->UEdGraphNode*
    { for(auto* G:Graphs) if(G->GetName()==GraphName) for(UEdGraphNode* N:G->Nodes) if(N->GetName()==NodeName)return N;return nullptr; };
    auto* Slash=Cast<UK2Node_IfThenElse>(Find(TEXT("EventGraph"),TEXT("K2Node_IfThenElse_11")));
    auto* Width=Cast<UK2Node_CallFunction>(Find(TEXT("rrrrrrrrr"),TEXT("K2Node_CallFunction_0")));
    auto* HitMode=Cast<UK2Node_IfThenElse>(Find(TEXT("EventGraph"),TEXT("ProphecyOptimisedHitMode")));
    auto* TickMode=Cast<UK2Node_IfThenElse>(Find(TEXT("handle cuts f"),TEXT("ProphecyOptimisedSkipTick")));
    if(!Slash||!Width||!HitMode||!TickMode||Mesh->GetBoundingBox().GetSize().Z<200)return;
    if(Slash->GetThenPin()->LinkedTo.Num()>1 || (Slash->GetThenPin()->LinkedTo.Num()==1
        && Slash->GetThenPin()->LinkedTo[0]->GetOwningNode()->GetName()!=TEXT("K2Node_VariableSet_1")))return;
    BP->Modify();
    Slash->Modify();Slash->GetThenPin()->BreakAllPinLinks();
    Slash->NodeComment=TEXT("Spear: side impacts retain normal collision; only the existing tip pike path may create a cut.");
    Slash->bCommentBubbleVisible=true;
    // Imported spear breadth is local X; A_Sword's original mesh breadth was Y.
    Width->Modify();Width->SetFromFunction(USceneComponent::StaticClass()->FindFunctionByName(TEXT("GetForwardVector")));
    Width->ReconstructNode();
    if(auto* Stain=Find(TEXT("Stain Blade"),TEXT("K2Node_CallFunction_1")))
    {Stain->Modify();Stain->FindPinChecked(TEXT("SourceMaterial"))->DefaultObject=LoadObject<UObject>(nullptr,TEXT("/Game/_mygame/spear/M_ImperialSpear.M_ImperialSpear"));}
    // The blood edge's lateral scale follows this mesh's X breadth as well.
    if(auto* Break=Find(TEXT("Stain Blade"),TEXT("K2Node_CallFunction_9")))
        if(auto* Divide=Find(TEXT("Stain Blade"),TEXT("K2Node_CallFunction_20")))
        {Break->Modify();Divide->Modify();auto* A=Divide->FindPinChecked(TEXT("A"));A->BreakAllPinLinks();Break->FindPinChecked(TEXT("X"))->MakeLinkTo(A);}
    for(auto* Mode:{HitMode,TickMode})
    { Mode->Modify();Mode->GetConditionPin()->BreakAllPinLinks();Mode->GetConditionPin()->DefaultValue=TEXT("true"); }
    FEdGraphPinType Real;Real.PinCategory=UEdGraphSchema_K2::PC_Real;Real.PinSubCategory=UEdGraphSchema_K2::PC_Double;
    if(FBlueprintEditorUtils::FindNewVariableIndex(BP,TEXT("Pike Target Thickness Cm"))==INDEX_NONE)
        FBlueprintEditorUtils::AddMemberVariable(BP,TEXT("Pike Target Thickness Cm"),Real,TEXT("15"));
    FBlueprintEditorUtils::SetBlueprintVariableCategory(BP,TEXT("Pike Target Thickness Cm"),nullptr,FText::FromString(TEXT("Spear|Pike")));
    FBlueprintEditorUtils::SetBlueprintVariableMetaData(BP,TEXT("Pike Target Thickness Cm"),nullptr,TEXT("Tooltip"),
        TEXT("Target axial thickness in centimetres. The whole spear, including pommel, must clear its far face before forward release. Cached on cut admission."));
    FBlueprintEditorUtils::MarkBlueprintAsStructurallyModified(BP);FKismetEditorUtilities::CompileBlueprint(BP);
    if(BP->Status==BS_Error)return;
    auto* CDO=Cast<AActor>(BP->GeneratedClass->GetDefaultObject());
    CDO->Tags.AddUnique(TEXT("Prophecy.Spear.PassThrough"));
    const FVector Scale(.8623427588789339,.8834927125312151,.7619161867885869);
    auto Set=[&](const TCHAR* Name,double Value)
    { if(auto* P=FindFProperty<FNumericProperty>(CDO->GetClass(),Name)){void* V=P->ContainerPtrToValuePtr<void>(CDO);if(P->IsInteger())P->SetIntPropertyValue(V,int64(Value));else P->SetFloatingPointPropertyValue(V,Value);} };
    // Dimensions measured from the user's final blade, before its FBX grip pivot offset.
    const double Blade=46.96560204029083*Scale.Z;
    Set(TEXT("blade length"),Blade);Set(TEXT("hilt half length"),Mesh->GetBoundingBox().Max.Z*Scale.Z-Blade);
    Set(TEXT("blade half width"),5.434734746813774*Scale.X);
    Set(TEXT("freeze tick"),-1);Set(TEXT("unfreeze tick"),0);
    for(auto Pair:{TPair<const TCHAR*,bool>(TEXT("Optimised"),true),{TEXT("debug mode"),false},{TEXT("enable gravity"),true}})
        if(auto* P=FindFProperty<FBoolProperty>(CDO->GetClass(),Pair.Key))P->SetPropertyValue_InContainer(CDO,Pair.Value);
    for(auto* Node:BP->SimpleConstructionScript->GetAllNodes())
        if(Node->GetVariableName()==TEXT("sword"))
            if(auto* Component=Cast<UStaticMeshComponent>(Node->ComponentTemplate))
            {Component->Modify();Component->SetStaticMesh(Mesh);Component->SetRelativeScale3D(Scale);Component->SetMassOverrideInKg(NAME_None,1.2f,true);
                Component->SetUseMACD(false);Component->SetUseCCD(true);}
    BP->MarkPackageDirty();
    FString Audit=FString::Printf(TEXT("status=%d\nbladeCm=%.9f\nrootCm=%.9f\nrearCm=%.9f\nlengthCm=%.9f\nhulls=%d\ntriangles=%d\n"),int32(BP->Status),Blade,
        Mesh->GetBoundingBox().Max.Z*Scale.Z-Blade,Mesh->GetBoundingBox().Min.Z*Scale.Z,Mesh->GetBoundingBox().GetSize().Z*Scale.Z,
        Mesh->GetBodySetup()?Mesh->GetBodySetup()->AggGeom.ConvexElems.Num():-1,Mesh->GetNumTriangles(0));
    for(auto* G:Graphs)for(UEdGraphNode* N:G->Nodes)
    {Audit+=G->GetName()+TEXT(" | ")+N->GetName()+TEXT(" | ")+N->GetNodeTitle(ENodeTitleType::FullTitle).ToString()+TEXT("\n");
        for(auto* P:N->Pins){Audit+=TEXT("  ")+P->PinName.ToString()+TEXT("=")+P->DefaultValue+TEXT(" ->");for(auto* L:P->LinkedTo)Audit+=TEXT(" ")+L->GetOwningNode()->GetName()+TEXT(".")+L->PinName.ToString();Audit+=TEXT("\n");}}
    FFileHelper::SaveStringToFile(Audit,*(FPaths::ProjectSavedDir()/TEXT("Diagnostics/SpearPike20261030/SpearSetup.txt")),FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    UE_LOG(LogTemp,Display,TEXT("A_Spear pike-only setup compiled; only the new spear asset changed, not saved."));
}
FAutoConsoleCommand Command(TEXT("Prophecy.Spear.Install"),TEXT("Configure only the duplicated A_Spear; no saves or original sword edits."),FConsoleCommandDelegate::CreateStatic(&Install));
}
