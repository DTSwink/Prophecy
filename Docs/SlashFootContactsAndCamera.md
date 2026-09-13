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
following, and restores its added offset after attacks or loss of possession.
Unreal owns its lifetime so a pending tick remains valid during a stop/destruction.
The initial manually allocated tick experiment crashed on retirement and was
replaced before final verification.

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
