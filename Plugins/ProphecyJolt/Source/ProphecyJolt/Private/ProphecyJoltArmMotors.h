#pragma once
#include "ProphecyJoltVelocityServo.h"
#include <Jolt/Physics/Constraints/SixDOFConstraint.h>

namespace ProphecyJolt::ArmMotors
{
struct FDrive { JPH::Ref<JPH::SixDOFConstraint> Motor; bool Published = false; };
using FDrives = TMap<uint32, FDrive>;
void Set(JPH::PhysicsSystem& Physics, JPH::BodyID Body, bool Enabled);
void Clear(JPH::PhysicsSystem& Physics);
FDrives* Find(JPH::PhysicsSystem& Physics);
// Called outside Update. Unpublished targets must never retain last tick's motors.
void Prepare(JPH::PhysicsSystem& Physics, TConstArrayView<FVelocityServo::FTarget> Targets);
bool Apply(FDrives* Drives, JPH::Body& Body, const FVelocityServo::FTarget& Target,
    float DeltaSeconds, JPH::Vec3Arg Linear, JPH::Vec3Arg Angular,
    const FVector& LinearFollow, const FVector& AngularFollow);
}
