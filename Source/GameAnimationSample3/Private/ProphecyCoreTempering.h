#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyCoreTempering
{
float Rotation(const AProphecyAgent* Agent);
void Begin(const AProphecyAgent* Agent);
void CancelMotion(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
void CaptureReset(const AProphecyAgent* Agent);
void RestoreReset(const AProphecyAgent* Agent);
void ForgetReset(const AProphecyAgent* Agent);
}
