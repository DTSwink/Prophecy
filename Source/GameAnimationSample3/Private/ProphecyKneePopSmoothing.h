#pragma once
#include "CoreMinimal.h"

namespace ProphecyKneePopSmoothing
{
// Stateless soft IK near full extension: ease the ankle directly toward its hip,
// the shortest displacement to the softened reach, then solve the same bend
// side with both segments connected. No lag, stretch or pelvis move.
inline bool Apply(FTransform& Thigh,FTransform& Calf,FTransform& Foot,FTransform* Toe,
    double SoftZoneCm,const FVector& FallbackPole=FVector::ZeroVector)
{
    if (SoftZoneCm<=0) return false;
    const FVector Hip=Thigh.GetTranslation(),Knee=Calf.GetTranslation(),Ankle=Foot.GetTranslation();
    const FVector Upper=Knee-Hip,Lower=Ankle-Knee,Delta=Ankle-Hip;
    const double L1=Upper.Length(),L2=Lower.Length(),Distance=Delta.Length(),Reach=L1+L2;
    if (L1<1.e-5 || L2<1.e-5 || Distance<1.e-5) return false;
    const double Zone=FMath::Min(SoftZoneCm,Reach*.25),Start=Reach-Zone;
    if (Distance<=Start) return false;
    const FVector Axis=Delta/Distance;
    const double SoftDistance=Reach-Zone*FMath::Exp(-(Distance-Start)/Zone);
    const FVector Shift=Axis*(SoftDistance-Distance);
    if (Shift.SizeSquared()<1.e-16) return false;
    FVector Pole=Upper-Axis*FVector::DotProduct(Upper,Axis);
    const FVector NewAnkle=Ankle+Shift,NewDelta=NewAnkle-Hip;
    const double D=NewDelta.Length();
    if (D<=FMath::Abs(L1-L2)+1.e-6) return false;
    const FVector NewAxis=NewDelta/D;
    const double Along=(L1*L1-L2*L2+D*D)/(2.*D);
    const double Radius=FMath::Sqrt(FMath::Max(0.,L1*L1-Along*Along));
    const FVector Reference=(FallbackPole-Axis*FVector::DotProduct(FallbackPole,Axis)).GetSafeNormal();
    if (!Reference.IsNearlyZero())
    {
        // Radial amplification must not magnify an unstable near-straight pole
        // or a one-frame reversed branch. Fade in the reliable thigh-frame bend
        // as knee radius is added. The nonnegative forward component avoids the
        // cancellation/singularity of interpolating opposite unit directions.
        Pole+=Reference*(FMath::Max(0.,-FVector::DotProduct(Pole,Reference))+FMath::Max(0.,Radius-Pole.Length()));
    }
    if (!Pole.Normalize()) return false;
    const FVector NewUpper=NewAxis*Along+Pole*Radius;
    const FVector NewKnee=Hip+NewUpper,NewLower=NewAnkle-NewKnee;
    Thigh.SetRotation((FQuat::FindBetweenNormals(Upper/L1,NewUpper/L1)*Thigh.GetRotation()).GetNormalized());
    Calf.SetRotation((FQuat::FindBetweenNormals(Lower/L2,NewLower/L2)*Calf.GetRotation()).GetNormalized());
    Calf.SetTranslation(NewKnee);Foot.SetTranslation(NewAnkle);
    if (Toe) Toe->AddToTranslation(Shift);
    return true;
}
}
