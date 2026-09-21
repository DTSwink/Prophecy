# Attack controls

**Set Attack Return To Root Balancing** chooses the per-agent root placement when
a full/half attack ends or is cancelled into locomotion. **Use Root Balancing
Target=true** is the default, including when no node is called: the flat midpoint
of the feet. Set it false to place the root directly below the current pelvis.
Both use simulated body positions when available, otherwise visible kinematic
bones, and preserve root height. The balancing target is used even if its spring
is disabled or its activation thresholds are not met. This is a handoff target,
not an instruction to enable the spring.

The selection is read only at the existing attack-to-locomotion handoff. No Tick,
timer or ongoing target sampling is added. Both choices retain the existing whole
window rebase, world-pose preservation and registered magic-cube reset. Direct
attack replacements do not recenter; parry/dodge handoffs keep their feet midpoint.

Return selector compiled and loaded via Live Coding2026-09-19 at13:30UTC. No
restart or Blueprint/scene changes. Validation is limited to compilation, reflected
node availability and inspection of the shared handoff wiring; scene testing remains
with the user.

The recovery interface was expanded on2026-09-20: **Set Attack To Locomotion Blend**
now has separate Pelvis, Left Leg and Right Leg source/hold/duration controls and
returns each to **normal selection**, not a forced walk endpoint. See
[Regional attack recovery](AttackRecoveryBlend.md) for current behavior. The notes
below describe the earlier implementation and its validation.

Previously, `Set Attack To Locomotion Blend` took Agent, Duration Seconds (default **1**) and
Hold Duration Seconds (default **0**, preserving existing calls).
After a full or half attack returns to locomotion, the first lower prediction uses
100% Run. It holds that pure Run checkpoint for the hold duration, then its weight
fades to 0% with the existing smoothstep blend, reaching100% Walk after the additional
blend duration. Both durations use60 unpaused engine ticks per authored second,
regardless of actual FPS or time dilation. NN evaluations consume the accumulated
ticks once; repeated evaluations in a frame cannot accelerate the blend. A read
crossing the hold boundary uses only the remaining ticks for blending. The clock
starts with the first pure-Run prediction. The hold uses one checkpoint inference.
Pelvis, legs, foot pinning,
published checkpoint weights and upper-body conditioning use that same mixture.
Normal walk/run rules (including speed overrides) are bypassed during recovery and
resume afterward. This changes checkpoint selection, not movement input or speed.

Call the setter once to configure subsequent handoffs. **Duration Seconds=0 disables
this recovery, including its hold**, preserving the existing zero-cost opt-out:
ordinary checkpoint rules remain in control, no recovery entry is created at attack
exit, and no extra inference/blend work runs. Setting zero during an existing recovery
clears its mixture at the next policy step using ordinary selection. Negative/nonfinite
values return false. Positive duration/hold changes apply to the next handoff. New attacks,
active defenses and agent reset cancel recovery;
direct attack replacements do not create a locomotion handoff. Both normal completion
and explicit cancellation returning to locomotion use it. Only the active blend
requires both lower checkpoint outputs; the inactive registry has an empty fast path.
Current-scene movement quality is left for user testing.

Loaded through Live Coding on 2026-09-19 without restarting or editing assets.
Blueprint function lookup/call succeeded; `Prophecy.NN.PolicyBlend.AttackRecovery`
and `DirectionalTiming` passed (pure-run first sample, default/custom durations,
exact walk endpoint). Zero-duration semantics were subsequently changed to a true
recovery bypass. This is timing validation, not a
current-scene combat rollout.

The zero-duration bypass passed the focused PolicyBlend tests in a normal-build
headless test run on 2026-09-19, together with the lower tempering/leg-chain checks.
The hold extension subsequently compiled/loaded via Live Coding; AttackRecovery
and LowerTempering.ReturnTimeline passed at12:33UTC on2026-09-19. Existing zero-hold
timing and zero-duration bypass remain covered. No editor restart or asset edits.

`Get NN Attack State` already exposes the active attack's name, Half Attack, Armed,
Hit and policy frame. Check its return value: false means there is no ongoing attack.

New `Get NN Attack Colliders` takes Agent and returns Attack, Bone Names, Sword
Collider and an active return value. Inactive calls clear every output. This is
on-demand metadata, including the pre-Armed phase; it does not enable collision.

| Attack | Bone Names / component |
| --- | --- |
| jabl, hookl, overl | hand_l, lowerarm_l |
| jabr, hookr, overr | hand_r, lowerarm_r |
| kickl | calf_l, foot_l; ball_l only if it has a PHAT body |
| kickr | calf_r, foot_r; ball_r only if it has a PHAT body |
| headbutt | head |
| slashl/r/ld/rd/lu/ru, pike | Sword Collider component only; empty bone list |

Only body names present in the agent's current reference Physics Asset are returned.
The sword component is null if no sword is held. Sword readiness still follows the
existing attack/Armed collision gate, independently of this metadata.

`Set Attack Initialization Mode` / `Get Attack Initialization Mode` are per-agent.
Dynamic is the unchanged default. Static duplicates CURRENT into PREVIOUS for both
the 41-value lower state and 90-value upper state, once at the next attack start.
This removes incoming pose velocity from the two-frame input without moving the pose.
The target, attack labels, latches, current state, anchor, and subsequent recurrence
are preserved. Direct attack-to-attack chains retain their current raw NN pose/anchor
and duplicate that current state; presentation-only corrections are not fed back.
Half attacks retain the authored current GT ghost placement, with its current lower
and upper seed repeated instead of the dynamic GT previous/current pair. Changing
the setting does not restart an ongoing attack. No per-frame setting evaluation,
extra inference, or change to locomotion/root/magic velocity is introduced.

Existing tolerance blend nodes already mirror magnetization:
- `Blend Physical Feedback Tolerance`
- `Blend Physical Feedback Tolerance Below`
- `Cancel Physical Feedback Tolerance Blend` (None cancels all for the agent)

Both blend setters expose duration, linear/angular tolerances, Walk/Run/Both and
Drawn/Sheathed/Both. They use the same smoothstep timeline and checkpoint-weight
resolution as magnetization. Duration <= 0 applies immediately. Only supported
feedback channels are affected; the Below node returns the number changed. The
shared timeline callback is removed when there are no active blends.

Per-body force and torque already work through the regular Unreal nodes:
`Physical Mesh -> Add Force` and `Physical Mesh -> Add Torque in Radians`, with
Bone Name selecting the simulated PHAT body. They route to Jolt when active and
Chaos otherwise. Values are world-space. Accel Change bypasses mass/inertia scaling.
Forces/torques act over the simulation interval; call repeatedly for sustained force.
The existing magnetization drive can resist the motion. No duplicate APIs were added.

Focused new test: `Prophecy.Attack.Controls.HistoryAndColliders` verifies both history
blocks, preservation of current state/control fields, and all 16 attack mappings.
