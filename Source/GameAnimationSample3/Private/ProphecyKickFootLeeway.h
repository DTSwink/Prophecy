#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyKickFootLeeway
{
void Begin(AProphecyAgent* Agent,FName Attack);
// End joint allowance if present; full special exits also capture pose-only
// calf-length continuity when no kick allowance is active (default 60 ticks).
void End(AProphecyAgent* Agent,bool RecoverPose=true);
void CancelPoseRecovery(const AProphecyAgent* Agent);
// Signed, independently captured length differences; zero outside the finite return.
float ReturningLengthDeltaCm(const AProphecyAgent* Agent,int32 Side);
bool HasLengthReturn(const AProphecyAgent* Agent);
// Destination follows the current locomotion calf-clamp allowance, without
// changing the captured outgoing length or its existing finite return clock.
void SetLocomotionLengthTarget(const AProphecyAgent* Agent,FVector2D RequestedDeltaCm);
void Cancel(AProphecyAgent* Agent);
void Remove(AProphecyAgent* Agent);
bool Reapply(AProphecyAgent* Agent,FString& Error);
// Reuses the existing publication; unchanged joint ranges do not rebuild or wake.
bool Synchronize(AProphecyAgent* Agent,float LocomotionLeeway,FString& Error);
float Current(const AProphecyAgent* Agent);
}
