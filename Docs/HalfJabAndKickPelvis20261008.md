# Half jab accuracy and kick pelvis tuning — October 7–8, 2026

All tick numbers below are **absolute tick debug**. The current TestNN setup was tested in Physical mode through owned Play sessions. No Blueprint graph, saved scene setting, checkpoint, or physics setting was changed. Final graph matches the initial graph (Live Coding CDO paths normalized); Play ended and trace CVars restored.

## Half jabR: distance mismatch after mounting

The first jab starts at 103 in half mode, arms at 106, reports learned Hit at 114, and ends after 120. Requested, effective and ghost world-target query outputs agree exactly; the target is the victim's physical head-bone position. The miss is visible in the authored pose as well as the physical mesh.

At 114:

| Quantity | Measured value |
| --- | ---: |
| Real pelvis ahead of ghost pelvis | 48.4 cm |
| Ghost chest (`spine_05`) to requested head target | 89.53 cm |
| Real authored chest to target | 45.23 cm |
| Ghost chest-to-wrist length | 67.95 cm |
| Mounted real chest-to-wrist length | 67.95 cm |
| Authored wrist relative to target (world X/Y/Z) | -6.7 / +12.9 / +20.5 cm |
| Physical wrist relative to target (world X/Y/Z) | -16.9 / -1.0 / +13.3 cm |

The independently simulated attack ghost aims from its own pelvis; the real lower body keeps running and brings the real torso much closer. The existing distributed spine compensation is already enabled, including position compensation. Its position option turns the transported target ray toward the actual target. It preserves the upper chain's chest-to-hand extension. It cannot make a 68 cm extension into the shorter reach needed from the current chest. The already generated punch rotates upward and goes past the head. At 116 the physical wrist is about 21.4 cm above the requested target.

This is a concrete limitation of **turn-only compensation after an independently generated attack**, not evidence that motion inertia is stalling the jab or that the target query is pointing at a different object. The raw ghost also trails the moving target: at learned Hit its wrist is about 23 cm from the target. A learned Hit is not a guaranteed physical contact, and this investigation does not claim the vanilla checkpoint's endpoint is perfect.

### Matched comparisons

All comparison prefixes through tick 90 match exactly. Each changes only a temporary per-agent setting before entry.

| Change | Closest physical wrist-to-head-target distance during attack |
| --- | ---: |
| Current distributed direction/position compensation | 19.782 cm |
| Disable entry hand, entry core and motion inertia | 19.783 cm |
| Single-spine compensation instead of distributed | 18.790 cm |
| Disable compensation | 38.409 cm |

Disabling all three entry filters changes the physical wrist at 114 by only 0.082 cm. The raw ghost histories are not asserted identical across whole runs: physical interactions can change the subsequently requested moving target. Distances above use bone origins, not collision-shape penetration or a physical Hit-event count.

**Suggested fix:** make the upper attack NN solve for the target relative to the real predicted pelvis/torso that will carry its output. Transform its aim target into ghost coordinates through the inverse of the intended mount, accounting for both distance and direction. Update target conversion and mounting together so they use one consistent frame. Keep the separate lower ghost and learned attack phases; this can use the existing inference, without an extra NN pass. Validate moving/turning targets and chained half attacks before adopting it. This is a proposed implementation, not a change made during this investigation.

Source: `ProphecyNNSlashRuntime.inl::ApplySlashPose`, `ProphecyHalfAttackMount.h::MountDistributed`, `CompensateSpinePosition`, and the current independent-ghost contract in `HalfAttackGTInitialization.md`.

## Kick pelvis: existing settings that remove entry retreat

Current profile: translation window 15 ticks, strength 1; rotation window 10 ticks, strength 1. Full-strength entry momentum first carries the pelvis forward, then the short fade catches back up with the slower authored pelvis. This creates the visible reversal. Lengthening that window at strength 1 alone produces excessive forward carry and is less effective physically.

Use **Set Attack Start Pelvis Inertia** before kick entry:

| Pin | Kick profile |
| --- | ---: |
| Enabled | true |
| Translation Window Frames | **90** |
| Translation Inertia | **0.65** |
| Rotation Window Frames | **10** |
| Rotation Inertia | **1.0** |

This uses only the already enabled entry-inertia feature. Supporting-foot loco drag, the hidden Run leg, rotation settings, magnetization, root balancing, and all disabled features are unchanged. Window frames count unpaused game ticks: 90 is 1.5 authored seconds. Restore the normal 15 / 1 translation profile before other full attack families; the configuration latches at entry. A ready-to-reference JSON is `Saved/Diagnostics/HalfJabKick20261007/kick-preset.json`. The saved Blueprint has **not** been changed automatically.

Maximum backward travel along the entry running direction, measured from running maxima during the first complete kick:

| Kick | Current physical pelvis | Tuned physical pelvis | Tuned presented pelvis |
| --- | ---: | ---: | ---: |
| kickR | 8.815 cm | **0 cm** | **0 cm** |
| kickL | 11.239 cm | **0 cm** | **0 cm** |

Both chosen replays match their baseline physical-bone prefix through 102 exactly. Both start at 103, arm at 112 and report learned Hit at 120; kickR ends at 125 and kickL at 126 with either profile. Closest kicking-foot-to-target distances differ by only about 0.01 cm (these are foot-bone distances, not contact assertions).

Extended captures reach 240. Between attack end and 215, existing recovery/locomotion still has some backward motion: right 6.82 -> 2.11 cm; left 7.34 -> 4.23 cm. The preset solves the requested **kick-entry** reversal; it is not a universal no-backward-motion constraint. It does not merely replace the entry reversal with a larger delayed return. The next automatically requested jab remains half mode. Different approach speeds, poses or contacts may need different tuning.

## Evidence and reproduction

`Saved/Diagnostics/HalfJabKick20261007/` contains the current graph, `capture.py`, sequential `run_batch.py`, baseline/ablation captures, kick parameter trials, `kick-metrics.json`, chosen extended captures, phase/geometry analyses, `findings.png`, and final-state receipt. All edits were temporary Play-session calls. The live debug counters/logging are off again.

Chosen pairs: `kick_normal_extended.json` vs `kick_t90_s0p65_extended.json`, and `kick_normal_left_extended.json` vs `kick_t90_s0p65_left_extended.json`. The jab baseline is `baseline.json`; alternatives are `comp_single`, `comp_off`, and `no_entry`.

![Measured jab and kick paths](../Saved/Diagnostics/HalfJabKick20261007/findings.png)
