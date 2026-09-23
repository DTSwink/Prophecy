#pragma once
#include "CoreMinimal.h"

namespace ProphecyRecoveryLegLength
{
// Preserve the ankle (and therefore floor/pin placement), both segment rolls and
// the current bend side. Only repair the interpolated knee and segment aims.
inline bool Resolve(FTransform& Thigh,FTransform& Calf,const FTransform& Foot,double Upper,double Lower)
{
    const FVector Hip=Thigh.GetLocation(),Knee=Calf.GetLocation(),End=Foot.GetLocation();
    const FVector Delta=End-Hip;
    const double Distance=Delta.Size();
    if (Upper<=1.e-5 || Lower<=1.e-5 || Distance<=1.e-5) return false;
    const FVector Axis=Delta/Distance;
    const FVector OldUpper=Knee-Hip,OldLower=End-Knee;
    const FVector Projected=OldUpper-Axis*FVector::DotProduct(OldUpper,Axis);
    // At a straight singularity preserve the existing solution, never invent a pole.
    if (Projected.SizeSquared()<1.e-12) return false;
    // Unclamped endpoints may be outside reach. Keep the endpoint instead of
    // pulling a pinned foot down or changing the user's outward-reach setting.
    Lower=FMath::Clamp(Lower,FMath::Abs(Distance-Upper)+1.e-6,Distance+Upper-1.e-6);
    const double Along=(Upper*Upper-Lower*Lower+Distance*Distance)/(2*Distance);
    const FVector NewUpper=Axis*Along+Projected.GetSafeNormal()*FMath::Sqrt(FMath::Max(0.,Upper*Upper-Along*Along));
    const FVector NewKnee=Hip+NewUpper,NewLower=End-NewKnee;
    Thigh.SetRotation((FQuat::FindBetweenNormals(OldUpper.GetSafeNormal(),NewUpper.GetSafeNormal())*Thigh.GetRotation()).GetNormalized());
    Calf.SetRotation((FQuat::FindBetweenNormals(OldLower.GetSafeNormal(),NewLower.GetSafeNormal())*Calf.GetRotation()).GetNormalized());
    Calf.SetLocation(NewKnee);
    return true;
}
}
