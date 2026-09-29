# Attack performance investigation — September 27, 2026

Full attacks were still requesting lower and upper locomotion inference, correcting the locomotion legs, and decoding two complete locomotion poses before the attack replaced those results. Half attacks also calculated upper locomotion output that the ghost replaced. This redundant work is now skipped once the attack has its initialized pose.

## Ownership and preserved behavior

Optional [attack foot locomotion authoring](AttackFootLocomotion.md) is an explicit exception: full attacks retain lower locomotion while at least one foot needs it. The final foot release restores the lower skip from the next inference step. Upper locomotion remains skipped. Disabled/completed authoring introduces no extra inference.

- Full attack: skip its requests for lower/upper locomotion networks, lower correction, upper feature construction/output correction, and the two discarded locomotion pose decodes.
- Half attack: retain lower locomotion inference/correction and pelvis mounting; skip the discarded upper locomotion work. The independent ghost still needs its own lower, cone and upper networks.
- Keep mover/root-window advancement and previous pose/recurrent samples. Attack feedback writes the current recurrent state before the next inference step, including catch-up steps. Recovery therefore starts from the same attack pose.
- Keep initial full-attack seeding, authored animation-layer evaluation and defense paths on the reference route. Resume normal region processing immediately on a mode switch or exit.
- Preserve equipment-state updates. The last locomotion pinning diagnostic is marked as not applying to visible feet during full attacks, rather than generating a fresh discarded pinning sample.

The editor switch `Prophecy.Attack.SkipOverwrittenLocomotion` defaults to **1**. Set it to **0** only for a paired reference capture. Shipping behavior uses the optimization without that editor switch. No retained manager/model layout or reflected API changed.

## Measurements

The current `/Game/testNN` scene has three inference-enabled agents. Locomotion uses DirectML models with a **fixed batch of 100**, despite only three active agents. Attacks use three CPU networks, dynamically batched at one for these captures. Removing the attacker's request cannot eliminate a shared locomotion call while another agent still requires it; its unused row remains part of the fixed tensor.

Two original physical-scene captures, after discarding the first 180 captured ticks:

| CPU world actor-tick interval | Reference A | Reference B |
| --- | ---: | ---: |
| Locomotion | 8.37 ms | 8.55 ms |
| Full attack | 11.67 ms | 11.06 ms |

The attack stage adds about **1.59 ms per engine tick averaged across inference and non-inference ticks**. Its three actual network runs account for about 1.52 ms of that. Native physics stepping rises from about **0.44 to 1.55 ms**. These are measured costs; this investigation does not establish that the additional physics work is redundant.

The optimized physical-scene capture averaged **11.21 ms during attacks**. That is within the reference variation: there is **no demonstrated substantial FPS gain in this three-agent scene**. Shared network call counts stayed unchanged. The removed pose/correction work is small compared with inference and physics.

A controlled kinematic replay temporarily disabled inference on the two background agents, allowing the shared calls to disappear. Identical six-case scripts were run with the optimization off and on:

| CPU world interval during attacks | Reference A → optimized A | Reference B → optimized B |
| --- | ---: | ---: |
| Full | 7.48 → 5.74 ms | 6.36 → 5.83 ms |
| Half | 7.51 → 6.41 ms | 6.23 → 7.02 ms |

Full attacks consistently saved work, although the wall-time gain varied. Half-attack wall time was noisy; its eliminated upper calls are verified, but a stable total-time improvement is **not** established.

For established attack inference ticks (player frame > 1, excluding exit-only ticks), the final isolated replay proves:

| Mode | Inference ticks | Lower locomotion calls, before → after | Upper locomotion calls, before → after |
| --- | ---: | ---: | ---: |
| Full | 63 | 63 → **0** | 63 → **0** |
| Half | 69 | 108 → **108** | 69 → **0** |

Lower counts may exceed ticks during required walk/run recovery blending. Initial seeding and post-attack recovery still run normally.

These are PIE CPU actor-tick intervals, **not FPS or complete GPU frame times**. The scene retained its 60 FPS cap and simulation settings. Profiling phases nest and must not be summed. Python pose reads occur outside the native timed interval; editor scheduling, CPU/GPU synchronization and memory pressure still affect timing. Fixed-100 locomotion export/batching is a remaining optimization opportunity, requiring separately validated model/binding changes; checkpoint files and weights were not changed here.

## Verification and reproduction

- Final Live Coding patch **33**, loaded **2026-09-26 23:24:04 UTC**; build succeeded. Incorporate source into a normal editor build before a requested fresh launch, as with the preceding Live Coding changes.
- Natural physical-scene replay: **506 frames exactly identical**, including future/presented pose, root and attack state.
- Mixed-agent replay: **1,080 frames exactly identical for all three agents**. Cases: full, pure half, full→half, half→full, full→half→full, half→full→half. Includes moving targets and recovery intervals.
- Final isolated reference/optimized repeat: **1,080 frames exactly identical for all three agents**, including roots and lifecycle events. An earlier comparison had at most 0.0000149 cm positional roundoff on one frozen background agent; the same difference occurred between reference runs. The attacker matched exactly throughout. Final paired comparisons use strict equality, not an increased tolerance.
- **6/6 focused native tests passed:** HalfAttack.GhostSwordDrawing, HalfAttack.PelvisMount, SpecialRecovery.AllExitsAndRetirement, SpecialRecovery.RegionalOwnership, PolicyBlend.AttackRecovery, Blends.SixtyTickClock.

Reproducible scripts are in `Tools/NN/AttackPerformance/`. Run Unreal scripts through `Saved/RunUnrealRemote.py`; they refuse existing user PIE, start/end their own session, and restore the diagnostic switch. `CaptureAttackPerformance.py <tag> <frames>` records the natural scene. `CaptureAttackOwnership.py <tag> <0|1 optimized> <0|1 isolated>` records the six controlled cases. Run `CompareAttackPerformancePoses.py <reference> <candidate>` and `AnalyzeAttackPerformance.py <tags...>` locally from the project directory.

Raw local evidence is under `Saved/Diagnostics/AttackPerformance/`: `baseline_a/b`, `optimized_a`, `ownership_mixed_reference/optimized`, and `ownership_isolated_reference/optimized` plus their `_b` repeats, pose files and comparison JSON. Large captures stay under Saved.

The native command `Prophecy.AttackPerf.Capture <tag> <1..4000 frames>` is opt-in and editor-only. It records actual NNE RunSync calls/times and existing Jolt profiling phases. Completion, explicit `stop`, or world cleanup removes its delegates and disables profiling; inactive scopes read no clocks and allocate nothing. All diagnostic PIE sessions ended; the optimization is enabled in the open editor. No Blueprint/map save or Git push was performed for this investigation.
