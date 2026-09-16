#pragma once
#include "CoreMinimal.h"

// World-space target motion. No actor/skeleton dependency or runtime allocation.
namespace ProphecyPelvisInertia
{
inline FVector RotationVector(FQuat Delta)
{
    Delta.Normalize();
    if (Delta.W < 0.) Delta = Delta * -1.;
    const FVector Imaginary(Delta.X, Delta.Y, Delta.Z);
    const double Sine = Imaginary.Length();
    return Imaginary * (Sine > 1e-12 ? 2.*FMath::Atan2(Sine, Delta.W)/Sine : 2.);
}

inline FQuat RotationIncrement(const FVector& Vector)
{
    const double Angle = Vector.Length();
    return Angle > 1e-12 ? FQuat(Vector/Angle, Angle) : FQuat::Identity;
}

struct FMotion
{
    FTransform World = FTransform::Identity;
    FVector LinearVelocity = FVector::ZeroVector;
    FVector AngularVelocity = FVector::ZeroVector; // world radians/second

    void Seed(const FTransform& Previous, const FTransform& Current, double Dt)
    {
        World = Previous;
        LinearVelocity = (Current.GetLocation()-Previous.GetLocation())/Dt;
        AngularVelocity = RotationVector(Current.GetRotation()*Previous.GetRotation().Inverse())/Dt;
    }

    FTransform Step(const FTransform& Target, const FVector& LinearFollow,
        const FVector& AngularFollow, double Dt)
    {
        const FVector DesiredVelocity = (Target.GetLocation()-World.GetLocation())/Dt;
        LinearVelocity += (DesiredVelocity-LinearVelocity)*LinearFollow;
        FVector Position = World.GetLocation()+LinearVelocity*Dt;
        // Follow=1 is the exact original target component, without roundoff drift.
        for (int32 Axis=0; Axis<3; ++Axis)
            if (LinearFollow[Axis] == 1.) Position[Axis] = Target.GetLocation()[Axis];

        const FQuat PreviousRotation = World.GetRotation();
        const FVector DesiredAngularVelocity = RotationVector(Target.GetRotation()*PreviousRotation.Inverse())/Dt;
        AngularVelocity += (DesiredAngularVelocity-AngularVelocity)*AngularFollow;
        FQuat Rotation = AngularFollow == FVector::OneVector ? Target.GetRotation()
            : (RotationIncrement(AngularVelocity*Dt)*PreviousRotation).GetNormalized();
        World = FTransform(Rotation, Position, Target.GetScale3D());
        return World;
    }
};
}
