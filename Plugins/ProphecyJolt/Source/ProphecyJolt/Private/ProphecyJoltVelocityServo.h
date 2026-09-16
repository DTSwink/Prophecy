#pragma once

#include "CoreMinimal.h"

THIRD_PARTY_INCLUDES_START
#include <Jolt/Jolt.h>
#include <Jolt/Physics/Body/BodyID.h>
#include <Jolt/Physics/PhysicsStepListener.h>
THIRD_PARTY_INCLUDES_END

class FProphecyJoltWorldState;

namespace ProphecyJolt
{
/** Fixture listener. Owner publishes only outside synchronous PhysicsSystem::Update. */
class FVelocityServo final : public JPH::PhysicsStepListener
{
public:
    struct FTarget
    {
        JPH::BodyID Body;
        FVector TargetPositionCm = FVector::ZeroVector;
        FQuat TargetRotation = FQuat::Identity;
        float LinearStrength = 1.0f;
        float AngularStrength = 1.0f;
        float DenominatorSeconds = 1.f / 60.f;
        float GravityCompensationCmPerSecondSquared = 0.0f;
        FVector StartPositionCm = FVector::ZeroVector;
        FQuat StartRotation = FQuat::Identity;
        float TrajectoryDurationSeconds = 0.0f;
        // Runtime clock, retained by the owning rig between flattened packets.
        // Public publication starts it at zero; only owner recommits preserve it.
        double TrajectoryElapsedSeconds = 0.0;
    };
    struct FSample
    {
        bool bValid = false;
        FVector PositionCm = FVector::ZeroVector;
        FQuat Rotation = FQuat::Identity;
        FVector LinearBeforeCmPerSecond = FVector::ZeroVector;
        FVector AngularBeforeRadiansPerSecond = FVector::ZeroVector;
        FVector LinearAfterCmPerSecond = FVector::ZeroVector;
        FVector AngularAfterRadiansPerSecond = FVector::ZeroVector;
    };

    // Legacy uniform-h publication; the flattened world path uses one explicit denominator per target.
    bool Publish(TConstArrayView<FTarget> InTargets, float MaximumSubstepSeconds, FString& OutError);
    bool PublishPerTarget(TConstArrayView<FTarget> InTargets, FString& OutError);
    // Immediately before synchronous Update: wake moving targets before Jolt snapshots active bodies
    // for gravity/drag. Targets/body state must have one owner until Update completes.
    // The opt-in read policy requires that same exclusive owner; activation still uses ordinary locks.
    bool PrepareActivation(JPH::PhysicsSystem& Physics, FString& OutError, bool bUseNoLockIdleReads = false,
        float FirstStepSeconds = 0.0f);
    void Clear();
    // Sparse opt-in world-axis tracking weights; retained when packets are rebuilt.
    void SetBodyFollow(JPH::BodyID Body, const FVector& Linear, const FVector& Angular);
    void RemoveBodyFollow(JPH::BodyID Body);
    virtual void OnStep(const JPH::PhysicsStepListenerContext& Context) override;
    const TArray<FSample>& GetLastSamples() const { return Samples; }
    uint64 GetInvocationCount() const { return Invocations; }
    uint64 GetInvalidBodyCount() const { return InvalidBodies; }
    float GetLastIntegrationSeconds() const { return LastIntegrationSeconds; }
    // Legacy diagnostic only; zero denotes an empty or mixed-h flattened packet.
    float GetDenominatorSeconds() const { return DenominatorSeconds; }

private:
    friend class ::FProphecyJoltWorldState;
    // Only the synchronous native owner may concatenate already validated, disjoint rig packets.
    // All other callers enter through Publish/PublishPerTarget and retain their full preflight.
    void CommitValidatedTargets(TConstArrayView<FTarget> InTargets);

    TArray<FTarget> Targets;
    TArray<FSample> Samples;
    float DenominatorSeconds = 1.f / 60.f;
    float LastIntegrationSeconds = 0.0f;
    uint64 Invocations = 0;
    uint64 InvalidBodies = 0;
};
}
