#pragma once

#include "CoreMinimal.h"

THIRD_PARTY_INCLUDES_START
#include <Jolt/Jolt.h>
#include <Jolt/Physics/Constraints/SixDOFConstraint.h>
THIRD_PARTY_INCLUDES_END

struct FProphecyJoltRigJoint;

namespace ProphecyJolt
{
// This is a hard-limit fixture conversion report, not a production parity claim.
// CurrentProfile remains the lossless source of every authored coefficient.
struct FHardJointConversionReport
{
    int32 JoltBody1Index = INDEX_NONE; // UE Body2: parent/reference
    int32 JoltBody2Index = INDEX_NONE; // UE Body1: child
    int32 HardAngularAxisCount = 0;
    int32 FixedAngularAxisCount = 0;
    int32 FreeAngularAxisCount = 0;
    int32 RejectedThresholdAxisCount = 0;
    bool bAuthoredSoftSwing = false;
    bool bAuthoredSoftTwist = false;
    bool bDisableCollision = false;
    TArray<FString> DeferredProfileFeatures;
};

// Creates stock Jolt hard cone/twist limits at the exact authored angles.
// UE Swing1 maps to RotationZ; Swing2 to RotationY; Twist to RotationX.
// Frame1/Frame2 must already be the final, scaled body-origin-local frames in cm.
// AngularRotationOffset is provenance: UE component frame updates bake it into
// Frame2, while FConstraintInstance::GetRefFrame uses the stored axes unchanged.
// COM transforms here mean Jolt COM-to-body-origin, NOT the UE principal inertia
// frame. Standard Jolt bodies use identity rotation plus their shape COM offset;
// a rotated COM-to-origin input is rejected to catch principal-frame confusion.
// Translation supports Locked/Free only in this first rig fixture. Limited
// translation requires a separate scaled-distance/coupling conversion contract.
// IMPORTANT: create the constraint with descriptor Body2 FIRST, Body1 SECOND;
// OutReport explicitly returns this order, matching Chaos's parent-first solver.
// Success means limit geometry is representable for the isolated fixture only.
// Motors, projection, conditioning, etc. are reported, never claimed implemented.
// Caller must honor bDisableCollision in its collision filter. No collision pair
// filtering is performed by a SixDOFConstraintSettings object.
// OutSettings is unchanged on failure. OutReport is always reset/populated.
bool BuildHardJointSettings(const FProphecyJoltRigJoint& Joint,
    const FTransform& Body1COMToBodyOrigin, const FTransform& Body2COMToBodyOrigin,
    JPH::SixDOFConstraintSettings& OutSettings, FHardJointConversionReport& OutReport,
    FString& OutError);
}
