#pragma once
#include "CoreMinimal.h"

namespace ProphecyRecoveryLegLength
{
// Preserve the ankle (and therefore floor/pin placement), both segment rolls and
// the current bend side. Only repair the interpolated knee and segment aims.
inline bool Resolve(FTransform& Thigh,FTransform& Calf,const FTransform& Foot,double Upper,double Lower,
    const FVector& CalfLocalAim=FVector::ZeroVector)
{
    const FVector Hip=Thigh.GetLocation(),Knee=Calf.GetLocation(),End=Foot.GetLocation();
    const FVector Delta=End-Hip;
    const double Distance=Delta.Size();
    if (Upper<=1.e-5 || Lower<=1.e-5 || Distance<=1.e-5) return false;
    const FVector Axis=Delta/Distance;
    const FVector OldUpper=Knee-Hip,OldLower=End-Knee;
    // World position interpolation and rotation interpolation need not agree on
    // the segment aim. Transport the anatomical calf axis, not that erroneous
    // interpolated knee-to-foot vector. The shortest swing preserves calf roll.
    const FVector OldAim=CalfLocalAim.IsNearlyZero() ? OldLower.GetSafeNormal()
        : Calf.TransformVectorNoScale(CalfLocalAim).GetSafeNormal();
    const FVector Projected=OldUpper-Axis*FVector::DotProduct(OldUpper,Axis);
    // At a straight singularity preserve the existing solution, never invent a pole.
    if (Projected.SizeSquared()<1.e-12)
    {
        if (!CalfLocalAim.IsNearlyZero() && !OldLower.IsNearlyZero())
            Calf.SetRotation((FQuat::FindBetweenNormals(OldAim,OldLower.GetSafeNormal())*Calf.GetRotation()).GetNormalized());
        return false;
    }
    // Unclamped endpoints may be outside reach. Keep the endpoint instead of
    // pulling a pinned foot down or changing the user's outward-reach setting.
    Lower=FMath::Clamp(Lower,FMath::Abs(Distance-Upper)+1.e-6,Distance+Upper-1.e-6);
    const double Along=(Upper*Upper-Lower*Lower+Distance*Distance)/(2*Distance);
    const FVector NewUpper=Axis*Along+Projected.GetSafeNormal()*FMath::Sqrt(FMath::Max(0.,Upper*Upper-Along*Along));
    const FVector NewKnee=Hip+NewUpper,NewLower=End-NewKnee;
    Thigh.SetRotation((FQuat::FindBetweenNormals(OldUpper.GetSafeNormal(),NewUpper.GetSafeNormal())*Thigh.GetRotation()).GetNormalized());
    Calf.SetRotation((FQuat::FindBetweenNormals(OldAim,NewLower.GetSafeNormal())*Calf.GetRotation()).GetNormalized());
    Calf.SetLocation(NewKnee);
    return true;
}
inline bool ResolveBlended(FTransform& Thigh,FTransform& Calf,const FTransform& Foot,double Upper,double Lower,
    const FVector& CalfLocalAim,double Weight)
{
    if(Weight<=0)return false;
    if(Weight>=1)return Resolve(Thigh,Calf,Foot,Upper,Lower,CalfLocalAim);
    const FQuat OldThigh=Thigh.GetRotation(),OldCalf=Calf.GetRotation();
    const FVector OldKnee=Calf.GetLocation();
    const bool Changed=Resolve(Thigh,Calf,Foot,Upper,Lower,CalfLocalAim);
    Thigh.SetRotation(FQuat::Slerp(OldThigh,Thigh.GetRotation(),Weight).GetNormalized());
    Calf.SetRotation(FQuat::Slerp(OldCalf,Calf.GetRotation(),Weight).GetNormalized());
    Calf.SetLocation(FMath::Lerp(OldKnee,Calf.GetLocation(),Weight));
    return Changed;
}
}
