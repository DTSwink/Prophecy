#pragma once
#include "ProphecyNNPolicyBlend.h"

namespace ProphecyAttackRecovery
{
struct FWeights
{
    float Pelvis=1.f, Left=1.f, Right=1.f;
    FWeights() = default;
    explicit FWeights(float W) : Pelvis(W),Left(W),Right(W) {}
    bool NeedsWalk() const { return Pelvis>0 || Left>0 || Right>0; }
    bool NeedsRun() const { return Pelvis<1 || Left<1 || Right<1; }
    bool NeedsBoth() const { return NeedsWalk() && NeedsRun(); }
    FVector2f Legs() const { return FVector2f(Left,Right); }
};
void Begin(const AProphecyAgent* Agent,FName Attack=NAME_None);
void Cancel(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
void NotifyEnded(AProphecyAgent* Agent,FName Attack,bool Half,bool ReturningToLocomotion);
bool IsEndEvent(const AProphecyAgent* Agent);
// Overlay the normal selection without changing its ordinary blend state.
void Step(const AProphecyAgent* Agent, float NormalWalkWeight, FWeights& Out);
}
