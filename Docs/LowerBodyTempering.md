# Root-local locomotion tempering

`Set Locomotion Lower Body Tempering` takes **Agent**, **Enabled**, and four values:

| Pin | Controls |
| --- | --- |
| Feet Translation | Both ankle positions |
| Feet Rotation | Both feet, toe articulation and the knee-frame motion used by IK |
| Pelvis Translation | Pelvis position |
| Pelvis Rotation | Pelvis orientation |

All four default to **1** (normal locomotion). **0** holds the previous completed
pose in its own root-local frame. Intermediate values interpolate toward the new
lower NN prediction on each 30 Hz policy step: linear for positions, shortest-path
quaternion interpolation for rotations. This is per-step following, not a blend
duration or a blend toward a permanently captured initial pose. All four at zero
keep the lower body as a statue carried by the root, except for pinning and required
reach/floor correction. Values outside [0,1] or nonfinite values are rejected.

To return to ordinary motion, call **Blend Locomotion Lower Body Tempering To Normal**
after setting your values. The menu exposes only **Set** and **Blend**. The Blend
node has Agent plus four timing pins:
- **Feet Duration Seconds** (default1)
- **Feet Hold Duration Seconds** (default0)
- **Pelvis Duration Seconds** (default1)
- **Pelvis Hold Duration Seconds** (default0)

It captures the current values, then independently holds and smoothstep restores
feet translation/rotation and pelvis translation/rotation to1. For example, feet
duration1/hold0.5 waits30 ticks then returns over60 ticks, while pelvis
duration0.5/hold0 returns in30 ticks. One authored second always means60 unpaused world
ticks, regardless of actual FPS or time dilation. Repeated reads in one tick do
not advance the timer.
The return clock starts when this node executes, including time spent in a full
attack/defense where tempering itself does not affect the pose (including half attacks).

At completion the settings and return timeline are removed, so the ordinary path
has no tempering, history copy, extra IK or timing work. Only active returns use
the shared blend-clock callback, which unregisters when no timelines remain.
A subsequent Set cancels the scheduled return; another Blend captures the
currently interpolated values and replaces the prior return. Disabled/all-one
settings cancel it too. Already-normal agents allocate nothing. Duration0 snaps to
normal after the optional hold;0/0 returns immediately. Negative/nonfinite times
are rejected. Completion is resolved on the next eligible lower-policy evaluation.

A completed part retires independently; once both are normal all tempering pose/IK
work is bypassed. A new Blend replaces both return schedules. The briefly exposed
Feet/Pelvis-only functions are hidden from the menu, retained only for existing
graph references. Existing Duration/Hold pins on the combined node retain their
internal names and connections but now label feet timing; set the added pelvis
pins explicitly. Refresh an already-placed Blend node to expose its new pins.

Validated via Live Coding without restart on2026-09-19 at13:19UTC:
SeparateReturns, ReturnTimeline and SixtyTickClock passed. The focused check verifies
exactly two exposed Blueprint functions and different feet/pelvis holds and durations
through the single Blend node, together with timer retirement and zero-duration paths.
No Blueprint/scene edits.

Order:

1. Lower NN prediction and normal state cleanup.
2. Temper against the previous **published root-local** lower state. Do not use
   the current recurrent state, which is already rebased to preserve world motion.
3. Existing foot-roll/pinning and floor logic. Pins use the usual rebased state,
   so a selected pin stays in global space even with Feet Translation = 0.
4. Existing walk/run output blending.
5. Resolve fixed-length thigh/calf chains using the tempered pre-pin knee frame,
   reach projection and final exact foot/toe floor geometry. Write the corrected
   ankle and thigh rotation into the actual lower state, as with pelvis inertia.
6. Existing pelvis inertia (if separately enabled), recurrent commit and upper NN
   conditioning use the corrected pose.

This affects locomotion only. Every active special bypasses tempering, including
half attacks even though they use the locomotion lower policy, plus full attacks,
parry and dodge. The settings are retained for locomotion; scheduled returns keep
their existing clock and do not restart or freeze on special entry. Pending defense
requests do not suppress locomotion tempering until the defense actually activates.
The former half-attack exception was removed and loaded through Live Coding on
2026-09-19 at13:55UTC. Compile/source-path verification only; no scene replay,
Blueprint edits or restart for this gate change.

### Repeated full attacks from a zero-tempered finishing stance

Bounded current-scene diagnosis on2026-09-19: the live Blueprint issued two full
`overL` attacks (the user described hooks), with all four tempering values0 and
Hold=100 (6000 game ticks). Three360-frame PIE captures preserved the
Blueprint/map and restored diagnostic CVars; no restart or gameplay changes.

- Baseline second attack: pelvis per-axis ranges3.88/3.54/0.89cm in the attack
  state, compared with20.49/33.59/9.98cm on the first attack.
- Disable tempering after the second Trigger but before its first prediction:
  **all18 attack inputs and outputs matched baseline exactly**, including the
  weak lower movement. This rules out direct tempering of that full attack.
- Disable tempering in the locomotion gap at2.7167s instead: pelvis recovered
  from77.66cm to90.75cm before attack2; attack2 ranges became22.80/21.87/8.80cm.
  Its Blueprint re-enabled zero tempering at Trigger as in baseline.

The zero setting retains the previous attack's finishing stance. A fresh full
attack correctly seeds its two recurrent frames from the current published pose;
it does not restore a ready stance. The lower attack model receives current pose,
frozen-lower prediction, family and target height, with no new-attack/Armed/Hit
phase input. Restarting the upper attack therefore does not imply repeating the
first lower-body movement from this different stance. Supporting a visible
preparation/recovery on new attack would be a behavior change, not another
tempering bypass. No automatic pose reset or invented lower motion was added.

Evidence: `Saved/Diagnostics/TemperingHooks`, `TemperingHooksDisabled`,
`TemperingHooksGap`; capture helper `Saved/Diagnostics/CaptureTemperingHooks.py`.

At an impossible reach,
the solver must move a pinned ankle to preserve bone lengths; there is no bone stretch.
Simulated-body motion and other explicitly enabled modifiers remain independent.

**Disabled or all-one settings remove the per-agent entry.** No tempering math,
history copies, additional inference, or additional leg solving runs. The dormant
registry returns immediately when empty. No extra tick or retained pose history is
needed: the existing published lower state supplies the previous pose.

Implementation: `ProphecyLowerTemperingLibrary`, `ProphecyLowerTempering.inl`, the
locomotion correction stage and the existing `ResolvePelvisLeg` solver. No changes
to Blueprint graphs, scene transforms, checkpoints or authored collider geometry.

Validation (2026-09-19): normal Editor target build succeeded (111.38 s; Unreal
was already closed). A temporary headless Entry-map process passed four focused
tests: `LowerTempering.RootLocalPinAndChain`, `PelvisInertia.LegChain`, and both
`PolicyBlend` tests. Covered exact identity/zero pose endpoints, separate controls,
root-local following, world pin precedence, fixed-length/floor solving, and zero
attack-recovery bypass. The process exited successfully. No current-scene rollout
or performance benchmark was run; scene testing remains with the user.

Hold/return extension: Live Coding compiled and both reflected signatures loaded
on2026-09-19, without restarting or editing user assets. `ReturnTimeline` and
`PolicyBlend.AttackRecovery` passed: hold boundaries, separate four-value return,
normal endpoint/removal, setter cancellation, zero-duration snap/bypass, pure Run
hold without dual inference, and residual time across the hold/blend boundary.
