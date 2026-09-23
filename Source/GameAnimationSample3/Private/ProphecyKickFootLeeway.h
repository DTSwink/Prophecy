#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyKickFootLeeway
{
void Begin(AProphecyAgent* Agent,FName Attack);
void End(AProphecyAgent* Agent,bool RecoverPose=true);
void CancelPoseRecovery(const AProphecyAgent* Agent);
// Signed, independently captured length differences; zero outside the finite return.
float ReturningLengthDeltaCm(const AProphecyAgent* Agent,int32 Side);
void Cancel(AProphecyAgent* Agent);
void Remove(AProphecyAgent* Agent);
bool Reapply(AProphecyAgent* Agent,FString& Error);
float Current(const AProphecyAgent* Agent);
}
