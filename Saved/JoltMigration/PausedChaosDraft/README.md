# Paused default Chaos solver diagnostic — source-only draft

Status: not built or run. Only files below Saved/JoltMigration/PausedChaosDraft were written. No active source changes, engine changes, configuration edits, or launches.

The candidate retains the normal UE StartPhysics/EndPhysics scene lifecycle and requests zero solver integration delta through the public pause flag. It is restricted to the isolated, sole NNJoltCrowd case after the live Jolt handoff. All current NN, capsule movement, Jolt step, full 88-bone presentation, all 22 native query-body checks, head/capsule rays, callback removal, and cancellation tests remain enabled. The original Chaos warmup still runs.

## Promotion

Copy the two new private source files under Source/GameAnimationSample3/Private. The controlled foundation test is embedded in the new cpp under WITH_DEV_AUTOMATION_TESTS and creates no test UCLASS.

Apply Benchmark.merge.patch and Launcher.merge.patch as isolated hunks. Their original lines were checked against active files and matched once when written; they are not full file replacements.

The launcher adds -PauseChaos, which passes -PhysicsBenchPauseChaos. It is opt-in and requires NNJoltCrowd, FloorOnly, MovementOnly and one repeat. The C++ side independently checks the sole case and native solver configuration. No default changes.

Run the focused test **Prophecy.Jolt.QueryPose.PausedSceneMaintenanceLifecycle** in the same binary before accepting a paused benchmark result. Then run a small actual NN crowd and the full 100-agent validation workload. A control failure or changed query result rejects the experiment; do not weaken the query gates or inject extra body moves into the timed workload.

## Public implementation contract

The new controller follows the benchmark processor-control ownership pattern: exact UObject lifetime key plus weak world and exact scene/solver identity. Another temporary world's teardown is a no-op. It restores the captured pause state after every measured frame and NN counter has been validated, immediately **before** SaveMultiJoltCase starts its unmeasured lifecycle checks. That function deliberately creates 22 temporary Chaos dynamic bodies during a pending enable/cancel test; it has no intervening normal Chaos frame and therefore must run after restoring normal solver policy. Error Finish, ClearCase before actor destruction, and Deinitialize also restore idempotently. Audits found during restoration are reported after restoring the original flag; an unrelated or replaced solver is never modified.

Admission enumerates all live same-world UPrimitiveComponents and each component's GetAllPhysicsObjects, under one native read lock. It rejects any physics receiver whose owning actor is outside the explicit fixture allowlist, any dynamic/sleeping GT object, inaccessible particle, different solver, or unsupported object state. It counts unique objects, so aliases do not become fictitious particles. A settled PT all-particle view must contain exactly the same number; otherwise an unknown/orphan/unprocessed native proxy is rejected. Additional module-registered world solvers are refused. Unknown actors with no native physics objects do not suppress any simulation and need not be fixture actors.

GT-to-PT handoff state is explicit: the pre-pause PT body states are recorded and can still reflect the prior warmup. Every measured completed maintenance frame must have zero GT **and** PT dynamics, matching native counts, an advancing solver frame (exactly +1), and solver last-dt exactly zero. The world must retain bShouldSimulatePhysics and the same live scene. Actual world delta, external packet timestamp, object/particle counts, pause state, solver frame and last-dt are reported. All inspection is after EndPhysics and outside the measured world timer.

Fixed-dt/async results, substepping, standalone solvers and an already paused baseline are explicitly unsupported. No fallback flush, direct PT write, manual world tick, skipped physics tick, or hidden replacement simulator is installed.

## Why normal zero-dt maintenance is source-backed

Local source root: C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime.

- Experimental/Chaos/Public/Chaos/Framework/PhysicsSolverBase.h:659 exposes IsPaused_External / SetIsPaused_External; :760 exposes GetLastDt.
- Experimental/Chaos/Private/Chaos/Framework/PhysicsSolverBase.cpp:432–516: in the non-fixed, non-substepped path, paused input sets InternalDt=0 while NumSteps remains 1. PushPhysicsState and the normal task dispatch still run. The fixed/substepped branches do not provide this guarantee and are rejected.
- Experimental/Chaos/Private/PBDRigidsSolver.cpp:532–563: zero dt skips physical integration but explicitly computes intermediate spatial acceleration. :604–614 advances the solver frame and conditionally buffers results. :1442–1446 still destroys pending proxies on the final step.
- Experimental/Chaos/Private/PBDRigidsSolver.cpp:882–933,1320–1348: unregister operations enqueue actual native destruction and release unique indices after the solver frame advances. The test exercises this path through real component registration/removal.
- PhysicsCore/Private/ChaosScene.cpp:StartFrame/EndFrame still own push, completion, tree copy and synchronization. The proposal does not remove these costs or call Flush each frame.
- Engine/Private/PhysicsEngine/PhysLevel.cpp:137–180: disabling bShouldSimulatePhysics instead would unregister normal physics ticks (outside the editor trace-collision exception). That alternative is deliberately not this experiment.
- PhysicsCore/Public/Chaos/ChaosScene.h:130–135: Flush exists for nonrunning scene maintenance, but PhysicsCore/Private/ChaosScene.cpp:165 calls an explicit advance/wait/evolution flush/copy. Replacing normal scene ticks with repeated Flush would need separate evidence and may be more expensive.

## Non-teleport capsule proof and limitation

A real root capsule uses ETeleportType::None. Engine/Private/PhysicsEngine/BodyInstance.cpp:2786–2800 routes simulated kinematics to the kinematic-target setter. PhysicsCore/Private/ChaosEngineInterface.cpp:2596–2619 deliberately updates immediate GT X/R with invalidation=false; PT X/R are expected to be produced by kinematic integration. Zero dt therefore does **not** establish PT pose or kinematic velocity equivalence.

However, Experimental/Chaos/Private/PhysicsProxy/SingleParticlePhysicsProxy.cpp:127–140 computes PT shape bounds from a newly received kinematic target while pushing its data, before physical integration. This may retain the required GT query behavior even under paused maintenance. It must be measured and tested, not inferred from a continuously moving ray that still overlaps a previous body.

The controlled test:

1. Creates an actual transient Game world and uses the public SetUpForFrame/StartFrame/WaitPhysScenes/EndFrame sequence with nonzero requested dt.
2. Starts an owned paused controller after a positive-dt baseline frame.
3. Repeats three real capsule registration/move/removal cycles. The capsule is moved 150 cm with **ETeleportType::None**, not a teleport.
4. Leaves that capsule completely stationary for eight maintenance frames. A different, distant native capsule changes position to force newer PT trees; it cannot refresh the tested body's unique pending query entry.
5. Requires a returned tree timestamp strictly newer than the tested capsule's movement packet, so the tested body's old external pending entry has been consumed. Every frame still requires current-area hit, original receiver and analytic impact, plus old-area miss.
6. Requires each removed native particle/proxy count to return to baseline on ordinary maintenance.
7. Restores the original pause flag and verifies the next normal scene frame again integrates positive dt.
8. Verifies unknown native receivers and allowlisted dynamic bodies are rejected before pausing, and unrelated restoration cannot release another owner.

This is query and proxy lifecycle evidence only. It does not prove arbitrary kinematic simulation, later geometry/filter changes, all Niagara velocity consumers, external solver callbacks, physics replication, or arbitrary mixed-backend world behavior under pause. The helper remains a benchmark-owned diagnostic even if it passes. Production ownership would need explicit rules for future Chaos dynamic admission and the remaining affected functions.

## Measurement interpretation

The retained CSV indicated roughly 0.85 ms exclusive GT Physics plus 0.21 ms SyncBodies in the prior actual 100-agent case, with only about 0.018 ms EndPhysics wait. These are attribution data, not a promised speedup: normal scene management and query tree updates remain, and zero-dt synchronization may still consume existing results. Only an A/B run with the same binary, worker settings, placement and all functional gates can establish the effect.

The crowd report includes paused_chaos_diagnostic and each completed frame includes paused_chaos_maintenance. This changed execution policy must remain visible in any performance claim; it cannot be reported as an unchanged default engine-world benchmark.
