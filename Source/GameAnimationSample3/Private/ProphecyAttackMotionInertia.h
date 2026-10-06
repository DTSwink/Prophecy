#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyAttackMotionInertia
{
bool Configured(const AProphecyAgent* Agent);
bool FilteringArms(const AProphecyAgent* Agent);
void Begin(const AProphecyAgent* Agent,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TConstArrayView<FTransform> Previous,TConstArrayView<FTransform> Current);
bool Apply(const AProphecyAgent* Agent,TArrayView<FTransform> Pose,bool Armed,bool Hit=false);
// Publish only after all attack/locomotion feedback is committed. Retain the
// unsmoothed source for older entry modifiers that read the preceding endpoint.
void Publish(const AProphecyAgent* Agent,TArrayView<FTransform> Pose,const FTransform& Carrier,bool Armed,bool Hit);
TConstArrayView<FTransform> PreviousSource(const AProphecyAgent* Agent);
void TranslateSource(const AProphecyAgent* Agent,const FVector& Delta);
void Cancel(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
void CaptureReset(const AProphecyAgent* Agent);
void RestoreReset(const AProphecyAgent* Agent);
void ForgetReset(const AProphecyAgent* Agent);
}
