#pragma once

#include "CoreMinimal.h"
#include "ProphecyJoltRig.h"

class UPrimitiveComponent;
class FProphecyJoltPreparedBodyState;

/** A native shape omitted from simulation import; no triangle or paint FaceIndex mapping is implied. */
struct FProphecyJoltQueryShapeProvenance
{
    int32 NativeShapeIndex = INDEX_NONE;
    uint32 NativeGeometryType = 0;
    bool bQueryEnabled = false;
    bool bSimulationEnabled = false;
    bool bProbe = false;
    uint32 SimulationFilterWords[4] = {};
    uint32 QueryFilterWords[4] = {};
    FBox BoundsInBodyOriginCm = FBox(ForceInit);
};

/** Immutable after capture. A standalone component has no invented skeletal bone or Physics Asset. */
struct FProphecyJoltBodySnapshot
{
    FGuid CaptureId;
    TWeakObjectPtr<UPrimitiveComponent> SourceComponent;
    TWeakObjectPtr<UWorld> SourceWorld;
    FString ComponentPath;
    FString BodySetupPath;
    FString StaticMeshPath;
    uint64 EngineFrame = 0;
    double WorldTimeSeconds = 0.0;
    FTransform ComponentToWorld = FTransform::Identity; // Includes visual scale as provenance.
    FTransform BodyOriginToComponent = FTransform::Identity; // Rigid frames only; no scale reapplied.
    FProphecyJoltBodyData Body;
    TArray<FProphecyJoltQueryShapeProvenance> NonSimulationShapes;
    int32 NativeShapeCount = 0;
    int32 AuthoredSimpleShapeCount = 0;
    int32 AuthoredConvexInputVertexCount = 0;
    TArray<FString> CoverageNotes;
};

namespace ProphecyJolt::Body
{
    // Game thread at a completed synchronous Chaos step. Never changes component/body/asset state.
    // Single non-welded dynamic primitive body only; skeletal components must use CaptureLiveRig.
    PROPHECYJOLT_API bool CaptureLiveBody(UPrimitiveComponent& Component, FProphecyJoltBodySnapshot& OutSnapshot, FString& OutError);
    PROPHECYJOLT_API bool ValidateSnapshot(const FProphecyJoltBodySnapshot& Snapshot, FString& OutError);
}

/** Prepared native simulation shape and captured mass tensor. Creates no world, body, joint or asset. */
class PROPHECYJOLT_API FProphecyJoltPreparedBody
{
public:
    FProphecyJoltPreparedBody();
    ~FProphecyJoltPreparedBody();
    FProphecyJoltPreparedBody(FProphecyJoltPreparedBody&& Other) noexcept;
    FProphecyJoltPreparedBody& operator=(FProphecyJoltPreparedBody&& Other) noexcept;
    FProphecyJoltPreparedBody(const FProphecyJoltPreparedBody&) = delete;
    FProphecyJoltPreparedBody& operator=(const FProphecyJoltPreparedBody&) = delete;
    bool Build(const FProphecyJoltBodySnapshot& Snapshot, FString& OutError);
    void Reset();
    bool IsValid() const;
    FGuid GetCaptureId() const;
    static int32 GetLivePreparedBodyCount();
    bool GetGeometrySummary(FVector& OutCOMCm, FBox& OutBoundsInBodyOriginCm, FString& OutError) const;
    // Read-only native seams also support synthetic physics tests and the owner implementation.
    const JPH::Shape* GetNativeShape() const;
    bool GetNativeMassProperties(JPH::MassProperties& OutProperties) const;
private:
    TUniquePtr<FProphecyJoltPreparedBodyState> Native;
};
