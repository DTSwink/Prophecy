#include "ProphecyJoltStandardPhysicsLibrary.h"
#include "ProphecyJoltConstraintRuntime.h"
#include "PhysicsEngine/PhysicsConstraintComponent.h"
#include "ProphecyJoltMeshPhysics.h"
#include "ProphecyJoltBodyComponent.h"
#include "ProphecyJoltSceneCollisionComponent.h"
#include "ProphecyJoltStaticMeshLibrary.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"

using namespace ProphecyJolt::MeshPhysics;

void UProphecyJoltStandardPhysicsLibrary::GetConstraintForce(UPhysicsConstraintComponent* Component,
    FVector& OutLinearForce, FVector& OutAngularForce)
{
    if (!ProphecyJolt::Constraints::ReadReaction(Component, OutLinearForce, OutAngularForce) && IsValid(Component))
        Component->GetConstraintForce(OutLinearForce, OutAngularForce);
}
float UProphecyJoltStandardPhysicsLibrary::GetCurrentTwist(UPhysicsConstraintComponent* Component)
{
    FQuat Q;
    return ProphecyJolt::Constraints::ReadRotation(Component,Q) ? FMath::RadiansToDegrees(Q.GetTwistAngle(FVector::ForwardVector))
        : (IsValid(Component) ? Component->GetCurrentTwist() : 0.f);
}
float UProphecyJoltStandardPhysicsLibrary::GetCurrentSwing1(UPhysicsConstraintComponent* Component)
{
    FQuat Q;
    return ProphecyJolt::Constraints::ReadRotation(Component,Q) ? FMath::RadiansToDegrees(Q.GetTwistAngle(FVector::UpVector))
        : (IsValid(Component) ? Component->GetCurrentSwing1() : 0.f);
}
float UProphecyJoltStandardPhysicsLibrary::GetCurrentSwing2(UPhysicsConstraintComponent* Component)
{
    FQuat Q;
    return ProphecyJolt::Constraints::ReadRotation(Component,Q) ? FMath::RadiansToDegrees(Q.GetTwistAngle(FVector::RightVector))
        : (IsValid(Component) ? Component->GetCurrentSwing2() : 0.f);
}

namespace
{
UProphecyJoltBodyComponent* AdapterFor(USceneComponent* Component)
{
    if (!IsValid(Component)) return nullptr;
    TInlineComponentArray<UProphecyJoltBodyComponent*> Bodies(Component->GetOwner());
    for (auto* Body : Bodies) if (Body->GetSourceComponent() == Component) return Body;
    return nullptr;
}
bool Read(UPrimitiveComponent* Component, FName BoneName, FProphecyJoltBodyState& State)
{
    if (!IsValid(Component) || !Component->GetWorld()) return false;
    FProphecyJoltBodyHandle Handle;
    if (auto* Agent = Cast<AProphecyAgent>(Component->GetOwner()); Agent && Agent->GetPoseReferenceMesh() == Component
        && Agent->IsJoltPhysicalAnimationEnabled())
    {
        if (BoneName.IsNone())
        {
            auto* Mesh = Cast<USkeletalMeshComponent>(Component);
            auto* Asset = Mesh ? Mesh->GetPhysicsAsset() : nullptr;
            if (Asset && Asset->SkeletalBodySetups.IsValidIndex(Mesh->RootBodyData.BodyIndex))
                BoneName = Asset->SkeletalBodySetups[Mesh->RootBodyData.BodyIndex]->BoneName;
        }
        if (!Agent->GetJoltCharacterComponent()->GetBodyHandle(BoneName, Handle)) return false;
    }
    else if (auto* Adapter = AdapterFor(Component)) return Adapter->GetBodyState(State);
    else
    {
        auto* Scene = UProphecyJoltSceneCollisionComponent::FindForWorld(Component->GetWorld());
        if (!Scene || !Scene->GetBodyHandle(*Component, INDEX_NONE, Handle)) return false;
    }
    return Component->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>()->ReadBody(Handle, State).IsSuccess();
}
void Report(const FString& Error)
{ if (!Error.IsEmpty()) UE_LOG(LogTemp, Error, TEXT("Standard Jolt physics node: %s"), *Error); }
}

void UProphecyJoltStandardPhysicsLibrary::SetSimulatePhysics(UPrimitiveComponent* Component, bool bSimulate)
{
    if (!IsValid(Component)) return;
    if (auto* Adapter = AdapterFor(Component))
    {
        if (Adapter->IsJoltBody()) { FString Error; Adapter->SetSimulationEnabled(bSimulate, Error); Report(Error); return; }
        if (Adapter->IsEnablePending())
        {
            if (bSimulate) return;
            UProphecyJoltStaticMeshLibrary::DisableJoltStaticMeshPhysics(Cast<UStaticMeshComponent>(Component));
        }
    }
    Component->SetSimulatePhysics(bSimulate);
}
void UProphecyJoltStandardPhysicsLibrary::SetMassOverrideInKg(UPrimitiveComponent* Component, FName BoneName, float MassInKg, bool bOverrideMass)
{
    if (!IsValid(Component)) return;
    Component->SetMassOverrideInKg(BoneName, MassInKg, bOverrideMass);
    if (auto* Adapter = AdapterFor(Component))
    { FString Error; Adapter->SetMassKg(bOverrideMass ? MassInKg : Component->GetMass(), Error); Report(Error); }
}
FVector UProphecyJoltStandardPhysicsLibrary::GetPhysicsLinearVelocity(UPrimitiveComponent* Component, FName BoneName)
{
    FProphecyJoltBodyState State;
    return Read(Component, BoneName, State) ? State.CenterOfMassVelocityCmPerSecond
        : (IsValid(Component) ? Component->GetPhysicsLinearVelocity(BoneName) : FVector::ZeroVector);
}
FVector UProphecyJoltStandardPhysicsLibrary::GetPhysicsLinearVelocityAtPoint(UPrimitiveComponent* Component, FVector Point, FName BoneName)
{
    FProphecyJoltBodyState State;
    return Read(Component, BoneName, State) ? State.CenterOfMassVelocityCmPerSecond
        + FVector::CrossProduct(State.AngularVelocityRadiansPerSecond, Point - State.CenterOfMassPositionCm)
        : (IsValid(Component) ? Component->GetPhysicsLinearVelocityAtPoint(Point, BoneName) : FVector::ZeroVector);
}
FVector UProphecyJoltStandardPhysicsLibrary::GetPhysicsAngularVelocityInRadians(UPrimitiveComponent* Component, FName BoneName)
{
    FProphecyJoltBodyState State;
    return Read(Component, BoneName, State) ? State.AngularVelocityRadiansPerSecond
        : (IsValid(Component) ? Component->GetPhysicsAngularVelocityInRadians(BoneName) : FVector::ZeroVector);
}
FVector UProphecyJoltStandardPhysicsLibrary::GetPhysicsAngularVelocityInDegrees(UPrimitiveComponent* Component, FName BoneName)
{ return FMath::RadiansToDegrees(GetPhysicsAngularVelocityInRadians(Component, BoneName)); }
bool UProphecyJoltStandardPhysicsLibrary::IsSimulatingPhysics(USceneComponent* Component, FName BoneName)
{
    if (auto* Adapter = AdapterFor(Component); Adapter && Adapter->IsEnablePending()) return true;
    FProphecyJoltBodyState State;
    return Read(Cast<UPrimitiveComponent>(Component), BoneName, State) ? State.bDynamic : (IsValid(Component) && Component->IsSimulatingPhysics(BoneName));
}
void UProphecyJoltStandardPhysicsLibrary::AddTorqueInDegrees(UPrimitiveComponent* Component, FVector Torque, FName BoneName, bool bAccelChange)
{ AddTorqueInRadians(Component, FMath::DegreesToRadians(Torque), BoneName, bAccelChange); }
void UProphecyJoltStandardPhysicsLibrary::AddAngularImpulseInDegrees(UPrimitiveComponent* Component, FVector Impulse, FName BoneName, bool bVelChange)
{ AddAngularImpulseInRadians(Component, FMath::DegreesToRadians(Impulse), BoneName, bVelChange); }
void UProphecyJoltStandardPhysicsLibrary::SetPhysicsAngularVelocityInDegrees(UPrimitiveComponent* Component, FVector NewAngVel, bool bAddToCurrent, FName BoneName)
{ SetPhysicsAngularVelocityInRadians(Component, FMath::DegreesToRadians(NewAngVel), bAddToCurrent, BoneName); }
void UProphecyJoltStandardPhysicsLibrary::K2_SetWorldLocation(USceneComponent* Component, FVector NewLocation, bool bSweep, FHitResult& SweepHitResult, bool bTeleport)
{
    if (!IsValid(Component)) return;
    Component->K2_SetWorldLocation(NewLocation, bSweep, SweepHitResult, bTeleport);
    if (auto* Adapter = AdapterFor(Component)) Adapter->SynchronizeSourceTransform();
}
void UProphecyJoltStandardPhysicsLibrary::K2_SetWorldRotation(USceneComponent* Component, FRotator NewRotation, bool bSweep, FHitResult& SweepHitResult, bool bTeleport)
{
    if (!IsValid(Component)) return;
    Component->K2_SetWorldRotation(NewRotation, bSweep, SweepHitResult, bTeleport);
    if (auto* Adapter = AdapterFor(Component)) Adapter->SynchronizeSourceTransform();
}
void UProphecyJoltStandardPhysicsLibrary::K2_SetWorldTransform(USceneComponent* Component, const FTransform& NewTransform, bool bSweep, FHitResult& SweepHitResult, bool bTeleport)
{
    if (!IsValid(Component)) return;
    Component->K2_SetWorldTransform(NewTransform, bSweep, SweepHitResult, bTeleport);
    if (auto* Adapter = AdapterFor(Component)) Adapter->SynchronizeSourceTransform();
}

void UProphecyJoltStandardPhysicsLibrary::AddForce(UPrimitiveComponent* Component, FVector Force, FName BoneName, bool bAccelChange)
{
    if (!IsValid(Component)) return;
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Force;
    Command.Value = Force;
    Command.bMassIndependent = bAccelChange;
    FSelection Selection;
    Selection.Bone = BoneName;
    if (!Execute(*Component, Command, Selection)) Component->AddForce(Force, BoneName, bAccelChange);
}

void UProphecyJoltStandardPhysicsLibrary::AddImpulse(UPrimitiveComponent* Component, FVector Impulse, FName BoneName, bool bVelChange)
{
    if (!IsValid(Component)) return;
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Impulse;
    Command.Value = Impulse;
    Command.bMassIndependent = bVelChange;
    FSelection Selection;
    Selection.Bone = BoneName;
    if (!Execute(*Component, Command, Selection)) Component->AddImpulse(Impulse, BoneName, bVelChange);
}

void UProphecyJoltStandardPhysicsLibrary::AddTorqueInRadians(UPrimitiveComponent* Component, FVector Torque, FName BoneName, bool bAccelChange)
{
    if (!IsValid(Component)) return;
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Torque;
    Command.Value = Torque;
    Command.bMassIndependent = bAccelChange;
    FSelection Selection;
    Selection.Bone = BoneName;
    if (!Execute(*Component, Command, Selection)) Component->AddTorqueInRadians(Torque, BoneName, bAccelChange);
}

void UProphecyJoltStandardPhysicsLibrary::AddAngularImpulseInRadians(UPrimitiveComponent* Component, FVector Impulse, FName BoneName, bool bVelChange)
{
    if (!IsValid(Component)) return;
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::AngularImpulse;
    Command.Value = Impulse;
    Command.bMassIndependent = bVelChange;
    FSelection Selection;
    Selection.Bone = BoneName;
    if (!Execute(*Component, Command, Selection)) Component->AddAngularImpulseInRadians(Impulse, BoneName, bVelChange);
}

void UProphecyJoltStandardPhysicsLibrary::AddForceAtLocation(UPrimitiveComponent* Component, FVector Force, FVector Location, FName BoneName)
{
    if (!IsValid(Component)) return;
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Force;
    Command.Value = Force;
    Command.bMassIndependent = false;
    FSelection Selection;
    Selection.Bone = BoneName;
    Command.bAtPosition = true;
    Command.Position = Location;
    if (!Execute(*Component, Command, Selection)) Component->AddForceAtLocation(Force, Location, BoneName);
}

void UProphecyJoltStandardPhysicsLibrary::AddForceAtLocationLocal(UPrimitiveComponent* Component, FVector Force, FVector Location, FName BoneName)
{
    if (!IsValid(Component)) return;
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Force;
    Command.Value = Force;
    Command.bMassIndependent = false;
    FSelection Selection;
    Selection.Bone = BoneName;
    Command.bAtPosition = true;
    Command.Position = Location;
    Command.bLocalSpace = true;
    if (!Execute(*Component, Command, Selection)) Component->AddForceAtLocationLocal(Force, Location, BoneName);
}

void UProphecyJoltStandardPhysicsLibrary::AddImpulseAtLocation(UPrimitiveComponent* Component, FVector Impulse, FVector Location, FName BoneName)
{
    if (!IsValid(Component)) return;
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Impulse;
    Command.Value = Impulse;
    Command.bMassIndependent = false;
    FSelection Selection;
    Selection.Bone = BoneName;
    Command.bAtPosition = true;
    Command.Position = Location;
    if (!Execute(*Component, Command, Selection)) Component->AddImpulseAtLocation(Impulse, Location, BoneName);
}

void UProphecyJoltStandardPhysicsLibrary::AddRadialForce(UPrimitiveComponent* Component, FVector Origin, float Radius, float Strength, ERadialImpulseFalloff Falloff, bool bAccelChange)
{
    if (!IsValid(Component)) return;
    if (Component->bIgnoreRadialForce) return;
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Force;
    Command.Value = FVector::ZeroVector;
    Command.bMassIndependent = bAccelChange;
    FSelection Selection;
    Selection.Type = ESelection::Radial;
    Selection.Origin = Origin;
    Selection.Radius = Radius;
    Selection.Strength = Strength;
    Selection.Falloff = Falloff;
    if (!Execute(*Component, Command, Selection)) Component->AddRadialForce(Origin, Radius, Strength, Falloff, bAccelChange);
}

void UProphecyJoltStandardPhysicsLibrary::AddRadialImpulse(UPrimitiveComponent* Component, FVector Origin, float Radius, float Strength, ERadialImpulseFalloff Falloff, bool bVelChange)
{
    if (!IsValid(Component)) return;
    if (Component->bIgnoreRadialImpulse) return;
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Impulse;
    Command.Value = FVector::ZeroVector;
    Command.bMassIndependent = bVelChange;
    FSelection Selection;
    Selection.Type = ESelection::Radial;
    Selection.Origin = Origin;
    Selection.Radius = Radius;
    Selection.Strength = Strength;
    Selection.Falloff = Falloff;
    if (!Execute(*Component, Command, Selection)) Component->AddRadialImpulse(Origin, Radius, Strength, Falloff, bVelChange);
}

void UProphecyJoltStandardPhysicsLibrary::SetPhysicsLinearVelocity(UPrimitiveComponent* Component, FVector NewVel, bool bAddToCurrent, FName BoneName)
{
    if (!IsValid(Component)) return;
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::LinearVelocity;
    Command.Value = NewVel;
    Command.bMassIndependent = false;
    FSelection Selection;
    Selection.Bone = BoneName;
    Command.bAddToCurrent = bAddToCurrent;
    if (!Execute(*Component, Command, Selection)) Component->SetPhysicsLinearVelocity(NewVel, bAddToCurrent, BoneName);
}

void UProphecyJoltStandardPhysicsLibrary::SetPhysicsAngularVelocityInRadians(UPrimitiveComponent* Component, FVector NewAngVel, bool bAddToCurrent, FName BoneName)
{
    if (!IsValid(Component)) return;
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::AngularVelocity;
    Command.Value = NewAngVel;
    Command.bMassIndependent = false;
    FSelection Selection;
    Selection.Bone = BoneName;
    Command.bAddToCurrent = bAddToCurrent;
    if (!Execute(*Component, Command, Selection)) Component->SetPhysicsAngularVelocityInRadians(NewAngVel, bAddToCurrent, BoneName);
}

void UProphecyJoltStandardPhysicsLibrary::SetAllPhysicsLinearVelocity(UPrimitiveComponent* Component, FVector NewVel, bool bAddToCurrent)
{
    if (!IsValid(Component)) return;
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::LinearVelocity;
    Command.Value = NewVel;
    Command.bMassIndependent = false;
    FSelection Selection;
    Command.bAddToCurrent = bAddToCurrent;
    Selection.Type = ESelection::All;
    if (!Execute(*Component, Command, Selection)) Component->SetAllPhysicsLinearVelocity(NewVel, bAddToCurrent);
}

void UProphecyJoltStandardPhysicsLibrary::SetAllPhysicsAngularVelocityInRadians(UPrimitiveComponent* Component, const FVector& NewAngVel, bool bAddToCurrent)
{
    if (!IsValid(Component)) return;
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::AngularVelocity;
    Command.Value = NewAngVel;
    Command.bMassIndependent = false;
    FSelection Selection;
    Command.bAddToCurrent = bAddToCurrent;
    Selection.Type = ESelection::All;
    if (!Execute(*Component, Command, Selection)) Component->SetAllPhysicsAngularVelocityInRadians(NewAngVel, bAddToCurrent);
}
