#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyArmCone
{
void Begin(const AProphecyAgent* Agent,FName Attack);
void Cancel(const AProphecyAgent* Agent);
bool Active(const AProphecyAgent* Agent);
bool ApplyNNPose(AProphecyAgent* Agent,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TArrayView<FTransform> Pose,const FTransform& Carrier,float DeltaSeconds);
bool ApplyNNPublication(AProphecyAgent* Agent,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TArrayView<FTransform> Previous,TArrayView<FTransform> Current,const FTransform& PreviousCarrier,
    const FTransform& Carrier,float DeltaSeconds,bool NewSample);
void Remove(const AProphecyAgent* Agent);
void CaptureReset(const AProphecyAgent* Agent);
void RestoreReset(const AProphecyAgent* Agent);
void ForgetReset(const AProphecyAgent* Agent);
}
