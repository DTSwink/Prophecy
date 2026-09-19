#include "ProphecyJoltVelocityServo.h"
#include "ProphecyJoltConversions.h"
#include "ProphecyJoltPHATSweeps.h"

THIRD_PARTY_INCLUDES_START
#include <Jolt/Physics/Body/BodyLock.h>
#include <Jolt/Physics/PhysicsSystem.h>
THIRD_PARTY_INCLUDES_END

namespace ProphecyJolt
{
namespace
{
struct FFollow { FVector Linear, Angular; };
using FBodyFollows = TMap<uint32, FFollow>;
// No modification of live servo/rig layouts. Writes only outside synchronous Update;
// the physics worker reads an immutable map, never game objects.
TMap<const FVelocityServo*, FBodyFollows> Follows;
TMap<const FVelocityServo*, TMap<uint32, FTransform>> TargetOffsets;

struct FVelocityRewrite
{
    JPH::Vec3 NativeLinear = JPH::Vec3::sZero();
    JPH::Vec3 NativeAngular = JPH::Vec3::sZero();
};

bool CalculateRewrite(const FVelocityServo::FTarget& Target, const JPH::Body& Body, float DenominatorSeconds,
    double TrajectoryElapsedSeconds, float IntegrationSeconds,
    FVelocityServo::FSample& Sample, FVelocityRewrite& Rewrite, const FFollow* Follow,
    const FTransform* TargetOffset)
{
    using namespace Conversions;
    Sample.PositionCm = FromJoltPosition(Body.GetPosition());
    Sample.Rotation = FromJoltRotation(Body.GetRotation());
    Sample.LinearBeforeCmPerSecond = FromJoltLinearVelocity(Body.GetLinearVelocity());
    Sample.AngularBeforeRadiansPerSecond = FromJoltAngularVelocity(Body.GetAngularVelocity());
    FVector Linear = Sample.LinearBeforeCmPerSecond;
    FVector Angular = Sample.AngularBeforeRadiansPerSecond;
    FVector TargetPositionCm = Target.TargetPositionCm;
    FQuat TargetRotation = Target.TargetRotation;
    if (Target.TrajectoryDurationSeconds > 0.0f)
    {
        const double Alpha = FMath::Clamp(TrajectoryElapsedSeconds / Target.TrajectoryDurationSeconds, 0.0, 1.0);
        TargetPositionCm = FMath::Lerp(Target.StartPositionCm, Target.TargetPositionCm, Alpha);
        TargetRotation = FQuat::Slerp(Target.StartRotation, Target.TargetRotation, Alpha).GetNormalized();
    }
    if (TargetOffset)
    {
        const FTransform Shifted = *TargetOffset * FTransform(TargetRotation, TargetPositionCm);
        TargetPositionCm = Shifted.GetLocation(); TargetRotation = Shifted.GetRotation();
    }
    // The authored target is the body origin; Jolt stores linear velocity at the COM.
    // Convert the requested origin velocity to COM velocity after calculating W below.
    if (Target.LinearStrength > 0.0f)
    {
        const FVector Desired = (TargetPositionCm - Sample.PositionCm) / DenominatorSeconds;
        Linear += (Desired - Linear) * Target.LinearStrength;
        // The listener runs before Jolt integrates gravity/forces. Match Chaos's
        // strength-scaled gravity cancellation without changing native gravity.
        Linear.Z += Target.GravityCompensationCmPerSecondSquared * IntegrationSeconds * Target.LinearStrength;
    }
    if (Target.AngularStrength > 0.0f)
    {
        FQuat Delta = TargetRotation * Sample.Rotation.Inverse();
        Delta.Normalize();
        if (Delta.W < 0.0) Delta = Delta * -1.0;
        FVector Axis = FVector::ForwardVector;
        float Angle = 0.0f;
        Delta.ToAxisAndAngle(Axis, Angle);
        const FVector Desired = Axis.GetSafeNormal() * (Angle / DenominatorSeconds);
        Angular += (Desired - Angular) * Target.AngularStrength;
    }
    if (Follow) Angular = Sample.AngularBeforeRadiansPerSecond
        + (Angular-Sample.AngularBeforeRadiansPerSecond)*Follow->Angular;
    if (Target.LinearStrength > 0.0f)
    {
        // Vcom = Vorigin + W x (COM - origin). Omitting this term makes the
        // joint solve oppose the requested rotation of bodies such as the hands.
        // Use the resulting W, including retained spin when the angular drive is off.
        // Scale with the linear drive so disabling it leaves COM velocity untouched.
        const FVector WorldCOMOffset = Sample.Rotation.RotateVector(
            FromJoltPosition(JPH::RVec3(Body.GetShape()->GetCenterOfMass())));
        Linear += Angular.Cross(WorldCOMOffset) * Target.LinearStrength;
    }
    if (Follow)
    {
        Linear = Sample.LinearBeforeCmPerSecond + (Linear-Sample.LinearBeforeCmPerSecond)*Follow->Linear;
        // Keep the separately configured gravity compensation, even when tracking is zero.
        if (Target.LinearStrength > 0.0f)
            Linear.Z += (1.-Follow->Linear.Z)*Target.GravityCompensationCmPerSecondSquared
                * IntegrationSeconds*Target.LinearStrength;
    }
    Rewrite.NativeLinear = ToJoltLinearVelocity(Linear);
    Rewrite.NativeAngular = ToJoltAngularVelocity(Angular);
    return !Linear.ContainsNaN() && !Angular.ContainsNaN()
        && !FromJoltDirection(Rewrite.NativeLinear).ContainsNaN()
        && !FromJoltDirection(Rewrite.NativeAngular).ContainsNaN()
        && FMath::IsFinite(Rewrite.NativeLinear.Length()) && FMath::IsFinite(Rewrite.NativeAngular.Length());
}

bool RequiresNativeWake(const FVelocityServo::FTarget& Target, const FVelocityRewrite& Rewrite)
{
    // Native velocity units/threshold; a disabled channel makes no setter call and cannot wake.
    return (Target.LinearStrength > 0.0f && !Rewrite.NativeLinear.IsNearZero())
        || (Target.AngularStrength > 0.0f && !Rewrite.NativeAngular.IsNearZero());
}

bool HasPendingTrajectoryMotion(const FVelocityServo::FTarget& Target)
{
    return Target.TrajectoryElapsedSeconds < Target.TrajectoryDurationSeconds
        && ((Target.LinearStrength > 0.0f && Target.StartPositionCm != Target.TargetPositionCm)
            || (Target.AngularStrength > 0.0f && !Target.StartRotation.Equals(Target.TargetRotation)));
}
}

bool FVelocityServo::Publish(TConstArrayView<FTarget> InTargets, float MaximumSubstepSeconds, FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread() || !FMath::IsFinite(MaximumSubstepSeconds) || MaximumSubstepSeconds <= 0.0f)
    { OutError = TEXT("Fixture servo publication requires the game thread and a positive finite denominator."); return false; }
    TArray<FTarget> UniformTargets;
    UniformTargets.Append(InTargets.GetData(), InTargets.Num());
    for (FTarget& Target : UniformTargets) Target.DenominatorSeconds = FMath::Max(MaximumSubstepSeconds, UE_SMALL_NUMBER);
    if (!PublishPerTarget(UniformTargets, OutError)) return false;
    DenominatorSeconds = FMath::Max(MaximumSubstepSeconds, UE_SMALL_NUMBER);
    return true;
}

bool FVelocityServo::PublishPerTarget(TConstArrayView<FTarget> InTargets, FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread())
    { OutError = TEXT("Servo publication requires the game thread outside Update."); return false; }
    TSet<uint32> UniqueBodies;
    for (const FTarget& Target : InTargets)
    {
        if (Target.Body.IsInvalid() || UniqueBodies.Contains(Target.Body.GetIndexAndSequenceNumber()) ||
            Target.TargetPositionCm.ContainsNaN() || Target.TargetRotation.ContainsNaN() || !Target.TargetRotation.IsNormalized() ||
            !FMath::IsFinite(Target.GravityCompensationCmPerSecondSquared) ||
            !FMath::IsFinite(Target.LinearStrength) || Target.LinearStrength < 0.0f ||
            !FMath::IsFinite(Target.AngularStrength) || Target.AngularStrength < 0.0f ||
            !FMath::IsFinite(Target.DenominatorSeconds) || Target.DenominatorSeconds <= 0.0f ||
            !FMath::IsFinite(Target.TrajectoryDurationSeconds) || Target.TrajectoryDurationSeconds < 0.0f ||
            (Target.TrajectoryDurationSeconds > 0.0f && (Target.StartPositionCm.ContainsNaN()
                || Target.StartRotation.ContainsNaN() || !Target.StartRotation.IsNormalized())))
        { OutError = TEXT("Servo targets require distinct valid bodies, finite endpoints, nonnegative strengths, positive finite denominators and valid optional trajectories."); return false; }
        UniqueBodies.Add(Target.Body.GetIndexAndSequenceNumber());
    }
    CommitValidatedTargets(InTargets);
    for (FTarget& Target : Targets) Target.TrajectoryElapsedSeconds = 0.0;
    return true;
}

void FVelocityServo::CommitValidatedTargets(TConstArrayView<FTarget> InTargets)
{
    check(IsInGameThread());
    Targets.Reset(InTargets.Num());
    Targets.Append(InTargets.GetData(), InTargets.Num());
    for (FTarget& Target : Targets) Target.DenominatorSeconds = FMath::Max(Target.DenominatorSeconds, UE_SMALL_NUMBER);
    Samples.SetNum(InTargets.Num()); // All allocation happens before Update.
    for (FSample& Sample : Samples) Sample = FSample();
    DenominatorSeconds = Targets.IsEmpty() ? 0.0f : Targets[0].DenominatorSeconds;
    for (const FTarget& Target : Targets)
        if (Target.DenominatorSeconds != DenominatorSeconds) { DenominatorSeconds = 0.0f; break; }
}

bool FVelocityServo::PrepareActivation(JPH::PhysicsSystem& Physics, FString& OutError, bool bUseNoLockIdleReads,
    float FirstStepSeconds)
{
    OutError.Reset();
    if (!IsInGameThread())
    { OutError = TEXT("Fixture servo activation preparation requires the game thread outside Update."); return false; }
    TArray<JPH::BodyID, TInlineAllocator<32>> BodiesToWake;
    const auto* BodyFollows = Follows.IsEmpty() ? nullptr : Follows.Find(this);
    const auto* Offsets = TargetOffsets.IsEmpty() ? nullptr : TargetOffsets.Find(this);
    const JPH::BodyLockInterface& ReadLocks = bUseNoLockIdleReads
        ? static_cast<const JPH::BodyLockInterface&>(Physics.GetBodyLockInterfaceNoLock())
        : static_cast<const JPH::BodyLockInterface&>(Physics.GetBodyLockInterface());
    // Validate every candidate before mutating any activation state. This pass does not write V/W.
    for (const FTarget& Target : Targets)
    {
        const JPH::BodyLockRead Lock(ReadLocks, Target.Body);
        if (!Lock.SucceededAndIsInBroadPhase() || !Lock.GetBody().IsDynamic())
        { ++InvalidBodies; OutError = TEXT("Fixture servo activation found an invalid/non-dynamic body."); return false; }
        const JPH::Body& Body = Lock.GetBody();
        if (Body.IsActive()) continue;
        FSample Sample;
        FVelocityRewrite Rewrite;
        const float H = Target.TrajectoryDurationSeconds > 0.0f && FirstStepSeconds > 0.0f
            ? FirstStepSeconds : Target.DenominatorSeconds;
        if (!CalculateRewrite(Target, Body, H, Target.TrajectoryElapsedSeconds + H,
            FirstStepSeconds > 0.0f ? FirstStepSeconds : H, Sample, Rewrite,
            BodyFollows ? BodyFollows->Find(Target.Body.GetIndexAndSequenceNumber()) : nullptr,
            Offsets ? Offsets->Find(Target.Body.GetIndexAndSequenceNumber()) : nullptr))
        { ++InvalidBodies; OutError = TEXT("Fixture servo sleeping-body candidate overflows native velocity precision."); return false; }
        if (RequiresNativeWake(Target, Rewrite) || HasPendingTrajectoryMotion(Target)) BodiesToWake.Add(Target.Body);
    }
    // No body locks remain held here. Ordinary BodyInterface activation takes its own write lock.
    // Waking before Update includes these bodies in its first gravity/force/drag pass. Jolt only
    // deactivates bodies in the final collision step, so immutable targets need one preflight.
    for (const JPH::BodyID Body : BodiesToWake) Physics.GetBodyInterface().ActivateBody(Body);
    return true;
}

void FVelocityServo::SetBodyFollow(JPH::BodyID Body, const FVector& Linear, const FVector& Angular)
{
    check(IsInGameThread());
    if (Linear == FVector::OneVector && Angular == FVector::OneVector) { RemoveBodyFollow(Body); return; }
    Follows.FindOrAdd(this).Add(Body.GetIndexAndSequenceNumber(), {Linear,Angular});
}
void FVelocityServo::RemoveBodyFollow(JPH::BodyID Body)
{
    check(IsInGameThread());
    if (auto* Map=Follows.Find(this))
    {
        Map->Remove(Body.GetIndexAndSequenceNumber());
        if (Map->IsEmpty()) Follows.Remove(this);
    }
}
void FVelocityServo::Clear()
{
    check(IsInGameThread());
    Targets.Reset();
    Samples.Reset();
    Invocations = 0;
    InvalidBodies = 0;
    LastIntegrationSeconds = 0.0f;
}

void FVelocityServo::SetBodyTargetOffset(JPH::BodyID Body, const FTransform& Offset)
{
    check(IsInGameThread());
    TargetOffsets.FindOrAdd(this).Add(Body.GetIndexAndSequenceNumber(), Offset);
}
void FVelocityServo::RemoveBodyTargetOffset(JPH::BodyID Body)
{
    check(IsInGameThread());
    if (auto* Map = TargetOffsets.Find(this))
    {
        Map->Remove(Body.GetIndexAndSequenceNumber());
        if (Map->IsEmpty()) TargetOffsets.Remove(this);
    }
}

void FVelocityServo::OnStep(const JPH::PhysicsStepListenerContext& Context)
{
    using namespace Conversions;
    if (Targets.IsEmpty()) { PHATSweeps::AfterServo(Context.mPhysicsSystem, Context.mDeltaTime); return; }
    ++Invocations;
    LastIntegrationSeconds = Context.mDeltaTime;
    const auto* BodyFollows = Follows.IsEmpty() ? nullptr : Follows.Find(this);
    const auto* Offsets = TargetOffsets.IsEmpty() ? nullptr : TargetOffsets.Find(this);
    for (int32 Index = 0; Index < Targets.Num(); ++Index)
    {
        FTarget& Target = Targets[Index];
        if (Target.TrajectoryDurationSeconds > 0.0f)
            Target.TrajectoryElapsedSeconds = FMath::Min(double(Target.TrajectoryDurationSeconds),
                Target.TrajectoryElapsedSeconds + Context.mDeltaTime);
        FSample& Sample = Samples[Index];
        Sample = FSample();
        // Jolt already holds body/constraint mutexes here. Do not lock again, add/remove bodies
        // or inspect UObjects. Any required wake happened before Update's active-body snapshot.
        JPH::BodyLockWrite Lock(Context.mPhysicsSystem->GetBodyLockInterfaceNoLock(), Target.Body);
        if (!Lock.SucceededAndIsInBroadPhase() || !Lock.GetBody().IsDynamic())
        { ++InvalidBodies; continue; }
        JPH::Body& Body = Lock.GetBody();
        FVelocityRewrite Rewrite;
        const float H = Target.TrajectoryDurationSeconds > 0.0f ? Context.mDeltaTime : Target.DenominatorSeconds;
        if (!CalculateRewrite(Target, Body, H, Target.TrajectoryElapsedSeconds, Context.mDeltaTime, Sample, Rewrite,
            BodyFollows ? BodyFollows->Find(Target.Body.GetIndexAndSequenceNumber()) : nullptr,
            Offsets ? Offsets->Find(Target.Body.GetIndexAndSequenceNumber()) : nullptr)
            || (!Body.IsActive() && RequiresNativeWake(Target, Rewrite)))
        { ++InvalidBodies; continue; }
        // Stock clamped setters enforce the body's captured caps without changing those limits.
        if (Target.LinearStrength > 0.0f) Body.SetLinearVelocityClamped(Rewrite.NativeLinear);
        if (Target.AngularStrength > 0.0f) Body.SetAngularVelocityClamped(Rewrite.NativeAngular);
        Sample.LinearAfterCmPerSecond = FromJoltLinearVelocity(Body.GetLinearVelocity());
        Sample.AngularAfterRadiansPerSecond = FromJoltAngularVelocity(Body.GetAngularVelocity());
        Sample.bValid = true;
    }
    // Ordered after ALL target velocities; a separate Jolt listener could race this servo.
    PHATSweeps::AfterServo(Context.mPhysicsSystem, Context.mDeltaTime);
}
}
