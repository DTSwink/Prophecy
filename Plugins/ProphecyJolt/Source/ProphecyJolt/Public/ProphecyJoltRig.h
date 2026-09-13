#pragma once

#include "CoreMinimal.h"
#include "PhysicsEngine/ConstraintInstance.h"

class USkeletalMeshComponent;
class UWorld;
class UProphecyJoltWorldSubsystem;
class FProphecyJoltWorldState;
class FProphecyJoltPreparedRigState;
namespace JPH { class Shape; class MassProperties; }

enum class EProphecyJoltRigShape : uint8 { Sphere, Box, Capsule, Convex };

/** Geometry in physical body-origin coordinates; cm, unit transform scale. */
struct FProphecyJoltRigShape
{
    EProphecyJoltRigShape Kind = EProphecyJoltRigShape::Sphere;
    int32 SourceElementIndex = INDEX_NONE;
    int32 SourceNativeShapeIndex = INDEX_NONE;
    bool bGeometryCapturedFromNative = false;
    double NativeCollisionMarginCm = 0.0;
    TArray<uint32> NativeGeometryTypeChain; // Outer wrappers through concrete leaf, diagnostic IDs only.
    FName ElementName;
    FTransform LocalToBodyOrigin = FTransform::Identity;
    // Source AggGeom values before Body.Scale3D. BuildScale3D is already baked into AggGeom by UE.
    FTransform AuthoredLocalToBodyOrigin = FTransform::Identity;
    double AuthoredRadiusCm = 0.0;
    FVector AuthoredBoxHalfExtentCm = FVector::ZeroVector;
    double AuthoredCapsuleCylinderLengthCm = 0.0;
    double RadiusCm = 0.0;
    FVector BoxHalfExtentCm = FVector::ZeroVector;
    // UE Sphyl.Length: straight cylinder length, excluding both hemispherical caps. Native axis is Z.
    double CapsuleCylinderLengthCm = 0.0;
    TArray<FVector> ConvexVerticesCm;
    ECollisionEnabled::Type AuthoredCollisionEnabled = ECollisionEnabled::NoCollision;
    ECollisionEnabled::Type CurrentCollisionEnabled = ECollisionEnabled::NoCollision;
    bool bNativeSimulationEnabled = false;
    bool bNativeQueryEnabled = false;
    // Exact native filter provenance. Simulation Word2 is component ID; query Word2 is overlaps.
    uint32 NativeSimulationFilterWords[4] = {};
    uint32 NativeQueryFilterWords[4] = {};
    ECollisionChannel NativeSimulationObjectType = ECC_WorldDynamic;
    FCollisionResponseContainer NativeSimulationResponses;
    ECollisionChannel NativeQueryObjectType = ECC_WorldDynamic;
    FCollisionResponseContainer NativeQueryResponses;
    bool bContributesToAuthoredMass = false;
    double RestOffsetCm = 0.0;
};

/** Common rigid-body data. Component and skeletal identities live in their respective snapshots. */
struct FProphecyJoltBodyData
{
    FVector SourceBodyScale3D = FVector::OneVector;
    FVector SourceBuildScale3D = FVector::OneVector;
    FTransform BodyOriginToWorld = FTransform::Identity;
    // Principal mass frame: rotation diagonalizes inertia; translation is COM in body-origin space.
    FTransform MassFrameToBodyOrigin = FTransform::Identity;
    double MassKg = 0.0;
    FVector PrincipalInertiaKgCmSquared = FVector::ZeroVector;
    FVector CenterOfMassVelocityCmPerSecond = FVector::ZeroVector;
    FVector AngularVelocityRadiansPerSecond = FVector::ZeroVector;
    bool bSimulating = false;
    bool bAwake = false;
    bool bGravityEnabled = false;
    bool bCCD = false;
    bool bMACD = false;
    bool bInertiaConditioning = false;
    double LinearDamping = 0.0;
    double AngularDamping = 0.0;
    double MaxLinearVelocityCmPerSecond = 0.0;
    double MaxAngularVelocityRadiansPerSecond = 0.0;
    // Configured initial-overlap override, not the general solver depenetration limit.
    bool bOverrideMaxDepenetrationVelocity = false;
    double MaxDepenetrationVelocityCmPerSecond = 0.0;
    int32 PositionSolverIterations = -1;
    int32 VelocitySolverIterations = -1;
    int32 ProjectionSolverIterations = -1;
    ECollisionEnabled::Type CollisionEnabled = ECollisionEnabled::NoCollision;
    // Raw BodyInstance values before skeletal-component/per-shape overrides; provenance only.
    ECollisionChannel SourceBodyObjectType = ECC_WorldDynamic;
    FCollisionResponseContainer SourceBodyCollisionResponses;
    // Effective native simulation policy agreed by every simulated shape (block/ignore only).
    ECollisionChannel ObjectType = ECC_WorldDynamic;
    FCollisionResponseContainer CollisionResponses;
    FString PhysicalMaterialPath;
    double Friction = 0.0;
    double StaticFriction = 0.0;
    double Restitution = 0.0;
    uint8 EffectiveFrictionCombineMode = 0;
    uint8 EffectiveRestitutionCombineMode = 0;
    uint8 SurfaceType = 0;
    TArray<FProphecyJoltRigShape> Shapes;

    // Jolt's COM frame retains body rotation. Do NOT use MassFrameToBodyOrigin's principal-axis rotation here.
    FTransform GetCenterOfMassToBodyOrigin() const
    {
        return FTransform(FQuat::Identity, MassFrameToBodyOrigin.GetTranslation());
    }
};

struct FProphecyJoltRigBody : FProphecyJoltBodyData
{
    int32 SourceBodyIndex = INDEX_NONE;
    int32 BoneIndex = INDEX_NONE;
    FName BodyName;
};

/** Independent live joint description. CurrentProfile is a value UStruct, with no native constraint handle. */
struct FProphecyJoltRigJoint
{
    int32 SourceConstraintIndex = INDEX_NONE;
    FName JointName;
    FName Bone1;
    FName Bone2;
    int32 Body1Index = INDEX_NONE;
    int32 Body2Index = INDEX_NONE;
    // Native GetLocalPose frames: body-origin local, with live translation scaling already applied.
    FTransform Frame1 = FTransform::Identity;
    FTransform Frame2 = FTransform::Identity;
    // Provenance only: native connector frames already supply final axes; never apply this again.
    FRotator AngularRotationOffsetDegrees = FRotator::ZeroRotator;
    FConstraintProfileProperties CurrentProfile;
};

struct FProphecyJoltRigDisabledPair
{
    int32 Body1Index = INDEX_NONE;
    int32 Body2Index = INDEX_NONE;
    bool bFromPhysicsAsset = false;
    bool bFromCurrentJoint = false;
};

/** Completed game-thread capture. Caller must choose a quiescent/finished Chaos step; no physics is advanced. */
struct FProphecyJoltRigSnapshot
{
    FGuid CaptureId;
    TWeakObjectPtr<USkeletalMeshComponent> SourceComponent;
    TWeakObjectPtr<UWorld> SourceWorld;
    FString ComponentPath;
    FString SkeletalMeshPath;
    FString PhysicsAssetPath;
    uint64 EngineFrame = 0;
    double WorldTimeSeconds = 0.0;
    TArray<FProphecyJoltRigBody> Bodies;
    TArray<FProphecyJoltRigJoint> Joints;
    TArray<FProphecyJoltRigDisabledPair> DisabledPairs;
    TArray<FString> CoverageNotes;
};

namespace ProphecyJolt::Rig
{
    // All-or-nothing output; unsupported/missing live bodies, joints, scales or geometry fail explicitly.
    PROPHECYJOLT_API bool CaptureLiveRig(USkeletalMeshComponent& Component, FProphecyJoltRigSnapshot& OutSnapshot, FString& OutError);
    PROPHECYJOLT_API bool ValidateSnapshot(const FProphecyJoltRigSnapshot& Snapshot, FString& OutError);
}

/** Owns prepared native shapes and explicit mass/inertia; does not create bodies, constraints or a world. */
class PROPHECYJOLT_API FProphecyJoltPreparedRig
{
public:
    FProphecyJoltPreparedRig();
    ~FProphecyJoltPreparedRig();
    FProphecyJoltPreparedRig(FProphecyJoltPreparedRig&& Other) noexcept;
    FProphecyJoltPreparedRig& operator=(FProphecyJoltPreparedRig&& Other) noexcept;
    FProphecyJoltPreparedRig(const FProphecyJoltPreparedRig&) = delete;
    FProphecyJoltPreparedRig& operator=(const FProphecyJoltPreparedRig&) = delete;

    bool Build(const FProphecyJoltRigSnapshot& Snapshot, FString& OutError);
    void Reset();
    int32 GetBodyCount() const;
    FGuid GetCaptureId() const;
    static int32 GetLivePreparedRigCount();
    bool GetBodyGeometrySummary(int32 BodyIndex, FVector& OutCenterOfMassCm, FBox& OutBoundsInBodyOriginCm, FString& OutError) const;

private:
    friend class UProphecyJoltWorldSubsystem;
    friend class FProphecyJoltWorldState;
    const JPH::Shape* GetNativeBodyShape(int32 BodyIndex) const;
    bool GetNativeBodyMassProperties(int32 BodyIndex, JPH::MassProperties& OutProperties) const;
    TUniquePtr<FProphecyJoltPreparedRigState> Native;
};
