# Exact unblended physical-target endpoint cache (draft)

**No active edits, Unreal launch, build, or performance claim.** Promote the three files under `Source/GameAnimationSample3/Private/` in this draft, apply `AgentEndpointCache.apply-patch.txt` as three isolated hunks, and apply `EndpointCacheControl.apply-patch.txt` for the profiling enum/name, boundary report, and two launcher switches. Active baseline hashes and source-preservation checks are in `SourceVerification.json` and `ControlVerification.json`. `BuildDraft.py` and `BuildControls.py` regenerate only this Saved draft from current source plus the small addition text files; do not run them after promotion. `ControlPreview` is verification output, not a request to overwrite the parent's entire files.

## Scope / lifetime

The existing `FNNPoseDataSource` receives a mutable private `FEndpointCache`. It is used only by the physical data-source branch of `ReadNNFutureWorldPoseWithSnapshot`. Reconfiguration to another AgentId resets it; existing `ClearNNPoseDataSource` and `EndPlay` remove that map value and all its cache storage. No new global cache, UObject ownership, delegate, tick, public Blueprint setting, or source-store protocol is introduced.

The current public `ProphecyNNPhysicalTargets::BuildWorldPoses` remains literally unchanged and available as an uncached oracle. `FLayout::Evaluate` receives only the requested entry profiling scope; its validation, math, and output gathering remain literal original code. The cache owns a layout with the same `Update` implementation. Every call still reads non-null live PHAT body names in order and compares source names, reference names/parents, reference count, and all original source/reference length requirements. Weak mesh/PHAT identities reset the entire cache when either asset changes.

The only saved result is the complete, **unblended** previous and future target arrays. Existing Agent interpolation alpha/time handling, `BlendAuthoredWorldTransform`, and `ApplyRigidForearms` remain unchanged and execute every call with the current snapshot and attack set. Current local hand offsets remain live, even when the endpoint component-space poses do not change.

## Equality and invalidation

A hit requires exact equality of the actual expansion operands:

- Both captured previous/current component-to-world transforms.
- Both endpoint source transforms for every needed NN-supplied bone.
- The current reference-local transform for each needed bone absent from the NN source.

The existing needed-ancestor layout already stops at supplied **component-space** bones. Every required missing-bone `Local * ParentWorld` multiplication retains its original ordering, including nonuniform/reflected scale. This cache does not precompose chains or interpolate reference/source components.

Matching copies each operand's complete object representation into a private byte array and compares those bytes. It never uses a tolerance, quaternion sign equivalence, a layout hash, or revision as proof. Signed zero, quaternion sign, and SIMD-lane changes miss conservatively; any padding difference is only a harmless false miss. Comparing only ten public scalar components would be insufficient for arbitrary low-level inputs: UE's public raw-register constructor can retain nonzero scale W (Core/Public/Math/TransformVectorized.h:229-234), and its private negative-scale test checks all four lanes (720-722). No padding-dependent numerical claim is made. Revision/time changes alone can hit only because every operand byte and live layout still matches. Inputs not read by the original expansion need not invalidate its endpoints: for example, an ignored null PHAT row, an unused source transform, or local attack hand offsets (applied freshly afterward).

Non-finite needed operands or resulting endpoints are never retained; repeated such input calls use the unchanged arithmetic again. Diagnostic configurations with `ENABLE_NAN_DIAGNOSTIC || DO_GUARD_SLOW` retain no endpoints at all, preserving repeated engine math diagnostics/slow checks. These guards affect eligibility only, not acceptance, normalization, clamping, or output values. Finite zero/nonuniform/negative scales are not altered. Public malformed-length inputs return the same false/empty result; a failed call invalidates any previous ready result.

## Why this can help, and limits

Current manager `Tick` calls `PublishAgentPose` only when `Steps > 0` (manager cpp 1849-1877), whereas Agent physical-target reading happens each presentation frame (Agent cpp 1779-1839). The pose store copies unchanged endpoint values on intermediate frames; captured component worlds belong to their policy frames, so current carrier motion is not an extra input to these particular endpoints. A fully NN-supplied 22-target cache hit removes 44 transform multiplications. It still performs live layout checks, 46 exact operand-transform comparisons (44 source endpoints plus two worlds), and copies 44 output transforms. Cache misses add retained-input/output copies. Per-agent layout storage also replaces the prior shared layout for this private branch. No timing benefit is assumed; compare target_read and whole-world means on the same workload before adoption.

Source authority: `ProphecyNNPhysicalTargetPose.cpp:43-133` for layout/dependency and literal math; `ProphecyNNPoseTypes.cpp:123-168,210-249,258-278` for publication/copy/clear and fresh rigid-forearm behavior; `ProphecyAgent.cpp:74-81,1448,1603-1617,1779-1839` for source ownership and interpolation. Current revision allocation is process-global uint32 and skips zero on wrap (pose types cpp 10-19); clearing currently does not reset its counter, but arbitrary snapshots/tests can reuse a revision and uint32 can wrap. The cache does not depend on either fact.

## Meaningful regression drafts

All prior three physical-target oracle tests are retained unchanged. Four new tests compare all previous and future output scalar bits against **both** the unchanged public evaluator and the frozen original full-skeleton traversal:

1. `Prophecy.NN.PhysicalTargets.EndpointCacheMatchesUncached`: 96 deterministic varied normalized/nonuniform/reflected pose/layout cases, initial call, repeated identical call, and revision/time-only change. Four layouts cover supplied bones, missing helpers, entirely reference-local fallback, and duplicate/reordered/unknown source names.
2. `Prophecy.NN.PhysicalTargets.EndpointCacheDependencyChanges`: same revision through individual endpoint/source/world changes, quaternion sign and signed zero, zero/negative scale, a public raw-register hidden scale-lane change, NN ordering, PHAT body names/order/duplicates/nulls, missing reference roots, live ref-pose/topology edits, asset replacement, and rejected short source followed by valid reuse.
3. `Prophecy.NN.PhysicalTargets.EndpointCacheInterpolationAndLifetime`: six interpolation alphas with real pose-store rigid forearms off/on and changed current local hand offsets, source clearing/republication using the same source/output storage and a deliberately reused revision, plus explicit cache lifetime reset. Every final interpolated target also matches the original path.
4. `Prophecy.NN.PhysicalTargets.EndpointCacheNonFiniteFallback`: NaN/Inf input edits after a valid cache, repeated non-finite reads, and return to finite input; no false hit and both unchanged endpoint oracles remain authoritative. This test is compiled only where the diagnostic/slow-check configuration allows intentionally non-finite math inputs.

The direct hit observation exists only under `WITH_DEV_AUTOMATION_TESTS`; it verifies that the comparisons exercise a real cached path, while full output oracles establish correctness. Parent owns compilation and execution; these tests have not been run.

## Same-binary A/B and independent expansion count

`-ProphecyNNNoEndpointCache` is parsed once by `IsEndpointCacheDisabledByCommandLine`. The Agent's physical DataSource branch chooses the unchanged public evaluator when that switch is present, and the new cache otherwise; interpolation/attack adjustment follows the branch unchanged. The per-case audit and final JSON independently record the actual parsed selector under `physical_endpoint_cache_disabled_by_commandline` and `physical_endpoint_cache_disabled_by_commandline_at_finish`.

Both existing launchers accept `-NoEndpointCache`: `Tools/NN/RunSterilePhysicsBenchmark.ps1` permits explicit `JoltCrowd` or `NNJoltCrowd`, and `Tools/Jolt/RunGameModuleSimdBenchmark.ps1` forwards it and records it in its provenance sidecar. No process-launching behavior changes besides this argument.

The new existing-framework GT phase `TargetEndpointExpand` / `target_endpoint_expand` surrounds **only** `FLayout::Evaluate`, so every actual evaluator entry increments its existing per-frame call count. The phase includes that evaluator's retained checks and output gathering, not cache-key validation or cached output copies. Existing generic JSON serialization automatically reports `character_cpu_ms`, `character_cpu_calls`, and the mean time. It is nested inside `target_read`; do not add it to the parent or world total.

For 100 actual-NN agents with exactly one target read each frame, disabled-cache control should show 100 evaluator calls each frame. With unchanged 30 Hz source snapshots between 60 Hz presentation frames, the cached path can alternate 100 and 0; the counts must establish this rather than assuming it. Additional real publications, dependency edits, source reads, or conservative byte-key misses can legitimately change that pattern. Synthetic JoltCrowd's per-frame authored changes need not yield hits. Normal gameplay profiling remains disabled as before; the switch and phase introduce no update-cadence change.

## Current checks

`BuildDraft.py` verified three unique Agent hunk anchors and byte-preservation of the old evaluator arithmetic/public wrapper and all old tests (apart from the declared evaluator entry scope). `BuildControls.py` verified eleven full-line isolated control hunk anchors; its profiling enum and name tables both contain 39 phases. Both preview PowerShell launchers passed parser AST checks without execution. The Agent hunk changes only the endpoint-building branch; per-frame blend/rigid-forearm code remains untouched. Baseline active files were read, not modified. Independent review was requested; the other agent was occupied, so it remains pending.
