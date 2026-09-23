#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyHandInertia
{
void Remove(const AProphecyAgent* Agent);
void ResetMotion(const AProphecyAgent* Agent);
void ResolveTarget(FTransform& Shoulder,FTransform& Elbow,FTransform& Wrist,
    const FTransform& Target,const FVector& Pole,double LowerLength);
bool IsActive(const AProphecyAgent* Agent, float WalkWeight, bool bAttack);
bool Apply(const AProphecyAgent* Agent, int32 Hand, float WalkWeight, bool bAttack, double Time, double Dt,
    const FTransform& PreviousRoot, const FTransform& Root, const FTransform& PreviousHand,
    FTransform& Shoulder, FTransform& Elbow, FTransform& Wrist, const FVector& Pole, double LowerLength);
}
