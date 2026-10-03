# Physical feedback controls: verified DEFAULT build

All three complete 100-character runs pass the independent [full-row auditor](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/AuditPhysicalFeedbackModes.py>) and [machine comparison](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/PhysicalFeedbackComparison.json>). Each run passes 48 checks; all 1,080 measured rows are retained. PreparedParallel reduces the inclusive physical-feedback wall time, but these single runs do not demonstrate a reliable whole-pipeline improvement. Original remains the default.

| Feedback mode / source report | World mean ms | Reported median ms | p95 ms | Inclusive resample ms / world frame |
|---|---:|---:|---:|---:|
| [Original](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/nn_jolt_feedback_original_100_20260909_1641.json>) | 11.521021 | 11.542801 | 14.564000 | 0.544910 |
| [PreparedSerial](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/nn_jolt_feedback_preparedserial_100_20260909_1641.json>) | 11.376522 | 11.458300 | 14.110100 | 0.535807 |
| [PreparedParallel](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/nn_jolt_feedback_preparedparallel_100_20260909_1641.json>) | 11.472184 | 11.642002 | 13.852797 | 0.258446 |

The report median is sorted sample index 180, and p95 is index 342, for 360 samples. Conventional medians are also preserved in the machine output. These are elapsed world/GT wall intervals in NullRHI, not summed worker CPU time, rendered FPS or a Shipping result. No run meets the requested sub-10ms full-pipeline mean.

## What the counter and scope checks establish

Every run has 180 actual CPU NN steps and 18,000 successful physical samples, with exactly 180 inference frames and 180 interpolation-only frames. All run/walk/upper models remain CPU batch 100; foot-roll steps remain four. On each inference frame:

- Original records 100 physical samples, 200 raw-encoding scopes and zero prepared items/joins.
- Each prepared mode records 100 physical samples, 100 prepared items and one completed batch. The measured totals are exactly 18,000 items and 180 joins.
- Prepared raw-encoding scope count is zero because that work is inside the joined batch scope. The math was not removed.
- On interpolation-only frames, all feedback counter increments and feedback scope calls are zero. The mode is verified in the initial state, all 360 rows and final summary.

The auditor independently reconstructs the counter deltas, expected calls, cumulative NN timer deltas and summary means. The sample/prepare/raw/batch child scopes remain within inclusive resample wall time. PreparedSerial and PreparedParallel share GT sampling/preparation and the same kernel; the explicit serial control isolates dispatch from those structural changes.

| Per-world-frame scope, ms | Original | PreparedSerial | PreparedParallel |
|---|---:|---:|---:|
| GT physical sample read | 0.111404 | 0.107094 | 0.111449 |
| GT prepared input capture | 0 | 0.037457 | 0.038692 |
| Joined prepared math wall | 0 | 0.376720 | 0.091571 |
| Legacy raw encoder scope | 0.079294 | 0 | 0 |
| Whole NN manager tick | 2.362157 | 2.335447 | 2.170577 |

All kernel invocations and output writes finish before ParallelFor returns; scheduler bookkeeping may outlive that return. The manager continues only after commits. The [three NN tests](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/Foundation-20260909-163756-375/index.json>) pass cleanly: PreparedBatchFullState, RotationCacheRawEncoder and PhysicalFeedbackTolerance. The prepared test compares all eleven float-buffer families and sample flags with the legacy serial helper using exact finite float-bit checks, including mixed skipped lanes and captured-input mutation. The runtime reports do not themselves dump/compare all recurrent arrays across runs. The [59 Jolt foundations](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/Foundation-20260909-163819-866/index.json>) also pass with zero warnings, errors or skipped tests.

## Whole-world differences and attribution limits

Original to PreparedParallel: inclusive feedback decreases 0.286463 ms, while the arithmetic remainder of the world interval increases 0.237627 ms. Net world mean changes -0.048837 ms (-0.424%); reported median increases 0.099201 ms. PreparedSerial to PreparedParallel saves 0.277361 ms in feedback, but the world mean increases 0.095662 ms.

For Original to PreparedParallel, the non-overlapping top-level scope differences are manager -0.191580 ms, agent ticks +0.039775 ms, coordinator +0.036136 ms, and the remaining world interval +0.066832 ms. Within the manager, visual-root time increases 0.030008 ms, NN inference 0.026229 ms, output 0.016871 ms and store 0.010833 ms. These are measured associations across one run per mode; neither random noise nor a causal scheduling penalty is proven.

The NN build timer decreases 0.279420 ms, but [StepSimulation](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp:2777>) starts that timer before ResamplePhysicalAgents and also accumulates upper-input construction. Its reduction overlaps the feedback saving; it is not an additional model-input optimization. Detailed child phases must not be summed with their parents.

Original inference/interpolation world means are 13.282408 / 9.759633 ms; PreparedParallel means are 13.014703 / 9.929665 ms. The interpolation frames execute no feedback batch, yet their mean is higher in the parallel run. The retained data cannot isolate whether scheduling carryover, caches, clocks or unrelated variation caused that difference.

## Preserved workload, ownership and binary evidence

Each run validates 36,000 agent-frames, 792,000 dynamic-body checks and 3,168,000 skeleton-bone checks. All 2,200 Jolt bodies are active on every frame; 2,100 joints, 100 real floor-blocking capsules, 25 policy bones and full 88-bone feedback/presentation remain. All 36,000 ordinary unfiltered head queries and capsule identities pass after EndPhysics, checking 792,000 query-body poses with zero own-capsule fallback. All existing pose tolerances remain satisfied. Every character travels at least 1,200.010681 cm.

The world remains 60Hz with 30Hz actual NN, fresh 60Hz target endpoint expansion, one shared DuringPhysics step per frame, worker count seven/job concurrency eight, NoLock idle reads, 40cm query-tree padding, no Chaos pause and no synthetic targets after adoption. Camera subtrees are detached with 200 components retained; movement-only scope is unchanged. Zero Chaos dynamic ownership is verified throughout. Removal from bone finalization, 22 removed stale handles, 2,178 survivor handles, two unmeasured lifecycle steps, pending cancellation and final floor-only teardown with 2,200 stale handles all pass.

GT entry/exit and all 36,000 refresh entries per run are observed on P-class CPUs. The explicit diagnostic restores original GT mask 0xfff after using 0xff; process affinity stays 0xfff and Normal priority stays unchanged. Observed entries do not establish continuous residency, worker utilization, clock speed or thermals.

The [before capture](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/FeedbackBatchBinaryCapture-20260909-1641.json>) and [after verification](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/FeedbackBatchBinaryAfter-20260909-1641.json>) independently match all seven DLL/executable hashes. The game DLL is CF2AE0511530FEBCF991C03AAA2BD4A7FCBF2532DB569044B86B4F54BBF1C626; the native Jolt DLL remains the SSE2 profile. All reports identify ordinary DEFAULT game profile 0, no private PCH or AVX flags, expected stored math layouts and enabled stock Engine ISPC controls. This is saved boundary identity evidence, not continuous loaded-memory monitoring.

The fixture remains a separated moving crowd with explicit floor contacts, original PHAT hard angular limits and local ownership. It does not claim full production-world/contact-stress integration, rendered blood-pixel validation or completion of the migration plan.

