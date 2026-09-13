# Jolt character contact controls

Both controls are Blueprint nodes on **Prophecy Agent**. Existing defaults and saved gameplay graphs are unchanged.

## Suggested starting point for the sword/thigh setup

1. **Set Jolt CCD Mode**: `Continuous (Linear Cast)`.
2. **Set Jolt Solver Iterations**: velocity `10`, position `12` for tighter joints. Try position `4` for less solver work.

Set these once during setup, or change them at runtime. They also work before Jolt admission and persist across kinematic/half-sim/physical and Chaos/Jolt switches. They affect Jolt only. Each returns success/error information.

## CCD mode

- `Physics Asset / Existing Sword Policy` is the default. It preserves each body's imported CCD setting; a welded sword can promote the hand to CCD.
- `Discrete` forces the entire rig, including its welded sword carrier, to discrete detection.
- `Continuous (Linear Cast)` selects Jolt CCD consistently across the rig. Sword attach/detach/re-equip retains this choice.

**Get Jolt CCD Mode** returns the requested policy. An independently simulated or dropped sword keeps its own body policy. Other agents are not changed by the setter.

The original setup mixed a CCD hand/sword with discrete limbs. Jolt integrates discrete bodies before its CCD sweep; its CCD relative-motion calculation accounts differently for another CCD body. In this moving, self-colliding articulation the mixed policy produced a large disturbance. Consistent CCD removed most of that disturbance in the captured scene.

Linear Cast does not continuously sweep the full rotation of a long sword. It is not a guarantee of zero penetration at arbitrary speeds. Enabling CCD can add native casts for sufficiently fast motion.

## Solver iterations

Velocity/position counts accept `0..128`. Zero removes the override and uses world defaults, currently `10 / 2`. **Get Jolt Solver Iterations** returns the requested overrides, so `0 / 0` means defaults, not no solving.

Position iterations help repair remaining joint separation. Increasing counts costs native solver work. Jolt takes the highest requested counts for the connected simulation island; if this character contacts another dynamic actor, the extra work can include that actor. These are iteration counts, not simulation substeps: timestep and game speed are unchanged.

The setter preserves joint identity, frames, limits and drive settings. Overrides survive enabling/disabling predictive angular limits. Neither control adds a new tick or pose-processing pass.

## Evidence and limits

Isolation captures: `Saved/Diagnostics/SwordThigh/Isolation`. The unchanged warm scene reproduced exactly across repeated runs. In ticks 95–140, maximum native wrist-anchor gap was 22.647 cm, lowerarm/right-thigh penetration 7.316 cm, and welded sword/left-thigh penetration 9.893 cm. With consistent CCD and 10/4 iterations, these were 0.356 cm, 0.388 cm and 0.001 cm respectively. This is measured improvement in that setup, not an exact-rigidity guarantee.

Reducing inertia or arm magnetization alone did not fix the separation. Extra velocity iterations alone did not fix it either. Reducing global contact slop did not consistently improve the result, so no slop change is applied or recommended here. Some sword/right-thigh penetration remains in the capture; these nodes do not establish perfect rotational collision detection.

Longer runs captured every tick from 60 through 1200 (20 simulation seconds from Play), using the actual Blueprint setters. Maximum values in cm:

| CCD / velocity / position | Wrist anchor gap | Forearm / right thigh | Sword / left thigh | Sword / right thigh |
| --- | ---: | ---: | ---: | ---: |
| Original policy / defaults | 22.647 | 7.316 | 9.893 | 10.588 |
| Continuous / 10 / 4 | 2.480 | 0.388 | 0.058 | 2.905 |
| Continuous / 10 / 8 | 0.957 | 0.512 | 0.145 | 3.099 |
| Continuous / 10 / 12 | 0.428 | 0.518 | 0.115 | 3.154 |
| Continuous / 10 / 20 | 0.112 | 0.842 | 0.089 | 3.196 |

The wrist's later peak occurs at tick 996, so the short original interval alone understated the remaining separation. Penetrations are direct native shape-overlap depths, not rendered mesh distances or contact-manifold impulses. More position iterations improve joint attachment but do not monotonically improve every contact. No performance benchmark was run; these controls add native CCD/solver work when enabled.

Lifecycle verification covered native CCD/iteration values, default restoration, sword simulation/drop/equip, kinematic/half-sim/physical, Chaos/Jolt round trips, and predictive-limit wrapper transitions. Other agents retain their preferences. This exposed an implicit UE auto-weld during sword backend handoff; Equip now disables that redundant auto-weld because the sword controller owns its explicit Jolt weld/Chaos attachment. Without this correction, foreign sword shapes prevented later Jolt rig capture.

The separate temporary native ragdoll-stabilization experiment crashed in its diagnostic mass-settings path before yielding results. That diagnostic command was removed; no mass-stabilization change is included in these controls.
