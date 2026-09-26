#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
enum class EProphecyClampProfileMode : uint8;
namespace ProphecyAttackWrist
{
bool Enabled(const AProphecyAgent* Agent);
float Degrees(const AProphecyAgent* Agent,EProphecyClampProfileMode Mode);
bool ConstrainPose(FTransform& Hand,const FVector& Elbow,float MaxBendDegrees);

// Training slash2_wrist_neutral.WristNeutral(55), in native row-basis space.
// Preserve exact in-cone values. Antipodes use the hand Y axis deterministically.
inline bool Constrain(FVector3f* Rows,const FVector3f& Elbow,const FVector3f& Wrist,float MaxBendDegrees=55.f)
{
    const FVector3f Delta=Wrist-Elbow;
    const float Length=Delta.Size();
    if (Length<=1.e-8f) return false;
    const FVector3f Direction=Delta/Length;
    const float Cosine=FMath::Clamp(FVector3f::DotProduct(Rows[0],Direction),-1.f,1.f);
    const FVector3f Cross=FVector3f::CrossProduct(Rows[0],Direction);
    const float Sine=Cross.Size();
    const float Excess=FMath::Atan2(Sine,Cosine)-FMath::DegreesToRadians(MaxBendDegrees);
    if (Excess<=1.e-7f) return false;
    const FVector3f Axis=Sine>1.e-8f ? Cross/Sine : Rows[1];
    const FQuat4f Correction(Axis,Excess);
    for (int32 I=0;I<3;++I) Rows[I]=Correction.RotateVector(Rows[I]);
    return true;
}
}
