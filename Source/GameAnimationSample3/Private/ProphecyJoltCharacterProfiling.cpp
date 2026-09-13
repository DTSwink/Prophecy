#include "ProphecyJoltCharacterProfiling.h"
#include "HAL/PlatformTime.h"
#include "HAL/PlatformMisc.h"
#include "Dom/JsonObject.h"
#if PLATFORM_WINDOWS
#include "Windows/WindowsHWrapper.h"
#endif

namespace ProphecyJolt::CharacterProfiling
{
const TCHAR* const PhaseNames[PhaseCount] = { TEXT("targets"), TEXT("target_read"), TEXT("helper_pose"),
    TEXT("fingers"), TEXT("target_packet"), TEXT("target_commit"), TEXT("completed_pose_serial"),
    TEXT("body_read"), TEXT("compose"), TEXT("anim_buffer"), TEXT("parallel_wait"),
    TEXT("anim_tick"), TEXT("refresh_bones"), TEXT("query_update"), TEXT("agent_tick_total"),
    TEXT("ensure_fists"), TEXT("fixture_pose_publish"), TEXT("coordinator_total"),
    TEXT("client_prepare"), TEXT("client_consume_total"), TEXT("native_step_total"),
    TEXT("manager_tick_total"), TEXT("manager_visual_roots"), TEXT("manager_physical_resample"), TEXT("manager_pose_publish"),
    TEXT("pose_proxy_preupdate"), TEXT("pose_proxy_preevaluate"), TEXT("pose_proxy_evaluate"),
    TEXT("pose_proxy_postevaluate_base"), TEXT("pose_finalize_after_query"), TEXT("pose_publication_validation"), TEXT("compose_batch_wall"),
    TEXT("query_validate"), TEXT("query_scale"), TEXT("query_body_write"), TEXT("query_scene_update"),
    TEXT("physical_sample_read"), TEXT("physical_raw_encode"), TEXT("target_endpoint_expand"), TEXT("physical_feedback_prepare"), TEXT("physical_feedback_batch_wall") };
namespace
{
bool bEnabled = false;
FFrame Current;
TSharedPtr<FJsonObject> ProcessorEnvironment;

FProcessorLocation ReadProcessor()
{
    FProcessorLocation Result;
#if PLATFORM_WINDOWS
    PROCESSOR_NUMBER ProcessorNumber = {};
    ::GetCurrentProcessorNumberEx(&ProcessorNumber);
    Result.Group = ProcessorNumber.Group;
    Result.Number = ProcessorNumber.Number;
#endif
    return Result;
}
bool SameProcessor(const FProcessorLocation& A, const FProcessorLocation& B)
{
    return A.Group == B.Group && A.Number == B.Number;
}
int32 ProcessorPhaseIndex(EPhase Phase)
{
    return Phase == EPhase::Compose ? 0 : (Phase == EPhase::RefreshBones ? 1 : INDEX_NONE);
}
TSharedPtr<FJsonObject> LocationJson(const FProcessorLocation& Processor)
{
    auto Result = MakeShared<FJsonObject>();
    Result->SetNumberField(TEXT("group"), Processor.Group);
    Result->SetNumberField(TEXT("logical_processor_index"), Processor.Number);
    return Result;
}
TSharedPtr<FJsonObject> ReadPolicyJson()
{
    auto Result = MakeShared<FJsonObject>();
#if PLATFORM_WINDOWS
    Result->SetNumberField(TEXT("process_id"), ::GetCurrentProcessId());
    Result->SetNumberField(TEXT("game_thread_id"), ::GetCurrentThreadId());
    Result->SetNumberField(TEXT("process_priority_class"), ::GetPriorityClass(::GetCurrentProcess()));
    Result->SetNumberField(TEXT("game_thread_priority"), ::GetThreadPriority(::GetCurrentThread()));
    DWORD_PTR ProcessMask = 0, SystemMask = 0;
    const bool bAffinityRead = ::GetProcessAffinityMask(::GetCurrentProcess(), &ProcessMask, &SystemMask) != 0;
    const DWORD AffinityError = bAffinityRead ? ERROR_SUCCESS : ::GetLastError();
    Result->SetBoolField(TEXT("process_affinity_read"), bAffinityRead);
    Result->SetNumberField(TEXT("process_affinity_error"), AffinityError);
    if (bAffinityRead)
    {
        Result->SetStringField(TEXT("process_affinity_mask_hex"), FString::Printf(TEXT("0x%llx"), uint64(ProcessMask)));
        Result->SetStringField(TEXT("system_affinity_mask_hex"), FString::Printf(TEXT("0x%llx"), uint64(SystemMask)));
    }
    GROUP_AFFINITY ThreadAffinity = {};
    const bool bThreadAffinityRead = ::GetThreadGroupAffinity(::GetCurrentThread(), &ThreadAffinity) != 0;
    const DWORD ThreadAffinityError = bThreadAffinityRead ? ERROR_SUCCESS : ::GetLastError();
    Result->SetBoolField(TEXT("thread_group_affinity_read"), bThreadAffinityRead);
    Result->SetNumberField(TEXT("thread_group_affinity_error"), ThreadAffinityError);
    if (bThreadAffinityRead)
    {
        Result->SetNumberField(TEXT("thread_affinity_group"), ThreadAffinity.Group);
        Result->SetStringField(TEXT("thread_affinity_mask_hex"), FString::Printf(TEXT("0x%llx"), uint64(ThreadAffinity.Mask)));
    }
#if defined(PROCESS_POWER_THROTTLING_CURRENT_VERSION)
    PROCESS_POWER_THROTTLING_STATE ProcessPower = {};
    ProcessPower.Version = PROCESS_POWER_THROTTLING_CURRENT_VERSION;
    const bool bProcessPowerRead = ::GetProcessInformation(::GetCurrentProcess(), ProcessPowerThrottling,
        &ProcessPower, sizeof(ProcessPower)) != 0;
    const DWORD ProcessPowerError = bProcessPowerRead ? ERROR_SUCCESS : ::GetLastError();
    Result->SetBoolField(TEXT("process_power_throttling_read"), bProcessPowerRead);
    Result->SetNumberField(TEXT("process_power_throttling_error"), ProcessPowerError);
    if (bProcessPowerRead)
    {
        Result->SetNumberField(TEXT("process_power_control_mask"), ProcessPower.ControlMask);
        Result->SetNumberField(TEXT("process_power_state_mask"), ProcessPower.StateMask);
    }
#endif
#if defined(THREAD_POWER_THROTTLING_CURRENT_VERSION)
    THREAD_POWER_THROTTLING_STATE ThreadPower = {};
    ThreadPower.Version = THREAD_POWER_THROTTLING_CURRENT_VERSION;
    const bool bThreadPowerRead = ::GetThreadInformation(::GetCurrentThread(), ThreadPowerThrottling,
        &ThreadPower, sizeof(ThreadPower)) != 0;
    const DWORD ThreadPowerError = bThreadPowerRead ? ERROR_SUCCESS : ::GetLastError();
    Result->SetBoolField(TEXT("thread_power_throttling_read"), bThreadPowerRead);
    Result->SetNumberField(TEXT("thread_power_throttling_error"), ThreadPowerError);
    if (bThreadPowerRead)
    {
        Result->SetNumberField(TEXT("thread_power_control_mask"), ThreadPower.ControlMask);
        Result->SetNumberField(TEXT("thread_power_state_mask"), ThreadPower.StateMask);
    }
#endif
#endif
    return Result;
}
void CaptureProcessorEnvironment()
{
    ProcessorEnvironment = MakeShared<FJsonObject>();
    ProcessorEnvironment->SetBoolField(TEXT("captured"), true);
    ProcessorEnvironment->SetStringField(TEXT("cpu_brand"), FPlatformMisc::GetCPUBrand());
    ProcessorEnvironment->SetStringField(TEXT("capture_boundary"), TEXT("First profiled BeginFrame, before the measured world timer; CPU-set topology queried once. Final policy snapshot is outside timing."));
    ProcessorEnvironment->SetStringField(TEXT("scope"), TEXT("Read-only Windows processor placement, OS efficiency-class labels and policy state; no affinity, priority, QoS or power settings changed. Does not measure core residency between samples, clock frequency, turbo or temperature."));
    ProcessorEnvironment->SetObjectField(TEXT("initial_policy"), ReadPolicyJson());
    TArray<TSharedPtr<FJsonValue>> CpuSets;
    bool bCpuSetsRead = false;
    uint32 CpuSetsError = 0;
#if PLATFORM_WINDOWS && (_WIN32_WINNT >= _WIN32_WINNT_WIN10)
    ULONG RequiredBytes = 0;
    const BOOL bSizeRead = ::GetSystemCpuSetInformation(nullptr, 0, &RequiredBytes, ::GetCurrentProcess(), 0);
    const DWORD SizeError = bSizeRead ? ERROR_SUCCESS : ::GetLastError();
    if ((bSizeRead || SizeError == ERROR_INSUFFICIENT_BUFFER) && RequiredBytes > 0 && RequiredBytes < 16u * 1024u * 1024u)
    {
        TArray<uint8> Buffer;
        Buffer.SetNumUninitialized(int32(RequiredBytes));
        ULONG ReturnedBytes = RequiredBytes;
        bCpuSetsRead = ::GetSystemCpuSetInformation(reinterpret_cast<PSYSTEM_CPU_SET_INFORMATION>(Buffer.GetData()),
            RequiredBytes, &ReturnedBytes, ::GetCurrentProcess(), 0) != 0;
        CpuSetsError = bCpuSetsRead ? ERROR_SUCCESS : ::GetLastError();
        if (bCpuSetsRead && ReturnedBytes <= RequiredBytes)
        {
            for (ULONG Offset = 0; Offset < ReturnedBytes;)
            {
                if (ReturnedBytes - Offset < sizeof(SYSTEM_CPU_SET_INFORMATION))
                { bCpuSetsRead = false; CpuSetsError = ERROR_INVALID_DATA; break; }
                const auto* Entry = reinterpret_cast<const SYSTEM_CPU_SET_INFORMATION*>(Buffer.GetData() + Offset);
                if (Entry->Size < sizeof(SYSTEM_CPU_SET_INFORMATION) || Entry->Size > ReturnedBytes - Offset)
                { bCpuSetsRead = false; CpuSetsError = ERROR_INVALID_DATA; break; }
                if (Entry->Type == CpuSetInformation)
                {
                    auto CpuSet = MakeShared<FJsonObject>();
                    CpuSet->SetNumberField(TEXT("id"), Entry->CpuSet.Id);
                    CpuSet->SetNumberField(TEXT("group"), Entry->CpuSet.Group);
                    CpuSet->SetNumberField(TEXT("logical_processor_index"), Entry->CpuSet.LogicalProcessorIndex);
                    CpuSet->SetNumberField(TEXT("core_index"), Entry->CpuSet.CoreIndex);
                    CpuSet->SetNumberField(TEXT("efficiency_class"), Entry->CpuSet.EfficiencyClass);
                    CpuSet->SetNumberField(TEXT("numa_node_index"), Entry->CpuSet.NumaNodeIndex);
                    CpuSet->SetNumberField(TEXT("last_level_cache_index"), Entry->CpuSet.LastLevelCacheIndex);
                    CpuSet->SetNumberField(TEXT("flags_at_capture"), Entry->CpuSet.AllFlags);
                    CpuSets.Add(MakeShared<FJsonValueObject>(CpuSet));
                }
                Offset += Entry->Size;
            }
        }
        else if (bCpuSetsRead) { bCpuSetsRead = false; CpuSetsError = ERROR_INVALID_DATA; }
    }
    else CpuSetsError = SizeError != ERROR_SUCCESS ? SizeError : ERROR_INVALID_DATA;
#else
    ProcessorEnvironment->SetStringField(TEXT("cpu_sets_unavailable"), TEXT("Platform or target SDK does not expose Windows CPU-set information."));
#endif
    ProcessorEnvironment->SetBoolField(TEXT("cpu_sets_read"), bCpuSetsRead);
    ProcessorEnvironment->SetNumberField(TEXT("cpu_sets_error"), CpuSetsError);
    ProcessorEnvironment->SetArrayField(TEXT("cpu_sets"), CpuSets);
}
void RecordProcessorPhase(int32 PhaseIndex, const FProcessorLocation& StartProcessor, double Elapsed)
{
    const FProcessorLocation EndProcessor = ReadProcessor();
    if (StartProcessor.Group == INDEX_NONE) return;
    int32 Slot = 0;
    while (Slot < Current.ObservedProcessorCount && !SameProcessor(Current.ProcessorSamples[Slot].Processor, StartProcessor)) ++Slot;
    if (Slot == MaxObservedProcessors) { ++Current.ProcessorSampleOverflow; return; }
    if (Slot == Current.ObservedProcessorCount)
    {
        ++Current.ObservedProcessorCount;
        Current.ProcessorSamples[Slot].Processor = StartProcessor;
    }
    auto& Samples = Current.ProcessorSamples[Slot];
    Samples.Seconds[PhaseIndex] += Elapsed;
    ++Samples.Calls[PhaseIndex];
    Samples.DifferentExitProcessor[PhaseIndex] += !SameProcessor(StartProcessor, EndProcessor);
}
}
void BeginFrame()
{
    check(IsInGameThread());
    if (!ProcessorEnvironment) CaptureProcessorEnvironment();
    Current = {};
    Current.StartProcessor = ReadProcessor();
    bEnabled = true;
}
FFrame EndFrame()
{
    check(IsInGameThread());
    Current.EndProcessor = ReadProcessor();
    bEnabled = false;
    return Current;
}
void Disable() { check(IsInGameThread()); bEnabled = false; }

TSharedPtr<FJsonObject> ProcessorEnvironmentJson()
{
    check(IsInGameThread());
    if (!ProcessorEnvironment)
    {
        auto Result = MakeShared<FJsonObject>();
        Result->SetBoolField(TEXT("captured"), false);
        return Result;
    }
    ProcessorEnvironment->SetObjectField(TEXT("final_policy"), ReadPolicyJson());
    return ProcessorEnvironment;
}
TSharedPtr<FJsonObject> ProcessorFrameJson(const FFrame& Frame)
{
    check(IsInGameThread());
    auto Result = MakeShared<FJsonObject>();
    Result->SetObjectField(TEXT("begin"), LocationJson(Frame.StartProcessor));
    Result->SetObjectField(TEXT("end"), LocationJson(Frame.EndProcessor));
    Result->SetNumberField(TEXT("overflowed_scope_samples"), Frame.ProcessorSampleOverflow);
    Result->SetStringField(TEXT("attribution"), TEXT("Compose/RefreshBones elapsed wall time is attributed to the processor sampled at scope entry. A differing exit detects some migrations; matching endpoints cannot exclude migration/preemption within a scope. Counts are samples, not CPU residency. Processor calls are explicit benchmark overhead inside world timing, outside phase timing."));
    TArray<TSharedPtr<FJsonValue>> Samples;
    const TCHAR* const SampledPhases[] = { TEXT("compose"), TEXT("refresh_bones") };
    for (int32 Slot = 0; Slot < Frame.ObservedProcessorCount; ++Slot)
    {
        const auto& Source = Frame.ProcessorSamples[Slot];
        auto Sample = LocationJson(Source.Processor);
        for (int32 PhaseIndex = 0; PhaseIndex < ProcessorPhaseCount; ++PhaseIndex)
        {
            auto PhaseSample = MakeShared<FJsonObject>();
            PhaseSample->SetNumberField(TEXT("ms"), Source.Seconds[PhaseIndex] * 1000.0);
            PhaseSample->SetNumberField(TEXT("calls"), Source.Calls[PhaseIndex]);
            PhaseSample->SetNumberField(TEXT("different_exit_processor"), Source.DifferentExitProcessor[PhaseIndex]);
            Sample->SetObjectField(SampledPhases[PhaseIndex], PhaseSample);
        }
        Samples.Add(MakeShared<FJsonValueObject>(Sample));
    }
    Result->SetArrayField(TEXT("phase_entry_processors"), Samples);
    return Result;
}
double Timestamp() { return bEnabled ? FPlatformTime::Seconds() : 0.0; }
void RecordElapsed(EPhase Phase, double Start)
{
    if (Start != 0.0 && bEnabled)
    {
        check(IsInGameThread());
        const int32 Index = static_cast<int32>(Phase);
        Current.Seconds[Index] += FPlatformTime::Seconds() - Start;
        ++Current.Calls[Index];
    }
}
FScope::FScope(EPhase InPhase) : Phase(InPhase)
{
    if (bEnabled)
    {
        check(IsInGameThread());
        if (ProcessorPhaseIndex(Phase) != INDEX_NONE) StartProcessor = ReadProcessor();
        Start = FPlatformTime::Seconds();
    }
}
FScope::~FScope()
{
    if (Start != 0.0 && bEnabled)
    {
        const int32 Index = static_cast<int32>(Phase);
        const double Elapsed = FPlatformTime::Seconds() - Start;
        Current.Seconds[Index] += Elapsed;
        ++Current.Calls[Index];
        const int32 ProcessorPhase = ProcessorPhaseIndex(Phase);
        if (ProcessorPhase != INDEX_NONE) RecordProcessorPhase(ProcessorPhase, StartProcessor, Elapsed);
    }
}
}
