#include "CoreMinimal.h"
#include "Editor.h"
#include "Engine/Blueprint.h"
#include "Engine/BlueprintGeneratedClass.h"
#include "Engine/SimpleConstructionScript.h"
#include "Engine/SCS_Node.h"
#include "Engine/StaticMesh.h"
#include "Components/StaticMeshComponent.h"
#include "PhysicsEngine/PhysicsConstraintComponent.h"
#include "GameFramework/Actor.h"
#include "Kismet2/KismetEditorUtilities.h"
#include "HAL/IConsoleManager.h"

namespace
{
void MakeConstraintBlueprintFixture()
{
    if (!GEditor || GEditor->PlayWorld) return;
    if (FindObject<UBlueprint>(GetTransientPackage(), TEXT("CodexConstraintFixture"))) return;
    auto* BP = FKismetEditorUtilities::CreateBlueprint(AActor::StaticClass(), GetTransientPackage(), TEXT("CodexConstraintFixture"),
        BPTYPE_Normal, UBlueprint::StaticClass(), UBlueprintGeneratedClass::StaticClass());
    if (!BP) return;
    BP->SetFlags(RF_Transient); BP->AddToRoot(); // Explicit temporary test fixture, never saved/cooked.
    USimpleConstructionScript* SCS = BP->SimpleConstructionScript;
    auto* Anchor = SCS->CreateNode(UStaticMeshComponent::StaticClass(), TEXT("Anchor"));
    auto* Dynamic = SCS->CreateNode(UStaticMeshComponent::StaticClass(), TEXT("Dynamic"));
    auto* Joint = SCS->CreateNode(UPhysicsConstraintComponent::StaticClass(), TEXT("Joint"));
    SCS->AddNode(Anchor); Anchor->AddChildNode(Dynamic); Anchor->AddChildNode(Joint);
    auto* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    for (auto* Node : {Anchor,Dynamic})
    {
        auto* Mesh = CastChecked<UStaticMeshComponent>(Node->ComponentTemplate);
        Mesh->SetStaticMesh(Cube); Mesh->SetMobility(EComponentMobility::Movable);
        Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        Mesh->SetCollisionResponseToAllChannels(ECR_Block); Mesh->SetEnableGravity(false);
        Mesh->BodyInstance.bSimulatePhysics = Node == Dynamic;
        Mesh->BodyInstance.bOverrideMass = true; Mesh->BodyInstance.SetMassOverride(2.f);
    }
    CastChecked<USceneComponent>(Dynamic->ComponentTemplate)->SetRelativeLocation(FVector(150,0,0));
    auto* C = CastChecked<UPhysicsConstraintComponent>(Joint->ComponentTemplate);
    C->SetRelativeLocation(FVector(75,0,0));
    C->ComponentName1.ComponentName = Dynamic->GetVariableName();
    C->ComponentName2.ComponentName = Anchor->GetVariableName();
    C->SetDisableCollision(true);
    C->SetLinearXLimit(LCM_Locked,0); C->SetLinearYLimit(LCM_Locked,0); C->SetLinearZLimit(LCM_Locked,0);
    C->SetAngularTwistLimit(ACM_Locked,0); C->SetAngularSwing1Limit(ACM_Locked,0); C->SetAngularSwing2Limit(ACM_Locked,0);
    FKismetEditorUtilities::CompileBlueprint(BP,EBlueprintCompileOptions::SkipGarbageCollection);
    UE_LOG(LogTemp,Display,TEXT("ConstraintBlueprintFixture: status=%d class=%s"),int32(BP->Status),*GetPathNameSafe(BP->GeneratedClass));
}
FAutoConsoleCommand FixtureCommand(TEXT("Prophecy.Debug.MakeConstraintBlueprintFixture"),
    TEXT("Build an unsaved temporary Actor Blueprint with two ordinary mesh components and a placed constraint."),
    FConsoleCommandDelegate::CreateStatic(&MakeConstraintBlueprintFixture));
}
