# Optional fist-pose cache draft

2026-09-09. Draft only; no active edits, compilation, Unreal launches, tests, or asset changes were performed. The user subsequently prioritized movement and explicitly permitted disabling fist/camera work for the crowd benchmark. This cache is optional follow-up work for characters with fists enabled, not a prerequisite for the movement-only 10 ms goal.

## Measured source and scope

`Saved/Benchmarks/jolt_target_profile_100_20260909_1118.json` attributed about 8.7163 ms to Fingers within 11.5093 ms Targets for 100 characters. That is the pre-change profile, not a measured speedup from this uncompiled draft.

Old `ProphecyAttackFists::PreUpdate` reconstructs the source reference pose, samples every source bone from `closed_fist` at time zero, builds source/target component-space poses, resolves finger names/parents, and converts the authored deformation on every character frame. All of that depends on the clip and target mesh, not the current fist level. Only the final rotation Slerp and translation/scale Lerp depend on the left/right levels.

The draft shares the invariant open/closed finger locals by weak clip and mesh identity. The per-frame level sampling, exact blend expressions, NaN handling, per-proxy snapshot publication, worker application, manual/attack lifecycle and time semantics remain unchanged. Zero still explicitly overlays the target reference fingers. No animation frequency reduction, early-out at level zero, pose simplification, or authored-data replacement is added.

## Files and baseline

| Draft file | Destination |
| --- | --- |
| ProphecyAttackFistPoseCache.h/.cpp | New `Source/GameAnimationSample3/Private/` files |
| ProphecyAttackFists.cpp | Existing `Source/GameAnimationSample3/Private/ProphecyAttackFists.cpp` |
| GameAnimationSample3.cpp | Existing `Source/GameAnimationSample3/GameAnimationSample3.cpp` |
| ProphecyAttackFistPoseCacheTests.cpp | New `Source/GameAnimationSample3/Private/Tests/` file |

Copied active SHA256 baselines:

- `ProphecyAttackFists.cpp`: `8D7FD3D37131D476FEDA55A41CAA8871312858275340E821F669DA29B504F33A`
- `GameAnimationSample3.cpp`: `97FD642DD6062CB714567BB22F63AFD68EE9DC588ACC85EC3BDC16AFBB0BEA4F`

Check hashes before promotion; merge if active files changed. Agent.cpp/.h and CharacterComponent were not edited. No build-rule change is required: helper dependencies are Engine/CoreUObject, and editor APIs/tests have WITH_EDITOR guards. The project already uses current UE5.7/C++20 defaults.

The only primary-module change replaces `FDefaultGameModuleImpl` with a subclass whose shutdown first clears the cache and unregisters delegates. It preserves the same module identity and base behavior. This avoids callbacks surviving game-module teardown. Existing process-lifetime proxy storage and live proxy allocation layout remain untouched.

## Invalidation and ownership

- Cache keys are weak clip/mesh pointers including UObject serial identity. Entries contain transform values and weak dependency references only. Expired entries are pruned on misses; at most 64 pairs remain, with LRU eviction affecting rebuild cost only.
- Every access checks source and target reference-skeleton transforms exactly, plus bone names and parents. This detects direct in-place `SetRefSkeleton` changes without requiring an editor property notification. Ref-pose comparison is a byte comparison of copied FTransform arrays; name/parent checks use exact values, not tolerances.
- The extraction stamp includes source skeleton identity/GUIDs, virtual-bone GUIDs, retarget-source name, interpolation, frame rate/play length, additive type, current compressed-data/codec/track-map identity and validity, and the actual raw-versus-compressed extraction predicate. Switching `a.ForceEvalRawData` or changing the clip/mesh therefore does not reuse the wrong result.
- Animation data-model modified notifications invalidate immediately, including notifications emitted inside controller edit brackets. Source skeleton retarget-source callbacks also invalidate.
- Editor object property/modified/replacement/reload notifications and animation/mesh compilation completion invalidate the cache. Compile completion matters when the raw preview changes back to newly generated compressed data, even if an allocator reuses a data address.
- A revision counter is atomic; callbacks only mark it dirty. Cache lookup/build and reference signatures are game-thread-only. The cache never reaches into worker proxy data; existing snapshots remain protected by their original lock.
- There is no once-per-frame refresh or level-change threshold. A relevant edit between two accesses in the same frame is eligible for immediate rebuild. Runtime cooked assets use the same identity/reference/extraction checks; editor-only raw-model notifications do not enter Shipping.
- Model and retarget delegates are explicitly removed on entry eviction/reset and module shutdown. Global editor delegates are removed on shutdown.

This follows supported UE asset-edit/controller/compression paths; it does not attempt to detect arbitrary memory writes into an otherwise unchanged compressed byte buffer. The original implementation also relies on UE's synchronized animation and reference-skeleton APIs.

## Correctness tests ready for root execution

Filter: `Prophecy.Fists.Cache`

1. `FullPoseAndIndependentLevels` loads the actual `/Game/_mygame/closed_fist.closed_fist` and `/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin`. A deferred native agent invokes the real `SetFistClosedLevels`, `PreUpdate`, and `ApplyToLocalPose` path. It compares all 88 target local transforms against a frozen copy of the original uncached algorithm with zero comparison tolerance, verifies all 38 finger/metacarpal bones, checks independent open/closed/partial left/right values and 100 varying level pairs, and checks that levels do not rebuild the invariant cache. Non-finger input transforms are deliberately non-reference. Disabling fists must clear the previous overlay and preserve the full input pose.
2. `SourceAndReferenceEdits` uses a transient duplicated clip and a transient mesh containing only copied reference data. It edits a real finger track using the animation controller, checks same-frame rebuild and changed output, then changes the target ref pose through `SetRefSkeleton` without a property notification. Both outputs must match the frozen legacy algorithm. The original clip model GUID and original mesh reference pose must remain unchanged. No package is saved.

These are source-only authored tests until root compiles/runs them. No visual validation or measured post-cache performance is claimed. Source/header inspection and whitespace checks were completed; runtime behavior and exact comparison tolerance still require execution.

## Movement-only disable seam

Set `Agent->bEnableAttackFists = false`. A normal subsequent `PreUpdate` writes an empty proxy snapshot, clearing a previous closed-finger overlay. If a movement-only fast path skips `PreUpdate` altogether, call `ProphecyAttackFists::ReleaseProxy(Proxy)` on the transition before applying local poses, so the old snapshot cannot persist. Do not merely skip source reconstruction while leaving the prior snapshot installed.

## UE5.7 source evidence

- `Engine/Private/Animation/AnimSequence.cpp:1468-1514`: `GetBoneTransform` takes the compressed-data read lock, chooses raw/compressed extraction, initializes decompression context and samples the requested track; raw transform curves also affect the sampled local pose.
- `AnimSequence.cpp:3698-3709`: actual raw-data predicate, including `a.ForceEvalRawData`, compressed validity and virtual-bone GUID mismatch.
- `AnimSequence.cpp:4679-4710`: controller/model modifications update source data and clear/rebuild compressed results outside edit brackets.
- `Engine/Classes/Animation/AnimData/IAnimationDataModel.h:361-385,464-468`: data-model modification event and content GUID contract. The draft subscribes to changes instead of hashing every track on every character update.
- `Engine/Private/Animation/AnimDataModel.cpp:510-558`: `GenerateGuid` traverses key/curve/attribute data; it is used only in the test's before/after source-preservation assertion.
- `Engine/Classes/Engine/SkeletalMesh.h:2032-2053`: ref-skeleton getter synchronization and setter; setter itself does not emit a change delegate.
- `Engine/Classes/Animation/Skeleton.h:602-632`: retarget-source callback registration/removal.
- `Engine/Public/AssetCompilingManager.h:24-41,109`: asset compilation completion event.
- `CoreUObject/Public/UObject/UObjectGlobals.h:3253-3309,3367-3368`: object edit/replacement/reload notifications and delegate signatures.
- Project `Docs/AttackFistsBlueprint.md`: authored deformation semantics and prior 38-finger rendered audit; the cache preserves that conversion rather than copying source local tracks.
