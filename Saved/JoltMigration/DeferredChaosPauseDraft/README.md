# Deferred Chaos pause diagnostic draft

Source-only; unbuilt and unrun. No active files were changed. This revises the existing opt-in diagnostic; normal scene processing remains the preferred baseline pending evidence.

## Behavior and promotion

- Promote the two `ProphecyJoltBenchmarkChaosPause` files to the existing game Private directory, and apply `NNValidation.merge.patch` to the existing NN benchmark file.
- `Begin` retains exact owner/world/scene/configuration/allowlist checks and only arms the controller. It leaves the pause flag false.
- The first **two ordinary measured frames** must advance the solver exactly once each with finite positive dt and zero completed GT/PT dynamics. After the second frame's body, query and NN checks pass, `ValidateFrame` sets pause.
- Every later ordinary measured frame must advance exactly once with zero dt and preserve all native inventory/query checks. A 360-sample run therefore reports **2 positive + 358 paused = 360 validated frames**. No frame/sample is omitted, and the benchmark injects no extra tick or scene advance.
- Report fields include `required_positive_delta_frames_before_pause`, `positive_frames_remain_in_benchmark_samples`, `validated_positive_delta_frames`, `validated_zero_delta_frames`, `validated_total_frames`, `applied_after_solver_frame` and a per-frame `phase`. The captured state for the second positive frame is correctly still unpaused; the pause applies to the next scene frame.
- Armed cancellation and applied-pause restoration both preserve exact ownership and the original flag. Another owner's teardown remains a no-op. Existing restoration before the unmeasured multi-character lifecycle checks stays in place.
- The isolated NN hunk moves pause admission after **all** NN lane/cadence checks. Current active ordering performs that call before the NN-specific checks; that is acceptable for immediate-pause observation but would be wrong for the new deferred activation promise.

## Source basis and limits

Dynamic-to-kinematic state changes call `RemoveFromActiveArray(..., bStillDirty=true)` in [PBDRigidsSOAs.h:711](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Experimental/Chaos/Public/Chaos/PBDRigidsSOAs.h:711>), adding the particle to the transient dirty list at [line 1191](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Experimental/Chaos/Public/Chaos/PBDRigidsSOAs.h:1191>). The normal dirty view includes active bodies, moving kinematics and transient dirty entries: [PBDRigidsSOAs.cpp:82](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Experimental/Chaos/Private/Chaos/PBDRigidsSOAs.cpp:82>).

The first positive result therefore may still include all 2,200 rig transition entries. `BufferPhysicsResults` clears transient dirty only **after** buffering and its post-solve callback: [PBDRigidsSolver.cpp:2739](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Experimental/Chaos/Private/PBDRigidsSolver.cpp:2739>). The next positive frame replaces that transition buffer. Positive frames publish a new result through `FinalizePullData_Internal`: [line 1434](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Experimental/Chaos/Private/PBDRigidsSolver.cpp:1434>).

This is not an empty-buffer guarantee: moving pawn capsules and other accepted moving kinematics can legitimately remain in the next result. The draft neither calls the results manager to force a pull nor asserts an invented zero result count. Runtime timing must decide whether deferred pause is beneficial.

## Controlled regression

The existing `Prophecy.Jolt.QueryPose.PausedSceneMaintenanceLifecycle` now creates and advances a real dynamic capsule with velocity, verifies native PT dynamic presence, switches that receiver to kinematic, and arms the controller. It exercises owner cancellation before any counted refresh frame and foreign-owner restoration. It then verifies the two positive scene advances, retained receiver/analytic queries, and activation only after the second advance. Subsequent controls still cover actual spawn, nonteleport 150 cm motion, stationary receivers across strictly newer returned PT trees, removal back to the baseline particle count, normal restoration and rejection of unknown/dynamic receivers. Public scene lifecycle calls remain confined to the owned transient test world; no recursive world tick is introduced.

Required before acceptance: compile; run the revised focused lifecycle test; run actual NN smoke; then repeat matched 100-agent normal/deferred-pause measurements. These have not been run by this agent.

## Active source hashes at draft creation

| File under game Private | SHA256 |
|---|---|
| ProphecyJoltBenchmarkChaosPause.cpp | 79B7D0E910077E7770B08845A1D5F66A1812FC98D55565A12CE7AA21D3CA8116 |
| ProphecyJoltBenchmarkChaosPause.h | 689F90D1C25007B832FCF8B5EE65CE8862953E16573194D84BF18E7436F1F3AA |
| ProphecyPhysicsBenchmarkNNJolt.cpp | AF9F9C0D81768A6B4FE69F83299504351DD313B354D3F4EDC44C97A5F6A32A39 |
