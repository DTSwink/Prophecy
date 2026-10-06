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

## Player camera (current: 2026-10-05)

By default attacks keep the camera on the capsule. Animated pelvis displacement
does not change the camera offset at follow alpha 0. A transient `UProphecyAttackCameraComponent` is created
only for a possessed full attacker (or defense); NPCs receive no camera work.
Defense retains its pelvis-follow behavior.

**Set Attack Camera COM Follow** takes Agent and Alpha (default 0, clamped 0–1).
During a full attack, 0 keeps the capsule camera, 1 follows the horizontal
mass-weighted center of the displayed body, and 0.5 follows half its displacement.
Only XY is added; the camera's vertical behavior is unchanged. The reference is
captured at the first completed attack frame. PHAT body masses and local mass
centers are cached per attack, using captured Jolt masses when active. Missing
physics bodies fall back to the pelvis. Alpha 0 skips COM sampling entirely.

The COM offset is combined with inverse capsule-snap compensation at full-to-half
or attack exit and fades using **Set Attack Camera Offset Fade Duration**. Any
previous fade continues during a new attack alongside that attack's COM offset.
Disabling follow mid-attack fades its existing offset rather than dropping it.
Settings can be assigned before possession, but only the player computes COM.

NPCs keep the inherited camera/spring objects so existing Blueprint references
and authored settings survive. In game those components are unregistered, their
ticks disabled, and their subtree detached from the capsule: no camera/spring
updates or collision sweeps. Possession reattaches/registers the same configured
rig; unpossession immediately removes its follow offset and parks the rig again.
Editor camera templates/previews remain intact. This avoids runtime rig work on
NPCs; it does not eliminate the inherited UObject allocations.

COM validation: `Saved/Diagnostics/CameraCOM20261005/`. Both native camera tests
passed, including mass weighting/local mass centers, late handoff movement,
NPC registration state and possession/re-possession. Three unchanged 350-tick
TestNN runs at alpha 0, 0.5 and 1 had identical root positions; half strength
matched the midpoint within 4e-15 cm and added zero vertical offset. First attack
exit pivot error was zero at all strengths. A separate full-to-half capture at
alpha 1 also had zero handoff pivot error. NPC rigs remained detached/inactive.

At full-to-half or attack-to-locomotion handoff, the existing root handoff samples
the spring origin before carrier catch-up and balancing/pelvis root placement.
The camera subtracts their combined **actual** origin displacement:
`new spring origin + new offset = old spring origin + old offset`.
This includes translation caused by yaw of an off-center spring attachment and
avoids counting intermediate catch-up twice. Compensation is finalized in
PostPhysics, after the agent and manager updates, so later Blueprint/physics
capsule corrections in the handoff frame join the same fade. The snap frame
retains the exact compensated pivot; the fade begins on the next game tick.

**Set Attack Camera Offset Fade Duration** is unchanged: default 1 means 60
unpaused game ticks, independent of frame delta/time dilation. The offset fades
with the existing smoothstep curve. Zero removes it immediately; nonfinite or
negative durations are rejected. Changing duration during a fade retimes from the
current offset. Chained attacks let an existing fade continue; a subsequent root
snap combines its inverse displacement with the remaining offset and starts a
new fade. No animated pelvis offset is introduced by a new attack.

Independent Blueprint TargetOffset edits are preserved: the component adds only
the difference in its own offset. Loss of possession and teardown restore that
offset. Component ticks retire after the fade when no full attack/defense needs
them. The actor/root, NN, camera rotation, arm length and spring collision behavior
are unchanged. This guarantees pivot translation continuity at the handoff; it
does not interpolate camera rotation, collision reactions or unrelated teleports.

The earlier September implementation followed the pelvis during full attacks and
cancelled the fade on a new attack. That behavior is superseded by the capsule
camera above. Historical September captures remain in `Saved/Diagnostics/SlashContacts/`.

Initial capsule-camera validation and reproduction: `Saved/Diagnostics/CapsuleAttackCamera20261005/`;
the native regression is `Prophecy.Camera.AttackOffsetFade` (passed on the final normal DLL).
Two owned TestNN captures (175 and 120 ticks) checked full-to-half, attack-to-locomotion
and chained attacks. The first handoff moved the capsule/spring origin 18.7204 cm
with exactly 0 cm pivot error; attack pelvis movement added 0 cm camera offset.
The fade completed and a full attack remained ready for another snap when the
previous fade expired. The Blueprint compiled with status 3 and no stale native types.

The initial synchronous handoff check missed later same-frame root updates in the
normal Blueprint sequence. With Duration Seconds = 10, the first hookL had a
4.85 cm pivot jump after its synchronous compensation; camera lag spread the
visible displacement over the next few frames. This is covered by the final
PostPhysics compensation above. The node was already using the requested
600-tick fade. Replaying the unchanged Blueprint with the fix reduced the tick-60
rendered-camera jump from 1.212344 cm to 4e-13 cm (pivot: 4.849376 cm to zero).
Root positions matched exactly across all 350 captured ticks. The expanded native
regression passed, including late same-frame motion and the 600-tick duration.
Evidence: `Saved/Diagnostics/CameraHitch20261005/`.

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
