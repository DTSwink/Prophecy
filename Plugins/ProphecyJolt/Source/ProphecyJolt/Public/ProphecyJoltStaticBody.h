#pragma once

#include "CoreMinimal.h"
#include "ProphecyJoltBody.h"

class FProphecyJoltPreparedStaticBodyState;

/** Cooked simulation triangles, with native wrappers baked into body-origin centimetres. */
struct FProphecyJoltStaticMeshShape
{
    int32 NativeShapeIndex = INDEX_NONE;
    TArray<uint32> NativeGeometryTypeChain;
    TArray<FVector> VerticesCm;
    TArray<FIntVector> Triangles;
    // Parallel to Triangles; native cook provenance, never directly assigned to UE FHitResult::FaceIndex.
    TArray<int32> ExternalFaceIndices;
    TArray<uint16> MaterialIndices;
    uint32 SimulationFilterWords[4] = {};
    uint32 QueryFilterWords[4] = {};
    bool bQueryEnabled = false;
    bool bReversedWindingForNegativeScale = false;
};

/** One actual static primitive body or one ISM/HISM instance. Immutable after capture.
 * InstanceIndex is capture-time provenance, not a stable identity across instance reordering.
 * No scene discovery, lifetime subscription, moving-body support or UE query replacement is implied.
 */
struct FProphecyJoltStaticBodySnapshot
{
    FGuid CaptureId;
    TWeakObjectPtr<UPrimitiveComponent> SourceComponent;
    TWeakObjectPtr<UWorld> SourceWorld;
    int32 InstanceIndex = INDEX_NONE;
    FString ComponentPath;
    FString BodySetupPath;
    FString StaticMeshPath;
    uint64 EngineFrame = 0;
    FTransform ComponentToWorld = FTransform::Identity;
    FTransform InstanceToWorld = FTransform::Identity;
    FTransform BodyOriginToWorld = FTransform::Identity;
    FVector SourceBodyScale3D = FVector::OneVector;
    FVector SourceBuildScale3D = FVector::OneVector;
    ECollisionEnabled::Type CollisionEnabled = ECollisionEnabled::NoCollision;
    ECollisionChannel ObjectType = ECC_WorldStatic;
    FCollisionResponseContainer CollisionResponses;
    FString PhysicalMaterialPath;
    TArray<FString> ComplexPhysicalMaterialPaths;
    double Friction = 0.0;
    double Restitution = 0.0;
    uint8 EffectiveFrictionCombineMode = 0;
    uint8 EffectiveRestitutionCombineMode = 0;
    TArray<FProphecyJoltRigShape> SimpleShapes;
    TArray<FProphecyJoltStaticMeshShape> MeshShapes;
    TArray<FProphecyJoltQueryShapeProvenance> NonSimulationShapes;
    int32 NativeShapeCount = 0;
    TArray<FString> CoverageNotes;
};

namespace ProphecyJolt::StaticBody
{
    // Read-only GT capture at a completed synchronous Chaos step. Pass INDEX_NONE for a non-ISM.
    PROPHECYJOLT_API bool CaptureStaticBody(UPrimitiveComponent& Component, int32 InstanceIndex,
        FProphecyJoltStaticBodySnapshot& OutSnapshot, FString& OutError);
    PROPHECYJOLT_API bool ValidateSnapshot(const FProphecyJoltStaticBodySnapshot& Snapshot, FString& OutError);
}

/** Pure geometry preparation; no invented mass/inertia and no native body creation. */
class PROPHECYJOLT_API FProphecyJoltPreparedStaticBody
{
public:
    FProphecyJoltPreparedStaticBody();
    ~FProphecyJoltPreparedStaticBody();
    FProphecyJoltPreparedStaticBody(FProphecyJoltPreparedStaticBody&& Other) noexcept;
    FProphecyJoltPreparedStaticBody& operator=(FProphecyJoltPreparedStaticBody&& Other) noexcept;
    FProphecyJoltPreparedStaticBody(const FProphecyJoltPreparedStaticBody&) = delete;
    FProphecyJoltPreparedStaticBody& operator=(const FProphecyJoltPreparedStaticBody&) = delete;
    bool Build(const FProphecyJoltStaticBodySnapshot& Snapshot, FString& OutError);
    void Reset();
    bool IsValid() const;
    FGuid GetCaptureId() const;
    const JPH::Shape* GetNativeShape() const;
    bool GetBoundsInBodyOriginCm(FBox& OutBounds, FString& OutError) const;
private:
    TUniquePtr<FProphecyJoltPreparedStaticBodyState> Native;
};
