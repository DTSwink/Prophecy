#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyAttackControls
{
bool IsStatic(const AProphecyAgent* Agent);
bool UsesRootBalancingTarget(const AProphecyAgent* Agent);
// Slash input layout: lower previous/current 41 each, upper previous/current 90 each.
inline void MakeHistoryStatic(TArrayView<float> State)
{
    check(State.Num() >= 262);
    FMemory::Memcpy(State.GetData(), State.GetData() + 41, 41 * sizeof(float));
    FMemory::Memcpy(State.GetData() + 82, State.GetData() + 172, 90 * sizeof(float));
}
bool ColliderRoles(FName Attack, TArray<FName>& Bones, bool& Sword);
bool ArmedBlocked(const AProphecyAgent* Agent);
void StartAttackTickCounter(const AProphecyAgent* Agent);
void FullAttackStarted(AProphecyAgent* Agent);
void LowerAttackFinished(const AProphecyAgent* Agent);
void BeginLowerReturn(const AProphecyAgent* Agent);
void CancelLowerReturn(const AProphecyAgent* Agent);
float RunBoost(const AProphecyAgent* Agent,float Normal);
void Remove(const AProphecyAgent* Agent);
void CaptureReset(const AProphecyAgent* Agent);
void RestoreReset(const AProphecyAgent* Agent);
void ForgetReset(const AProphecyAgent* Agent);
// Block only the transition into Armed. Never rewind an already committed strike.
inline void PhaseLatches(bool Block,bool Legacy,float PriorArmed,float PriorHit,
    float ArmRequest,float HitRequest,float Threshold,float& Armed,float& Hit)
{
    Hit=PriorHit>=.5f || (PriorArmed>=.5f && HitRequest>=Threshold) ? 1.f:0.f;
    Armed=PriorArmed>=.5f || (!Block && (ArmRequest>=Threshold || (Legacy && (Hit>=.5f || HitRequest>=Threshold)))) ? 1.f:0.f;
}
}
