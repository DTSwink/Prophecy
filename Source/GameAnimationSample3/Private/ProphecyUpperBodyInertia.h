#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyUpperBodyInertia
{
bool Active(const AProphecyAgent* Agent);
void Begin(const AProphecyAgent* Agent,TConstArrayView<FTransform> PreviousWorld,TConstArrayView<FTransform> World,
    TConstArrayView<FName> Names,TConstArrayView<FName> CoreNames,double Dt);
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
