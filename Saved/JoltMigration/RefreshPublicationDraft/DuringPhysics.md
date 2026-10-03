# DuringPhysics overlap audit for the query-only Jolt pilot

Source-only candidate, not an implemented or measured speedup. The latest root measurement is approximately 2.214 ms Jolt update and 1.752 ms game-thread wait for Chaos completion. Overlap can reduce elapsed world-tick time; it does not reduce the sum of worker CPU time. Contention may reduce the available saving.

## Frame ordering

`Engine/Private/LevelTick.cpp:1721–1749` runs PrePhysics, StartPhysics, DuringPhysics without waiting for physics, EndPhysics, then PostPhysics. StartPhysics calls `FChaosScene::StartFrame`; that pushes external state and dispatches Chaos tasks (`PhysicsCore/Private/ChaosScene.cpp:363–379`). EndPhysics waits on scene completion and invokes FinishPhysicsSim/EndFrame (`Engine/Private/PhysicsEngine/PhysLevel.cpp:256`).

The narrowly useful experiment changes only the automatic coordinator tick's start/end group to DuringPhysics, retaining game-thread execution, current Agent publisher prerequisites, the one native Step and synchronous all-character publication. It does not change dt, substep count, NN target cadence, bodies, joints, bones, query shape count or any collision flags. Explicit manual stepping remains synchronous at its caller's existing time. Admission still closes before queued execution; moving the automatic group does not justify accepting late clients in the queued frame.

Current PrePhysics publishers still produce the current frame's targets. A consumer that requires the newly completed current-frame physical pose must depend on the coordinator or run after its completion; moving groups cannot promise a new pose to arbitrary earlier PrePhysics consumers. The present isolated manual fixture observes completed poses after actor ticks and has no mixed Chaos/Jolt physical coupling.

## External scene queries remain immediately writable

`FChaosScene::UpdateActorsInAccelerationStructure` (`PhysicsCore/Private/ChaosScene.cpp:236`) takes the solver external-data write lock and updates the external query tree from each current external particle X/R/geometry. It also calls `UpdateParticleInAccelerationStructure_External` for every actor.

`PhysicsSolverBase.cpp:354` records these pending operations with the current external marshalling timestamp. `FChaosMarshallingManager::Step_External` records the timestamp on the physics packet and then increments the external timestamp (`Chaos/ChaosMarshallingManager.cpp:95,117`). Thus writes after StartPhysics are newer than the packet the current solver step consumed.

Although `FChaosScene::EndFrame` has an old comment about stomping game-thread query changes, the called code actually preserves pending changes: `PBDRigidsSolver.cpp:3199` forwards to `FPBDRigidsEvolutionBase::UpdateExternalAccelerationStructure_External`; `Chaos/PBDRigidsEvolution.cpp:972` swaps the newest completed PT tree and calls `FlushExternalAccelerationQueue`. At line 705, pending operations whose timestamp is newer than or equal to the copied tree are reapplied using **current external particle** transforms and geometry, and retained until the physics snapshot has consumed them. Older operations are removed. If no new tree was swapped, the existing external tree already contains the immediate updates.

External body X/R writes also record overwrite timestamps (`PhysicsProxy/SingleParticlePhysicsProxy.h:1178,1186`). `PullFromPhysicsState` avoids replacing newer external X/R with older solver results (`Private/PhysicsProxy/SingleParticlePhysicsProxy.cpp:491,497`); interpolated pulling has corresponding timestamp checks. Ordinary non-simulation-following kinematic bodies additionally do not pull their positions from simulation.

This supports immediate own-mesh ray/query publication during Chaos work and preservation after EndPhysics, without touching PT particles. It does not mean the current Chaos simulation sees newly published Jolt query proxies: those inputs reach a later Chaos step. In the current QueryOnly, zero-Chaos-dynamic character fixture that does not change solver collisions. It would need a separate timing contract for future Chaos interaction partners, simulation callbacks that query PT state, or a mixed physical scene.

## Required isolated proof

1. Capture actual coordinator tick start/end groups and current target frame/revision, proving one shared step and all 100 current-frame target packets.
2. Preserve the existing all-88 completed/render/socket checks and immediate finalized-callback original-mesh ray tests.
3. Add a ray at OnWorldPostActorTick or later after EndPhysics through a known current moved body; require original mesh/bone identity and current hit position. The existing immediate-before-EndPhysics ray alone cannot prove the tree swap retained the write.
4. Verify query proxy X/R and collision geometry still match the completed pose after EndPhysics, including a moving/rotated frame, not just a stationary body.
5. Repeat existing callback removal, pending cancellation and survivor explicit-step tests. No callbacks or native ownership are deferred into the next frame.
6. Compare same-workload whole-world mean/median/p95 and actual EndPhysics wait with the old group; retain all functionality gates. A trace can verify overlap rather than assuming that time simply subtracts.

No active source change is included. This candidate has a more direct measured opportunity than parallel skeletal evaluation after the finalizer fix, while keeping the retained mesh and current synchronous publication design.
