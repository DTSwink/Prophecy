#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyAttackStartHands
{
bool Active(const AProphecyAgent* A);
void Begin(const AProphecyAgent* A);
uint8 Apply(const AProphecyAgent* A,TConstArrayView<FName> Names,TArrayView<FTransform> Pose,
    const FTransform& Carrier,double PoseStepSeconds);
void Cancel(const AProphecyAgent* A);
void Remove(const AProphecyAgent* A);
void CaptureReset(const AProphecyAgent* A);
void RestoreReset(const AProphecyAgent* A);
void ForgetReset(const AProphecyAgent* A);
}
