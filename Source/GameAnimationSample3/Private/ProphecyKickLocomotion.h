#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyKickLocomotion
{
inline int32 Side(FName Attack) { return Attack==TEXT("kickL") ? 0 : Attack==TEXT("kickR") ? 1 : INDEX_NONE; }
void Begin(AProphecyAgent* Agent,FName Attack);
void End(const AProphecyAgent* Agent);
uint8 DragMask(const AProphecyAgent* Agent,FName Attack);
// Only the hidden running leg; the actual pelvis and supporting leg stay shared.
struct FRunLegFrame { float Leg[16]; FVector3f Root; float Yaw; };
struct FRunLegHistory { FRunLegFrame Previous,Current; int32 Side=INDEX_NONE; };
FRunLegHistory& SaveRunLeg(const AProphecyAgent* Agent);
const FRunLegHistory* FindRunLeg(const AProphecyAgent* Agent);
void ClearRunLeg(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
void CaptureReset(const AProphecyAgent* Agent);
void RestoreReset(const AProphecyAgent* Agent);
void ForgetReset(const AProphecyAgent* Agent);
}
