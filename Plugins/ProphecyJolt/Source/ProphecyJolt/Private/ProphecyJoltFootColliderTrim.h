#pragma once
#include "ProphecyJoltRig.h"

namespace ProphecyJolt::FootColliderTrim
{
// Work in the collider's own frame. Moving the centre by half the removed
// length leaves every point of its heel face unchanged, including rotated boxes.
inline bool Build(TConstArrayView<FProphecyJoltRigShape> Original, const FVector& ToeDirection,
    double TrimCm, TArray<FProphecyJoltRigShape>& Out, FString& Error)
{
    if (!FMath::IsFinite(TrimCm) || TrimCm < 0.0 || ToeDirection.ContainsNaN() || ToeDirection.IsNearlyZero())
    { Error=TEXT("Foot trim needs a finite nonnegative distance and a valid toe direction."); return false; }
    Out = TArray<FProphecyJoltRigShape>(Original);
    if (TrimCm == 0.0) return true;
    if (Out.IsEmpty()) { Error=TEXT("The foot has no colliders."); return false; }
    for (auto& Shape : Out)
    {
        if (Shape.Kind != EProphecyJoltRigShape::Box)
        { Error=TEXT("Foot front trim currently requires box foot colliders."); return false; }
        const FVector Local = Shape.LocalToBodyOrigin.InverseTransformVectorNoScale(ToeDirection.GetSafeNormal());
        int32 Axis=0;
        if (FMath::Abs(Local.Y)>FMath::Abs(Local[Axis])) Axis=1;
        if (FMath::Abs(Local.Z)>FMath::Abs(Local[Axis])) Axis=2;
        if (FMath::Abs(Local[Axis]) < 0.7 || 2.0*Shape.BoxHalfExtentCm[Axis]-TrimCm < 0.1)
        { Error=TEXT("Foot trim would leave less than 0.1 cm, or the collider has no clear toe-facing axis."); return false; }
        FVector Shift=FVector::ZeroVector;
        Shift[Axis]=-FMath::Sign(Local[Axis])*TrimCm*0.5;
        Shape.BoxHalfExtentCm[Axis]-=TrimCm*0.5;
        Shape.LocalToBodyOrigin.AddToTranslation(Shape.LocalToBodyOrigin.TransformVectorNoScale(Shift));
    }
    return true;
}
}
