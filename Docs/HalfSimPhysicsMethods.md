# Half Sim controller options and standalone physics benchmark

## Quick actual Full Sim comparison — 2026-09-09

Follow-up requested by the user: the earlier `WorldOneStep` row only measured the shared force rule, not the real agent's full Sim pipeline. Added `FullSim` and `AgentHalfSim` benchmark cases that spawn native `AProphecyAgent`, enter the real simulation mode via `SetSimulationMode`, and use its production native pose animation/tick path. Synthetic component-space pose endpoints replace NN inference; there are no Blueprint actors, user Blueprint Tick/debug, or rendering.

100 agents, gravity/floor, 60 warm-up + 180 measured frames each, one short pass per mode, hidden standalone NullRHI, BelowNormal priority:

| Actual agent mode | Mean world tick | Headless equivalent FPS | Final position RMS |
| --- | ---: | ---: | ---: |
| Full Sim (Physical / absolute world magnetization) | 51.70 ms | 19.34 | 0.0146 cm |
| Half Sim (default Native World) | 51.28 ms | 19.50 | 0.0366 cm |

**Effectively tied in this quick test:** Full Sim was 0.42 ms / 0.82% slower, too small for a meaningful ranking from one short run. Both audits confirmed 100 skeletal meshes, 2,200 dynamic/awake bodies, 2,100 anatomical constraints, zero Blueprint actors and zero nonfinite transforms. Half Sim additionally configured 2,200 native target constraints; Full Sim configured none. Full Sim retains its production angular constraint settings (Half Sim uses its own settings). Both use 4/1/0 solver iterations, no self/crowd contacts, common moving targets and a head impulse. These results include the native agent/pose-store/animation path, unlike the earlier minimal controller-only fixture; do not pool them with the older table.

Authoritative data: `Saved/Benchmarks/full_sim_validated_100.json` and `.log` (completed without errors/ensures). Reproduce with `Tools/NN/RunSterilePhysicsBenchmark.ps1 -Count 100 -Warmup 60 -Samples 180 -Repeats 1 -Methods 'FullSim,AgentHalfSim' -FloorOnly -Label unique_label`.

Discard preliminary `full_sim_quick_100` / `full_sim_only_100` measurements: the initial local-only pose publication omitted component-space endpoints, leaving Full Sim unpowered; validation caught ~113 cm pose error. `agent_half_sim_only_100` also failed startup due to spawn collision. The corrected harness publishes full endpoints and explicitly AlwaysSpawns benchmark agents. No production agent behavior or Blueprint assets changed for this follow-up, and the user's editor was left open.

## Results — 2026-09-09

Measured on this i5-12450H laptop (8 cores / 12 logical processors, 16 GB RAM), in a separate hidden standalone process. **These are physics-focused headless throughput figures, not gameplay/rendered FPS.** World-tick timing includes the common native skeletal animation/update pipeline as well as the selected controller, Chaos, and physics pose blending.

Final matched-gain contenders, 100 characters, gravity + floor, three 300-frame measurements per method after 120 warm-up frames:

| Controller | Mean world tick | Equivalent headless FPS | Mean position RMS error | Mean angular RMS error |
| --- | ---: | ---: | ---: | ---: |
| Native World (original Half Sim) | 45.09 ms | 22.2 | 0.04 cm | 0.03° |
| Anatomical Joint Motors + Pelvis | 28.12 ms | 35.6 | 14.38 cm | 30.04° |
| World Force / Torque PD | 34.16 ms | 29.3 | 0.46 cm | 0.06° |
| World Magnetization (native Sim rule) | 35.35 ms | 28.3 | 0.02 cm | 0.03° |
| Anatomical Joint Motors, no support | 32.03 ms | 31.2 | 172.96 cm | 86.96° |

The joint+pelvis option is cheapest among externally supported methods, **but its current tuning is not an equivalent-quality replacement**. Its pelvis stays up while the articulation sags/oscillates substantially. PD and one-step magnetization were about 24.2% and 21.6% cheaper than Native World respectively, with much better tracking. PD and one-step are too close, given run-to-run variation, to declare a definitive speed winner between them. Do not select an unsupported/collapsed rig just because it is cheap.

Same final contenders with no gravity/floor:

| Controller | Mean world tick | Equivalent headless FPS | Position RMS |
| --- | ---: | ---: | ---: |
| Native World | 43.61 ms | 22.9 | 0.02 cm |
| Joint Motors + Pelvis | 28.49 ms | 35.1 | 1.10 cm |
| PD | 32.77 ms | 30.5 | 0.06 cm |
| Native Sim rule | 32.49 ms | 30.8 | 0.02 cm |
| Joint Motors, no support | 30.69 ms | 32.6 | 9.96 cm |

Other unchanged methods/baselines from the preceding full 54-pass suite (separate run; do not pool timings across runs):

| Controller/baseline | No-gravity tick / FPS | Gravity-floor tick / FPS | Gravity-floor position RMS |
| --- | ---: | ---: | ---: |
| Empty world | 0.56 ms / 1788 | 0.48 ms / 2099 | — |
| Kinematic + colliders | 14.00 ms / 71.4 | 12.21 ms / 81.9 | 0.02 cm |
| Passive, free-angular ragdoll | 24.03 ms / 41.6 | 28.80 ms / 34.7 | 112.41 cm |
| Native Local, no support | 40.97 ms / 24.4 | 46.38 ms / 21.6 | 176.86 cm |
| Native Local + Pelvis | 43.44 ms / 23.0 | 44.84 ms / 22.3 | 2.01 cm |

The corresponding Native World floor result in that earlier run was 39.71 ms, so the local-space variant did not produce a speed gain there. That earlier run's joint-motor rows used unconverted angular gains and are superseded by the final contender suite. Final joint motor gains include UE's same angular stiffness/damping conversion as native Physical Animation (1.5 by default).

All final timing passes had 100 meshes, 2,200 valid dynamic bodies, zero Blueprint actors, zero nonfinite transforms, and no logged errors/ensures. Bodies were woken before each step; end-of-step audits occasionally found one or two islands asleep in unsupported-joint / no-gravity one-step cases (2,178 or 2,156 awake rather than 2,200). The externally supported gravity comparisons above all ended with 2,200 awake bodies. Pose errors are final-sample body errors, not full-trajectory or contact-quality certification. No visual/hit-response equivalence is claimed.

Functional validation: all **56 ordered controller switches** on a real native `AProphecyAgent` passed. Body identities, simulation, transforms and velocities were retained; maximum normalized immediate state difference was 5.17e-8; returning to Kinematic passed. This tests immediate continuity, not later motion under different controllers. The selector/getter UFunctions and enum were also verified in the existing live editor after Live Coding; Python's old generated class wrapper did not refresh, so use Blueprint/reflection rather than assuming a missing Python method means a missing node.

Retained data:

- `Saved/Benchmarks/sterile_100_contenders_v3.json` / `.log`: authoritative final 30-pass contender comparison.
- `Saved/Benchmarks/sterile_100_v2.json` / `.log`: full 54-pass suite for unchanged local methods and baselines; superseded joint gains.
- `Saved/Benchmarks/half_sim_switches_v3b.json` / `.log`: passing real-agent switch test.
- `Saved/Benchmarks/sterile_100_final.json`: extra native-world-only control run (not the full contender suite despite its old filename).
- `sterile_smoke.json` and `half_sim_switches_v3.json` were diagnostic iterations with flawed quaternion/pose-error comparisons, not accepted evidence. The aborted `sterile_100_contenders.log` selected only one method due to FParse stopping at commas; the launcher/native parser now handle lists correctly.

No saved Blueprint/map/material changes, editor restart, Git push, or `Weaken Body Drive` implementation. New modes remain selectable; Native World remains the default.

## Blueprint usage

On a Prophecy Agent, call **Set Half Sim Drive Method**, select a method, then call **Set Simulation Mode → Half Sim**. The method may also be changed while already in Half Sim. **Get Half Sim Drive Method** reads the selection. **Half Sim Drive Method** is editable in Blueprint defaults; use the setter node for runtime changes.

Default remains **Native World Drives (original)**. No Blueprint asset is automatically switched. All methods use the agent's existing pose-reference skeletal mesh. Changing the controller does not require a second skeletal mesh or changing the top-level Kinematic / Half Sim / Sim interface.

Do not run a separate Blueprint per-body Sim follower against the same bodies while a Half Sim controller owns them. These options replace the native Half Sim driver; they do not globally disable your custom Blueprint gameplay/debug Tick. The benchmark contains none of that Blueprint logic.

| Half Sim method | Mechanism | External support |
| --- | --- | --- |
| Native World | Native physical-animation target and drive for each physical body | Every driven body |
| Native Local | Native local-orientation targets for non-root bodies; no positional drives | None; pelvis intentionally not driven toward an invalid parent target |
| Native Local + Pelvis | Local limb targets plus one world-space pelvis target | Pelvis |
| Anatomical Joint Motors | SLERP motors on the actual PHAT joints; UE updates their animation targets | None |
| Anatomical Joint Motors + Pelvis | Actual joint motors plus one native pelvis target | Pelvis |
| World Force / Torque PD | Implicit PD acceleration controller, implemented in C++ | Every driven body |
| Passive Ragdoll | Existing bodies and joints, with drives disabled | None |
| World Magnetization | Existing native Sim one-step acceleration rule, with a clean native animation target source | Every driven body |

Kinematic animation with colliders is also benchmarked as a baseline; it remains the existing **Kinematic** top-level mode, not a dynamic Half Sim controller.

The unsupported methods are not balance controllers. They can fall or collapse under gravity. A pelvis-supported joint rig can still sag or twist compared with a fully world-supported follower. Cost and pose quality must be considered together.

Existing `PhysicalDriveSettings`, `Set Physical Drive Strength Multiplier`, and per-body magnetization settings feed the selected controller. Native local/joint methods use angular strengths; their positional settings do not pull every limb into place. The PD option uses inertia-normalized, timestep-stabilized acceleration, so equal numeric gains do not mean identical response to native constraint motors. One-step magnetization uses the same shared acceleration math as `Apply Body World Magnetization`; it is not the user's complete Blueprint Sim implementation. Force caps apply to PD; the original one-step rule remains uncapped as before. No `Weaken Body Drive` recovery feature is implemented.

## Implementation

- `Source/GameAnimationSample3/Public/ProphecyHalfSimDriveComponent.h`: method enum and native shared controller.
- `Source/GameAnimationSample3/Private/ProphecyHalfSimDriveComponent.cpp`: native drive configuration, anatomical motors, PD and one-step control.
- `Source/GameAnimationSample3/Private/ProphecyAgentHalfSimulation.cpp`: Half Sim entry/exit and runtime selector integration.
- `Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmark.cpp`: headless native test scene, deterministic pose generator, audits and timing.
- `Tools/NN/RunSterilePhysicsBenchmark.ps1`: background standalone launcher. Refuses to overwrite an existing report.

Switching releases the previous auxiliary native target constraints, disables the previous motor/controller path, then installs the new one. Existing dynamic ragdoll bodies are retained. Leaving Half Sim restores the saved PHAT joint profiles and existing mode-transition behavior.

## Sterile benchmark protocol

Runs in **standalone game mode**, using `UnrealEditor-Cmd.exe -game`, not PIE and not a packaged Shipping executable. It loads `/Engine/Maps/Entry` with native `GameModeBase`, creates plain native actors, and rejects Blueprint actors. No production Blueprint, NN network, mover, attack logic, debug printing/drawing, materials, or scene lighting is used by the character harness.

`-nullrhi -RenderOffscreen` disables rendering and keeps the game window off screen; `Start-Process -WindowStyle Hidden` hides startup. Process priority is BelowNormal so foreground laptop work takes precedence. The open editor is not closed or restarted. Other laptop activity and power/thermal throttling can still affect measurements; this is not an isolated hardware lab.

Each nonempty case uses 100 copies of `/Game/_mygame/SKM_UEFN_Mannequin`, its default Physics Asset, and exactly one skeletal mesh per actor. Each has 22 bodies / 21 anatomical joints. All methods use the same cheap native procedural animation (reference pose, small head/arm oscillation and pelvis bob), no URO, full bone evaluation, fixed simulation timestep 1/60 s, solver iterations 4 position / 1 velocity / 0 projection, CCD/MACD off, and substepping off. Dynamic bodies are kept awake every frame. A common head impulse is applied 30 frames into sampling.

Two fixtures:

1. No gravity and no floor: avoids collapse/contact differences when comparing controller overhead.
2. Gravity and a static floor: exposes support quality and floor-contact cost. Motion and contact counts can differ between methods.

Collision responses allow WorldStatic contacts only. Self/crowd body collisions and hit/overlap events are disabled. This is deliberate for the sterile comparison, not a production collision recommendation.

All anatomical angular limits are free, with rigid linear anchors, matching the existing Half Sim calibration. The passive baseline is consequently a free-angular articulated ragdoll, not a PHAT joint-limit fidelity test.

Each case is freshly created; bodies/constraints are explicitly released and garbage collection happens outside the measured interval. Case order is seeded/shuffled. Main suite: 120 warm-up frames, 300 measured frames, 3 repetitions per method and fixture. Timing wraps native world actor/physics ticks, including component animation/controller work, Chaos stepping and physics-pose blending. It is **not** the sum of solver CPU time alone. Frame intervals are separately recorded. Any reciprocal reported as FPS is **headless throughput**, not rendered gameplay FPS. Empty-scene and kinematic baselines help distinguish fixed/animation overhead from added dynamic-physics work.

Audits record body/constraint/motor counts, awake/dynamic bodies, Blueprint actors, nonfinite transforms, pelvis height, and errors against an independently generated authored pose. Do not measure pose error against the mesh's post-physics local transforms: that buffer may already contain the ragdoll result.

## Reproduction

After building the editor runtime module, from the project root:

```powershell
& Tools/NN/RunSterilePhysicsBenchmark.ps1 -Count 100 -Warmup 120 -Samples 300 -Repeats 3 -Label my_physics_run
```

Optional `-Methods 'NativeWorld,JointMotorsPelvis,WorldOneStep'` limits the method set; both fixtures still run. Raw results/logs go to `Saved/Benchmarks/<Label>.json` and `.log`. The launcher returns immediately with the process ID. Do not run compilation or another benchmark concurrently with measured passes.

For the separate real-agent API switch test, use the same standalone arguments with `-PhysicsBenchSwitchTest`. It publishes a synthetic pose, exercises every ordered pair of Half Sim controllers, checks that body identity/transforms/velocities are preserved, and returns to Kinematic. It performs no performance measurement.

Primary engine references: UE 5.7 `PhysicalAnimationComponent.cpp` (world/local target construction and auxiliary constraints) and `PhysAnim.cpp::UpdateRBJointMotors` (actual PHAT joint motors and reference-frame conversion). [Epic's command-line reference](https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-command-line-arguments-reference) documents NullRHI headless execution.
