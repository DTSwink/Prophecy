#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyForearmStretch
{
bool OwnsPosition(const AProphecyAgent* Agent);
void Begin(AProphecyAgent* Agent);
void End(AProphecyAgent* Agent,bool Recover);
void Cancel(AProphecyAgent* Agent);
void Remove(AProphecyAgent* Agent);
bool Reapply(AProphecyAgent* Agent,FString& Error);
void BeforeModeChange(AProphecyAgent* Agent);
void PhysicalTarget(const AProphecyAgent* Agent,FName Bone,const FTransform& Elbow,FTransform& Hand);
bool Apply(const AProphecyAgent* Agent,TConstArrayView<FName> Names,TArrayView<FTransform> Previous,
    TArrayView<FTransform> Current,TArrayView<FTransform> Local,bool FKReturning);
void CaptureReset(const AProphecyAgent* Agent);
void RestoreReset(AProphecyAgent* Agent);
void ForgetReset(const AProphecyAgent* Agent);
}
