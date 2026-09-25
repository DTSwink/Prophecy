# Attack arm return to neutral

`Set Attack Arm Return To Neutral` configures an automatic, temporary attacking-arm controller after **slashL, slashR, slashLD, slashRD, slashLU, slashRU, pike, jabL, jabR, hookL, hookR, overL, overR**. Slashes and pike return the right sword arm; jabL/hookL/overL return the left arm and jabR/hookR/overR return the right arm. Full and half versions share the setting. **Kicks, headbutts and defense are excluded.** Nothing is enabled until the node is called. The former `Set Slash Right Arm Return To Neutral` node retains its native function and pins, preserving existing Blueprint connections/settings.

Inputs, in order:

- Enabled (true): disabling cancels a running return and removes its configuration.
- Hold Duration Seconds (0.3): full procedural ownership while returning toward idle.
- Blend To NN Duration Seconds (0.5): smoothly transfer ownership to the ordinary locomotion arm output.
- Return Speed (100): reference positional route speed at an **initial distance of100cm**. Each return captures `FixedSpeed = ReturnSpeed * InitialDistanceCm /100` once. For example300 with20cm initially gives60cm per authored second, while80cm gives240. Approaching/moving the destination does not rescale the speed. Wrist orientation follows the same route progress. Zero initial distance or zero speed stops neutralward movement; the scheduled ownership blend still runs.

One authored second means **60 unpaused game ticks**, independent of actual FPS and agent time dilatation. Both durations zero disables the feature. Hold is not a delay before moving: it is the period during which the return controller fully authors the arm. A short hold/low speed need not reach idle before the blend begins.

Configure in delayed BeginPlay or in Attack Ended. The setter recognizes the ending attack inside that event and selects its eligible arm automatically. A new committed attack/parry/dodge cancels the active return immediately. Reset cancels motion and restores captured configuration. Queued defense before Armed remains ordinary locomotion.

## Pose contract

The destination is the authored neutral idle seed already used at initialization. Its selected arm is carried onto the corresponding current clavicle. The route is measured in an anatomical frame derived from the current pelvis, neck and shoulders, so it follows the torso instead of a world-space waypoint. Selecting the left arm preserves the same right-minus-left torso frame and uses the left arm's hinge axes, lengths and neutral wrist. Held-sword geometry is used only for the right arm; left-hand routing cannot accidentally inherit the right-hand grip.

The initial distance is the full3D straight distance between the outgoing wrist
and the neutral wrist mounted on the **outgoing clavicle**, before the first
recovery prediction moves the torso. It is sampled once on return initialization,
stored in the return's copied speed setting, and discarded at completion or
cancellation. Saved settings/reset baselines retain the unscaled reference speed.
This is not continuous distance-based slowing or an additional arrival ease.
The existing route/turn speed bounds and ownership blend still apply.

Wrist translation interpolates elliptical radius, front-side azimuth and height, rather than crossing the chest along the endpoint chord. Both neutralward motion and the handoff to the NN use this route. The route retains clearance even if the ordinary NN wrist destination lies inside the exclusion ellipse.

Hand rotation is calibrated from the held sword's mesh bounds and actual grip transform: its long blade axis returns to anatomical forward. Yaw is explicitly unwrapped, rather than shortest-arc quaternion slerped. Both rotation windings are evaluated against the blade's torso clearance along the return; this permits the longer outward turn in the user's sketch without forcing a needless revolution when the blade already points forward. Rotation shares the wrist's route progress. A padded segment guard includes grip offset, blade length and cross-section, moving an unsafe wrist target outward on its existing side. These are recovery pose checks, not changes to sword collisions or physical constraints.

A connected two-bone solve transports both source hinges to the same final wrist before blending their bend directions. It gradually restores coherent idle/NN guidance; wrist roll does not independently orbit the elbow. Nearly straight or ambiguous guidance retains the previous bend rather than amplifying numerical noise. A torso-envelope guard checks both shoulder–elbow and elbow–wrist segments and rotates the elbow on its exact IK solution circle toward the nearest clear solution. It preserves both lengths and the wrist target. Boundary refinement avoids discrete pole snapping; its turn rate is bounded, permitting gradual escape from an already-penetrating attack pose. Wrist-derived forearm roll retains the shared locomotion/specials convention. See [the elbow correction and validation](ElbowRecoveryBend.md).

The result is stored in the accepted upper-body state, feeding subsequent NN inputs and publication/physical targets. It runs after existing hand recovery, tempering and inertia: the return controller owns the selected arm during its hold, then yields to those ordinary controls. The other arm, FK core, legs, root and special poses are untouched. Existing physical constraints and authored clamp settings remain in force.

This uses an anatomical torso envelope and the held blade geometry, not an environment collision planner or a guarantee against every physical self-contact. It cannot repair arbitrary pre-existing body penetration or make an unreachable wrist target reachable. Existing target clamps may further constrain the decoded wrist. At the end, ordinary NN/tempering controls resume exactly.

## Cost and state

Separate weak sidecars preserve retained actor/manager layouts for Live Coding. Only active returns consume the finite 60-tick clock, decode the compiled idle seed, route or solve the arm. No extra model inference. The clock retires at its configured end, and the active pose record is removed on the next eligible policy sample. Inactive/finished settings introduce no recurring timer or pose work.

## Validation and limitations — 2026-09-23 correction

Earlier hook/over extension validated2026-09-24: Live Coding build213.42s loaded15:44:25UTC. Eight focused SlashReturn, HandRecovery and CoreTempering tests passed15:44:39UTC, including six-slash/four-melee arm selection, exclusions, left/right front-route mirror parity, finite arm targets, exact12-tick retirement at30/60/120FPS, disable and cancellation cleanup. Existing blade winding, proportional speed and lifecycle regressions remain passing. Pose Blueprint compiles status3 with zero stale native types;45 archived library defaults repaired with values/wiring preserved. No scene rollout was performed for the new melee extension, so these checks do not establish visual quality for every hook/over recovery pose. No graph wiring edits, asset save or restart. Fold this live patch into the next authorized normal build.

The following is historical validation of the original slash controller:

Earlier patch9 evidence checked wrists and arm segments, **not the blade sweep**, and did not establish the safety the user requested. Fresh audit also found no call to this opt-in node in the current pose Blueprint. Ordinary-recovery baseline `Saved/Diagnostics/SlashSword-20260923-140318.json` has blade/torso overlap (squared normalized clearance about0.004; outside is≥1).

First rotation revision (patch10) fixed the current horizontal slash but failed diagonal slashLD/LU and half slashL in the broader test. It independently advanced hand and sword, and a side-only winding rule forced an unnecessary near-full turn for an already-forward sword. Final revision evaluates blade winding along the route, couples its progress to the wrist and adds blade/grip clearance. `CheckSlashWinding.py` reproduces the sketch:135→360 is clear while135→0 crosses; an already-forward -5° blade selects0, not -360.

Final Live Coding patch11 loaded **12:23:37 UTC**,313.78-second build, no object changes. Seven focused native tests passed **12:25:20 UTC**: SlashReturn.RouteAndLifecycle; four HandRecovery; two CoreTempering. Node reflected/called; pose Blueprint compiled status3, zero stale native/pin types; wiring/values preserved and left unsaved. Existing retained actor, manager and earlier sidecar layouts were not resized.

`Saved/Diagnostics/SlashSwordVariants-20260923-142408.json`:900-frame owned PIE with six full directions, full pike, half slashL and half pike. Transient possessed-actor ticking was disabled only in this isolated test to prevent the user's per-frame attack setter overriding test choices. The manager still evaluated/published poses. Future targets, presented transforms and actual sword mesh transforms were captured. Blade clearance uses an analytical segment minimum against a torso ellipse padded by3cm, with eight subdivisions between displayed frames for the sampled sweep. Minimum full-slash swept clearances were1.85,2.19,2.08,2.33,1.012,1.95 respectively; all≥1. The1.012 slashLU minimum is the attack exit itself; after four ticks it stays≥1.267. Half slashL blade stays≥1.232. Actual sword component clearances match the presented hand-driven values.

All six full returns keep the measured upper arm and forearm outside the torso core. Maximum full-return future wrist step is6.07cm; maximum forearm rotation step28.03° in slashLU. Half slashL still starts with an already-penetrating arm and makes a bounded escape; maximum wrist step9.26cm. **These results do not establish universally snap-free motion, instant removal of initial penetration, or clearance for every parameter/pose.** Pike/half-pike were intentionally untouched in that historical test; half pike exhibited its original crossing. Pike is now eligible for the same controller, as described above.

Current scene with feature enabled only in transient PIE: `Saved/Diagnostics/SlashSwordEnabled-20260923-142539.json`,360 frames/three slashL exits. Actual/presented/interpolated blade clearances stay≥1.719. Existing Blueprint graph/scene settings were retained. No Blueprint graph edits, asset saves or editor restart. All diagnostic PIE sessions ended.

That original validation used an opt-in node not yet wired into the pose Blueprint
at12:26:30UTC. The user has since wired it under the shared Special Ended chain.
Current proportional-speed behavior and validation are recorded in
[SlashReturnSpeedDip](SlashReturnSpeedDip.md). Include these Live Coding changes
in the next authorized normal editor build before a fresh launch.

Jab/pike extension validated 2026-09-25 (local): `jabL` selects the left arm; `jabR` and `pike` select the right. Eligibility alone changed; shared position/rotation routing, elbow solve, initial-distance speed, lifecycle and inactive bypass remain unchanged. Live Coding succeeded in 49.16s, loaded 2026-09-24 21:57:12 UTC. All eight SlashReturn/HandRecovery/CoreTempering tests passed at 21:57:38 UTC, including all seven jab/hook/over/pike hand selections, finite targets, cancellation/disable cleanup and 12-tick retirement at 30/60/120 FPS. Pose Blueprint inspection reports status3, zero stale native/pin types, wiring preserved. No scene replay, Blueprint edits/save or restart performed. Fold this live patch into the next authorized normal editor build.
