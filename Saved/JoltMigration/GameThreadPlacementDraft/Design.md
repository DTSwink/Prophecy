# Explicit game-thread processor-class diagnostic

This is an opt-in measurement control, not a production default or an optimization claim. Keep the executable, 100-agent workload, model precision, 30 Hz inference, 60 Hz physics/presentation, movement profile, contacts and measurement boundaries identical across the controlled comparisons. Worker policy is unchanged. Synthetic JoltCrowd results do not satisfy the actual-NN acceptance gate.

## Why this diagnostic is needed

Retained 360-frame reports show different placement even with Normal process priority, GT priority +1 and unchanged process/thread/system masks `0xfff`:

| Report under Saved/Benchmarks | Process policy | Frame-start class | World mean ms | Refresh entry class / mean microseconds per call |
| --- | --- | --- | ---: | --- |
| jolt_processor_preA_100_20260909_1244.json | BelowNormal | 360/360 class 0 | 17.8816 | 36,000 class 0 / 48.7025 |
| jolt_processor_normalA_100_20260909_1246.json | Normal | 360/360 class 1 | 10.5153 | 35,943 class 1 / 23.3302; 57 class 0 / 79.3140 |
| jolt_during_batch_100_20260909_1307.json | Normal | 360/360 class 0 | 14.9870 | 36,000 class 0 / 47.7482 |

On this host, the topology reports logical CPUs 0–7 as class 1 and 8–11 as class 0. The implementation does not contain those indices. The last report passed all 360 per-frame checks but failed the final natural-motion edge-ray coverage requirement; that is a missing coverage gate, not a demonstrated pose/query failure. It must not be presented as a complete successful benchmark. See `../ProcessorProvenanceDraft/Placement-duringBatch-normalA-preA-20260909.json` for exact grouped metrics and partition checks.

CPU entry observations are not continuous residency or CPU time. Batched pose composition runs pure work across UE workers/caller; its worker processor placement is not sampled. Both process/thread power-throttling reads returned error 87, so QoS state is unknown. Frequency, thermal state and the OS's reason for placement have not been measured. These runs establish association, not that all timing changes were caused by code or core class.

## Supported mechanism and bounded policy

Microsoft describes CPU Sets as soft affinity; conflicting hard masks take precedence, and unavailable allocated sets may be ignored. They therefore do not give this diagnostic a strict measured placement invariant. [CPU Sets](https://learn.microsoft.com/en-us/windows/win32/procthread/cpu-sets)

`GetSystemCpuSetInformation` supplies variable-size topology entries. A higher `EfficiencyClass` means faster, less energy-efficient processors; group/logical indices map to thread affinity, and SMT siblings share a core index. The helper selects **every logical CPU in the highest reported class**, including all its SMT threads. [SYSTEM_CPU_SET_INFORMATION](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-system_cpu_set_information)

`SetThreadGroupAffinity` changes only the specified thread and returns its previous group/mask. The helper applies it to the current GT and retains the exact returned original for restoration. Thread affinity must remain within process affinity. [SetThreadGroupAffinity](https://learn.microsoft.com/en-us/windows/win32/api/processtopologyapi/nf-processtopologyapi-setthreadgroupaffinity), [SetThreadAffinityMask](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-setthreadaffinitymask)

A single group/mask cannot describe Windows 11's default affinity spanning multiple processor groups. The helper refuses multi-group hosts rather than recording an incomplete original policy. It also refuses indistinguishable classes, malformed/unavailable topology, a highest-class CPU exclusively allocated elsewhere, or an existing process/thread mask that excludes any highest-class CPU. It never widens a prior policy or silently substitutes a subset. Ordinary unflagged runs remain available. [GetThreadGroupAffinity](https://learn.microsoft.com/en-us/windows/win32/api/processtopologyapi/nf-processtopologyapi-getthreadgroupaffinity), [Processor Groups](https://learn.microsoft.com/en-us/windows/win32/procthread/processor-groups)

## Lifecycle and evidence

- Native flag: `-PhysicsBenchPClassGameThread`; launcher switch: `-PClassGameThread`. Only explicit `JoltCrowd` or `NNJoltCrowd` is accepted. Normal launcher/process behavior remains the default without the switch.
- `Begin` runs after fixture creation/admission and warmup, before the first measured timestamp/profiler frame. Existing UE and Jolt worker pools already exist. No process/worker affinity, CPU sets, priority, QoS or machine power policy is changed.
- The first measured frame still includes the existing cold Jolt workload. No additional warmup or cadence change was introduced.
- Begin reads topology and policies once, applies the GT mask, verifies native readback and unchanged process/system masks. Later calls use cached state; there are no new OS queries inside timed loops.
- Existing per-frame processor observations must place the GT frame start/end and every sampled compose/refresh entry inside the selected mask, with no provenance overflow. Validation remains outside the timed interval.
- `Finish`, including failure paths, restores and verifies the original GT affinity before writing the final report. `Deinitialize` retries if needed. Restore failure is an explicit report error, not silently accepted. Restoration is scoped to this process; a process crash ends the thread itself.
- JSON `game_thread_processor_control` records request/apply/restore state, native GT ID, selected logical CPUs/class/flags, original/applied/requested/restored GT affinity, original process/system masks, and apply-time unchanged-process verification. The profiler's initial policy will observe the applied mask; the helper separately retains the pre-apply original. No claim is made to have sampled actual worker residency.

## Local UE source explains why Normal alone is insufficient

Verified against the installed UE5.7 source under `C:/Program Files/Epic Games/UE_5.7/Engine/Source`:

- `Runtime/Launch/Private/LaunchEngineLoop.cpp:2140–2146` assigns GT priority and the platform main-game mask. `Runtime/Core/Public/Windows/WindowsPlatformAffinity.h:20` selects AboveNormal for the GT.
- `Runtime/Core/Public/GenericPlatform/GenericPlatformAffinity.h:48,78,88,93` supplies unrestricted default masks for main-game/task/background workers. `Runtime/Core/Private/Windows/WindowsPlatformProcess.cpp:822–837` does not issue a native affinity change for the NoAffinity mask.
- `Runtime/Core/Private/Async/Fundamental/Scheduler.cpp:178–221` configures worker priorities/affinities separately. The project `ProphecyJoltPoseBatch.cpp:7` uses normal `ParallelFor`, and the plugin `ProphecyJoltWorldSubsystem.cpp:373` creates its separate Jolt worker pool.
- `ProphecyJoltCharacterWorldSubsystem.cpp:41` keeps the coordinator on the GT. `TickTaskManager.cpp:1059` permits GT work while DuringPhysics is released nonblocking; `LevelTick.cpp:781–789,1721–1749` orders the tick groups. Changing phase affects when work is runnable and what can overlap; it does not identify or pin a P/E core.

The OS retains placement choice when only priority changes. Exact OS scheduling, thermal or frequency causes remain unproved; use matched controlled observations rather than selecting the fastest historical run.

## Promotion and checks

Two new private helper files plus `BenchmarkHooks.patch` constitute the source checkpoint. `BaselineHashes.json` records the original two benchmark file hashes. `Launcher.patch` is a separate minimal hunk preserving process priority, CSV, stdout and existing method flags. Root owns promotion/build/execution.

Source review verified the active profiler fields, UE Windows API guards and FString concatenation overload (`UnrealString.h.inl:687`). The source patch passed `git apply --check` before promotion. No build, UE launch, affinity change or benchmark was performed by this subtask. Root must require successful compilation, normal/unflagged behavior, flagged smoke, original/applied/restored evidence, complete functionality gates and same-binary repeated 100-agent comparisons before drawing performance conclusions.
