# Generic joint and scoped collision-exclusion draft

2026-09-09. Draft only. No active source changes, builds, Unreal launches, or asset writes were performed for this task. Root owns review, promotion, compilation, and runtime execution. These tests have not yet run; no performance or gameplay-completion claim is made.

## Files and promotion baseline

- `ProphecyJoltWorldSubsystem.h` -> `Plugins/ProphecyJolt/Source/ProphecyJolt/Public/ProphecyJoltWorldSubsystem.h`
- `ProphecyJoltWorldSubsystem.cpp` -> `Plugins/ProphecyJolt/Source/ProphecyJolt/Private/ProphecyJoltWorldSubsystem.cpp`
- `ProphecyJoltGenericJointTests.cpp` -> new `Plugins/ProphecyJolt/Source/ProphecyJolt/Private/Tests/ProphecyJoltGenericJointTests.cpp`

The copied active baseline already contains the 41-test-validated collision-profile/PHAT filter stage. SHA256 at copy and final source review:

| Active file | SHA256 |
| --- | --- |
| Public/ProphecyJoltWorldSubsystem.h | `A49DBA3BC09E6F2FB65D6427C0906DD15A8239000CF1C73A78540F50E1D993A3` |
| Private/ProphecyJoltWorldSubsystem.cpp | `734A8B552964E60BE77FB4A76A9FAF1B638035AC5B3F4581E3C8D09DC505BDF2` |

If either active file has changed, merge this delta rather than overwrite. The standalone-body draft changes body/rig preparation files, not these world files. A future standalone creation method should still call existing `AddNative` and `DestroySlot`; those body slots then participate in generic joints without a second lifetime mechanism. Coordinator step-client changes are separate and must retain the idle-world mutation contract.

## Public contract

`FProphecyJoltJointHandle` contains the world lifetime, slot, and 64-bit generation. `CreateJoint` takes explicit settings plus a list of temporary body-pair exclusions. `UpdateJoint` replaces connector frames/limits only; endpoint identities, order, type and exclusion ownership stay fixed. `ReadJoint` returns accepted settings for diagnostics. `DestroyJoint` and `OwnsJoint` remain usable while faulted/ending, outside Update on the game thread.

Settings choose Fixed or hard SixDOF. Endpoints use literal A/B order. Connector transforms are body-origin-local centimeters with normalized rotations and unit scale. The helper subtracts the actual Jolt shape COM offset, preserving body orientation; it does not rotate connectors through the principal inertia frame. No implicit fixed-to-world endpoint is accepted. At least one endpoint must be dynamic.

Hard SixDOF uses independent translation X/Y/Z intervals in centimeters, twist X and swing Y/Z intervals in radians. Cone swing is symmetric and has Jolt's coupled swing-quaternion geometry; pyramid accepts asymmetric swing. This is not UE spherical translation limits or three independent Euler-angle clamps. Locked, Free and Limited are explicit. Invalid/unrepresentable intervals, asymmetric cone swing, and Limited angular ranges that stock Jolt converts to locked/free at its internal thresholds are rejected before replacement. Fixed joints require default locked limit fields. No motors, spring tuning, friction drives, breakage or implicit pose snap is supplied. Updates rebuild the native constraint and intentionally discard warm-start history.

`MaxGenericJoints` (default 1024) and `MaxSuppressedBodyPairs` (default 4096) are checked before registration. Joint generations approaching wrap are retired. Duplicate/reversed pairs are canonicalized once per owner and do not consume extra references or pair capacity. Allocator failure is not made recoverable; this matches existing world creation behavior.

## Suppression and teardown

The existing immutable channel profiles and exact per-rig PHAT `GroupFilterTable` objects remain unchanged. An additional world-owned stock `SimShapeFilter` rejects explicitly scoped body pairs at the root shape dispatch. When no temporary exclusions exist, the filter is unregistered, avoiding that extra lookup. Queries retain their current behavior.

Ownership is a GT-only map keyed by both full adapter body identities (slot plus generation; world implicit in the owner). Reference counts are checked before mutation. Workers see only a sorted immutable array of canonical native BodyID pairs. No callback touches a UObject, adapter generation map, or mutable state. The filter is declared before `PhysicsSystem` and explicitly detached for teardown.

Only count transitions 0->1 and 1->0 rebuild the numeric view, invalidate contact caches, and wake surviving dynamic bodies. Both directions matter: Jolt caches body pairs with no generated contacts as well as pairs with contacts. Joint create/update/destroy also wake endpoints once; no per-frame unconditional wake is added.

Body slots index incident joints and suppression pairs. Destroying either joint endpoint removes the native constraint and releases the joint's references before deleting the body. Removing a third body referenced only by an exclusion retires just its pairs; the joint remains valid. Later release skips that retired generation-specific key, so a replacement body in the same slot cannot lose a new exclusion. Removing one owner decrements its references only; other owners and PHAT exclusions remain intact. Rig and world teardown route through this same cleanup. An owner may explicitly suppress the held sword against every character body without inventing a new PHAT cohort.

## Tests to execute after review/build

Filter: `Prophecy.Jolt.GenericJoint`

1. `FixedGripAndDrop`: rotated connectors, an offset COM with nonidentity principal inertia rotation, off-center impulse, actual held-pose check, then free fall on drop.
2. `HardSixDOFAndReplacement`: a rotated free translation axis, locked translations, asymmetric hard twist, replacement with a bounded linear range, failed asymmetric-cone update preserving old settings, explicit pyramid acceptance.
3. `CachedSuppressionReferenceCounts`: establish and sleep a sphere on a floor; two all-free joint owners reference the same deduplicated exclusion; removing one still permits fall into the floor; final removal restores collision without teleporting either body. The all-free joints cannot support the sphere themselves.
4. `SuppressionPreservesPHATAndPeers`: one rig passes through its explicitly excluded prop and own PHAT-disabled partner while a second rig still blocks on a same-profile prop; after release, a return pass proves PHAT exclusions survived.
5. `EndpointThirdPartyAndReuse`: third-party teardown, replacement in the same body slot, old-owner release preserving a new-generation pair, either endpoint deletion, stale/reused joint identities, live-joint world teardown, and owner-rig deletion while the independent prop survives.
6. `CapacityAndAtomicPreflight`: complete pair-batch rejection, dedup at capacity, invalid frames/absent endpoints, joint capacity, rejected endpoint swaps and frame updates preserving the native grip, successful frame replacement, and world-lifetime invalidation.

All simulations are bounded at 1/120 second per step and use existing fixture sphere/box/rig paths. Collision penetration assertions allow pinned Jolt's default 2 cm penetration slop; the solver is not retuned. These fixtures exercise discrete simulation. The pinned filter also appears in the CCD path, but a CCD suppression runtime test is not claimed here. Actual sword asset capture, actor/component transfer, hold/drop input wiring, presentation and rendering remain the next integration layer.

## Pinned source checks

Jolt 5.6.0, upstream SHA `e77f175595e64cb44218cc9d9d56fc365ad0e36a`, local `Intermediate/JoltMigration/Upstream`:

- `Jolt/Physics/Collision/SimShapeFilter.h:23-34`: read-only, multithreaded body/shape filter signature.
- `Jolt/Physics/Collision/CollisionDispatch.h:38,58`: filter gate before shape collision/cast dispatch.
- `Jolt/Physics/PhysicsSystem.h:83-90`: caller-owned simulation-filter lifetime.
- `Jolt/Physics/PhysicsSystem.cpp:1081-1106`: cached contact/no-contact pair reuse and invalidation bypass; shape-filter wrapper for discrete collision.
- `Jolt/Physics/PhysicsSystem.cpp:2020-2047`: simulation shape filter in the CCD cast path.
- `Jolt/Physics/Body/BodyInterface.cpp:269-285`: constraint creation locks both bodies and substitutes fixed world for absent bodies; activate-constraint behavior. This adapter validates both IDs and releases its read locks before calling it.
- `Jolt/Physics/Body/BodyInterface.cpp:1092-1096`: per-body contact-cache invalidation.
- `Jolt/Physics/Body/Body.inl:9-24`: body-origin transform versus COM transform.
- `Jolt/Physics/Constraints/FixedConstraint.cpp:64-116`: explicit local COM frames; no autodetected anchor required.
- `Jolt/Physics/Constraints/SixDOFConstraint.h:60-98` and `.cpp:91-136`: stock range/cone/pyramid semantics and internal range normalization.
- `Jolt/Physics/Constraints/ConstraintPart/SwingTwistConstraintPart.h:48-145`: internal angular lock/free thresholds.
- `Jolt/Physics/Constraints/ConstraintManager.cpp:17-57`: separate add/remove registration; strong record ownership retained until after removal.
- `Jolt/Physics/Collision/CollisionGroup.h:94-105` and `GroupFilterTable.h:113-137`: group filters are not automatically composed; temporary cohorts would disturb current ownership/filter semantics.

Source-only checks completed: API/header inspection, active-baseline hashes, review of cleanup/refcount transitions, and whitespace/diff checks. No compilation or runtime result is implied.
