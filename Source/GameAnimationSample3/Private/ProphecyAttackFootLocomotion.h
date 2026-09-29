#pragma once
#include "ProphecyAttackFootLocomotionLibrary.h"
namespace ProphecyAttackFootLocomotion
{
struct FConfig { EProphecyAttackFootLocomotionMode Mode;float Distance,Height; };
struct FRun
{
    FConfig Config;int32 PoseId=INDEX_NONE;int32 Legs[2][4];uint8 Loco=0;bool Suspended=false;
};
uint8 Mask(const AProphecyAgent* Agent);
FRun* FindActive(const AProphecyAgent* Agent);
void Begin(const AProphecyAgent* Agent,int32 Id,TConstArrayView<FName> Names,
    TConstArrayView<FTransform> Pose,const FTransform& Carrier,const FVector& Target);
void Suspend(const AProphecyAgent* Agent,bool Half);
void End(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
void CaptureReset(const AProphecyAgent* Agent);
void RestoreReset(const AProphecyAgent* Agent);
void ForgetReset(const AProphecyAgent* Agent);
float WalkWeight(const FRun& Run,float Current);
// Separate sparse storage: no retained FConfig/FRun layout change for Live Coding.
struct FFreezeWindow { float XY[16]; };
float FreezeBlend(const AProphecyAgent* Agent);
void CaptureFreezeWindow(const AProphecyAgent* Agent,const float* Encoded);
void ClearFreezeWindow(const AProphecyAgent* Agent);
const FFreezeWindow* FindFreezeWindow(const AProphecyAgent* Agent);
// Returns feet newly handed to attack; cannot acquire a locomotion bit.
uint8 Step(FRun& Run,const FVector& Pelvis,const FVector& Target,float Floor,
    const FVector& Left,const FVector& Right);
// Positive durations retain the ownership bit until that foot's fade completes.
// Position weights are locomotion contributions; zero-duration releases retain
// the existing final locomotion feedback sample. Extra settings latch at entry.
uint8 Advance(const AProphecyAgent* Agent,FRun& Run,const FVector& Pelvis,const FVector& Target,float Floor,
    const FVector& Left,const FVector& Right,float (&Position)[2],float& AlphaRotation);
uint8 ReleaseAll(const AProphecyAgent* Agent);
// -1 means disabled for that foot. Clocks start at drag entry, not handoff.
void AdvancePoles(const AProphecyAgent* Agent,uint8 Remaining,float (&AttackAlpha)[2]);
}
