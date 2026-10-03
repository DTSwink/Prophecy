# Idle Jolt body-read candidate (draft only)

2026-09-09. No active source edits, compilation, automation execution, or editor launch were performed by this draft. `IdleBodyReads.apply-patch.txt` is ready for parent review/promotion. All 19 hunks apply exactly once to the current seven source files in memory; both resulting PowerShell scripts parse without errors.

## Bounded change

`-ProphecyJoltNoLockIdleReads` selects the existing nonlocking Jolt interface only for `ReadBody`, the pre-Update servo activation **read** pass, and post-Update state validation. It is resolved once per native world. The default remains locking; both benchmark and foundation launchers expose `-NoLockIdleReads`. Benchmark diagnostics serialize the actual native-world boolean, rather than inferring it from a requested switch.

Every adapter generation/lifetime check, Jolt full BodyID lookup, broadphase-presence check, motion/finiteness check, read ordering, and output copy remains intact. Activations still use the ordinary locking BodyInterface after the read scopes end. No mutation, ray-query, joint, or in-Update listener lock policy changes. The step timing scopes added by the parent remain intact.

## Source contract

Pinned upstream: Jolt 5.6, `e77f175595e64cb44218cc9d9d56fc365ad0e36a`. These sources were inspected locally at `Intermediate/JoltMigration/Upstream`.

- Jolt explicitly permits its nonlocking interface for single-threaded access. It separately prohibits overlapping outside body access with Update. This is an ownership precondition, not a global claim that Jolt requires no synchronization: [Architecture, Single Threaded Access](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Docs/Architecture.md#L153-L164).
- `BodyLockRead` obtains a body through the same `TryGetBody` under either interface; the nonlocking interface replaces mutex operations with no-ops. Its `SucceededAndIsInBroadPhase` test is unchanged: [BodyLock.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Body/BodyLock.h#L17-L68), [BodyLockInterface.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Body/BodyLockInterface.h#L49-L100).
- `BodyManager::TryGetBody` validates the index, live body pointer, and complete BodyID equality, including sequence; removing the mutex does not remove that lookup: [BodyManager.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Body/BodyManager.h#L151-L175).
- Synchronous `PhysicsSystem::Update` waits for all jobs, cleans up, and releases all body locks before returning: [PhysicsSystem.cpp](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/PhysicsSystem.cpp#L628-L672). The no-active-body early return also releases its locks.
- `BodyLockMultiRead` can aggregate mutexes once, but would require a new batched adapter API and value-copy/handle-validation route. It offers no additional safety over the simpler current exclusive-owner proof: [BodyLockMulti.h](https://github.com/jrouwe/JoltPhysics/blob/e77f175595e64cb44218cc9d9d56fc365ad0e36a/Jolt/Physics/Body/BodyLockMulti.h#L18-L84).

The local `WorldSubsystem` owns its PhysicsSystem privately. `ValidateReady()` rejects non-GT and reentrant access; Step holds `bStepInProgress` throughout preparation, synchronous Update, and validation. No native body reference escapes these reads. The completed-pose worker math consumes copied values, not native bodies. The native servo helper separately rejects non-GT preparation. Together these establish the required exclusive idle interval for the three selected sites. Future asynchronous Update, off-GT native queries, or another externally owned native job would require reassessing this policy before enabling that feature.

## Verification and measurement boundaries

Run the existing complete foundation suite with `-NoLockIdleReads`, which exercises world body lifecycle, invalid/stale handles, pre-step wake, contacts, constraints, and query readback using the selected world policy. Standalone servo tests retain the default two-argument locking path unless their caller explicitly selects the new optional policy; do not claim that flag alone changes every standalone PhysicsSystem in the suite.

Then compare actual NN100 with/without the switch in the same binary, keeping padding, movement options, process priority, P-class affinity, frame counts, and all functional validators identical. Verify `no_lock_idle_body_reads` in the native diagnostic rows. Compare new activation and validation timers, completed body-read time, and whole-world distributions. The previously measured body-read and native-wrapper times are inclusive ceilings; no claimed saving is supported before this A/B. No scan, callback, cadence, pose, or query is removed.

## Baselines checked before promotion

| File | SHA256 |
| --- | --- |
| WorldSubsystem.cpp | B228BC76A94634DCA104122AE423A357A440E55F983CBCE8FA857AA329E05F71 |
| WorldSubsystem.h | B5955BC52036530807D4D28FA5C49198BFF83D3439F09FB6B6114060A873A538 |
| VelocityServo.h | 93C8F253693C452DF93014BE25E4EFE9507D49A2EA78B5D3F46E26A1292E9E65 |
| VelocityServo.cpp | 85D62EC68B02B38798FC992326B260C2E27F674C24BAED0E4212233B0EE64F68 |
| ProphecyPhysicsBenchmarkLiveJolt.cpp | 29673A535BF618EB87F688F1E9F941FFA7BCC466510286E2E34ED54CC9AE245E |
| RunSterilePhysicsBenchmark.ps1 | C34E85F3A16992CBEB3D6D27CA8258348BA4A4E2367F976077BFE5A450C4C85F |
| RunFoundationTests.ps1 | 4C255F5C73803389FE61D6F83EDAE30FC4B1341E6CE77C8E6B31B22A5E66102C |
