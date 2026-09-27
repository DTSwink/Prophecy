#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyHalfAttackCompensation
{
bool Enabled(const AProphecyAgent* Agent);
bool Distributed(const AProphecyAgent* Agent);
bool Position(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
void CaptureReset(const AProphecyAgent* Agent);
void RestoreReset(const AProphecyAgent* Agent);
void ForgetReset(const AProphecyAgent* Agent);
}
