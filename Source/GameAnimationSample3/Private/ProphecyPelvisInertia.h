#pragma once
#include "CoreMinimal.h"
#include "Containers/ArrayView.h"
class AProphecyAgent;
struct FBodyInstance;
namespace ProphecyPelvisInertia
{
void Remove(const AProphecyAgent* Agent);
void ResetMotion(const AProphecyAgent* Agent);
void SynchronizeJolt(const AProphecyAgent* Agent);
bool GetBodyFollow(const AProphecyAgent* Agent, FVector& Linear, FVector& Angular);
// Cheap gate before constructing geometry/carriers or doing any leg work.
bool HasTarget(const AProphecyAgent* Agent);
// Caller writes the result into lower policy state and resolves legs before upper inference.
bool ApplyTarget(const AProphecyAgent* Agent, double Time, double StepSeconds,
    const FTransform& PreviousCarrier, const FTransform& Carrier,
    FTransform& PreviousPelvis, FTransform& Pelvis);
bool ApplyChaosDrive(const AProphecyAgent* Agent, FName Bone, FBodyInstance* Body,
    const FTransform& Target, float Dt, float LinearScale, float AngularScale,
    bool bCancelGravity, float GravityZ);
}
