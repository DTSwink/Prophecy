#include "ProphecyPhysicsStaticMeshComponent.h"
#include "ProphecyJoltMeshPhysics.h"
#include "ProphecyJoltBodyComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/PhysicsSettings.h"
#include "PhysicalMaterials/PhysicalMaterial.h"

using namespace ProphecyJolt::MeshPhysics;

void UProphecyPhysicsStaticMeshComponent::SetPhysMaterialOverride(UPhysicalMaterial* NewPhysMaterial)
{
    Super::SetPhysMaterialOverride(NewPhysMaterial);
    if (!GetOwner()) return;
    TInlineComponentArray<UProphecyJoltBodyComponent*> Bodies(GetOwner());
    for (auto* Body : Bodies)
    {
        if (Body->GetSourceComponent() != this) continue;
        if (Body->IsEnablePending())
        {
            // Admission has captured its material already. Resolve the latest
            // receiver value once ownership completes, without polling.
            Body->OnDeferredEnableCompleted.AddWeakLambda(this, [this](bool Success, const FString&)
            {
                if (Success) SetPhysMaterialOverride(BodyInstance.GetPhysMaterialOverride());
            });
            return;
        }
        FProphecyJoltBodyHandle Handle;
        auto* World = Body->GetWorldOwner();
        if (!World || !Body->GetBodyHandle(Handle)) return;
        const auto* Material = BodyInstance.GetSimplePhysicalMaterial();
        if (!Material) return;
        FProphecyJoltBodyMaterial Value;
        Value.Friction = Material->Friction;
        Value.Restitution = Material->Restitution;
        Value.FrictionCombineMode = uint8(Material->bOverrideFrictionCombineMode
            ? Material->FrictionCombineMode.GetValue() : UPhysicsSettings::Get()->FrictionCombineMode.GetValue());
        Value.RestitutionCombineMode = uint8(Material->bOverrideRestitutionCombineMode
            ? Material->RestitutionCombineMode.GetValue() : UPhysicsSettings::Get()->RestitutionCombineMode.GetValue());
        const FProphecyJoltMaterialUpdate Update{Handle, Value};
        const auto Result = World->UpdateBodyMaterials(MakeArrayView(&Update, 1));
        if (!Result.IsSuccess()) UE_LOG(LogTemp, Warning, TEXT("Physical material override could not update Jolt on %s: %s"),
            *GetPathName(), *Result.Message);
        return;
    }
}

void UProphecyPhysicsStaticMeshComponent::AddForce(FVector Force, FName BoneName, bool bAccelChange)
{
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Force;
    Command.Value = Force;
    Command.bMassIndependent = bAccelChange;
    FSelection Selection;
    Selection.Bone = BoneName;
    if (!Execute(*this, Command, Selection)) Super::AddForce(Force, BoneName, bAccelChange);
}

void UProphecyPhysicsStaticMeshComponent::AddImpulse(FVector Impulse, FName BoneName, bool bVelChange)
{
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Impulse;
    Command.Value = Impulse;
    Command.bMassIndependent = bVelChange;
    FSelection Selection;
    Selection.Bone = BoneName;
    if (!Execute(*this, Command, Selection)) Super::AddImpulse(Impulse, BoneName, bVelChange);
}

void UProphecyPhysicsStaticMeshComponent::AddTorqueInRadians(FVector Torque, FName BoneName, bool bAccelChange)
{
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Torque;
    Command.Value = Torque;
    Command.bMassIndependent = bAccelChange;
    FSelection Selection;
    Selection.Bone = BoneName;
    if (!Execute(*this, Command, Selection)) Super::AddTorqueInRadians(Torque, BoneName, bAccelChange);
}

void UProphecyPhysicsStaticMeshComponent::AddAngularImpulseInRadians(FVector Impulse, FName BoneName, bool bVelChange)
{
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::AngularImpulse;
    Command.Value = Impulse;
    Command.bMassIndependent = bVelChange;
    FSelection Selection;
    Selection.Bone = BoneName;
    if (!Execute(*this, Command, Selection)) Super::AddAngularImpulseInRadians(Impulse, BoneName, bVelChange);
}

void UProphecyPhysicsStaticMeshComponent::AddForceAtLocation(FVector Force, FVector Location, FName BoneName)
{
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Force;
    Command.Value = Force;
    Command.bMassIndependent = false;
    FSelection Selection;
    Selection.Bone = BoneName;
    Command.bAtPosition = true;
    Command.Position = Location;
    if (!Execute(*this, Command, Selection)) Super::AddForceAtLocation(Force, Location, BoneName);
}

void UProphecyPhysicsStaticMeshComponent::AddForceAtLocationLocal(FVector Force, FVector Location, FName BoneName)
{
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Force;
    Command.Value = Force;
    Command.bMassIndependent = false;
    FSelection Selection;
    Selection.Bone = BoneName;
    Command.bAtPosition = true;
    Command.Position = Location;
    Command.bLocalSpace = true;
    if (!Execute(*this, Command, Selection)) Super::AddForceAtLocationLocal(Force, Location, BoneName);
}

void UProphecyPhysicsStaticMeshComponent::AddImpulseAtLocation(FVector Impulse, FVector Location, FName BoneName)
{
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Impulse;
    Command.Value = Impulse;
    Command.bMassIndependent = false;
    FSelection Selection;
    Selection.Bone = BoneName;
    Command.bAtPosition = true;
    Command.Position = Location;
    if (!Execute(*this, Command, Selection)) Super::AddImpulseAtLocation(Impulse, Location, BoneName);
}

void UProphecyPhysicsStaticMeshComponent::AddRadialForce(FVector Origin, float Radius, float Strength, ERadialImpulseFalloff Falloff, bool bAccelChange)
{
    if (bIgnoreRadialForce) return;
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
    if (!Execute(*this, Command, Selection)) Super::AddRadialForce(Origin, Radius, Strength, Falloff, bAccelChange);
}

void UProphecyPhysicsStaticMeshComponent::AddRadialImpulse(FVector Origin, float Radius, float Strength, ERadialImpulseFalloff Falloff, bool bVelChange)
{
    if (bIgnoreRadialImpulse) return;
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
    if (!Execute(*this, Command, Selection)) Super::AddRadialImpulse(Origin, Radius, Strength, Falloff, bVelChange);
}

void UProphecyPhysicsStaticMeshComponent::SetPhysicsLinearVelocity(FVector NewVel, bool bAddToCurrent, FName BoneName)
{
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::LinearVelocity;
    Command.Value = NewVel;
    Command.bMassIndependent = false;
    FSelection Selection;
    Selection.Bone = BoneName;
    Command.bAddToCurrent = bAddToCurrent;
    if (!Execute(*this, Command, Selection)) Super::SetPhysicsLinearVelocity(NewVel, bAddToCurrent, BoneName);
}

void UProphecyPhysicsStaticMeshComponent::SetPhysicsAngularVelocityInRadians(FVector NewAngVel, bool bAddToCurrent, FName BoneName)
{
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::AngularVelocity;
    Command.Value = NewAngVel;
    Command.bMassIndependent = false;
    FSelection Selection;
    Selection.Bone = BoneName;
    Command.bAddToCurrent = bAddToCurrent;
    if (!Execute(*this, Command, Selection)) Super::SetPhysicsAngularVelocityInRadians(NewAngVel, bAddToCurrent, BoneName);
}

void UProphecyPhysicsStaticMeshComponent::SetAllPhysicsLinearVelocity(FVector NewVel, bool bAddToCurrent)
{
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::LinearVelocity;
    Command.Value = NewVel;
    Command.bMassIndependent = false;
    FSelection Selection;
    Command.bAddToCurrent = bAddToCurrent;
    Selection.Type = ESelection::All;
    if (!Execute(*this, Command, Selection)) Super::SetAllPhysicsLinearVelocity(NewVel, bAddToCurrent);
}

void UProphecyPhysicsStaticMeshComponent::SetAllPhysicsAngularVelocityInRadians(const FVector& NewAngVel, bool bAddToCurrent)
{
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::AngularVelocity;
    Command.Value = NewAngVel;
    Command.bMassIndependent = false;
    FSelection Selection;
    Command.bAddToCurrent = bAddToCurrent;
    Selection.Type = ESelection::All;
    if (!Execute(*this, Command, Selection)) Super::SetAllPhysicsAngularVelocityInRadians(NewAngVel, bAddToCurrent);
}
