# Slash foot contacts and player attack camera — 2026-09-12

**2026-09-13 update:** gameplay now defaults to **4** frozen pin iterations per
agent at the user's request. Set **Attack Foot Pinning Iterations = 60** for the
source-exact configuration measured below. See
[AttackPinningAndHeadbutt.md](AttackPinningAndHeadbutt.md).

Attack-only overrides are now available: **Set Attack Foot Clamp** and **Set
Attack Calf Clamp** on an agent, each with Enabled and Leeway Cm inputs. Disabling
both removes full-attack leg clamps without changing locomotion settings. The
manager switches described below still apply unless an attack override is set.

The current hook setup had two independent differences from the original training
rollout: a four-step approximation in frozen-Walk foot pinning, and an optional
calf-length correction applied after the model had pinned the feet.

## Foot pinning and the reference

Production now runs the source's60 frozen pin integration steps and4 learned
Slash pin integration steps. The three ONNX networks/checkpoint bytes, source
training files, saved reference animation and raw Slash recurrence are unchanged.
Only the native frozen pin resolution and its exported startup oracle changed.

- Immutable30-attack reference:453 self-fed transitions, maximum joint error
  **0.034761 mm**, matrix-element error0.000195325, all Armed/Hit latches identical.
- Teacher transitions from those same inputs: maximum0.001073 mm.
-181 actual current hook inputs independently replayed through source Python:
  maximum0.000902 mm; maximum pin-weight difference7.16e-7; all latches identical.
- Current hook learned pin weights were positive on every captured step: left
  0.788–0.979, right0.931–0.988. These are the original weighted rolling-contact
  constraints, not a guarantee that a foot bone remains at one fixed XYZ point.
- Source foot/toe contact geometry on the current floor did not penetrate at
  policy endpoints. Ground in the attack carrier maps to the scene floorZ=-0.5cm.

## Clamps and the visible feet

**Set Clamp Foot=false AND Set Clamp Calf=false** on the owning
**Prophecy NN Locomotion Manager** for the original unconstrained leg pose.
The existing Blueprint variable Set nodes work during full attacks as well as
locomotion. No new node is needed. Disabling only Clamp Foot leaves Clamp Calf on.

Clamp Calf imposes an authored knee-to-foot length. Training permits that distance
to vary; moving the endpoint to enforce length can move a pinned foot below the
floor. In the actual kinematic hook agent (`BP_ProphecyManualPoseAgent4`), the
measured left-foot contact went **2.35cm below** the floor with that clamp on.

With both off, a40-second kinematic capture showed raw model feet reaching the
published future targets within **0.0002mm**. Actual rendered foot positions were
within1.39mm of the interpolated target; the source foot/toe contact metric on
the rendered mesh reached at worst0.748mm below the floor. This remaining bound
includes presentation/interpolation and is not a claim of zero skin penetration.
The large clamp-induced error is absent. Simulated bodies additionally have their
own contacts and physical-animation tracking error; the exact source comparison
uses kinematic playback, like the saved SlashChain reference.

User Blueprint/map settings were not rewritten. The capture changed only transient
PIE settings. The manager's clamp switches affect all agents it owns.

## Player camera

A transient `UProphecyAttackCameraComponent` is created only on a player-possessed
full attacker. It reads the completed mesh pelvis in PostPhysics before the
ordinary spring-arm tick. Its horizontal translation offset follows the body;
camera height, rotation, arm length, collision test and capsule/NN state retain
their existing behavior. Half attacks use the locomotion camera.

The component remains allocated while owned by that player, ticks only while
following or fading its offset after an attack, and restores its added offset
immediately on loss of possession or teardown.
Unreal owns its lifetime so a pending tick remains valid during a stop/destruction.
The initial manually allocated tick experiment crashed on retirement and was
replaced before final verification.

### Attack-end offset fade (2026-09-21)

**Set Attack Camera Offset Fade Duration** takes Agent and Duration Seconds,
default1. One authored second means60 unpaused game ticks, ignoring frame delta
and time dilation;0 restores immediately. Nonfinite/negative durations are rejected.
The setting may be configured before possession, but only the player-possessed
full-attack follower uses it. NPCs receive no camera follower or fade work.

At attack exit, the handoff samples the possessed player's spring origin before
the attack carrier catch-up and balancing/pelvis root placement, then subtracts
their combined **actual** origin displacement from the existing camera offset.
Thus `new spring origin + new offset = old spring origin + old offset` at the
snap. This compensates actual applied movement rather than the requested target
and avoids counting the intermediate catch-up twice. The combined offset then
eases to zero with smoothstep over the requested tick count. Duration0 retains
the immediate handoff without compensation. Camera baseline settings and any
independent Blueprint TargetOffset are preserved by applying only the change in
this component's offset. A new attack cancels the return and resumes pelvis
tracking from the remaining offset. Updating the duration during a fade retimes
it from its current value;0 stops immediately. Loss of possession and teardown
restore immediately. The finished fade removes its state and disables the
component tick; default duration needs no per-agent settings entry.

This fades the added offset plus inverse handoff displacement; it does not change actor/root movement,
camera rotation, arm collision or full-attack pelvis tracking. Uses the existing
PostPhysics component tick, without another timer or inference. Live component
layout is unchanged; transient return/settings data lives in weak-object maps.

Validation2026-09-21: Live Coding loaded12:45:59UTC; reflected node/default1 checked.
`Prophecy.Camera.AttackOffsetFade` passed12:46:47UTC, including60-tick completion,
paused/duplicate suppression, retiming/zero, possessed-only activation and real
component retirement on unpossession while retaining another camera offset.
Existing pose-agent Blueprint compiled status3 with no stale types or wiring
changes. Reload emitted handled RigVM delegate-access ensures; reload completed
and subsequent checks passed. No gameplay rollout or asset save/restart.

The follow-up root-snap regression test translates the actor twice and changes its
yaw with an off-center spring attachment. It checks continuity of the world-space
camera pivot, exactly-once inverse displacement, the combined fade's initial value,
and a new attack retaining that corrected offset. This is translation/pivot
compensation; camera rotation, arm collision and unrelated Blueprint teleports are
not interpolated by this feature.
The correction loaded through Live Coding12:55:49UTC on2026-09-21; the expanded
`Prophecy.Camera.AttackOffsetFade` test passed12:56:13UTC. Existing Blueprint
duration/node unchanged. No gameplay rollout, explicit asset save or restart.

Validation:40s in the current scene; within-attack horizontal pelvis-to-camera
offset change below3e-14cm. A further20s test switched possession to the other
attacking pawn, unpossessed, repossessed and stopped all attacks.4,804 actor
samples, nonplayer added offset0 after the first completed tick following possession changes,
final restored offset0, at most one follower
component per actor, clean PIE teardown. No camera component is created on an
agent that has never been possessed for an attack. The final normal-build run
recorded a residual offset up to2.531cm in the test callback immediately after
unpossessing, before another game tick ran; it was restored on that next tick.

## Cost and reproducibility

Source-exact CPU Slash model+geometry benchmark,200 measured transitions after20
warmups:1 attacker0.113ms median,4 attackers0.305ms,100 attackers5.017ms
(100-agent p95 5.761ms). This is one30Hz Slash policy step, **not total world or
frame time**. Batch resize/parity checks passed. No rendering or physics included.

Evidence: `Saved/Diagnostics/SlashContacts/` — `ExactChain/ExactSummary.json`,
`LiveSourceReplay.json`, `exact_analysis.json`, `kinematic_analysis.json`,
`Camera.json`, `Benchmark.json`, `BuildFinal.log`. The final camera code is included
in the normal Editor build, rather than depending on Live Coding patches.

Reproduce using Stepper Python and `Saved/RunUnrealRemote.py` for editor scripts:

1. `Tools/NN/PrepareProphecySlashExactPins.py` prepares source60/4 fixtures.
2. `Saved/Diagnostics/SlashContacts/AuditExact.py` audits the immutable chain.
3. `Saved/Diagnostics/FootClamp/SurveyAttacks.py` records the current scene; pass
   `kinematic` for transient unclamped kinematic playback.
4. `Tools/NN/AnalyzeProphecySlashContacts.py <survey> <trace.jsonl>` computes contacts.
5. `Tools/NN/ReplayProphecySlashContacts.py <trace.jsonl>` independently replays inputs.
6. `Saved/Diagnostics/SlashContacts/TestCamera.py` checks possession and cleanup.

The opt-in nonshipping trace uses `Prophecy.SlashTraceAgent` (manager index) and
`Prophecy.SlashTraceFrames` (bounded policy-step budget); both are inactive by
default. It writes `live_steps.jsonl` in the diagnostics folder.
