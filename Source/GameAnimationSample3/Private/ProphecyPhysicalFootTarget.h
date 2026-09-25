#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyPhysicalFootTarget
{
float Leeway(const AProphecyAgent* Agent);
// Explicit enabled locomotion calf clamp, including its current snapshot blend.
float LocomotionCalfLeeway(const AProphecyAgent* Agent);
// Same finite signed calf-length return as presentation. Zero is the exact old endpoint.
inline FVector CalfEnd(const FTransform& Calf,const FVector& ReferenceOffset,float RecoveryDeltaCm)
{
    const FVector End=Calf.TransformPosition(ReferenceOffset);
    if(RecoveryDeltaCm==0)return End;
    const FVector Axis=(End-Calf.GetLocation()).GetSafeNormal();
    return End+Axis*RecoveryDeltaCm;
}
// A returning pose has already sampled its signed length with the displayed
// frame. Preserve that sample in the drive instead of re-reading a newer clock.
inline FVector PresentedCalfEnd(const FTransform& Calf,const FVector& ReferenceOffset,const FVector& Foot)
{
    const FVector Rest=Calf.TransformPosition(ReferenceOffset),Origin=Calf.GetLocation();
    return Origin+(Rest-Origin).GetSafeNormal()*(Foot-Origin).Size();
}
inline FVector Clamp(const FVector& Target, const FVector& CalfEnd, float LeewayCm)
{
    if (LeewayCm<=0.f) return CalfEnd;
    const FVector Offset=Target-CalfEnd;
    if (Offset.SizeSquared()<=double(LeewayCm)*LeewayCm) return Target;
    return CalfEnd+Offset.GetSafeNormal()*LeewayCm;
}
}
