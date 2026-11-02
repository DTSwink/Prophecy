#pragma once
#include "ProphecyBodyflipRuntime.h"
#include "ProphecyJoltWorldSubsystem.h"

namespace ProphecyBodyflip::Drive
{
// The shared solver owns this temporary attack window; saved limits stay unchanged.
bool AttackFree(const AProphecyAgent* Agent);
// An effective controller profile, never a write to the agent's saved tuning.
// Jolt resolves each child's COM anchors from the live captured PHAT joint.
inline void Configure(FProphecyJoltRigVelocityTarget& Target,float WorldGravityZ)
{
    Target.bFiniteJointCarry=true;
    Target.LinearStrength=1.f;
    Target.AngularStrength=1.f;
    Target.GravityCompensationCmPerSecondSquared=-WorldGravityZ;
}
}
