#pragma once

#include "CoreMinimal.h"

class FJsonObject;

namespace ProphecyJolt::CharacterProfiling
{
enum class EPhase : uint8 { Targets, TargetRead, HelperPose, Fingers, TargetPacket, TargetCommit,
    CompletedPose, BodyRead, Compose, AnimBuffer, ParallelWait, AnimTick, RefreshBones, QueryUpdate,
    AgentTick, EnsureFists, FixturePosePublish, WorldCoordinator, ClientPrepare, ClientConsume, NativeStep,
    ManagerTick, ManagerVisualRoots, ManagerPhysicalResample, ManagerPosePublish,
    ProxyPreUpdate, ProxyPreEvaluate, ProxyEvaluate, ProxyPostEvaluateBase, FinalizeAfterQuery, PublicationValidation, ComposeBatch,
    QueryValidate, QueryScale, QueryBodyWrite, QuerySceneUpdate, PhysicalSampleRead, PhysicalRawEncode, TargetEndpointExpand, PhysicalFeedbackPrepare, PhysicalFeedbackBatch, Count };
constexpr int32 PhaseCount = static_cast<int32>(EPhase::Count);
extern const TCHAR* const PhaseNames[PhaseCount];
struct FProcessorLocation
{
    int32 Group = INDEX_NONE;
    int32 Number = INDEX_NONE;
};
// Only Compose and RefreshBones are sampled. Fixed storage avoids timed allocations.
constexpr int32 ProcessorPhaseCount = 2;
constexpr int32 MaxObservedProcessors = 64;
struct FProcessorPhaseSamples
{
    FProcessorLocation Processor;
    double Seconds[ProcessorPhaseCount] = {};
    uint32 Calls[ProcessorPhaseCount] = {};
    uint32 DifferentExitProcessor[ProcessorPhaseCount] = {};
};
struct FFrame
{
    double Seconds[PhaseCount] = {};
    uint32 Calls[PhaseCount] = {};
    FProcessorLocation StartProcessor, EndProcessor;
    FProcessorPhaseSamples ProcessorSamples[MaxObservedProcessors];
    int32 ObservedProcessorCount = 0;
    uint32 ProcessorSampleOverflow = 0;
};
// Explicit isolated benchmark instrumentation. Disabled in ordinary gameplay; game-thread only.
void BeginFrame();
FFrame EndFrame();
void Disable();
// Serializes outside the measured world interval. Environment is captured once at
// the first BeginFrame before the benchmark starts its timer; all queries are read-only.
TSharedPtr<FJsonObject> ProcessorFrameJson(const FFrame& Frame);
TSharedPtr<FJsonObject> ProcessorEnvironmentJson();
double Timestamp();
void RecordElapsed(EPhase Phase, double Start);
class FScope final
{
public:
    explicit FScope(EPhase InPhase);
    ~FScope();
private:
    EPhase Phase;
    double Start = 0.0;
    FProcessorLocation StartProcessor;
};
}
