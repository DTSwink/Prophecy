# Attack target cylinder

`Get Valid Attack Target(Agent, Attack, Target)` is a pure Blueprint function with three vector outputs and one scalar output:

- Effective Target: the nearest point inside the attack's horizontal reach cylinder.
- Difference: Effective Target minus Wanted Target.
- Wanted Target: the original input, unchanged.
- Distance To Limit: remaining horizontal distance in cm from the wanted target to the cylinder boundary, `max(0, radius - planar distance)`. It is zero on/outside the boundary and for invalid inputs. Target height does not affect it. For example, radius150 and target distance120 gives30; distance170 gives0. This reuses the projection's distance calculation and adds no recurring work.

Attack is an explicit Name (jabL, kickR, slashRU, pike, etc.), so the function can be called before starting an attack. Connect Effective Target to Trigger NN Attack or Set NN Attack Target. The query does not start/reset/change an attack itself and is not wired automatically into existing attacks. All 16 runtime families are supported; FName matching is case insensitive.

Per user clarification, the measured GT origin is **the normal self-balancing target on frame 0**, not the root bone and not the root at Hit. Native balancing uses the midpoint of foot_l and foot_r. Each radius is the horizontal distance from that first-frame midpoint to the saved GT hit target. The source clips are `training/slashes2/final_gt_attack_dataset_npz`, the same original GT dataset referenced by the accepted attack export. The saved contact target accounts for the authored strike point, including sword/pike geometry. Mirror augmentation clips (`*_M`) are not separate runtime attack families.

At runtime, the cylinder is centered on the agent's **current** flat feet midpoint, sampled through the existing balancing helper (simulated foot positions when available, otherwise the visible foot bones). It works even with self balancing disabled. The temporary kick/pelvis balancing exception does not change this ordinary feet-based reference. If no feet can be sampled, the current root is used. Target Z is always preserved: there is no ceiling, floor, angular cone or collision/path check.

`Set Attack Target Extra Reach` now has one float pin for each attack, in the same order as Set Trim Attack: slashL, slashR, slashLD, slashRD, slashLU, slashRU, pike, jabL, jabR, hookL, hookR, overL, overR, headbutt, kickL, kickR. Every pin defaults to50 cm on a new node. Settings remain per agent. Radius = that attack's measured GT radius + its extra reach; Distance To Limit uses this same radius. Zero uses GT reach exactly. All values must be finite and nonnegative; an invalid value rejects the entire update without partial changes. Setting all16 to50 removes overrides. Unknown attack names use zero horizontal reach rather than guessing a family. Invalid agent/target inputs pass through unchanged with zero Difference. The setter does not retarget an ongoing attack by itself.

Existing-node migration copies its old common value/connection onto every added attack pin. The former ExtraReachCm pin keeps its internal identity and displays slashL, preserving its connections. Explicit one-shot editor command `Prophecy.Editor.RefreshAttackTargetExtraReach` refreshes the pose Blueprint using its pre-change graph capture, verifies unrelated pin values/connections, compiles and leaves it unsaved. Repeated refreshes preserve the new per-attack settings.

September24 validation: Live Coding build162.37s, loaded13:28:21UTC. The existing node's common0 value was copied to all16 pins; graph audit confirms every value0 and original execution/Agent/return wiring preserved. Whole pose Blueprint compiles status3 with zero stale agent pin/property types after18 archived library defaults were repaired. Native TargetReach test passed13:28:37UTC. Owned PIE passed13:29:09UTC: all16 different extra values (0 through105 in7cm increments) matched the respective GT radii and distance-to-limit outputs, another agent stayed independent, invalid final-pin values rejected the whole update, and restoring all50 restored every default radius. Evidence: `Saved/Diagnostics/AttackTargetExtraReachPins.txt`, `LiveLibraryDefaults.txt`, `AttackTargetReachPIE.json`. No restart or asset save; owned PIE stopped. Include this patch in the next authorized normal build.

The static table is baked by `Tools/NN/ExportAttackTargetReach.py`. No NPZ, training checkpoint, Python, JSON load, inference, tick or timer is needed at runtime. The override uses weak agent keys and world cleanup, without modifying actor/manager layouts. The script reads source NPZs without changing Stepper; [the provenance report](AttackTargetReach.json) records SHA-256, both frame-0 feet, GT target and fractional Hit frame for each original clip. Training coordinates are Y-up: use X/Z for the measurement, then return ordinary Unreal X/Y-horizontal vectors. `global_joint_pos` is cm and `attack_target_world_m` is metres, matching the final harness's explicit `global_joint_pos * 0.01` conversion.

| Attack | GT radius cm | Default radius, GT + 50 cm |
|---|---:|---:|
| jabL | 89.40 | 139.40 |
| jabR | 88.38 | 138.38 |
| hookL | 77.00 | 127.00 |
| hookR | 62.00 | 112.00 |
| overL | 72.92 | 122.92 |
| overR | 86.84 | 136.84 |
| headbutt | 63.17 | 113.17 |
| kickL | 117.86 | 167.86 |
| kickR | 120.00 | 170.00 |
| slashL | 129.38 | 179.38 |
| slashR | 96.62 | 146.62 |
| slashLD | 122.35 | 172.35 |
| slashRD | 89.10 | 139.10 |
| slashLU | 123.79 | 173.79 |
| slashRU | 89.20 | 139.20 |
| pike | 140.41 | 190.41 |

## Validation

September22 margin output: Live Coding loaded10:38:54UTC; `Prophecy.Attack.TargetReach` passed10:41:34UTC, including interior, axis, boundary, outside, height independence and invalid-agent margin. Reflected call confirms four outputs. Existing two query nodes needed reconstruction to gain the new pin; `Prophecy.Editor.RefreshAttackTargetMargin` adds it and verifies old values/connections are unchanged. Whole pose Blueprint compiled successfully (status3). No restart, gameplay rollout or explicit asset save; changes remain in Live Coding until the next normal build.

September22 follow-up: the earlier API/PIE checks missed compile errors on existing Blueprint nodes after the native library was reinstanced. The affected unlinked self pins referenced `/Engine/Transient.BPGC_ARCH_FOR_CDO_ProphecyAttackControlLibrary_4`. `Prophecy.Editor.RepairLibraryDefaults` restored28 archived library defaults; the full pose Blueprint compiled successfully (status3), with every other value and connection verified unchanged. No C++ rebuild/restart or asset save. `CheckAttackTargetReach.py` now repairs/checks old library defaults and compiles the entire Blueprint before running the geometry test. This supersedes the prior implication that testing the new calls was sufficient validation of the existing class.

Live Coding loaded September21 at21:36:43UTC; final build succeeded in118.28seconds. `Prophecy.Attack.TargetReach` passed21:37:21UTC: all16 table entries, radial projection, unchanged Z/interior targets, difference sign, zero horizontal distance, unknown family, case-insensitive names and invalid-agent outputs. Owned PIE passed21:37:44UTC (`Saved/Diagnostics/TestAttackTargetReach.py`, result `AttackTargetReachPIE.json`): all16 Blueprint calls match independently measured live foot-midpoint radii, three outputs agree, setting X=0 removes exactly50cm, another agent stays unchanged, invalid margins are rejected, and restoring50 succeeds. No graph/map wiring, asset save, restart or training edit. Ended only the owned diagnostic PIE; Unreal remains open. Include these Live Coding changes in the normal DLL before the next authorized fresh launch.
