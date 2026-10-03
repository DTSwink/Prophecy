# Remaining completed-pose publication cost

Source-only review, 2026-09-09. No active source changes, UE launches, or builds.

## Measured boundary

`Saved/Benchmarks/jolt_bulk_query_100_20260909_1204-summary.json` reports 100 characters at 20.8337 ms mean whole-world tick. Completed publication is 10.1661 ms; normal `RefreshBoneTransforms` is 6.2135 ms inclusive of the 2.0805 ms query commit; `TickAnimation` is 1.0380 ms. All functionality checks passed.

The same run's engine CSV reports `Animation/GameThread/WorkerThreadTickTime` at 1.4008 ms. UE places this scope around all of `PerformAnimationProcessing`, including animation update if needed, compact-pose evaluation/copy, local-pose finalization and local-to-component recomposition. Consequently bypassing the repeated component-space calculation alone cannot recover all 4.1330 ms of refresh outside the query commit. Roughly 2.7 ms remains in refresh setup, post-evaluation and finalization (scope populations/timing must still be checked before treating this subtraction as exact).

## Direct component-space publication is incomplete through the public setters

Local engine root: `C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime`.

* `Engine/Classes/Components/SkinnedMeshComponent.h:1636`: `GetEditableComponentSpaceTransforms` is a public mutable array accessor.
* `Engine/Classes/Components/SkeletalMeshComponent.h:2076`: `FinalizeBoneTransform` is public and virtual.
* `Engine/Classes/Components/SkinnedMeshComponent.h:899` and `:1708`: the flip-needed flag and `FlipEditableSpaceBases` are protected.
* `Engine/Private/Components/SkinnedMeshComponent.cpp:4590`: buffer flip, render bone revision and motion-vector update bookkeeping happen only when the flip-needed flag is set. A public editable-array write followed by `FinalizeBoneTransform` alone does not set it.
* `Engine/Classes/Components/SkeletalMeshComponent.h:431`: local-pose accessors return a copy or const view. Its public `BoneSpaceTransforms` field is explicitly deprecated since 4.23; there is no equivalent public mutable setter in this header.
* `Engine/Classes/Components/SkeletalMeshComponent.h:2533`, `:2554`, `:2630`: context-buffer swap, stored evaluation context and full `FinalizeAnimationUpdate` are private.
* `Engine/Private/PhysicsEngine/PhysAnim.cpp:468`: full finalization includes bone callbacks, socket attachments, overlaps, bounds invalidation/update, render transform/dynamic-data dirtiness and follower refresh.

`PostAnimEvaluation(FAnimationEvaluationContext&)` is exported and public (`SkeletalMeshComponent.h:2125`). It can set the flip-needed flag and run full finalization. However it consumes the mesh's current local transforms, private curves/attributes and cache state; passing an independently constructed context does not install its transform arrays into the component. A direct-publication implementation would therefore depend on deprecated local-array mutation and reconstruct the evaluation-state invariants. This is not a clean replacement for `RefreshBoneTransforms` on the retained original component. Do not use a const cast, fabricated subclass cast, private-access trick, component replacement or engine patch to cross these boundaries.

## Narrow next measurement

Keep all current animation update/evaluation/callback calls. Add opt-in scopes to the existing native proxy:

1. Whole proxy `PreUpdate`, including its base call and immutable snapshot copy: distinguishes the native proxy's cost from `TickAnimation`'s surrounding UE work.
2. Base `PreEvaluateAnimation`: captures object/log/cache setup.
3. Native `Evaluate`: separates compact-pose reset/copy/normalization from the surrounding engine evaluation and component-space calculation. This callback may run on a worker outside the synchronous benchmark, so the current game-thread-only profiling accumulator must not be called unconditionally here.
4. Base `PostEvaluate` before the query hook: the base clears cached objects, flushes debug draw and processes animation logging in an Editor build.
5. A marker immediately after the query hook returns. The interval until `RefreshBoneTransforms` returns contains the retained disabled postprocess instance's post-evaluation callback, buffer flip/queued animation callbacks, socket attachments, overlap refresh, bounds, render dirtiness and follower refresh. It excludes evaluation and query publication.

If that final interval dominates, a lifetime-bound `OnBoneTransformsFinalized` observer can divide it into work before that callback and work after it. Delegate order means this is an observational boundary, not an exact measurement of every user callback. Register once per binding, remove by handle during teardown; do not add an allocation/registration per frame. Keep all callbacks intact and preserve existing post-callback identity validation.

Existing engine scopes already identify `STAT_FinalizeAnimationUpdate_UpdateChildTransforms`, `..._UpdateOverlaps`, `..._UpdateBounds` in `PhysAnim.cpp:464` onward. A trace/stat capture containing those scopes could further separate the final interval without engine source changes.

## Limits

No direct-publication implementation is proposed as ready. No measured speedup beyond the already passed query-batching run is claimed. A future direct path would need local/component/socket/render/previous-buffer agreement, nonuniform scale, hidden and LOD bone behavior, morph/material curves, follower/socket attachments, bounds and immediate query checks, plus callback disable/replacement tests. Those responsibilities should not be silently removed to reach the timing target.
