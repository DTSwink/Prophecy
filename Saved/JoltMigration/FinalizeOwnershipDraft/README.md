# Legacy Chaos finalizer versus Jolt pose ownership

Draft only. No active edits, builds or UE launches. The merge patch changes only the eligibility guard of `CorrectScaledPhysicsPose` in `Source/GameAnimationSample3/Private/ProphecyModeTransitions.cpp`.

## Concrete repeated work

The manual fixture enters Physical mode before enabling Jolt. `ProphecyModeTransitions::FScope::~FScope` stores a `Blends` entry and calls `RegisterFinalizer` on the retained `PhysicalMesh` (lines 137–153 in the reviewed active source). `Blends` remains present until another transition replaces it or `ReleaseAgent` removes it; reaching interpolation alpha one does not remove the entry.

`CorrectScaledPhysicsPose` (line 54) currently rejects Kinematic mode and missing/not-yet-started blends, but does not reject Jolt ownership. `AProphecyAgent::GetSimulationMode` explicitly returns Physical for an active Jolt binding. Consequently this legacy callback still runs after every completed Jolt pose. It copies all 88 component-space transforms, finds each bone's Chaos `FBodyInstance`, and takes the nonsimulating branch for every retained query body. That branch recalculates `Original[child].GetRelativeTransform(Original[parent]) * Final[parent]`. It also mutates the finalized render/read array through an existing const cast, after Jolt's query commit.

This is a Chaos scale/blend repair, not a Jolt controller or desired helper-pose layer. Jolt's composer already preserves all body-local scales and helper/finger locals in a full local/component/world pose. Skipping only this repair while Jolt owns the physical pose avoids the redundant allocation, lookup and transform traversal and leaves the already-published result authoritative. No engine callbacks are removed. All other registered callbacks still run. The stored transition and registration remain available for later Chaos transitions.

The patch uses the existing `IsJoltPhysicalAnimationEnabled()` ownership API. It also skips the repair for a faulted-but-still-owned binding, which must retain its last completed pose. It does not skip pending admissions before Jolt ownership is committed, and does not alter ordinary Chaos Physical/HalfSim or Kinematic behavior.

## Other transition callbacks and pending blends

The complete source callsite search found `ProphecyModeTransitions::PreUpdate` / `Evaluate` only in `ProphecyNNLocomotionAnimInstance` and `ProphecyNNPoseAnimInstance`. The Jolt pose proxy does not call either. Those former proxies release their transition snapshots from `DestroyAnimInstanceProxy`. Thus this patch does not remove an intentionally active Jolt transition-interpolation layer: the native Jolt binding already supplies its completed pose directly, while the retained finalization delegate independently continued running the old repair.

`EnableJoltPhysicalAnimation` converts to Chaos Physical first when necessary, then attempts immediate or deferred Jolt admission. While admission is pending, `IsJoltPhysicalAnimationEnabled()` remains false and this patch leaves the existing Chaos blend/repair behavior in place. The transition `Blends` entry is replaced on a later actual mode change and otherwise persists until `ReleaseAgent`; its alpha saturates at one after 0.25 seconds, but neither the entry nor the finalizer is removed at that time. This persistence explains why the callback still processes every measured Jolt frame long after warmup.

Jolt ownership sets `State->bActive` before the first explicit completed-pose publication, so the new guard applies to that first authoritative pose as well. Disabling moves the state away and restores the NN instance; the guard becomes false again. Normal Agent `SetSimulationMode` handles Jolt-owned transitions before constructing a new legacy `FScope`. No additional guard in `PreUpdate`, `Evaluate`, `FScope`, or release functions is justified by this audit.

## Verification for promotion

1. Full existing foundation and live 100-character checks: all 88 render/socket versus completed-feedback transforms, original query receiver identity, finite normalized rotations, callback removal and pending cancellation.
2. Immediate finalized-callback query tests, including nonuniform bone scale, continue to pass; this guard removes a post-query pose rewrite rather than deferring query publication.
3. Compare `pose_finalize_after_query` and whole-world time with the new instrumentation under the same workload. Source identifies repeated work; no speedup is claimed before measurement.
4. Retain a Chaos Physical/HalfSim transition test: the new branch is false and preserves the prior repair.

## Other finalization candidates checked

* The benchmark creates `PhysicalMesh` hidden, casts no shadow and disables overlap events (`ProphecyPhysicsBenchmarkManual.cpp:103–106,149`). It does not set fixed-bounds or leader-bounds flags.
* UE `USceneComponent::UpdateOverlaps` caches when no overlap/descendant/physics-volume work exists (`Engine/Private/Components/SceneComponent.cpp:1072`). `UPrimitiveComponent::UpdateOverlapsImpl` does not run an overlap query when overlap events are disabled (`PrimitiveComponent.cpp:4276`), and returns skippable if descendants and physics-volume requirements permit. There is no justified blanket change to `bUpdateOverlapsOnAnimationFinalize`.
* UE finalization already checks `bHasSocketAttachments` before updating socket children, and follower refresh only iterates actual followers (`Engine/Private/PhysicsEngine/PhysAnim.cpp:468`; `Engine/Private/Components/SkinnedMeshComponent.cpp:3074`).
* For the hidden fixture, `CalcMeshBound` selects asset bounds plus root translation when `ShouldRender()` is false and hidden shadow is false (`SkinnedMeshComponent.cpp:2030`). Thus PHAT geometry bounds traversal is not established as a cost in this workload. Visible gameplay still needs accurate posed bounds; do not force fixed bounds or use a different leader to lower benchmark cost.
* Skeletal `CalcBounds` already caches results until finalization invalidates them, avoiding repeat renderer calculations. A correct new-pose update is not an unchanged-pose cache hit.

Useful runtime provenance: `ShouldRender`, `bCastHiddenShadow`, `bUpdateOverlapsOnAnimationFinalize`, `GetGenerateOverlapEvents`, `ShouldSkipUpdateOverlaps`, `GetShouldUpdatePhysicsVolume`, `GetAttachChildren().Num()`, `HasAnyAttachedSockets`, `GetFollowerPoseComponents().Num()`, leader validity, `bUseBoundsFromLeaderPoseComponent`, `bComponentUseFixedSkelBounds`, `bConsiderAllBodiesForBounds`, `BoundsScale`.

If more attribution is required, UE already declares cycle scopes for finalization child transforms, overlaps and bounds (`PhysAnim.cpp:464–466`). `Core/Public/Stats/Stats.h:578` routes cycle scopes into the CPU trace when named events are enabled. An isolated CPU trace with those scopes provides exact engine call attribution without engine edits; its instrumentation overhead must not become the final acceptance timing.
