# Paused Chaos maintenance: retained scene cost audit

Read-only reduction and UE 5.7.4 source audit, 2026-09-09. No source changes, builds or process launches were made for this audit.

**Keep normal scene processing as the preferred configuration.** Paused maintenance passes its query/lifecycle controls, but the matched whole-world measurements regress. The strongest phase-level explanation is retained synchronization of the last positive-delta pull buffer; this is supported by source and the CSV pattern, but its exact buffer size was not instrumented.

## Recorded measurements

The same-binary, non-CSV pair uses SSE2, seven Jolt workers, the approved no-lock path and 40 cm broadphase padding. Values below are mean milliseconds over 360 benchmark samples; remainder is world minus the three disjoint project scopes.

| Scope | Normal | Paused | Paused minus normal |
|---|---:|---:|---:|
| Measured world | 11.275188 | 11.624585 | +0.349397 |
| Agent ticks | 1.202992 | 1.228552 | +0.025560 |
| Coordinator | 6.322009 | 6.390058 | +0.068049 |
| NN manager | 2.293738 | 2.304178 | +0.010440 |
| Remaining world time | 1.456450 | 1.701797 | +0.245347 |

Sources: [normal report](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/nn_jolt_cache_control_A_100_20260909_1525.json>), [paused report](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/nn_jolt_pause_A_100_20260909_1526.json>).

The additional [paused CSV report](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/nn_jolt_pause_csv_100_20260909_1527.json>) records 11.718573 ms world mean and **360 validated zero-delta frames**. Whole-world native counts remain 2,303; GT and PT dynamic/sleeping counts are zero after each completed frame. The pause flag is restored before teardown. Its admission record has 2,200 PT dynamics from the final Chaos warmup frame, despite already-kinematic GT bodies; that is relevant to the retained-buffer hypothesis below.

## Independent marked CSV reduction

Read [Profile(20260909_152548).csv](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Profiling/CSV/Profile(20260909_152548).csv>) by indexed columns and selected numeric rows with `ProphecyBenchmarkMeasured == 1`. There are **341 marked CSV rows**, not all 360 benchmark samples. Duplicate CSV header names make a normal PowerShell `Import-Csv` unsuitable; indexed parsing avoids collisions. Comparison values come from the independently reduced [older normal CSV](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/NNPadding40CSV-20260909-1421.json>) and therefore are **not a matched binary A/B**.

| CSV scope, mean ms | Paused, current | Normal, older binary |
|---|---:|---:|
| Exclusive/GameThread/Physics | 0.815521 | 0.848085 |
| Exclusive/GameThread/SyncBodies | 0.465755 | 0.212230 |
| Exclusive/GameThread/EventWait/EndPhysics | 0.012869 | 0.017564 |
| PhysicsVerbose/AllWorkers/StepSolver | 1.932148 | 2.209103 |
| PhysicsVerbose/AllWorkers/StepSolver_PullData | 0 | 0.230564 |
| PhysicsVerbose/AllWorkers/StepSolver_AdvanceOneTimeStepImpl | 0 | 0.987690 |
| PhysicsVerbose/AllWorkers/StepSolver_ComputeIntermediateSpatialAcceleration | 0 | 0.825174 |
| PhysicsVerbose/AllWorkers/StepSolver_IntegrateKinematicSpatial | 0 | 0.845787 |

Additional paused observations:

- `AcquireSceneWriteLock`: 0.025319 ms mean. StartPhysics wait: 0.002545 ms; DuringPhysics wait: 0.003452 ms.
- EndPhysics wait is nonzero in **only 1/341 rows**, with maximum 4.3882 ms. It is not a recurring 1–2 ms blocking phase.
- StartPhysicsTick and EndPhysicsTick counts are exactly one in every marked row. PhysicalMesh primary tick and skeletal EndPhysics tick counts are **zero in every marked row**. No duplicate mesh animation/physics tick is exposed here.
- The four recorded AABB dirty/overflow/oversized/nonempty-grid counters are zero. These are counts, not timings, and do not imply that the acceleration structure incurs no work.
- The two separate exclusive GT physics scopes total **1.281277 ms**. Their older normal total was 1.060315 ms. The +0.220962 ms difference is consistent with the paired report's +0.245347 ms remainder, but the different binaries prevent an exact causal attribution.
- Do not sum nested worker scopes, add worker CPU directly to GT world duration, or attribute all `WorldTickMisc` to the measured world timer. Benchmark validation runs after the timer has stopped: [EndTick](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmark.cpp:509>).

## Why zero-delta maintenance retains work

1. **No new pull buffer at zero dt.** [PBDRigidsSolver.cpp:614](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Experimental/Chaos/Private/PBDRigidsSolver.cpp:614>) calls `CompleteSceneSimulation` only for positive dt. This matches the paused CSV's zero `StepSolver_PullData`.
2. **The latest existing result survives.** [ChaosResultsManager.cpp:75](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Experimental/Chaos/Private/Chaos/Framework/ChaosResultsManager.cpp:75>) clears interpolation arrays while deliberately preserving Prev/Next. [PullSyncPhysicsResults_External:238](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Experimental/Chaos/Private/Chaos/Framework/ChaosResultsManager.cpp:238>) resets, collapses to the latest queued result, then rebuilds interpolation entries from Next. [AdvanceResult:179](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Experimental/Chaos/Private/Chaos/Framework/ChaosResultsManager.cpp:179>) changes Next only when a new result exists. Consequently the last positive-dt warmup buffer can be reset/rebuilt again on every paused frame.
3. **Body synchronization still visits those results.** [PhysicsSolverBaseImpl.h:137](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Experimental/Chaos/Public/Chaos/PhysicsSolverBaseImpl.h:137>) pulls synchronous results, loops rigid interpolations and calls each surviving proxy's `PullFromPhysicsState`. The kinematic receiver early return in [OnSyncBodies:2357](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Private/PhysicsEngine/Experimental/PhysScene_Chaos.cpp:2357>) occurs after that earlier work. Zero component transform changes does not mean zero synchronization cost.
4. **Spatial maintenance still runs.** [PBDRigidsSolver.cpp:563](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Experimental/Chaos/Private/PBDRigidsSolver.cpp:563>) explicitly calls `ComputeIntermediateSpatialAcceleration` when dt is below the minimum. The CSV scope with that name is instead around the positive-dt evolution call at [PBDRigidsEvolutionGBF.cpp:607](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Experimental/Chaos/Private/Chaos/PBDRigidsEvolutionGBF.cpp:607>). Its zero paused value is a scope-placement effect, **not evidence that spatial processing stopped**. The outer worker StepSolver still costs 1.932 ms.
5. **GT scene completion is unchanged.** [ChaosScene.cpp:553](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/PhysicsCore/Private/ChaosScene.cpp:553>) still obtains the returned query structure, syncs bodies, flips/dispatches events, syncs query materials and broadcasts scene completion. The exclusive Physics scope includes both normal start and end tick management: [PhysLevel.cpp:242](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Private/PhysicsEngine/PhysLevel.cpp:242>), [PhysLevel.cpp:260](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Engine/Private/PhysicsEngine/PhysLevel.cpp:260>). Current query publication also records solver-side pending spatial operations: [ChaosScene.cpp:270](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/PhysicsCore/Private/ChaosScene.cpp:270>). They preserve newer GT poses when an older PT tree returns and cannot be removed as redundant updates.

## Decision and remaining uncertainty

Pausing has not removed the expensive GT maintenance, and it likely makes the old dynamic warmup pull set persist longer than normal processing. This explains why a solver with no continuing Chaos dynamics can still spend more time in SyncBodies. Exact dirty-result counts and a same-binary nonpaused CSV would be required to prove the entire measured delta comes from that mechanism.

There is no demonstrated safe shortcut through these scene internals: skipping EndFrame, discarding solver results, or bypassing pending spatial operations would change tested lifecycle/query contracts. Retain pause as an opt-in diagnostic and use normal processing for the next performance baseline. The remaining timing data does not justify an asynchronous skeletal redesign or another tick-group experiment.

A subsequent source check identified a narrower control worth testing: let two ordinary measured positive-delta frames replace the dynamic warmup/transition buffer before applying pause. The first handoff frame alone can still buffer all transient dynamic-to-kinematic entries, so a second is needed to replace that transition result. The [deferred diagnostic draft](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/DeferredChaosPauseDraft/README.md>) retains every timed sample and all native checks. It remains unbuilt/unrun and does not change this audit's measured conclusion about immediate pause.
