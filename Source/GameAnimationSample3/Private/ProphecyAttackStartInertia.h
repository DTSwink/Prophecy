#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyAttackStartInertia
{
void Update(const AProphecyAgent* Agent,int32 PoseId);
void Begin(const AProphecyAgent* Agent,int32 PoseId,const FTransform& PreviousWorld,const FTransform& World);
void Cancel(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
void CaptureReset(const AProphecyAgent* Agent);
void RestoreReset(const AProphecyAgent* Agent);
void ForgetReset(const AProphecyAgent* Agent);
bool Active(int32 PoseId);
// Read-only on animation workers; all readers consume the same tick's correction.
void Apply(int32 PoseId,TConstArrayView<FName> Names,TArrayView<FTransform> Pose,
    const FTransform& SpaceToWorld=FTransform::Identity);
}
