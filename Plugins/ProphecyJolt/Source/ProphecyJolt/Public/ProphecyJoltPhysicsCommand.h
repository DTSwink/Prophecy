#pragma once

#include "CoreMinimal.h"

enum class EProphecyJoltPhysicsCommand : uint8
{
    Force, Impulse, Torque, AngularImpulse, LinearVelocity, AngularVelocity
};

/** UE units: cm, kg, seconds, radians. Physical torque/impulse uses kg*cm^2. */
struct FProphecyJoltPhysicsCommand
{
    EProphecyJoltPhysicsCommand Operation = EProphecyJoltPhysicsCommand::Force;
    FVector Value = FVector::ZeroVector;
    FVector Position = FVector::ZeroVector;
    bool bAtPosition = false;
    bool bLocalSpace = false;
    bool bMassIndependent = false; // Accel Change / Vel Change, including inertia for angular commands.
    bool bAddToCurrent = false; // Velocity setters only.
};
