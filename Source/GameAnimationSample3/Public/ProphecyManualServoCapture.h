#pragma once

#include "CoreMinimal.h"

class AProphecyAgent;

/** Opt-in local fixture diagnostics. All external functions must run on the game thread. */
namespace ProphecyManualServoCapture
{
inline constexpr int32 MaxBodies = 32;

enum class EPublishFailure : uint8
{
    None,
    PoseUnavailable,
    CallbackUnavailable,
    InvalidReplayPacket,
    ReplayBodyUnavailable
};

struct FBoneTarget
{
    FName BoneName = NAME_None;
    FTransform ActualBoneWorld = FTransform::Identity;
    FTransform BodyFromBone = FTransform::Identity;
    FVector TargetPosition = FVector::ZeroVector;
    FQuat TargetRotation = FQuat::Identity;
    float LinearStrength = 0.0f;
    float AngularStrength = 0.0f;
};

struct FPacket
{
    uint64 Sequence = 0;                 // Successful publication sequence within this capture (one-based).
    uint64 SourceSequence = 0;           // Original sealed packet sequence during replay; zero for live publication.
    uint64 AttemptSequence = 0;          // Includes failed publication attempts.
    uint64 GameFrame = 0;
    float FrameDeltaSeconds = 0.0f;
    float MaximumSubstepSeconds = 0.0f;  // Published denominator input, not necessarily actual integration dt.
    int32 BodyCount = 0;
    FBoneTarget Bodies[MaxBodies];
};

struct FBodyStep
{
    bool bValid = false;
    FVector Position = FVector::ZeroVector; // Raw Chaos X immediately before the velocity rewrite.
    FQuat Rotation = FQuat::Identity;        // Raw Chaos R, not the game-thread projected transform.
    FVector LinearVelocityBefore = FVector::ZeroVector;
    FVector AngularVelocityBefore = FVector::ZeroVector;
    FVector LinearVelocityAfter = FVector::ZeroVector;
    FVector AngularVelocityAfter = FVector::ZeroVector;
};

struct FStep
{
    uint64 Sequence = 0;
    uint64 PacketSequence = 0;           // Maps body order to FPacket::Bodies.
    uint64 SourceSequence = 0;
    uint64 LatestAttemptSequence = 0;
    double CallbackSimTimeSeconds = 0.0;
    double CallbackDeltaSeconds = 0.0;  // SimCallback context value; not asserted to be internal substep dt.
    float DenominatorSeconds = 0.0f;
    int32 BodyCount = 0;
    bool bRepeatedPacket = false;        // Informational: expected when one publication spans multiple substeps.
    bool bStaleAfterFailedPublish = false;
    bool bUnrecordedPacket = false;
    FBodyStep Bodies[MaxBodies];
};

struct FCapture
{
    TArray<FPacket> Packets;
    TArray<FStep> Steps;
    int32 PacketCapacity = 0;
    int32 StepCapacity = 0;
    int32 PacketsRecorded = 0;
    int32 StepsRecorded = 0;
    uint64 PublishAttempts = 0;
    uint64 PublishedPackets = 0;
    uint64 FailedPublications = 0;
    uint64 ConsumedCallbacks = 0;
    uint64 RepeatedPacketConsumptions = 0;
    uint64 StalePacketConsumptions = 0;
    uint64 UnrecordedPacketConsumptions = 0;
    uint64 MissingBodySamples = 0;
    EPublishFailure LastPublishFailure = EPublishFailure::None;
    bool bPacketOverflow = false;
    bool bStepOverflow = false;
    bool bBodyOverflow = false;
};

/** Preallocate capture buffers and create/reuse the real callback. Requires a live simulating manual PhysicalMesh. */
GAMEANIMATIONSAMPLE3_API bool BeginCapture(AProphecyAgent* Agent, int32 MaxPackets, int32 MaxSteps, FString& OutError);
/** Snapshot without stopping. Copies under the callback's existing target lock; keep outside timing. */
GAMEANIMATIONSAMPLE3_API bool ReadCapture(AProphecyAgent* Agent, FCapture& OutCapture, FString& OutError);
/** Detach recording and move out the sealed buffers. Does not stop or alter the controller. Call before actor/world teardown. */
GAMEANIMATIONSAMPLE3_API bool EndCapture(AProphecyAgent* Agent, FCapture& OutCapture, FString& OutError);
/** Resolve recorded bone names to this actor's bodies, then publish exact recorded endpoints to the existing callback.
 * Requires bAutoPublishManualFollowerSubstepTargets=false. Never changes that flag, body state, or the velocity math. */
GAMEANIMATIONSAMPLE3_API bool PublishReplayPacket(AProphecyAgent* Agent, const FPacket& Packet, FString& OutError);
}
