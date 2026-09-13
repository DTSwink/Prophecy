#include "ProphecyPhysicsSkeletalMeshComponent.h"
#include "ProphecyJoltMeshPhysics.h"

using namespace ProphecyJolt::MeshPhysics;

void UProphecyPhysicsSkeletalMeshComponent::AddForce(FVector Force, FName BoneName, bool bAccelChange)
{
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Force;
    Command.Value = Force;
    Command.bMassIndependent = bAccelChange;
    FSelection Selection;
    Selection.Bone = BoneName;
    if (!Execute(*this, Command, Selection)) Super::AddForce(Force, BoneName, bAccelChange);
}

void UProphecyPhysicsSkeletalMeshComponent::AddImpulse(FVector Impulse, FName BoneName, bool bVelChange)
{
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Impulse;
    Command.Value = Impulse;
    Command.bMassIndependent = bVelChange;
    FSelection Selection;
    Selection.Bone = BoneName;
    if (!Execute(*this, Command, Selection)) Super::AddImpulse(Impulse, BoneName, bVelChange);
}

void UProphecyPhysicsSkeletalMeshComponent::AddTorqueInRadians(FVector Torque, FName BoneName, bool bAccelChange)
{
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Torque;
    Command.Value = Torque;
    Command.bMassIndependent = bAccelChange;
    FSelection Selection;
    Selection.Bone = BoneName;
    if (!Execute(*this, Command, Selection)) Super::AddTorqueInRadians(Torque, BoneName, bAccelChange);
}

void UProphecyPhysicsSkeletalMeshComponent::AddAngularImpulseInRadians(FVector Impulse, FName BoneName, bool bVelChange)
{
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::AngularImpulse;
    Command.Value = Impulse;
    Command.bMassIndependent = bVelChange;
    FSelection Selection;
    Selection.Bone = BoneName;
    if (!Execute(*this, Command, Selection)) Super::AddAngularImpulseInRadians(Impulse, BoneName, bVelChange);
}

void UProphecyPhysicsSkeletalMeshComponent::AddForceAtLocation(FVector Force, FVector Location, FName BoneName)
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

void UProphecyPhysicsSkeletalMeshComponent::AddForceAtLocationLocal(FVector Force, FVector Location, FName BoneName)
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

void UProphecyPhysicsSkeletalMeshComponent::AddImpulseAtLocation(FVector Impulse, FVector Location, FName BoneName)
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

void UProphecyPhysicsSkeletalMeshComponent::AddRadialForce(FVector Origin, float Radius, float Strength, ERadialImpulseFalloff Falloff, bool bAccelChange)
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

void UProphecyPhysicsSkeletalMeshComponent::AddRadialImpulse(FVector Origin, float Radius, float Strength, ERadialImpulseFalloff Falloff, bool bVelChange)
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

void UProphecyPhysicsSkeletalMeshComponent::SetPhysicsLinearVelocity(FVector NewVel, bool bAddToCurrent, FName BoneName)
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

void UProphecyPhysicsSkeletalMeshComponent::SetPhysicsAngularVelocityInRadians(FVector NewAngVel, bool bAddToCurrent, FName BoneName)
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

void UProphecyPhysicsSkeletalMeshComponent::SetAllPhysicsLinearVelocity(FVector NewVel, bool bAddToCurrent)
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

void UProphecyPhysicsSkeletalMeshComponent::SetAllPhysicsAngularVelocityInRadians(const FVector& NewAngVel, bool bAddToCurrent)
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

void UProphecyPhysicsSkeletalMeshComponent::AddForceToAllBodiesBelow(FVector Force, FName BoneName, bool bAccelChange, bool bIncludeSelf)
{
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Force;
    Command.Value = Force;
    Command.bMassIndependent = bAccelChange;
    FSelection Selection;
    Selection.Bone = BoneName;
    Selection.Type = ESelection::Below;
    Selection.bIncludeSelf = bIncludeSelf;
    if (!Execute(*this, Command, Selection)) Super::AddForceToAllBodiesBelow(Force, BoneName, bAccelChange, bIncludeSelf);
}

void UProphecyPhysicsSkeletalMeshComponent::AddImpulseToAllBodiesBelow(FVector Impulse, FName BoneName, bool bVelChange, bool bIncludeSelf)
{
    FProphecyJoltPhysicsCommand Command;
    Command.Operation = EProphecyJoltPhysicsCommand::Impulse;
    Command.Value = Impulse;
    Command.bMassIndependent = bVelChange;
    FSelection Selection;
    Selection.Bone = BoneName;
    Selection.Type = ESelection::Below;
    Selection.bIncludeSelf = bIncludeSelf;
    if (!Execute(*this, Command, Selection)) Super::AddImpulseToAllBodiesBelow(Impulse, BoneName, bVelChange, bIncludeSelf);
}
