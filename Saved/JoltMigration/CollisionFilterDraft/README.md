# Shared-world collision filter draft

Prepared 2026-09-09. **Not built, executed, promoted, or performance validated.** This directory contains copies of the three active native files plus this note. Promotion must review the diff against the source versions listed below; do not overwrite later coordinator/world edits blindly.

| Draft file | Intended active location | Active SHA-256 when copied |
| --- | --- | --- |
| `ProphecyJoltWorldSubsystem.h` | `Plugins/ProphecyJolt/Source/ProphecyJolt/Public/ProphecyJoltWorldSubsystem.h` | `90628D038A78364BF539E08A5F0B193063D75AEBB613B43E11FB727CCF9C85E2` |
| `ProphecyJoltWorldSubsystem.cpp` | `Plugins/ProphecyJolt/Source/ProphecyJolt/Private/ProphecyJoltWorldSubsystem.cpp` | `7D287AFBA971E277420B5B63A1115BB1C1039B92112484E1E3CE36F27DF5B6D9` |
| `ProphecyJoltRigWorldTests.cpp` | `Plugins/ProphecyJolt/Source/ProphecyJolt/Private/Tests/ProphecyJoltRigWorldTests.cpp` | `4C66B4D8FD8271B8F33A8A063954AEBF3F0B6A0188DBB2FF633D8308000BCA4A` |

## Implemented in the draft

- Immutable simulation profiles `{static/moving, channel, BlockMask}` are interned into the existing 16-bit Jolt `ObjectLayer`. The key packs the complete 32-bit Block mask and five-bit channel, plus the static flag, without hashing away identity. A GT-only hash map finds existing profiles; worker filters only index plain immutable array records.
- The object-layer pair filter requires bilateral Block and rejects static/static. There is no rig-wide blanket exclusion. The two existing broadphase trees remain static/moving; conservative per-tree unions of channels prune trees that cannot match a profile's Block mask. New profiles update the unions before any body using that profile is added. Unused profiles and union bits remain until world shutdown, causing at most additional traversal.
- Each live rig owns a stock `GroupFilterTable`, sized by body count. Only the validated `Snapshot.DisabledPairs` are disabled. No automatic parent-child or initial-overlap suppression is invoked. All bodies use their original snapshot body index as subgroup ID and the same table reference. Each live instance receives a distinct monotonically allocated world-local group ID, independent of capture ID and recyclable adapter slots. Props keep Jolt's ordinary invalid-group default, so the rig table does not suppress their contacts.
- Existing constraints-before-bodies-before-record teardown remains intact. Jolt `CollisionGroup` also holds a strong `RefConst<GroupFilter>`. There is no worker-side UObject access, no pointer back into the rig registry, and no new contact listener.
- `CreateRig` and its legacy wrapper now accept actual captured object channels and Block masks. Existing dynamic/discrete, geometry, mass, frame and CCD/MACD restrictions remain. Existing WorldStatic-only captures retain exactly that behavior because their masks still ignore other channels.

## Public additions and boundaries

`FProphecyJoltFixtureBodySettings::ObjectChannel` is a `TOptional<ECollisionChannel>`. Unset preserves the fixture convention: static becomes `ECC_WorldStatic`, dynamic becomes `ECC_PhysicsBody`. `CollisionResponses` is an `FCollisionResponseContainer` initialized to all Block. Production body capture must supply its effective channel/responses explicitly. These fields are appended after the original fields to preserve existing positional aggregate initialization.

`FProphecyJoltWorldSettings::MaxCollisionProfiles` defaults to 65535, the number of usable layer IDs before Jolt's invalid sentinel, and permits smaller explicit capacity tests. It is appended after the original fields. `FProphecyJoltWorldDiagnostics::CollisionProfileCount` exposes actual interned profile count and resets on shutdown.

Only Block bits enter simulation profiles. Ignore and Overlap do not create contacts; overlap events and filtered UE-style queries are explicitly deferred. The captured native simulation Word2 is a skeletal component ID, **not overlap bits**. Query Word2 / `NativeQueryResponses` retain overlap provenance. No source material, asset, collision profile, geometry, motor or joint settings are retuned by this draft. Existing raw ray casts still examine all fixture layers.

This is creation-time filtering. No runtime profile/exclusion setter or contact-cache mutation API is added. Per-shape policy disagreement and arbitrary scene ignore-pair mutations retain their existing unsupported/deferred coverage.

## Capacity and lifetime checks

All requested new profiles are counted as a batch before any row is interned or body created. A whole-rig request cannot partially consume profile capacity. A successful preflight may retain profiles even if a later body allocation fails, as documented. There is no profile-ID recycling or mutation during Update.

Rig group allocation uses a `uint64` counter checked against `CollisionGroup::cInvalidGroup` before any body is created; it cannot wrap a valid native group ID into the sentinel. A successfully allocated ID may remain consumed after later rollback. The pinned `GroupFilterTable` constructor multiplies `N*(N-1)` in `uint32`, so the draft explicitly rejects a rig whose product would overflow before allocating that table. The table is constructed and populated before adding bodies.

The native profile registry is declared before all filter objects and `PhysicsSystem`; the existing synchronous GT/idle access contract prevents profile growth from racing worker reads or queries. Filters remain alive for `PhysicsSystem` destruction.

## Added real-physics tests

All tests use bounded synchronous Updates and real Jolt sphere/box collisions. Existing rig-world tests remain in the clone.

1. `Prophecy.Jolt.Collision.BilateralFixtureMasks`: a falling sphere rests only for bilateral Block. Either side's Ignore, an irrelevant Block channel, Overlap, and an empty Block mask permit passage. The floor uses channel 31, is created after an earlier Update, and is static despite its custom channel, checking unsigned masks and late broadphase-union expansion.
2. `Prophecy.Jolt.Collision.ExactPHATDisabledPairs`: two unconnected moving spheres stop each other when enabled and cross when the sole PHAT pair is explicitly disabled. No joint can produce a false positive.
3. `Prophecy.Jolt.Collision.IndependentRigGroupsAndReuse`: create a rig, translate and stop it through actual impulses, then instantiate the identical capture at its original pose. Equal subgroup indices in different rigs must resolve their 10 cm overlap. One rig is removed and its adapter slot reused; stale handles are rejected and the replacement still collides with the surviving group. Four equal policies must share one profile.
4. `Prophecy.Jolt.Collision.RigAndDynamicProp`: a rig sphere and ungrouped dynamic prop stop each other for bilateral Block and cross when the prop ignores the rig.
5. `Prophecy.Jolt.Collision.ProfileCapacityPreflight`: a request for two new rig profiles fails atomically with only one row free; a single new fixture profile still fits. Further profiles and invalid channel sentinels fail without adding bodies; identical retained profiles can be reused at capacity.

The 32-bit group-ID exhaustion guard is source-reviewed but not driven through billions of allocations. No test-only production hook is introduced to force the counter. Contact assertions allow the pinned solver's existing 0.02 m penetration slop (`PhysicsSettings.h:53`) rather than retuning it. Physics thresholds above are reviewable expectations, not recorded passes; the parent task owns compilation and execution after promotion.

## Pinned local source basis

- Jolt 5.6 `Jolt/Physics/Collision/ObjectLayer.h`: default 16-bit layers and invalid sentinel.
- `Jolt/Physics/Collision/BroadPhase/BroadPhaseQuadTree.cpp:590` and `QuadTree.cpp:1476`: broadphase-tree and object-pair filters run before candidate collection.
- `Jolt/Physics/Body/Body.inl:74`: group filtering precedes candidate collection.
- `Jolt/Physics/Collision/GroupFilterTable.h:94`: different groups collide; same-group subgroups use the symmetric table.
- `Jolt/Physics/Collision/CollisionGroup.h:104`: strong filter reference.
- `Jolt/Physics/Ragdoll/Ragdoll.h:35`: automatic parent/overlap exclusions would change the authored pair set and are deliberately not used.
- UE 5.7 `Runtime/Engine/Public/Physics/PhysicsFiltering.h:69,146,165`: simulation versus query word meanings and extraction.
- UE 5.7 `Runtime/Experimental/Chaos/Public/Chaos/ParticleHandle.h:191`: bilateral simulation Block-mask predicate.

Checks performed: local header/API review, diff review and whitespace checks. No active files, assets, running engine instances or dependency binaries were changed by this draft task.
