#include "ProphecyJoltBenchmarkProcessorControl.h"

#include "ProphecyJoltCharacterProfiling.h"
#include "Dom/JsonObject.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "UObject/Object.h"
#include "UObject/ObjectKey.h"
#if PLATFORM_WINDOWS
#include "Windows/WindowsHWrapper.h"
#endif

namespace ProphecyJolt::BenchmarkProcessorControl
{
namespace
{
bool bAttempted = false;
bool bRequested = false;
bool bApplied = false;
bool bNeedsRestore = false;
bool bRestored = false;
FObjectKey ControllingOwner;
FString Failure;
TSharedPtr<FJsonObject> Report;
int32 SelectedGroup = INDEX_NONE;
uint64 SelectedMask = 0;
#if PLATFORM_WINDOWS
GROUP_AFFINITY OriginalAffinity = {};
DWORD ControllingThreadId = 0;

TSharedPtr<FJsonObject> AffinityJson(const GROUP_AFFINITY& Affinity)
{
    auto Row = MakeShared<FJsonObject>();
    Row->SetNumberField(TEXT("group"), Affinity.Group);
    Row->SetStringField(TEXT("mask_hex"), FString::Printf(TEXT("0x%llx"), uint64(Affinity.Mask)));
    return Row;
}
#endif

bool Fail(FString& OutError, const FString& Message)
{
    Failure = Message;
    OutError = Message;
    if (Report) Report->SetStringField(TEXT("error"), Message);
    return false;
}

bool ProcessorAllowed(const CharacterProfiling::FProcessorLocation& Location)
{
    return Location.Group == SelectedGroup && Location.Number >= 0 && Location.Number < 64
        && (SelectedMask & (uint64(1) << Location.Number)) != 0;
}
}

bool Begin(const UObject& Owner, FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread()) return Fail(OutError, TEXT("Benchmark processor control requires the game thread."));
    if (bAttempted)
    {
        if (bRequested && ControllingOwner != FObjectKey(&Owner))
        {
            // Preserve the real owner's state/report. A second world cannot acquire or undo it.
            OutError = TEXT("Benchmark GT processor control already belongs to another subsystem lifetime.");
            return false;
        }
        if (!bRequested || (bApplied && bNeedsRestore)) return true;
        return Fail(OutError, Failure.IsEmpty() ? TEXT("Processor control cannot restart after restoration in this process.") : Failure);
    }
    bAttempted = true;
    bRequested = FParse::Param(FCommandLine::Get(), TEXT("PhysicsBenchPClassGameThread"));
    if (!bRequested) return true;
    ControllingOwner = FObjectKey(&Owner);
    Report = MakeShared<FJsonObject>();
    Report->SetStringField(TEXT("owning_benchmark_subsystem"), Owner.GetPathName());
    Report->SetBoolField(TEXT("requested"), true);
    Report->SetStringField(TEXT("scope"), TEXT("Explicit benchmark-only hard affinity for this game thread, derived from all logical processors in the highest exposed EfficiencyClass. Applied after fixture/worker creation, before measured timing. No process/worker affinity, priority, CPU-set, power or QoS policy is changed. Not a production default or a code-only speedup."));
    if (!FParse::Param(FCommandLine::Get(), TEXT("ProphecyPhysicsBenchmark")))
        return Fail(OutError, TEXT("GT class control is restricted to the isolated physics benchmark."));
#if PLATFORM_WINDOWS && (_WIN32_WINNT >= _WIN32_WINNT_WIN10)
    // A single GROUP_AFFINITY cannot restore Win11's default affinity spanning multiple groups.
    if (::GetActiveProcessorGroupCount() != 1)
        return Fail(OutError, TEXT("GT class control requires one processor group; cross-group original affinity is not representable by this bounded helper."));
    ControllingThreadId = ::GetCurrentThreadId();
    Report->SetNumberField(TEXT("game_thread_id"), ControllingThreadId);
    if (::GetThreadGroupAffinity(::GetCurrentThread(), &OriginalAffinity) == 0)
        return Fail(OutError, FString::Printf(TEXT("GetThreadGroupAffinity failed: %u."), ::GetLastError()));
    Report->SetObjectField(TEXT("original_game_thread_affinity"), AffinityJson(OriginalAffinity));
    DWORD_PTR ProcessMask = 0, SystemMask = 0;
    if (::GetProcessAffinityMask(::GetCurrentProcess(), &ProcessMask, &SystemMask) == 0)
        return Fail(OutError, FString::Printf(TEXT("GetProcessAffinityMask failed: %u."), ::GetLastError()));
    Report->SetStringField(TEXT("original_process_mask_hex"), FString::Printf(TEXT("0x%llx"), uint64(ProcessMask)));
    Report->SetStringField(TEXT("original_system_mask_hex"), FString::Printf(TEXT("0x%llx"), uint64(SystemMask)));
    ULONG Required = 0;
    const bool bSizeRead = ::GetSystemCpuSetInformation(nullptr, 0, &Required, ::GetCurrentProcess(), 0) != 0;
    const DWORD SizeError = bSizeRead ? ERROR_SUCCESS : ::GetLastError();
    if ((!bSizeRead && SizeError != ERROR_INSUFFICIENT_BUFFER) || Required == 0 || Required > 16u * 1024u * 1024u)
        return Fail(OutError, FString::Printf(TEXT("CPU-set topology size unavailable: error=%u bytes=%u."), SizeError, Required));
    TArray<uint8> Buffer;
    Buffer.SetNumUninitialized(int32(Required));
    ULONG Returned = Required;
    if (::GetSystemCpuSetInformation(reinterpret_cast<PSYSTEM_CPU_SET_INFORMATION>(Buffer.GetData()),
        Required, &Returned, ::GetCurrentProcess(), 0) == 0)
        return Fail(OutError, FString::Printf(TEXT("CPU-set topology unavailable: %u."), ::GetLastError()));
    if (Returned > Required) return Fail(OutError, TEXT("CPU-set topology exceeded the supplied buffer."));
    TArray<SYSTEM_CPU_SET_INFORMATION> CpuSets;
    int32 MinimumClass = MAX_int32, MaximumClass = INDEX_NONE;
    for (ULONG Offset = 0; Offset < Returned;)
    {
        if (Returned - Offset < sizeof(DWORD) + sizeof(CPU_SET_INFORMATION_TYPE))
            return Fail(OutError, TEXT("Truncated CPU-set topology entry."));
        const auto* Entry = reinterpret_cast<const SYSTEM_CPU_SET_INFORMATION*>(Buffer.GetData() + Offset);
        if (Entry->Size < sizeof(DWORD) + sizeof(CPU_SET_INFORMATION_TYPE) || Entry->Size > Returned - Offset)
            return Fail(OutError, TEXT("Invalid CPU-set topology entry size."));
        if (Entry->Type == CpuSetInformation)
        {
            if (Entry->Size < sizeof(SYSTEM_CPU_SET_INFORMATION)) return Fail(OutError, TEXT("CPU-set topology entry lacks required fields."));
            CpuSets.Add(*Entry);
            MinimumClass = FMath::Min(MinimumClass, int32(Entry->CpuSet.EfficiencyClass));
            MaximumClass = FMath::Max(MaximumClass, int32(Entry->CpuSet.EfficiencyClass));
        }
        Offset += Entry->Size;
    }
    if (CpuSets.IsEmpty() || MaximumClass == MinimumClass)
        return Fail(OutError, TEXT("No distinct processor performance classes were reported. Run without PhysicsBenchPClassGameThread; no P/E identity is guessed."));
    SelectedGroup = OriginalAffinity.Group;
    TArray<TSharedPtr<FJsonValue>> SelectedProcessors;
    for (const auto& Entry : CpuSets)
    {
        const auto& Cpu = Entry.CpuSet;
        if (Cpu.EfficiencyClass != MaximumClass) continue;
        if (Cpu.Group != SelectedGroup || Cpu.LogicalProcessorIndex >= 64)
            return Fail(OutError, TEXT("Highest-class processors cannot all be represented in the original thread group."));
        if (Cpu.Allocated && !Cpu.AllocatedToTargetProcess)
            return Fail(OutError, TEXT("A highest-class CPU is exclusively allocated to another process; no reduced subset is substituted."));
        const uint64 Bit = uint64(1) << Cpu.LogicalProcessorIndex;
        if ((SelectedMask & Bit) != 0) return Fail(OutError, TEXT("Duplicate logical processor in CPU-set topology."));
        SelectedMask |= Bit;
        auto CpuRow = MakeShared<FJsonObject>();
        CpuRow->SetNumberField(TEXT("cpu_set_id"), Cpu.Id);
        CpuRow->SetNumberField(TEXT("group"), Cpu.Group);
        CpuRow->SetNumberField(TEXT("logical_processor_index"), Cpu.LogicalProcessorIndex);
        CpuRow->SetNumberField(TEXT("core_index"), Cpu.CoreIndex);
        CpuRow->SetNumberField(TEXT("efficiency_class"), Cpu.EfficiencyClass);
        CpuRow->SetNumberField(TEXT("flags_at_selection"), Cpu.AllFlags);
        SelectedProcessors.Add(MakeShared<FJsonValueObject>(CpuRow));
    }
    if (SelectedMask == 0 || (SelectedMask & uint64(ProcessMask)) != SelectedMask
        || (SelectedMask & uint64(OriginalAffinity.Mask)) != SelectedMask)
        return Fail(OutError, TEXT("Existing process/thread affinity excludes some highest-class CPUs; no policy is widened or partial class substituted."));
    GROUP_AFFINITY RequestedAffinity = {};
    RequestedAffinity.Group = WORD(SelectedGroup);
    RequestedAffinity.Mask = KAFFINITY(SelectedMask);
    Report->SetNumberField(TEXT("selected_efficiency_class"), MaximumClass);
    Report->SetArrayField(TEXT("selected_logical_processors"), SelectedProcessors);
    Report->SetObjectField(TEXT("requested_game_thread_affinity"), AffinityJson(RequestedAffinity));
    GROUP_AFFINITY PreviousAtApply = {};
    if (::SetThreadGroupAffinity(::GetCurrentThread(), &RequestedAffinity, &PreviousAtApply) == 0)
        return Fail(OutError, FString::Printf(TEXT("SetThreadGroupAffinity failed: %u."), ::GetLastError()));
    // Keep the exact value returned by the mutation for rollback, even if an external agent raced it.
    OriginalAffinity = PreviousAtApply;
    Report->SetObjectField(TEXT("original_game_thread_affinity"), AffinityJson(OriginalAffinity));
    bApplied = bNeedsRestore = true;
    GROUP_AFFINITY AppliedAffinity = {};
    const bool bReadApplied = ::GetThreadGroupAffinity(::GetCurrentThread(), &AppliedAffinity) != 0;
    const DWORD ReadAppliedError = bReadApplied ? ERROR_SUCCESS : ::GetLastError();
    if (bReadApplied) Report->SetObjectField(TEXT("applied_game_thread_affinity"), AffinityJson(AppliedAffinity));
    DWORD_PTR ProcessAfter = 0, SystemAfter = 0;
    const bool bReadProcess = ::GetProcessAffinityMask(::GetCurrentProcess(), &ProcessAfter, &SystemAfter) != 0;
    const bool bProcessUnchanged = bReadProcess && ProcessAfter == ProcessMask && SystemAfter == SystemMask;
    Report->SetBoolField(TEXT("process_affinity_unchanged_after_apply"), bProcessUnchanged);
    if (!bReadApplied || AppliedAffinity.Group != RequestedAffinity.Group || AppliedAffinity.Mask != RequestedAffinity.Mask || !bProcessUnchanged)
    {
        FString RestoreError;
        Restore(Owner, RestoreError);
        return Fail(OutError, FString::Printf(TEXT("Applied GT affinity verification failed (read error %u). %s"), ReadAppliedError, *RestoreError));
    }
    return true;
#else
    return Fail(OutError, TEXT("GT class control requires Windows 10 CPU-set topology APIs. Unflagged benchmarks remain available."));
#endif
}

bool Restore(const UObject& Owner, FString& OutError)
{
    OutError.Reset();
    if (!bNeedsRestore) return true;
    if (ControllingOwner != FObjectKey(&Owner)) return true;
#if PLATFORM_WINDOWS
    if (!IsInGameThread() || ::GetCurrentThreadId() != ControllingThreadId)
        return Fail(OutError, TEXT("GT affinity restoration attempted from a different thread."));
    if (::SetThreadGroupAffinity(::GetCurrentThread(), &OriginalAffinity, nullptr) == 0)
        return Fail(OutError, FString::Printf(TEXT("Original GT affinity restoration failed: %u."), ::GetLastError()));
    GROUP_AFFINITY RestoredAffinity = {};
    if (::GetThreadGroupAffinity(::GetCurrentThread(), &RestoredAffinity) == 0)
        return Fail(OutError, FString::Printf(TEXT("Restored GT affinity readback failed: %u."), ::GetLastError()));
    if (Report) Report->SetObjectField(TEXT("restored_game_thread_affinity"), AffinityJson(RestoredAffinity));
    if (RestoredAffinity.Group != OriginalAffinity.Group || RestoredAffinity.Mask != OriginalAffinity.Mask)
        return Fail(OutError, TEXT("Restored GT affinity differs from the captured original."));
    bNeedsRestore = false;
    bRestored = true;
    return true;
#else
    return Fail(OutError, TEXT("GT affinity restoration unavailable on this platform."));
#endif
}

bool ValidateObservedFrame(const CharacterProfiling::FFrame& Frame, FString& OutError)
{
    OutError.Reset();
    if (!bRequested) return true;
    if (!bApplied || !bNeedsRestore || !ProcessorAllowed(Frame.StartProcessor) || !ProcessorAllowed(Frame.EndProcessor)
        || Frame.ProcessorSampleOverflow != 0)
        return Fail(OutError, TEXT("Controlled benchmark frame escaped the selected GT class or lost processor provenance."));
    for (int32 Index = 0; Index < Frame.ObservedProcessorCount; ++Index)
        if (!ProcessorAllowed(Frame.ProcessorSamples[Index].Processor))
            return Fail(OutError, TEXT("A sampled compose/refresh scope entered outside the selected GT class."));
    return true;
}

TSharedPtr<FJsonObject> ToJson()
{
    check(IsInGameThread());
    if (!Report) Report = MakeShared<FJsonObject>();
    Report->SetBoolField(TEXT("requested"), bRequested);
    Report->SetBoolField(TEXT("applied"), bApplied);
    Report->SetBoolField(TEXT("restoration_pending"), bNeedsRestore);
    Report->SetBoolField(TEXT("restored"), bRestored);
    return Report;
}
}
