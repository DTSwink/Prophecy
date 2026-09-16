# Pelvis inertia

Blueprint: **Set Pelvis Inertia**, with the agent connected to **Agent**. **Get Pelvis Inertia** reads the current settings. Per-agent, runtime controls; disabled by default.

| Pin | World-space motion controlled |
| --- | --- |
| Horizontal Follow | Linear X and Y together |
| Vertical Follow | Linear Z |
| Yaw Follow | Angular velocity about Z |
| Pitch Roll Follow | Angular velocity about X and Y together |

Each value is in `[0,1]`: **1 preserves ordinary behavior**, **0 keeps the existing velocity**, intermediate values blend toward ordinary motion. Invalid values are rejected without changing the previous settings. Example: enable, horizontal `0.3`, vertical `0.7`, yaw `0.5`, pitch/roll `1`.

**Simulated Body = false:** filters the pelvis in world space immediately after lower inference and pinning, before upper inference. The v4 leg solver recomputes hips from the corrected pelvis, projects ankles into fixed-length reach, transports the complete knee hinge frame, and stores solved thigh rotations and ankle positions in the normal lower state. That corrected state drives both recurrence and upper-body inputs. Spine FK therefore follows the corrected pelvis. Feet retain their rotations/toe values; reachable endpoints remain in place unless the final foot/toe floor check requires lifting them. The root window is unchanged.

Locomotion and full attacks apply this in their respective lower-to-upper inference boundaries. Half attacks use corrected locomotion legs and their existing pelvis-mounted attack upper body. There is no later isolated-pelvis modification during display publication. Disabled/all-one settings skip integration, geometry construction and leg solving; only the eligibility check remains.

Reference: `dodge_leg_feedback.py` v4 (`solve`, `foot_local_hinge_pole`) and `FINAL_FOOT_FLOOR_20260909.md` in `stepper/training/slashes2/ParryAndDodge`. The exact foot/toe box minimum is checked after reach projection. Floor correction projects onto the reachable floor-plane section, avoiding a radial reclamp that pulls the foot underground. Unlike the bounded Dodge controller, unconstrained zero-follow pelvis motion can eventually place the entire leg reach below the floor: then the solver retains bone lengths at the highest reachable ankle position. It cannot simultaneously preserve unrestricted pelvis coasting, fixed lengths and floor clearance in that impossible configuration.

**Simulated Body = true:** in **Sim**, weights the pelvis magnetisation drive's velocity correction directly, with both Jolt and Chaos. It does not teleport the body or overwrite the completed constraint solve. Zero removes that axis's tracking correction; collisions, joints, external forces, damping, velocity caps and the existing gravity/cancellation settings still apply. Thus a constrained physical pelvis is not guaranteed to coast through contact at constant velocity. Magnetisation must be enabled to have a tracking correction to adjust. In **Kinematic** and **Half Sim**, this option uses the kinematic-target path instead.

The angular controls split the **world angular-velocity vector**, not local Euler angles. Pitch and roll intentionally share one value. Target-mode angular integration uses shortest-arc quaternion differences and quaternion exponential increments.

Disable or return all four values to `1` to restore normal behavior. This is an immediate return, not a timed recovery blend. Retuning active non-one controls preserves current target momentum; re-enabling after bypass seeds velocity from the current pair of raw pose endpoints. Repeated publication of the same policy timestamp cannot advance inertia twice.

No new ticking component, timer, inference, or debug capture. Disabled/all-one settings skip inertia integration and bone changes; minimal state checks remain. Jolt keeps sparse overrides outside its rig layout, looks up the world's override map once per servo pass, and does additional vector work only for configured bodies. Body retirement removes its override; packet rebuilding preserves surviving bodies' settings.

Historical validation of the original implementation (2026-09-14): normal Editor build/link and 14 inertia/servo tests passed; PIE checked pelvis velocity and backend switching. **Those checks did not verify leg/torso attachment and missed the detached-pelvis defect. They do not validate the corrected state workflow above.** The late publication-only pelvis pass has been removed.

Historical test: `Tools/NN/TestProphecyPelvisInertia.py`; evidence `Saved/Diagnostics/PelvisInertia.json`, `PelvisInertiaAutomation.log`, `BuildPelvisInertia.log`. That original implementation required a restart for its new plugin export. The lower-state correction uses Live Coding and does not require another restart.

Current regression: `Prophecy.NN.PelvisInertia.LegChain` checks 1,001 pelvis poses, both segment lengths, calf FK reaching the stored ankle, feasible floor clearance, unchanged foot rotation, coincident and reversed targets. `Tools/NN/TestProphecyPelvisLegChain.py` checks live policy endpoints through running, turning/coasting, stopping, full and half hooks. It checks the actual locomotion/attack geometry contracts (their right thighs differ by 0.1382 cm). Half attacks retain their intentionally independent upper mount rotation, so that phase checks pelvis-to-spine distance rather than a fixed pelvis-local direction. Output: `Saved/Diagnostics/PelvisLegChain.json`.

Validated correction, 2026-09-14: Live Coding build and patch succeeded without restarting Unreal. All three inertia automation tests passed. Final PIE regression passed 1,251 endpoint observations over 21.67 simulation seconds, covering the six phases above. Largest segment-length error against the respective geometry contract: 0.000368 cm; largest checked pelvis attachment-offset error: 0.000187 cm. These verify policy endpoint connectivity; they are not a performance measurement or a guarantee against displacement of physical joints under external forces.
