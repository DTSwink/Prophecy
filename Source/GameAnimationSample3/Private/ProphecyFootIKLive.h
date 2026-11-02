#pragma once
#include "CoreMinimal.h"

class AProphecyAgent;
struct FProphecyFootIKLiveState;
class FProphecyFootIKForecast;
struct FProphecyFootIKForecastInput;

// Live Foot IK is a post-process of the game's real NN stream. It does not own
// the actor root, run a frozen NN checkpoint, or advance a second mover.
namespace ProphecyFootIKLive
{
struct FSourceSample
{
    FVector RootWorld=FVector::ZeroVector;
    FVector HeadingWorld=FVector::ForwardVector;
    // The canonical 25 body names, in the order passed to BuildSource.
    TArray<FTransform> BodiesWorld;
};
struct FInput
{
    int32 CurrentTick=0,SourceStartTick=0; // absolute 120Hz ticks since enable
    uint64 CommandRevision=0,GeometryRevision=0;
    FTransform CourseWorld=FTransform::Identity; // fixed for the enable epoch
    FString SourceJson,TerrainJson,InitialHistoryJson;
    // Optional copied game forecast input instead of an already computed source.
    // Prepare the matching model once on GT; prediction executes on this owner's
    // same serial worker, never on GT or a second inference worker.
    TSharedPtr<FProphecyFootIKForecast,ESPMode::ThreadSafe> Forecaster;
    TSharedPtr<const FProphecyFootIKForecastInput,ESPMode::ThreadSafe> ForecastInput;
};
struct FOutput
{
    int32 Tick=-1;
    uint64 CommandRevision=0;
    TArray<FTransform> PoseWorld,RawWorld; // includes virtual root, 26 entries
    FString DiagnosticsJson;
};
bool Enabled(const AProphecyAgent* Agent);
bool AnyEnabled();
bool HasCallbacks();
FString Settings(const AProphecyAgent* Agent);
bool Enable(AProphecyAgent* Agent,bool Value,FString& Error);
void Remove(AProphecyAgent* Agent);
bool Configure(AProphecyAgent* Agent,const FString& SettingsJson,FString& Error);
bool Status(const AProphecyAgent* Agent,FProphecyFootIKLiveState& Out);
// Explicit diagnostic snapshot; never serializes per-frame telemetry in the
// gameplay hot path. Includes worker stages and publication rejection reasons.
FString DiagnosticSnapshot(const AProphecyAgent* Agent);
// Poll after private NN warmup, before capturing a time-sensitive real pose
// pair. Pending initialization returns false without an error.
bool SourceReady(AProphecyAgent* Agent,FString& Error);
// One running job and one replaceable pending snapshot per agent. All UObject
// reads happen before submission; the worker owns only copied JSON/math data.
bool Submit(AProphecyAgent* Agent,const FInput& Input,FString& Error);
// Does not block. Only a frame from the requested command revision may publish.
// Consuming records the actual accepted boundary for the next worker replan.
bool Consume(AProphecyAgent* Agent,int32 Tick,uint64 CommandRevision,FOutput& Out,FString& Error);
// Publication join uses the previous final60Hz pose and current raw60Hz NN pose.
// It keeps the actual root/upper body and solves the planned leg correction at
// the current carrier without waiting for the background planning isolate.
bool ConsumeJoined(AProphecyAgent* Agent,int32 Tick,uint64 CommandRevision,
    const FSourceSample& PreviousActual,const FSourceSample& CurrentActual,FOutput& Out,FString& Error);
// Called after ordinary NN publication during preparation/fallback. These real
// displayed frames provide the entry boundary; no forecast is marked displayed.
bool ObserveActualPose(AProphecyAgent* Agent,int32 Tick,const FSourceSample& Sample,FString& Error);
// Clear speculative output after a real recurrent handoff. Warm models/VMs
// remain available; the next request captures a fresh actual source pair.
void InvalidatePrediction(AProphecyAgent* Agent);
bool TerrainExitReady(AProphecyAgent* Agent,int32 Tick,const FString& FrameJson,FString& Error);
void PublishContinuation(AProphecyAgent* Agent,int32 Tick);

// Exact inverse of ProphecyThrow::ToUnreal, including imported bone axes.
FTransform ToSolverBody(const FTransform& World,const FTransform& CourseWorld);
bool BuildSource(TConstArrayView<FName> Names,TConstArrayView<FSourceSample> Samples,
    const FTransform& CourseWorld,const FString& Gait,FString& SourceJson,FString& Error);
bool BuildInitialHistory(int32 PreviousTick,int32 CurrentTick,const FSourceSample& Previous,
    const FSourceSample& Current,const FTransform& CourseWorld,FString& HistoryJson,FString& Error);
// Copies actual finite horizontal box collider faces. Unsupported sloped or
// complex collision is reported, never replaced by its component AABB as a floor.
bool CaptureTerrain(AProphecyAgent* Agent,const FTransform& CourseWorld,
    TConstArrayView<FSourceSample> Samples,FString& TerrainJson,FString& Error);
// Inclines/walls use exact oriented finite faces for the surface/root adapter.
// This is separate from horizontal K tiles and never flattens a sloped face.
bool CaptureSurfaceTerrain(AProphecyAgent* Agent,const FTransform& CourseWorld,
    TConstArrayView<FSourceSample> Samples,FString& SurfacesJson,FString& Error);
// Stable collider-only key. A moving navigation-height profile does not change
// geometry. Primitive IDs and exact finite-face transforms do.
bool TerrainGeometryHash(const FString& TerrainJson,uint32& Hash,FString& Error);
}
