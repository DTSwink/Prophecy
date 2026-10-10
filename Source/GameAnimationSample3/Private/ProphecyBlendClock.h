#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;

// Authored blend seconds mean 60 unpaused world ticks, regardless of frame dt
// or time dilation. Only explicitly active blends subscribe to this clock.
namespace ProphecyBlendClock
{
enum class EKind : uint8 { Tempering, Profiles, Policy, Recovery, FeetTempering, PelvisTempering, KickBalance, LeftHandTempering, RightHandTempering, HandRecovery, CoreTempering, SlashReturn, UpperBodyInertia, LegReconstruction, LeftAttackFootHandoff, RightAttackFootHandoff, LeftAttackFootPole, RightAttackFootPole, ArmedUpperPose, ArmRepellantCone, AttackStartHands, FKReturn, Fists, ModeTransition, AnimationLayer, AttackStartFKCore, AttackMotionInertia, GhostLocoInertia, GetUp };
constexpr double TickSeconds = 1.0 / 60.0;
inline float TickBudget(bool Paused, float FrameDelta)
{ return !Paused && FrameDelta > 0 ? float(TickSeconds) : 0.f; }
void Start(const AProphecyAgent* Agent, EKind Kind, double DurationSeconds=0);
void Ensure(const AProphecyAgent* Agent, EKind Kind);
double Consume(const AProphecyAgent* Agent, EKind Kind);
void Stop(const AProphecyAgent* Agent, EKind Kind);
void Remove(const AProphecyAgent* Agent);
}
