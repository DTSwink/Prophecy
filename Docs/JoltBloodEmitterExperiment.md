# Blood emitter collision performance experiment

October 1, 2026. Follow-up requested by the user: experiment further and find the most optimized approach. This tests actual compiled CPU Niagara particle simulation, not only synthetic rays. **This remains an isolated prototype; production blood systems have not been migrated.**

## Best measured choices

- **Splat and arc:** buffer queries, run native Jolt first, and refine only native hits through the existing UE query backend. This preserved every exported position, normal and size exactly in these fixtures, with substantially lower CPU producer cost. It retains UE query geometry for refinement.
- **Wound:** buffered native Jolt queries were fastest among the tested options that preserved the output within sub-millimetre tolerance. Maximum exported position difference was only **0.00000573 cm**. The same output was produced with every UE query collider disabled in the fixture.
- Keep both force and movement query sites. They are different rays. Removing the movement query lost all wound exports; removing the force query changed splat/arc placement. Keep GPU visual emitters on their existing rendering collision path.

There is no claim of a globally optimal implementation, a measured gameplay FPS improvement, or a completed native Niagara integration.

## Measured CPU producer cost

Final capture: `Saved/Diagnostics/BloodNative20261001/emitters.json`, finished 00:49:59 UTC. Median milliseconds for **240 simulated ticks**, three rounds per mode with rotated execution order:

| Effect | Stock async UE | Buffered UE | Buffered Jolt | Jolt with UE hit refinement |
|---|---:|---:|---:|---:|
| Splat | 200.87 | 187.12 | 75.97 | **84.26** |
| Arc | 30.17 | 22.89 | 12.54 | **15.28** |
| Wound | 35.25 | 23.42 | **18.64** | 25.33 |

The selected choices reduce this measured workload by approximately **58%, 49%, and 47%**, respectively. Average cost per simulated tick changes from approximately **0.837 to 0.351 ms** for splat, **0.126 to 0.064 ms** for arc, and **0.147 to 0.078 ms** for wound. These averages describe the controlled fixture, not a frame-time promise for the user's fight scene.

The hybrid performs 11,956 UE refinements instead of 299,972 UE requests for splat (**96.0% fewer UE traces**) and 3,007 instead of 32,638 for arc (**90.8% fewer**). It still performs the native query for each request. Wound has a much higher hit rate; refining every wound hit costs more than buffered UE alone, so the blanket hybrid is not the best measured choice for all three effects.

## What was actually exercised

`Prophecy.Blood.EmitterExperiment` creates a transient world and duplicates `/Game/_mygame/blood2/NS_bloodsplat`, `NS_bloodarc`, and `NS_bloodwound` into transient packages. It disables GPU emitters only in those copies and uses deterministic seed 12345. Production assets and user parameters are not edited. Tests use the assets' defaults, not every possible Blueprint override.

The real compiled particle update bytecode performs spawning, movement, collision response, lifetime and export decisions. The diagnostic substitutes collision delegates **only in each isolated instance's execution table**, buffers their actual requests, and supplies next-tick results. The stock mode retains the engine collision interface. Niagara ticks run inside `OnWorldPreActorTick`, after the previous async traces complete and before the current frame's dispatch. Delegate pointers and the temporary world-tick handler are removed during cleanup.

The export boundary records the exact data the compiled script asks to send. **It does not invoke the decal-manager callback or time texture painting.** The export struct's `Velocity` field carries the collision **normal** in these assets, not particle velocity. Historical paint/receiver tests remain separate evidence; see [receiver validation](JoltBloodVisualValidation.md).

Equal UE QueryOnly boxes and Jolt static boxes form a floor for splat/arc and nearby surfaces for wound. All fixture shapes block every channel. Both backends use the same fixed friction/restitution. Admission is warmed for eight native/world ticks. This does not cover moving bones, triangle meshes, material variation, channel exclusions, unregistered geometry, LWC extremes, ISM promotion or native face-to-UV mapping.

The measured section includes isolated world ticks, CPU Niagara simulation, request/result handling, query work and the export recorder. It excludes system compilation/creation, GPU simulation/rendering, receiver painting, gameplay, character pose publication and scene import. Stock async work has little unrelated gameplay work to overlap in this fixture; actual game-thread savings require a real gameplay capture.

## Numerical acceptance and rejected shortcuts

81 trials: three effects × nine modes × three rounds. `validate_emitters.py` passed.

- Buffered UE exactly matches stock exported positions, normals, sizes and counts. This calibrates the diagnostic against the stock async lifecycle.
- Hybrid exactly matches those outputs for all three effects. Counts per 240 ticks: splat **1,161**, arc **245**, wound **1,975**. CPU particle-tick totals also match stock.
- Pure native queries return the same hit/miss decisions within the oracle tolerances. Maximum raw hit-position discrepancy is about **0.0000113 cm**, with zero normal discrepancy in these fixtures.
- Nevertheless, pure native splat/arc exports shift by up to **0.80135 cm / 8.47910 cm**. Counts alone incorrectly suggest equivalence. The compiled collision module derives `Transient.CollisionWorldPosition` through its plane/sphere response, including a division with a `1e-6` floor, and exports that reconstructed position. This is precision-sensitive; raw ray agreement is insufficient to approve the producer output. Refining hits through UE restores exact exported data without modifying the response module.
- Pure native wound export error remains below **0.00000573 cm**, with matching exported normals/sizes/counts.
- Disabling every UE query shape preserves pure-native counts, query hits, particle-tick totals and export-error measurements exactly. This establishes native producer feasibility in the admitted fixture, not that UE colliders can now be removed from gameplay.
- Both query sites submit for every eligible particle in these captures. They use channel **0 (WorldStatic)** for splat/arc and **18 (NiagaraWound)** for wound, and simple traces. The first constructs a force-directed ray; the second uses attempted movement after the first response. They are not duplicate requests.
- Removing the movement ray produces **zero wound exports**, and invalid extreme reconstructed positions in the other effects. Removing the force ray preserves counts in these fixtures but changes splat/arc positions (up to roughly **0.32 / 3.34 cm** relative to stock). Neither deletion is accepted as a global optimization.

## Production implementation boundary

The fastest tested conservative migration direction is a **buffered CPU collision interface with native wound queries and hit-refined native splat/arc queries**, retaining both existing query sites. Use a supported Niagara data interface rather than the diagnostic's execution-table hook. Preserve one-frame query IDs, skip behavior, LWC conversion and teardown. No global scan/tick is needed while there are no active instances or requests.

The current native `RayCast` is unfiltered. Before production use, add correct query-channel/ignore rules and generation-checked component/bone/instance identity. The hybrid can skip UE misses only where native geometry coverage is known complete; UE-only or non-equivalent geometry requires a proper fallback. Retained gameplay callers still need their UE query colliders. Keep exact UE static UV recovery where Jolt subshape IDs lack a verified UE face mapping.

GPU spray and per-instance paint storage are separate concerns. The `SM impostors` actors currently provide separate masks for ISM instances; changing particle collision does not remove that requirement. Do not disable them or all UE colliders based on this experiment.

No production migration is installed by these tests. The remaining integration gate is an actual asynchronous native interface feeding the live receiver/paint callback in mixed moving-character/static/instance scenes, followed by a gameplay capture including painting and rendering.

## Build, recovery and evidence

An initial diagnostic dereferenced the empty script context of a disabled emitter and crashed the editor at 00:32 UTC. The diagnostic now excludes disabled emitters and guards null scripts. Both the saved PoseAgent Blueprint and its newer autosave were backed up under `Saved/Diagnostics/BloodNative20261001/CrashRecovery`; the newer autosave was restored using the same file-copy procedure as Unreal's package recovery. No blood Blueprint or Niagara edits were made.

Subsequent experiments ran successfully in separate offscreen editor-game processes. The first stock timing capture was invalid because manual Niagara ticks happened after the world finished its async trace phase; that capture is retained as `emitters-first-invalid-stock.json` and must not be used as a stock performance baseline. Later captures corrected the tick ordering and verified exact buffered-UE parity. Regular editor builds passed, including the final build at approximately 00:49:36 UTC. The compiler reports one deprecated Niagara diagnostic accessor; no engine patch is involved. No screenshots, full test suite, heavy-asset transfer or push.

Unreal was reopened on `/Game/testNN`, verified outside PIE; the recovered PoseAgent Blueprint compiled and has a valid generated class. That verification did not save the Blueprint. Evidence: `recovery-status.json` in the experiment folder.

Code: `Source/GameAnimationSample3/Private/ProphecyJoltBloodEmitterExperiment.inl`, included only by the editor-only query experiment. Evidence/scripts: `Saved/Diagnostics/BloodNative20261001/{emitters.json,emitter-summary.json,validation.json,emitter-process.log,run_process.ps1,analyze_emitters.py,validate_emitters.py,HLSL/}`. Earlier stages retain their own filenames; the final JSON is authoritative for the table above.
