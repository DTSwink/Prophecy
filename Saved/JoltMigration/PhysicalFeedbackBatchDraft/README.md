# Physical feedback preparation and joined math draft

Draft only. No active source edits, build, UE launch or ISA change was performed. `Original` remains the default. This is a same-binary experiment, not a measured optimization claim.

Apply `ExistingFiles.patch` after checking `BaselineHashes.json`, then copy these two new files to their corresponding active paths:

- `Source/GameAnimationSample3/Private/ProphecyNNPhysicalFeedbackBatch.inl`
- `Source/GameAnimationSample3/Private/Tests/ProphecyNNPhysicalFeedbackBatchTests.inl`

The patch changes seven existing files: manager header/cpp, profiling header/cpp, actual-NN benchmark, normal benchmark launcher and the existing guarded game-ISA launcher. `MakeDraft.py`, this README and the baseline/patch files are tooling/evidence only. The generator reads active sources and writes only draft copies; do not promote entire stale copies over newer active work. The current endpoint-cache phase/launcher flag are preserved.

## Contract

`SetPhysicalFeedbackExecutionMode(int32)` is a native pre-BeginPlay setter. Modes are 0=Original, 1=PreparedSerial, 2=PreparedParallel. Invalid values and changes after BeginPlay are refused. The actual-NN fixture maps `-PhysicsBenchFeedbackMode=Original|PreparedSerial|PreparedParallel` to this setter before finishing the transient manager spawn. No Blueprint property, asset, collision, model precision or cadence changes are introduced.

Original keeps the immediate GT sample-then-commit order and its existing raw-encoder profiling. Its original post-sample math is moved into `CommitPhysicalSampleSerial` with only `Impl` reference syntax changed. The synchronous single-agent `ResamplePhysicalAgentState` caller in `SetAgentSimulationMode` still uses this serial path even when the crowd mode is prepared.

Prepared modes use the same live eligibility test and GT `SampleActualComponentPose`. Successful samples are captured into existing 25-transform slices. GT resolves lower/core/arm tolerance values, current walk/prior-sample flags and disjoint output pointers into preallocated work records. Failed captures/preparation never enter the kernel or modify recurrence. The 10-core-bone contract is checked during preparation; unsupported preparation becomes an explicit failed physical sample, not a hidden fallback.

One joined `ParallelFor` processes the successful indices; PreparedSerial uses `ForceSingleThread` with identical preparation and kernel. Workers read immutable native contract data and their prepared inputs, write only their own record and fixed output slices, and make no UObject calls, callbacks, tolerance-map accesses, array resizing, game-thread profiler calls or shared counter updates. Raw lower encoding accepts the captured walk flag through a boolean overload; the Agent overload is retained for the serial path and existing oracle. Global name construction is absent from the worker path. UE task scheduling still has allocation/dispatch/wait costs.

The original lower/upper operation order, equality branches, first-sample selection and recurrent-tail updates are retained. `bHasPhysicalSample`, completed/failed counters and batch/item counters are committed on GT after the join. All kernel invocations and output writes finish before `ParallelFor` returns; scheduler bookkeeping may outlive that return. NN BuildInputBatch runs only after all commits, and each kernel receives completed GT input capture.

## Measurement and acceptance

The existing total `manager_physical_resample` remains inclusive. New GT phases are `physical_feedback_prepare` (one successful capture preparation call per lane) and `physical_feedback_batch_wall` (one complete joined kernel wall interval per prepared NN step). Current `physical_raw_encode` applies only to Original's serial helper; zero in prepared mode means the raw math is inside the joined phase, not removed. Worker time is not accumulated into GT phase counters.

Every actual-NN row includes `physical_feedback_mode`, `prepared_physical_samples` and `prepared_physical_batches`. Frame validation requires monotonic counters and exactly one prepared join plus Count successful items per actual NN increment, and zero increments on interpolation-only frames. Original requires zero prepared counters. Thus a 100-agent/360-frame moving case must record 180 joins and 18,000 prepared samples in either prepared mode. All existing full NN/body/bone/query/capsule/lifetime gates remain unchanged.

Run the new `Prophecy.NN.PhysicalFeedback.PreparedBatchFullState` test plus the existing `Prophecy.NN.PhysicalFeedback.RotationCacheRawEncoder` and `Prophecy.NN.PhysicalFeedbackTolerance`. The new test compares all eleven float-buffer families and sample flags against the preserved legacy helper, with exact finite float-bit checks. It exercises 100 simultaneous items, later mixed omitted failed/disabled lanes, untouched boundary lanes, run/walk, first/subsequent samples, missing/zero/partial/large tolerances, quaternion sign/near-zero/non-unit inputs and all four lower/upper equality combinations. It deliberately changes source agent tolerance maps and flags after preparation to prove captured inputs are used. It also tests refused out-of-range preparation and an empty batch. Skipped lanes model the post-capture gate; actual UObject failure/eligibility behavior remains covered by source review and later live tests, not falsely claimed as executed by this pure-state oracle.

At the original draft handoff, no C++ build/test had been run by this agent. Root subsequently promoted and compiled the implementation, correcting the free test helper to call `Test.TestEqual`; this draft test is synchronized to that compile fix. Root's fresh-input rollback build is `UEBuild-FeedbackRollbackFreshInputs-20260909-1637.log`. Completed results now independently confirm all three NN tests and 59 Jolt foundations pass cleanly, and all three 100-character feedback modes pass every full-row functional gate; see `Saved/JoltMigration/PhysicalFeedbackComparison.md` and its machine JSON. Original source checks: the extracted serial math matches the prior tail exactly after mechanical `Impl` syntax replacement; the prepared worker has no profiler/tolerance lookup/FAgent access; the synchronous transition call remains; patch applicability and both PowerShell parsers passed; all seven active baseline hashes matched at the original handoff.

## Commands for root after promotion

Use the usual project build and the current selected game-module profile. This patch does not select SSE2/AVX2 or change Jolt workers. First run the full Jolt foundations and the three NN tests above, then 2-agent actual-NN smoke for all modes.

For the ordinary DEFAULT game build, compare separate complete runs of the same binary, using otherwise identical arguments:

```powershell
$bench = 'Tools/NN/RunSterilePhysicsBenchmark.ps1'
& $bench -Methods NNJoltCrowd -Count 100 -Warmup 60 -Samples 360 -Repeats 1 -FloorOnly -MovementOnly -DuringPhysics -PClassGameThread -NoLockIdleReads -JoltWorkerThreads 7 -QueryTreePaddingCm 40 -ProcessPriority Normal -FeedbackMode Original -Label feedback_original_A
& $bench -Methods NNJoltCrowd -Count 100 -Warmup 60 -Samples 360 -Repeats 1 -FloorOnly -MovementOnly -DuringPhysics -PClassGameThread -NoLockIdleReads -JoltWorkerThreads 7 -QueryTreePaddingCm 40 -ProcessPriority Normal -FeedbackMode PreparedSerial -Label feedback_prepared_serial_A
& $bench -Methods NNJoltCrowd -Count 100 -Warmup 60 -Samples 360 -Repeats 1 -FloorOnly -MovementOnly -DuringPhysics -PClassGameThread -NoLockIdleReads -JoltWorkerThreads 7 -QueryTreePaddingCm 40 -ProcessPriority Normal -FeedbackMode PreparedParallel -Label feedback_prepared_parallel_A
```

Each launcher returns an owned PID asynchronously. Wait for that run to finish and inspect its report before launching the next; these lines are separate operations, not a concurrent batch. Repeat/interleave controls to measure variability. If retaining an explicit game ISA build, use `RunGameModuleSimdBenchmark.ps1` with its existing `-GameProfile` guard and the added `-FeedbackMode` argument. That wrapper records the selected mode in the sidecar; its original CPU admission/native SSE2 checks are preserved. The earlier ISA reducer targets its historical schema/workload and must not be used to imply a same-source ISA comparison after this new kernel changes game source.

The original serial post-sample estimate was about 0.43 ms per world frame before dispatch/preparation costs. The retained full controls measure inclusive feedback at Original 0.544910 ms, PreparedSerial 0.535807 ms and PreparedParallel 0.258446 ms per world frame. The whole-world means are 11.521021 / 11.376522 / 11.472184 ms, so a reliable pipeline improvement and the sub-10ms goal are not established. Original remains the default. Disable the candidate simply by omitting the mode flag or passing Original; no runtime ownership teardown or asset restoration is required.
