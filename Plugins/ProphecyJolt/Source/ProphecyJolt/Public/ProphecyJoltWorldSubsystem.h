#pragma once

#include "CoreMinimal.h"
#include "Engine/EngineTypes.h"
#include "Subsystems/WorldSubsystem.h"
#include "ProphecyJoltWorldSubsystem.generated.h"

struct FProphecyJoltRigSnapshot;
struct FProphecyJoltRigJoint;
class FProphecyJoltPreparedRig;
class UPrimitiveComponent;
struct FProphecyJoltBodySnapshot;
class FProphecyJoltPreparedBody;
struct FProphecyJoltStaticBodySnapshot;
class FProphecyJoltPreparedStaticBody;

enum class EProphecyJoltWorldResult : uint8
{
    Success,
    WrongThread,
    UnsupportedWorld,
    WorldEnding,
    NotInitialized,
    AlreadyInitialized,
    Busy,
    InvalidArgument,
    RuntimeUnavailable,
    CapacityExceeded,
    InvalidHandle,
    AssociationUnavailable,
    ShapeCreationFailed,
    PhysicsFailure
};

struct FProphecyJoltWorldStatus
{
    EProphecyJoltWorldResult Code = EProphecyJoltWorldResult::Success;
    FString Message;
    bool IsSuccess() const { return Code == EProphecyJoltWorldResult::Success; }
};

/** Small-fixture resource settings. These are not production physics or collision-channel defaults. */
struct FProphecyJoltWorldSettings
{
    FVector GravityCmPerSecondSquared = FVector(0.0, 0.0, -981.0);
    uint32 MaxBodies = 256;
    uint32 MaxBodyPairs = 1024;
    uint32 MaxContactConstraints = 1024;
    uint32 TempAllocatorBytes = 8 * 1024 * 1024;
    int32 WorkerThreads = 1;
    // Interned simulation profiles are retained until shutdown; 65535 is the pinned 16-bit layer limit.
    uint32 MaxCollisionProfiles = 65535;
    uint32 MaxGenericJoints = 1024;
    uint32 MaxSuppressedBodyPairs = 4096;
};

/** Adapter identity only. A Jolt BodyID is deliberately not exposed. */
struct FProphecyJoltBodyHandle
{
    FGuid WorldLifetime;
    int32 Slot = INDEX_NONE;
    uint64 Generation = 0;
    bool IsSet() const { return WorldLifetime.IsValid() && Slot >= 0 && Generation != 0; }
};

/** Owns one complete rig in this world. Independent of capture identity and native BodyID. */
struct FProphecyJoltRigHandle
{
    FGuid WorldLifetime;
    int32 Slot = INDEX_NONE;
    uint64 Generation = 0;
    bool IsSet() const { return WorldLifetime.IsValid() && Slot >= 0 && Generation != 0; }
};

/** An independently owned joint between two existing bodies; no native constraint pointer escapes. */
struct FProphecyJoltJointHandle
{
    FGuid WorldLifetime;
    int32 Slot = INDEX_NONE;
    uint64 Generation = 0;
    bool IsSet() const { return WorldLifetime.IsValid() && Slot >= 0 && Generation != 0; }
};

enum class EProphecyJoltJointType : uint8 { Fixed, HardSixDOF };
enum class EProphecyJoltAxisMotion : uint8 { Locked, Free, Limited };
enum class EProphecyJoltSwingGeometry : uint8 { Cone, Pyramid };

struct FProphecyJoltAxisLimit
{
    EProphecyJoltAxisMotion Motion = EProphecyJoltAxisMotion::Locked;
    double Minimum = 0.0;
    double Maximum = 0.0;
};

struct FProphecyJoltJointDrive
{
    bool bPosition = false, bVelocity = false, bAcceleration = true;
    float Stiffness = 0, Damping = 0, MaximumForce = 0; // UE cm/kg units; 0 maximum means unlimited.
};

/** Literal A/B order, unlike the separate UE PHAT child/parent importer. Frames are rigid body-origin
 * local transforms in cm. Hard limits use independent translation XYZ (cm), twist X and swing Y/Z
 * (radians). Cone swing is symmetric; pyramid swing permits asymmetry. Neither is an Euler-angle box.
 * Limited angular ranges entering stock Jolt's internal 0.5/179.5 degree lock/free thresholds are
 * rejected. Optional SixDOF drives and soft translation springs are explicit settings.
 * Breaking is handled by the gameplay constraint bridge using native reaction readback.
 * Creation does not implicitly snap bodies or change their velocities.
 */
struct FProphecyJoltJointSettings
{
    FProphecyJoltBodyHandle BodyA;
    FProphecyJoltBodyHandle BodyB;
    FTransform FrameA = FTransform::Identity;
    FTransform FrameB = FTransform::Identity;
    EProphecyJoltJointType Type = EProphecyJoltJointType::Fixed;
    EProphecyJoltSwingGeometry SwingGeometry = EProphecyJoltSwingGeometry::Cone;
    FProphecyJoltAxisLimit Translation[3];
    FProphecyJoltAxisLimit Rotation[3];
    FProphecyJoltJointDrive Drives[6]; // translation XYZ, then twist X / swing YZ.
    FVector PositionTargetCm = FVector::ZeroVector;
    FVector VelocityTargetCmPerSecond = FVector::ZeroVector;
    FQuat OrientationTarget = FQuat::Identity;
    FVector AngularVelocityTargetRadians = FVector::ZeroVector;
    bool bSoftTranslation = false;
    float TranslationStiffness = 0, TranslationDamping = 0;
    // UE standard components use one circular/spherical radius for 2+ Limited axes.
    // False preserves the generic API's independent per-axis intervals.
    bool bRadialTranslation = false;
};

/** Explicit temporary simulation exclusion. Queries and existing PHAT/channel policy are unchanged. */
struct FProphecyJoltBodyPair
{
    FProphecyJoltBodyHandle A;
    FProphecyJoltBodyHandle B;
};

/** Closest hit against the current native fixture geometry. */
struct FProphecyJoltRayHit
{
    FProphecyJoltBodyHandle Handle;
    FVector PositionCm = FVector::ZeroVector;
    FVector Normal = FVector::ZeroVector;
    float Fraction = 1.0f;
    // Opaque Jolt shape path, valid with this body/shape lifetime. This is NOT a UE FaceIndex.
    uint32 NativeSubShapeId = MAX_uint32;
};

/** Units use the UE numeric basis: cm, kg, seconds and radians. No scale or kinematic bodies yet.
 * Unlisted BodyCreationSettings retain pinned Jolt defaults, including discrete collision and velocity
 * caps (500 m/s linear and 15*pi rad/s angular). This is a fixture API, not the project body adapter.
 */
struct FProphecyJoltFixtureBodySettings
{
    FVector PositionCm = FVector::ZeroVector;
    FQuat Rotation = FQuat::Identity;
    bool bDynamic = true;
    double MassKg = 1.0;
    float Friction = 0.2f;
    float Restitution = 0.0f;
    float LinearDamping = 0.0f;
    float AngularDamping = 0.0f;
    bool bAllowSleeping = false;
    // Optional identity association only; this object is never owned, moved or otherwise mutated.
    UObject* AssociatedObject = nullptr;
    // Unset preserves fixture defaults: static -> WorldStatic, dynamic -> PhysicsBody.
    // Project adapters must supply the captured effective channel, not infer one from motion type.
    TOptional<ECollisionChannel> ObjectChannel;
    // Only bilateral Block responses create solver contacts. Overlap is nonblocking; overlap events
    // and UE query-channel filtering are not implemented by this fixture API.
    FCollisionResponseContainer CollisionResponses = FCollisionResponseContainer(ECR_Block);
};

struct FProphecyJoltPhysicsCommand;

struct FProphecyJoltBodyState
{
    FVector PositionCm = FVector::ZeroVector;
    FVector CenterOfMassPositionCm = FVector::ZeroVector;
    FQuat Rotation = FQuat::Identity;
    FVector CenterOfMassVelocityCmPerSecond = FVector::ZeroVector;
    FVector AngularVelocityRadiansPerSecond = FVector::ZeroVector;
    bool bDynamic = false;
    bool bActive = false;
};

struct FProphecyJoltRigVelocityTarget
{
    FProphecyJoltBodyHandle Handle;
    FVector TargetPositionCm = FVector::ZeroVector;
    FQuat TargetRotation = FQuat::Identity;
    float LinearStrength = 1.0f;
    float AngularStrength = 1.0f;
    // Optional authored motion over the publication interval. Zero keeps the
    // existing fixed endpoint/caller-denominator controller semantics.
    FVector StartPositionCm = FVector::ZeroVector;
    FQuat StartRotation = FQuat::Identity;
    float TrajectoryDurationSeconds = 0.0f;
    // World-Z acceleration before LinearStrength scaling; zero disables compensation.
    float GravityCompensationCmPerSecondSquared = 0.0f;
};

struct FProphecyJoltCollisionUpdate
{
    FProphecyJoltBodyHandle Handle;
    ECollisionChannel ObjectChannel = ECC_PhysicsBody;
    FCollisionResponseContainer Responses = FCollisionResponseContainer(ECR_Block);
};

struct FProphecyJoltBodyMaterial
{
    float Friction = 0.0f;
    float Restitution = 0.0f;
    uint8 FrictionCombineMode = 0;
    uint8 RestitutionCombineMode = 0;
};

struct FProphecyJoltMaterialUpdate
{
    FProphecyJoltBodyHandle Handle;
    FProphecyJoltBodyMaterial Material;
};

struct FProphecyJoltRigServoSample
{
    FProphecyJoltBodyHandle Handle;
    bool bValid = false;
    FVector PositionCm = FVector::ZeroVector;
    FQuat Rotation = FQuat::Identity;
    FVector LinearBeforeCmPerSecond = FVector::ZeroVector;
    FVector AngularBeforeRadiansPerSecond = FVector::ZeroVector;
    FVector LinearAfterCmPerSecond = FVector::ZeroVector;
    FVector AngularAfterRadiansPerSecond = FVector::ZeroVector;
};

struct FProphecyJoltRigServoState
{
    TArray<FProphecyJoltRigServoSample> Samples;
    uint64 InvocationCount = 0;
    uint64 InvalidBodyCount = 0;
    float LastIntegrationSeconds = 0.0f;
    float DenominatorSeconds = 0.0f;
};

/** A completed synchronous snapshot. Does not claim recoverable OOM or internal solver-contact counts. */
struct FProphecyJoltWorldDiagnostics
{
    bool bInitialized = false;
    bool bFaulted = false;
    // Actual world-owned policy for the three idle read paths; ordinary locking is the default.
    bool bNoLockIdleBodyReads = false;
    FGuid WorldLifetime;
    FProphecyJoltWorldSettings Settings;
    uint64 CompletedSteps = 0;
    double SimulatedSeconds = 0.0;
    double LastStepWallSeconds = 0.0;
    // Disjoint wall sections inside Step. PhysicsUpdate includes the native servo listener;
    // post-update validation is outside the historical LastStepWallSeconds interval.
    double LastServoPrepareWallSeconds = 0.0;
    double LastActivationWallSeconds = 0.0;
    double LastPhysicsUpdateWallSeconds = 0.0;
    double LastServoCaptureWallSeconds = 0.0;
    double LastValidationWallSeconds = 0.0;
    float LastRequestedDeltaSeconds = 0.0f;
    int32 LastCollisionSteps = 0;
    uint32 LastUpdateErrorBits = 0;
    uint32 BodyCount = 0;
    uint32 ActiveRigidBodyCount = 0;
    uint32 ConstraintCount = 0;
    uint32 CollisionProfileCount = 0;
    uint32 GenericJointCount = 0;
    uint32 SuppressedBodyPairCount = 0;
    int32 JobConcurrency = 0;
    uint64 BodyCreationFailures = 0;
    uint64 TempPeakBytes = 0;
    uint64 TempCurrentBytes = 0;
    uint64 TempAllocationCount = 0;
    FString Failure;
};

class FProphecyJoltWorldState;
struct FProphecyJoltWorldStateDeleter
{
    void operator()(FProphecyJoltWorldState* State) const;
};

/** No tick function or delegates drive physics. Only an explicit InitializeSimulation/Step caller can do so. */
UCLASS()
class PROPHECYJOLT_API UProphecyJoltWorldSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()

public:
    UProphecyJoltWorldSubsystem();
    virtual ~UProphecyJoltWorldSubsystem() override;

    /** Allowed contact penetration in cm for the entire shared Jolt world. Default 2.
     * Try 0.1 for less visible sinking. Zero is accepted; this is not a hard overlap cap.
     * Call once or when changing it; no Tick needed. May be set before Jolt initializes.
     * Does not enable CCD or change collision substeps. Negative/nonfinite values fail. */
    static bool SetJoltPenetrationSlop(const UObject* WorldContextObject, float SlopCm = 2.0f);

    /** Current world penetration allowance in cm; default 2 before customization. */
    static float GetJoltPenetrationSlop(const UObject* WorldContextObject);

    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void OnWorldEndPlay(UWorld& InWorld) override;
    virtual void PreDeinitialize() override;
    virtual void Deinitialize() override;
    virtual void BeginDestroy() override;

    FProphecyJoltWorldStatus InitializeSimulation(const FProphecyJoltWorldSettings& Settings);
    // Explicit shutdown permits reinitialization until world/subsystem teardown begins.
    FProphecyJoltWorldStatus ShutdownSimulation();
    FProphecyJoltWorldStatus Step(float DeltaSeconds, int32 CollisionSteps);
#if !UE_BUILD_SHIPPING
    // Explicit console-only experiment; no tick registration or production sampling.
    void RunContactExperiment(const TArray<FString>& Args);
#endif
    FProphecyJoltWorldStatus CreateSphere(double RadiusCm, const FProphecyJoltFixtureBodySettings& Settings,
        FProphecyJoltBodyHandle& OutHandle);
    // Convex radius is part of the requested box and is never silently clamped.
    FProphecyJoltWorldStatus CreateBox(const FVector& HalfExtentCm, double ConvexRadiusCm,
        const FProphecyJoltFixtureBodySettings& Settings, FProphecyJoltBodyHandle& OutHandle);
    // Creates one independent dynamic body from matching sealed capture/preparation. Native geometry
    // already contains scale and COM; component visual scale is never applied a second time.
    // Source association must be live and in this world when supplied; synthetic captures may omit it.
    // All outputs are cleared on failure. CCD selects stock Jolt LinearCast; MACD remains unsupported.
    FProphecyJoltWorldStatus CreateBody(const FProphecyJoltBodySnapshot& Snapshot, const FProphecyJoltPreparedBody& Prepared,
        FProphecyJoltBodyHandle& OutHandle, TArray<FString>& OutCoverageNotes);
    // Static-only counterpart using exact prepared simulation geometry, with no mass/velocity data.
    // The caller retains capture-time instance provenance and owns later source-change/removal handling.
    FProphecyJoltWorldStatus CreateStaticBody(const FProphecyJoltStaticBodySnapshot& Snapshot,
        const FProphecyJoltPreparedStaticBody& Prepared, FProphecyJoltBodyHandle& OutHandle, TArray<FString>& OutCoverageNotes);
    // Multiple independently owned rigs share one Step and captured bilateral Block masks.
    // Exactly the captured PHAT/current-joint disabled pairs are excluded within each rig.
    // All outputs are cleared on failure; handles follow Snapshot.Bodies order.
    FProphecyJoltWorldStatus CreateRig(const FProphecyJoltRigSnapshot& Snapshot, const FProphecyJoltPreparedRig& Prepared,
        FProphecyJoltRigHandle& OutRig, TArray<FProphecyJoltBodyHandle>& OutBodyHandles, TArray<FString>& OutCoverageNotes,
        bool bPlayerSwingLimits = false);
    // Event-driven possession policy. Only eligible limited swing joints get the extra solver row.
    // Retains native SixDOF objects/bodies; no added tick or worker-side player checks.
    FProphecyJoltWorldStatus SetRigPlayerSwingLimits(const FProphecyJoltRigHandle& Rig, bool bEnabled);
    // 0 retains PHAT plus attached-sword policy; 1 forces Discrete; 2 forces LinearCast.
    FProphecyJoltWorldStatus SetRigCCDMode(const FProphecyJoltRigHandle& Rig, uint8 Mode);
    // Zero restores world defaults. The highest override in a connected island determines its work.
    FProphecyJoltWorldStatus SetRigSolverIterations(const FProphecyJoltRigHandle& Rig, int32 Velocity, int32 Position);
    // Removes only this rig, constraints before bodies. Stale/cross-world identity is rejected.
    FProphecyJoltWorldStatus DestroyRig(const FProphecyJoltRigHandle& Rig);
    // Atomic idle-GT channel update. Retains native bodies/joints/velocities and wakes
    // affected contacts. Bilateral Block is required; Ignore/Overlap are nonblocking.
    FProphecyJoltWorldStatus UpdateBodyCollision(TConstArrayView<FProphecyJoltCollisionUpdate> Updates);
    // Atomic preflight; event-driven changes only, outside the synchronous native step.
    FProphecyJoltWorldStatus UpdateBodyMaterials(TConstArrayView<FProphecyJoltMaterialUpdate> Updates);
    FProphecyJoltWorldStatus ReadBodyMaterial(const FProphecyJoltBodyHandle& Handle, FProphecyJoltBodyMaterial& Out) const;
    // Effective solver policy; nonblocking channels are reported as Ignore.
    FProphecyJoltWorldStatus ReadBodyCollision(const FProphecyJoltBodyHandle& Handle, FProphecyJoltCollisionUpdate& Out) const;
    // Ownership remains inspectable when the world is faulted/ending, outside Update and on the game thread.
    bool OwnsRig(const FProphecyJoltRigHandle& Rig) const;
    // Reflected event-driven bridge; INDEX_NONE selects every anatomical joint.
    UFUNCTION()
    bool SetRigJointDamping(FGuid WorldLifetime, int32 BodySlot, int64 BodyGeneration, int32 SourceConstraintIndex,
        float Damping, FString& OutError);
    // Atomic idle-GT update of only swing/twist motion modes and angle fields. Pass every joint in
    // captured order with unchanged identity/endpoints/frames; other profile fields are not applied.
    // Native constraints and bodies are retained. Effective no-ops do not wake bodies/reset warm starts.
    FProphecyJoltWorldStatus UpdateRigAngularLimits(const FProphecyJoltRigHandle& Rig,
        TConstArrayView<FProphecyJoltRigJoint> Joints);
    // Captured descriptors with current native angular modes/limited angles. Other fields are provenance.
    FProphecyJoltWorldStatus ReadRigAngularLimits(const FProphecyJoltRigHandle& Rig,
        TArray<FProphecyJoltRigJoint>& OutJoints, int32* OutSpeculativeJointCount = nullptr) const;
    // Idle-GT runtime suppression layers over captured PHAT/current-joint exclusions. Enabling a
    // layer removes only its own suppression and never enables an authored-disabled pair.
    // Native bodies/joints/groups remain intact; changed contacts are invalidated and endpoints woken.
    FProphecyJoltWorldStatus SetRigSelfCollisionEnabled(const FProphecyJoltRigHandle& Rig, bool bEnabled);
    // Each selected body is suppressed against EVERY other body in its own rig. Complete index
    // validation precedes mutation; duplicate indices are harmless and an empty list is a no-op.
    FProphecyJoltWorldStatus SetRigBodiesSelfCollisionEnabled(const FProphecyJoltRigHandle& Rig,
        TConstArrayView<int32> BodyIndices, bool bEnabled);
    FProphecyJoltWorldStatus SetRigBodyPairSelfCollisionEnabled(const FProphecyJoltRigHandle& Rig,
        int32 Body1Index, int32 Body2Index, bool bEnabled);
    // Clears all three runtime suppression layers, restoring the captured authored self-collision filter.
    FProphecyJoltWorldStatus ResetRigSelfCollision(const FProphecyJoltRigHandle& Rig);
    // Reads this rig's effective pair filter, excluding bilateral object masks and generic-joint filters.
    // Distinct, valid body indices are required; output is false on failure.
    FProphecyJoltWorldStatus ReadRigBodyPairSelfCollisionEnabled(const FProphecyJoltRigHandle& Rig,
        int32 Body1Index, int32 Body2Index, bool& bOutEnabled) const;
    // Replaces only this rig's packet. Empty packets disable its servo; other rigs retain their packets.
    FProphecyJoltWorldStatus PublishRigVelocityTargets(const FProphecyJoltRigHandle& Rig,
        TConstArrayView<FProphecyJoltRigVelocityTarget> Targets, float MaximumSubstepSeconds);
    FProphecyJoltWorldStatus ReadRigServoSamples(const FProphecyJoltRigHandle& Rig, FProphecyJoltRigServoState& OutState) const;
    // Legacy fixture creation refuses an existing rig; wrappers subsequently address only that created rig.
    // Uses the same bilateral Block masks and per-rig exclusions as CreateRig; overlap events remain deferred.
    // Handles follow Snapshot.Bodies order. SourceWorld/SourceComponent are provenance, not associations.
    FProphecyJoltWorldStatus CreateRigFixture(const FProphecyJoltRigSnapshot& Snapshot, const FProphecyJoltPreparedRig& Prepared,
        TArray<FProphecyJoltBodyHandle>& OutBodyHandles, TArray<FString>& OutCoverageNotes);
    // Idempotent legacy teardown; clears that rig's packet/constraints/bodies and invalidates its handles.
    FProphecyJoltWorldStatus DestroyRigFixture();
    // Identity-only ownership check, in original rig order. Available while faulted/ending for safe cleanup.
    // Requires the game thread and no Update in progress; never treats stale/replacement handles as ownership.
    bool OwnsRigFixture(TConstArrayView<FProphecyJoltBodyHandle> Handles) const;
    // h is the captured controller denominator, independent of Step interval/collision-step count.
    FProphecyJoltWorldStatus PublishRigFixtureVelocityTargets(TConstArrayView<FProphecyJoltRigVelocityTarget> Targets, float MaximumSubstepSeconds);
    FProphecyJoltWorldStatus ReadRigFixtureServoSamples(FProphecyJoltRigServoState& OutState) const;
    FProphecyJoltWorldStatus ReadBody(const FProphecyJoltBodyHandle& Handle, FProphecyJoltBodyState& OutState) const;
    // Game-thread, idle-world closest segment query over all fixture layers; no UE channel/complex-trace filtering.
    // A miss succeeds with bOutHit=false and cleared OutHit. Stock Jolt treats convex interiors as fraction-zero hits.
    FProphecyJoltWorldStatus RayCast(const FVector& StartCm, const FVector& EndCm,
        FProphecyJoltRayHit& OutHit, bool& bOutHit) const;
    FProphecyJoltWorldStatus ExecutePhysicsCommand(const FProphecyJoltBodyHandle& Handle,
        const FProphecyJoltPhysicsCommand& Command);
    FProphecyJoltWorldStatus AddPointImpulse(const FProphecyJoltBodyHandle& Handle,
        const FVector& ImpulseKgCmPerSecond, const FVector& WorldPointCm);
    // Writes dynamic-body COM velocity and world angular velocity; captured Jolt speed caps apply.
    // bWake=false preserves activation state, including a sleeping body with a stored velocity.
    // Per-world-axis servo correction weights (0..1); all-one removes the override.
    // External forces, gravity, damping and constraint impulses remain native.
    FProphecyJoltWorldStatus SetBodyServoFollow(const FProphecyJoltBodyHandle& Handle,
        const FVector& Linear, const FVector& Angular);
    FProphecyJoltWorldStatus SetBodyVelocity(const FProphecyJoltBodyHandle& Handle,
        const FVector& CenterOfMassVelocityCmPerSecond, const FVector& AngularVelocityRadiansPerSecond, bool bWake);
    // Identity-only inspection remains available while faulted/ending, on GT and outside Update.
    bool OwnsBody(const FProphecyJoltBodyHandle& Handle) const;
    // Safe idle cleanup remains available while faulted/ending. Rig bodies require DestroyRig.
    FProphecyJoltWorldStatus DestroyBody(const FProphecyJoltBodyHandle& Handle);
    // Suppression pairs are deduplicated and owned by this joint. Shared pairs are reference counted.
    // A removed third-party suppression body retires only its pairs; either endpoint removes the joint.
    FProphecyJoltWorldStatus CreateJoint(const FProphecyJoltJointSettings& Settings,
        TConstArrayView<FProphecyJoltBodyPair> SuppressedPairs, FProphecyJoltJointHandle& OutJoint);
    // Endpoints/type and suppression ownership remain fixed. Replaces frames/limits after complete
    // preflight, intentionally resets warm-start state, and wakes endpoints once. Failure preserves old joint.
    FProphecyJoltWorldStatus UpdateJoint(const FProphecyJoltJointHandle& Joint, const FProphecyJoltJointSettings& Settings);
    /** Replace only this joint's pair exclusions, preserving its native constraint and warm start. */
    FProphecyJoltWorldStatus UpdateJointSuppressedPairs(const FProphecyJoltJointHandle& Joint,
        TConstArrayView<FProphecyJoltBodyPair> SuppressedPairs);
    /** Absolute dynamic mass; scales rotational inertia proportionally, without changing pose or velocity. */
    FProphecyJoltWorldStatus SetBodyMassKg(const FProphecyJoltBodyHandle& Body, float MassKg);
    FProphecyJoltWorldStatus SetBodyKinematic(const FProphecyJoltBodyHandle& Body);
    FProphecyJoltWorldStatus SetBodyDynamic(const FProphecyJoltBodyHandle& Body);
    FProphecyJoltWorldStatus SetBodyPose(const FProphecyJoltBodyHandle& Body, const FTransform& BodyOrigin);
    FProphecyJoltWorldStatus SetBodyRuntimeSettings(const FProphecyJoltBodyHandle& Body,
        bool bGravity, float LinearDamping, float AngularDamping, bool bCCD);
    /** Adds Source's collider to Parent without changing Parent mass, COM, inertia or constraints.
     * Source retains its identity/material/filter metadata but leaves the broadphase until detached. */
    FProphecyJoltWorldStatus WeldBodyShape(const FProphecyJoltBodyHandle& Parent,
        const FProphecyJoltBodyHandle& Source, const FTransform& SourceOriginToParentOrigin);
    bool IsBodyShapeWelded(const FProphecyJoltBodyHandle& Source) const;
    /** Absolute additive sword inertia factor; zero restores original parent inertia. Mass/COM/velocity stay unchanged. */
    FProphecyJoltWorldStatus SetWeldedBodyInertiaScale(const FProphecyJoltBodyHandle& Source, float Scale);
    FProphecyJoltWorldStatus MoveKinematicBody(const FProphecyJoltBodyHandle& Body,
        const FTransform& TargetBodyOrigin, float DeltaSeconds);
    /** Pair exclusions owned by a standalone body, automatically released with that body. */
    FProphecyJoltWorldStatus UpdateBodySuppressedPairs(const FProphecyJoltBodyHandle& Body,
        TConstArrayView<FProphecyJoltBodyPair> Pairs);
    FProphecyJoltWorldStatus ReadJoint(const FProphecyJoltJointHandle& Joint, FProphecyJoltJointSettings& OutSettings) const;
    FProphecyJoltWorldStatus ReadJointReaction(const FProphecyJoltJointHandle& Joint,
        FVector& Force, FVector& Torque) const;
    // Cleanup/ownership inspection remain available while faulted or ending, on GT and outside Update.
    FProphecyJoltWorldStatus DestroyJoint(const FProphecyJoltJointHandle& Joint);
    bool OwnsJoint(const FProphecyJoltJointHandle& Joint) const;
    // Absent/expired optional association returns AssociationUnavailable and a null output.
    FProphecyJoltWorldStatus ResolveAssociatedObject(const FProphecyJoltBodyHandle& Handle, UObject*& OutObject) const;
    FProphecyJoltWorldStatus GetDiagnostics(FProphecyJoltWorldDiagnostics& OutDiagnostics) const;

    // Optional solved-contact notifications. Delivery is GT-only after completed poses are published.
    FProphecyJoltWorldStatus SetRigHitEvents(const FProphecyJoltRigHandle& Rig, UPrimitiveComponent* Receiver, bool bEnabled);
    FProphecyJoltWorldStatus SetBodyHitEvents(const FProphecyJoltBodyHandle& Body, bool bEnabled);
    void DispatchPendingHitEvents();
    uint64 GetDeliveredHitEventCount() const;

    // Module ShutdownModule should verify zero before unregistering global Jolt types.
    static int32 GetLiveSimulationCount();

protected:
    virtual bool DoesSupportWorldType(EWorldType::Type WorldType) const override;

private:
    friend class UProphecyJoltBodyDriveLibrary;
    friend class UProphecyJoltFootJointLibrary;
    FProphecyJoltWorldStatus ValidateReady() const;
    FProphecyJoltWorldStatus ValidateBodySettings(const FProphecyJoltFixtureBodySettings& Settings) const;
    void RefreshDiagnostics();
    void StopForWorldTeardown();

    TUniquePtr<FProphecyJoltWorldState, FProphecyJoltWorldStateDeleter> Native;
    FProphecyJoltWorldDiagnostics Diagnostics;
    bool bSubsystemInitialized = false;
    bool bWorldEnding = false;
    bool bStepInProgress = false;
};
