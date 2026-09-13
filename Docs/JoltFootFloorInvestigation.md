# Foot/floor contact investigation — 2026-09-11

**Subsequent implementation:** body-level UE material combine modes are now applied and contact-tested; see `JoltMaterialCombine.md`. The investigation below records the pre-fix behavior. Live material updates, per-triangle materials and the remaining grazing issue are still separate work.

**Status: reproduced numerically; no permanent gameplay or physics change applied.** Restitution causes the large bouncing spikes in the current walk. Friction also contributes to forward catching. A complete fix of the user's visual complaint is not established.

## Controlled scene comparisons

Used the user's current `testNN` scene, two existing agents, existing auto-walk, full Physical mode. Every trial began in fresh PIE, selected the backend at one second through the public Agent API, and recorded 25 simulation seconds at 60 Hz. The walking actor is `BP_ProphecyManualPoseAgent_C_1`. Comparisons below exclude startup (`t < 4 seconds`) and use frames with the authored foot-bone target below 15 cm. This is a near-ground proxy, not measured collider clearance.

Across all seven comparisons, the walking actor's root positions and foot target positions match baseline exactly in the analyzed interval. Thus the measured differences are not different authored walking inputs. The stationary actor was not used for this table.

| Trial | Max vertical velocity change per frame, L/R (cm/s) | Max near-ground position error, L/R (cm) |
|---|---:|---:|
| Chaos | 44.2 / 69.2 | 1.70 / 1.55 |
| Original Jolt | 136.0 / 192.5 | 2.67 / 4.63 |
| Jolt ignoring only the floor channel | 38.2 / 46.0 | 1.76 / 2.22 |
| Jolt, restitution threshold 200 cm/s | 43.7 / 159.3 | 1.85 / 4.65 |
| Jolt, character friction zero | 98.2 / 134.9 | 2.00 / 2.16 |
| Jolt, speculative distance 0.1 cm | 98.9 / 145.7 | 2.45 / 4.41 |
| Jolt, penetration slop 0.1 cm | 135.7 / 188.8 | 2.66 / 4.69 |
| Jolt, character AND floor restitution zero, friction retained | 43.3 / 42.6 | 1.83 / 2.69 |

These are absolute changes in reported body COM vertical velocity between consecutive samples, not mathematical jerk or direct contact impulse measurements. Position error compares the physical body origin with the presented authored foot target. These metrics establish contact-induced discontinuities and improvement; they do not certify perceived smoothness.

Zero restitution preserved friction 0.7 and all colliders, joints, drive strengths, gravity cancellation and tick timing. It also reduced peak near-ground vertical speed from 181/124 to 77/77 cm/s. However, right-foot forward lag still reached 2.33 cm versus Chaos 1.32 cm, so removing bounce alone is not a complete grazing/stiction fix.

## Material and solver findings

- Both PHAT feet are boxes. Their body setups have no special physical material override. The fixed floor likewise resolves the default material: friction approximately 0.7, restitution approximately 0.3. This is not evidence of an accidentally assigned unusually sticky material.
- The bridge captures friction/restitution and assigns them to Jolt bodies. **UE material combining is not fully ported:** rig/body capture records the effective UE combine modes, but world creation does not install combine callbacks; static capture does not retain those modes. Jolt therefore uses geometric-mean friction and maximum restitution. UE defaults here use Average. Equal default coefficients yield the same combined value, so this gap alone does not explain the current baseline, but different foot/floor materials would behave differently.
- Jolt's default restitution threshold is 1 m/s, speculative contact distance 2 cm, penetration slop 2 cm. Changing one at a time showed that raising the threshold helps one foot and reducing slop does not solve the issue.
- **Correction to an intermediate update:** Unreal exposes `BounceThresholdVelocity = 200 cm/s`, but this UE 5.7 Chaos path does not simply consume that property. Chaos uses its collision-container acceleration threshold multiplied by the solver step duration. Treat 200 cm/s as a diagnostic Jolt setting, not proven Chaos equivalence.
- Jolt explicitly documents speculative-restitution artifacts in its contact implementation: a predicted collision may bounce before actual touching, and other constraints may later make that bounce unnecessary. This is consistent with the experiment; a per-contact trace would be needed to attribute each spike to that exact internal branch.
- `StaticFriction = 0` on the default UE material does not mean Chaos has zero static friction: Chaos takes the maximum of static and dynamic friction before combining.
- Runtime `SetPhysMaterialOverride` alone is not established as a live Jolt material update. These diagnostic trials rebuilt character rigs; the successful zero-restitution trial also disabled/re-enabled the static importer after changing the transient floor material. Setting only the character restitution to zero would not remove Jolt's maximum-combined floor restitution of 0.3.

## Outcome and next decision

No blanket slippery-floor workaround, collider reshaping, whole-world bounce suppression, threshold retuning, substepping or movement smoothing was shipped. The next material integration work should implement the actual UE combine policy and explicit material-update propagation, with asymmetric-material contact tests. The remaining driven-box grazing behavior needs contact-level analysis or a deliberate foot-contact material choice; do not present the trial settings as a completed fix.

PIE was stopped. Diagnostic CVars were reset to -1 (native defaults), and diagnostic C++ additions were removed from production source. The current editor still has the inactive Live Coding diagnostic patch loaded; its defaults preserve original behavior, and a restart uses the ordinary build. Saved Blueprint/map/material assets were not edited or saved. The editor reports dirty `BP_ProphecyManualPoseAgent` and `testNN`; these were left untouched, not discarded or saved.

## Evidence

Raw data and scripts: `Saved/Diagnostics/FootFloor/`. Baseline `jolt-053343.json`; Chaos `chaos-053514.json`; successful zero restitution `jolt_zero_restitution-055429.json`. `Compare.py` produces `comparison.json`; `CheckInputs.py` verifies matching walking inputs. `WorldSubsystem-DiagnosticSnapshot.cpp` preserves the opt-in test implementation for reproduction; `DiagnosticBuild.log` records its successful build. The earlier zero-restitution attempt at 05:52 did not reimport the floor and is excluded.

Primary implementation references: pinned Jolt 5.6 `ContactConstraintManager.cpp` (speculative restitution and friction), `PhysicsSettings.h`, and `PhysicsSystem.h`; UE 5.7 `PBDCollisionConstraints.cpp`, `PBDCollisionContainerSolver.cpp`, `PBDRigidsEvolutionGBF.h`; adapter `ProphecyJoltRig.cpp`, `ProphecyJoltStaticBody.cpp`, `ProphecyJoltWorldSubsystem.cpp`.
