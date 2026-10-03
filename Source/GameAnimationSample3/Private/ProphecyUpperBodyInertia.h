#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyUpperBodyInertia
{
bool Active(const AProphecyAgent* Agent);
bool CoreActive(const AProphecyAgent* Agent);
void Advance(const AProphecyAgent* Agent);
bool ArmsActive(const AProphecyAgent* Agent);
void ApplyArms(const AProphecyAgent* Agent,const FTransform& Carrier,TArrayView<FTransform> Pose,
    double StepSeconds,const FVector2D& RestForearmLengthsCm,const FTransform& Root=FTransform::Identity);
bool PublishArms(const AProphecyAgent* Agent,const FTransform& PreviousCarrier,const FTransform& Carrier,
    TArrayView<FTransform> PreviousPose,TArrayView<FTransform> Pose);
void Begin(const AProphecyAgent* Agent,TConstArrayView<FTransform> PreviousWorld,TConstArrayView<FTransform> World,
    TConstArrayView<FName> Names,TConstArrayView<FName> CoreNames,double Dt,
    const FTransform& PreviousRoot=FTransform::Identity,const FTransform& Root=FTransform::Identity);
bool Configured(const AProphecyAgent* Agent);
void Apply(const AProphecyAgent* Agent,TConstArrayView<int32> Parents,TConstArrayView<FName> Names,
    TConstArrayView<FName> CoreNames,const FTransform& Carrier,TArrayView<FTransform> Pose,double PoseStepSeconds=-1);
void Cancel(const AProphecyAgent* Agent);
void PreserveHandoff(const AProphecyAgent* Agent,TConstArrayView<int32> Parents,TConstArrayView<FName> Names,
    TConstArrayView<FName> CoreNames,const FTransform& PreviousCarrier,TArrayView<FTransform> PreviousPose);
void Remove(const AProphecyAgent* Agent);
void CaptureReset(const AProphecyAgent* Agent);
void RestoreReset(const AProphecyAgent* Agent);
void ForgetReset(const AProphecyAgent* Agent);
}
