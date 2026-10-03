# Actual CPU NN + Jolt moving-crowd fixture (draft, not run)

Mode `NNJoltCrowd` (17) measures real manager work at 30 Hz inside the existing 60 Hz world interval. It uses 22 bodies/21 original-angle joints and presents the complete 88-bone skeleton for each character. The explicitly requested movement profile disables optional fist closing and unused camera/spring-arm ticks through the existing shared `PrepareManualAgent` helper. Physics cadence, NN cadence, bone count and body/joint quality are unchanged.

## Promotion contents

Apply `ActualNNRoutingAndMetrics.patch` to the four existing source files, then copy the new `Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmarkNNJolt.cpp` to the same active path. The other source copies are review material; do not overwrite active files from them. No Build.cs or launcher change is required. Root's profiling, CSV markers, movement flag, stdout, priority selection and post-registration inherited-mesh tick fix remain intact. A read-only `git apply --check --ignore-space-change` passed against active sources; no compilation or runtime test has been performed for this draft.

Baseline SHA256:

| Source | SHA256 |
|---|---|
| Public/ProphecyNNLocomotionManager.h | d69f01fb62ce6838998713f24ae92b92c9dffb3a3bfdd542d5a3612ac4bd89d6 |
| Private/ProphecyNNLocomotionManager.cpp | 7c8d8f52ecb41142cde609d276a7739e3a508b7a8cbf863534ccfb6fbf1faf6f |
| Public/ProphecyPhysicsBenchmark.h | 64fa2527f4d138f8ca8aeb17cccd360e7f54a265f08a7b3315597f44ad720555 |
| Private/ProphecyPhysicsBenchmark.cpp | dbce053baac8dc029cb179fb024fe6a519f3fdd0736c6a07aef87142bf2b582b |

## Initialization and publication contract

1. The existing helper creates all transient native shells with automatic manager boot disabled and the real UEFN PHAT on a separate PhysicalMesh. Synthetic pose data is used only to construct these shells before manager adoption.
2. Once all shells have finished BeginPlay, the fixture enables their existing placed-agent collection flag and supplies public walking input +Y/facing +Y. It restores the current Physical root capsule policy: QueryAndPhysics, WorldStatic block, other channels ignored. The existing explicit floor becomes QueryAndPhysics, so the existing capsule sweep/slide path queries the same floor mirrored into Jolt.
3. A deferred native manager is configured through `ConfigureSimpleLocomotionTest`, then Count, 30 Hz, four foot integration steps and `NNERuntimeORTCpu` are set before FinishSpawning. The bridge remains off and InitialPhysicalAgentCount is zero so adoption does not apply MACD/drive initialization to the already prepared manual rigs.
4. The manager's real startup loads and validates its run, walk and upper models, initializes recurrent state, adopts the exact prepared actors and establishes manager-before-agent tick dependencies. The fixture rejects missing, duplicate or replacement actors. The manual Physical servo consumes the manager-assigned pose ID directly from the agent registry. It intentionally has no NN AnimInstance: entering Physical clears that evaluator, and the first normal Agent tick supplies only the reference/helper/finger proxy. Bootstrap pose IDs are cleared after adoption. The fixture does not install or rebind an NN animation evaluator over the physical warmup.
5. Every fixture synthetic publication is skipped for mode 17, including all warmup frames. The actual manager owns source poses throughout warmup and measurement. After the Chaos warmup, existing MultiJolt initialization imports each live rig and commits Jolt ownership. There is no extra unreported steady-state Jolt warmup: measurements begin at that handoff, as in the existing JoltCrowd fixture.
6. The existing shared coordinator steps once at 60 Hz after agent target publication. Manager physical resampling calls the public Agent.SampleActualComponentPose path at each 30 Hz NN update, so completed Jolt feedback feeds the recurrent input. At teardown, existing shared-world removal, survivor advancement, stale-handle and floor-only checks run outside timing; actors and the manager are destroyed by normal fixture cleanup.

The narrow manager seam exposes existing phase accumulators/runtime identity and adds success/failure counters at the existing `ResamplePhysicalAgentState` call. It does not duplicate model execution, add physical samples, change math, inject pose packets, change tick cadence or reset recurrent state.

## Assertions and report scope

- Count is 2..100 because this fixture reuses the existing multi-rig lifecycle validator. Count 2 is a smoke test; all three loaded model interfaces still retain batch capacity 100. Count 100 is the performance workload.
- CPU runtime identity for all three models, registered lane identity/count, 30 Hz, four foot steps, disabled bridge, movement profile, source IDs and interpolation remain checked. Conflicting command-line overrides fail clearly. The actual crowd override supported by the manager is `-ProphecyNNLocomotionCrowd`, not `-ProphecyNNCrowdSize`; this fixture needs neither.
- Completed NN steps must occur every other 60 Hz frame, with one successful physical sample per live lane per step and no new failures. Each step must publish a fresh finite 25-bone policy pose. Model phase time must advance and every managed root must move during the measured walking case.
- Existing per-frame checks retain 22N/21N native ownership, zero Chaos dynamic bodies, one shared step, revision advancement, and complete 88N feedback/socket agreement. These extensive diagnostics run after WorldMs. They are included in frame interval measurements, so those intervals are not an uncapped production throughput estimate.
- The output records actual model/contract paths, CPU runtime names/batch sizes, every capsule channel/response and dimensions, source rig capture, movement profile and native body policy. This is a separated crowd with static-only limb contacts and a single explicit floor. Self/inter-character contacts, arbitrary production world geometry and contact stress remain different workloads.
- WorldMs already includes real manager intent/movement, capsule sweeps, recurrent feedback, model inference/output/publication, Agent work, the shared Jolt step and full presentation. NN phase means are components of that measured interval and must not be added again. GT wall latency is not the sum of CPU utilization over worker threads. NullRHI does not measure rasterization, blood pixels or rendered FPS.
- Legacy generic Audit pose errors still use the synthetic reference and are explicitly marked inapplicable to actual NN trajectory. Actual lane cadence and completed feedback/render agreement are the acceptance checks; no Chaos/Jolt trajectory-equivalence gate is imposed.

## Root-run validation sequence

After promotion and a clean build, smoke the exact path first:

```powershell
& ./Tools/NN/RunSterilePhysicsBenchmark.ps1 -Methods NNJoltCrowd -Count 2 -Repeats 1 -Warmup 60 -Samples 180 -FloorOnly -MovementOnly -Label actual_nn_jolt_2_smoke
```

Then use a fresh label for the requested population:

```powershell
& ./Tools/NN/RunSterilePhysicsBenchmark.ps1 -Methods NNJoltCrowd -Count 100 -Repeats 1 -Warmup 120 -Samples 300 -FloorOnly -MovementOnly -ProcessPriority Normal -CsvProfile -Label actual_nn_jolt_100
```

These commands are proposed, not executed. Inspect the top-level error and `actual_nn_validation.success`, per-frame NN counters and multi-rig validation before using timing. The draft makes no claim that the 10 ms goal is met.

## Existing manager cleanup audit

`ProphecyNNLocomotionManager.cpp::SpawnVisualComponents` clears and disables the empty inherited Mesh after the actors are registered, so it already avoids the pre-FinishSpawning tick-reset bug found in the sterile helper. Its manual branch does not disable cameras/spring arms itself; this fixture inherits the explicit movement-only treatment from the shared helper. The manager's simple view setup returns for adopted unpossessed agents with no PlayerAgent, preserving the unrelated default view. No production camera policy is changed here.
