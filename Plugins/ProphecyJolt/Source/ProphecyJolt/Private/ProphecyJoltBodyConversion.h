#pragma once

#include "ProphecyJoltRig.h"
#include "Physics/PhysicsInterfaceCore.h"

THIRD_PARTY_INCLUDES_START
#include <Jolt/Jolt.h>
#include <Jolt/Core/Reference.h>
#include <Jolt/Physics/Body/MassProperties.h>
#include <Jolt/Physics/Collision/Shape/Shape.h>
THIRD_PARTY_INCLUDES_END

namespace Chaos { class FImplicitObject; }

namespace ProphecyJolt::BodyConversion
{
    // Geometry-only, no UObject access or mutation. Bakes cooked convex wrapper scale exactly once.
    bool CaptureGeometry(const Chaos::FImplicitObject& Geometry, FProphecyJoltRigShape& OutShape, FString& OutError);
    // Common live shape filter/identity capture used by both standalone and skeletal import.
    bool CaptureNativeShape(const FPhysicsShapeHandle& Handle, FProphecyJoltRigShape& OutShape, FString& OutError);
    bool ValidateShapes(TConstArrayView<FProphecyJoltRigShape> Shapes, FString& OutError);
    // Shared strict geometry preparation, independent of dynamic mass/COM ownership.
    bool PrepareShapes(TConstArrayView<FProphecyJoltRigShape> Shapes, JPH::RefConst<JPH::Shape>& OutShape, FString& OutError);
    bool ValidateBodyData(const FProphecyJoltBodyData& Body, FString& OutError);
    bool PrepareShapeAndMass(const FProphecyJoltBodyData& Body, JPH::RefConst<JPH::Shape>& OutShape,
        JPH::MassProperties& OutMass, FString& OutError);
}
