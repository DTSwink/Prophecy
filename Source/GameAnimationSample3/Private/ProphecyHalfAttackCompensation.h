#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyHalfAttackCompensation
{
bool Enabled(const AProphecyAgent* Agent);
bool Distributed(const AProphecyAgent* Agent);
bool Position(const AProphecyAgent* Agent);
float MinimumReach(const AProphecyAgent* Agent);
void CacheUpperTarget(const AProphecyAgent* Agent,const FVector& WorldTarget,const FVector& RealTarget,int32 Frame);
bool ReadUpperTarget(const AProphecyAgent* Agent,int32 Frame,FVector& Target,FVector* RealTarget=nullptr);
void ClearUpperTarget(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
void CaptureReset(const AProphecyAgent* Agent);
void RestoreReset(const AProphecyAgent* Agent);
void ForgetReset(const AProphecyAgent* Agent);
}
