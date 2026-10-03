#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyAttackStartFKCore
{
bool Active(const AProphecyAgent* Agent);
bool AwaitingFirstPose(const AProphecyAgent* Agent);
bool Configured(const AProphecyAgent* Agent);
void Begin(const AProphecyAgent* Agent, TConstArrayView<FName> Names, TConstArrayView<int32> Parents,
    TConstArrayView<FName> CoreNames);
bool Apply(const AProphecyAgent* Agent, TArrayView<FTransform> Pose, double PoseStepSeconds);
// Keep outgoing core motion when physical entry replaces the presentation history.
void PrepareEntryPose(const AProphecyAgent* Agent, TArrayView<FTransform> Pose);
void Cancel(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
void CaptureReset(const AProphecyAgent* Agent);
void RestoreReset(const AProphecyAgent* Agent);
void ForgetReset(const AProphecyAgent* Agent);
}
