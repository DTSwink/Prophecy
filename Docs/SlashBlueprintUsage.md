# Slash attacks in Blueprint

All nodes belong to **Prophecy Agent**, including `BP_ProphecyManualPoseAgent`.

**September24 checkpoint update:** step174664 omits the frozen Walk attack stage;
its learned pin pass uses training's four iterations. **Set Attack Foot Pinning
Iterations** controls the legacy frozen stage and has no effect on this new
checkpoint. Its phase rule requires actual Armed before a later Hit. See
[checkpoint contract and validation](AttackCheckpoint174664.md). Its learned pin strength saturates at0.99 as serialized by training.
Headbutts use checkpoint-authored arms throughout. The former GT preparation override was removed2026-09-24; old serialized preparation settings have no effect. See [AttackPinningAndHeadbutt.md](AttackPinningAndHeadbutt.md).
The agent must already be registered with its locomotion manager and NN inference enabled.
Nothing needs to be added to Blueprint Tick for a stationary attack target.

## Start an attack

Wire an input/event into **Trigger NN Attack**:

- **Target:** your agent reference (`Self` inside its Blueprint).
- **Attack:** a bone-name-style `Name`, for example `slashL`.
- **Target World Location:** the point to strike, in Unreal world centimetres. Use the opponent's bone/socket position if appropriate, not necessarily its capsule centre.
- **Half Attack:** off for full body; on to retain ordinary leg locomotion.
- **Return Value:** true means it started or updated the active attack. False means invalid agent/model/name/target, NN disabled, or a kick requested in half mode.

Names are case-insensitive:

`slashL`, `slashR`, `slashLD`, `slashRD`, `slashLU`, `slashRU`, `pike`,
`jabL`, `jabR`, `hookL`, `hookR`, `overL`, `overR`, `headbutt`, `kickL`, `kickR`.

Example: event → **Trigger NN Attack** (`Self`, `slashL`, opponent's chest world position, `Half Attack = true`).
Full attacks start from the agent's previous/current pose. Fresh half attacks use the original GT Armed/Armed-1 lower body and current upper pose; neither plays the saved parity rollout. See [HalfAttackGTInitialization.md](HalfAttackGTInitialization.md).

## During / after the attack

| Node | Use |
|---|---|
| **Set NN Half Attack Enabled** | True switches to upper-only; false switches back to full body. Can be called mid-attack. History, learned Armed/Hit latches and frame count are retained. Kicks reject true. |
| **Set NN Attack Target** | Change the world target of the current attack. Call when your gameplay target moves; the point is not an automatically tracked actor reference. |
| **Stop NN Attack** | Interrupt and return to locomotion. The last published pose feeds the locomotion continuation; there is no reset to an idle seed. |
| **Get NN Attack State** | Returns whether an attack is active, its family, half/full setting, Armed, Hit and 30 Hz policy-frame index. |

Natural completion uses the learned Hit latch plus the family-specific tail, shortened
by **Set Trim Attack** when configured.
Hit here is a **model timing signal**, not confirmation of a physics collision or damage.
An unreachable target may never produce Hit; gameplay can interrupt with **Stop NN Attack**.
Calling **Trigger NN Attack** while already attacking updates the target, attack family,
victim and half/full selection in place. It preserves Armed, Hit, policy frame,
first-Hit frame, recurrent history and ongoing progress. No Attack Ended event,
root handoff, reseeding, static-initialization repeat or end/start physics cycle occurs.
Use **Stop NN Attack → Trigger NN Attack** for a fresh attack with cleared latches.
Changing type updates its labels, tail length, fist settings and weapon/kick rules;
the first-Hit frame stays unchanged, so this does not restart the recovery countdown.

### Trim the ending

**Set Trim Attack** has one integer input for each of the 16 attack names above.
All default to **0**. One unit removes one **60 Hz frame (1/60 second)** from
that family's post-Hit tail, for both full and half attacks. The trim saturates at
the learned Hit: it cannot end before that unpredictable model signal. Negative
inputs reject the entire call. It does not change Armed/Hit timing or play speed.

Settings belong to the agent and persist across its attack/reset cycles. Call once
when configuring it; all zeros clear its trim configuration. A call during an
attack updates its cached tail without resetting the attack; if its shortened
ending has already passed, the existing completion check ends it next time it runs.
Family changes use the new family's trim. Normal Attack Ended and recovery run.

The NN remains at30Hz. Even values shorten its cached tail by whole NN frames;
odd values finish on the intervening unpaused game tick instead of rounding.
The existing completion check admits the final policy interval and schedules a
one-shot handoff only for an odd trim. Its callback removes itself immediately;
stop, retarget, setting changes and world teardown cancel stale handoffs. There
is no persistent timer/tick, additional NN inference or locomotion polling.
The last half-frame means one unpaused game tick (assuming60FPS), following the
project's tick convention, not a separate wall-clock timer.

Validated2026-09-22 in owned PIE: target updates each tick did not prevent natural
completion; slashRU→hookL retained Armed/frame10, slashRU→pike retained Armed+Hit/frame13.
Immediate root and published pose were unchanged, rejected requests preserved state,
and Stop/fresh start plus half/full changes passed. See
`Saved/Diagnostics/AttackRetargetPIE.json`. Sword weapon/melee retarget gating passed
`Prophecy.Jolt.Sword.AttackCollisionPhases`, including unchanged native body/joint counts.
Normal editor build passed285.45s after recovering a Live Coding reinstancing crash;
testNN reopened and pose Blueprint compiled successfully. No scene/Blueprint rewiring.

Full-body root handoff: the capsule remains fixed during the attack, then catches
up with the pelvis's accumulated **horizontal displacement** on natural completion,
or `Stop NN Attack`. The move uses the existing capsule sweep;
height stays unchanged. Root facing and its locomotion orientation target become the
horizontal direction from the final published pelvis to the ending attack's latest
world target (coincident XY keeps the old heading). Both pose-history frames are
rebased so the bones stay in the same world positions and rotations, without
injecting the catch-up as linear/angular velocity. Explicit Blueprint facing input
can author the next locomotion target normally; zero facing input retains this heading.
The production kinematic mesh and optional debug mesh are refreshed in the handoff
itself, including when Blueprint calls it after their normal update.

Active full-body updates retain the two raw lower/upper NN states and fixed world
anchor without resetting latches or the attack counter. Presentation corrections do
not enter that raw attack history. Attacks started after locomotion has resumed
start from its current pose.

Live attacks use the same final forearm correction as the saved preview: `hand_l`
and `hand_r` keep their skeleton-rest translations relative to the corresponding
lower arm. Hand rotations stay unchanged. The data targets, debug display and
kinematic renderer also enforce this after between-frame interpolation. This pass
affects attack presentation, not the neural weights or raw attack recurrence.
Attack publications also bypass the legacy locomotion calf-extension renderer, so
their authored calf transforms stay at unit scale instead of inflating all three axes.

An early Hit request while unarmed first arms the attack; Hit can latch only on
the following or a later step. This matches the source model's latch sequencing.

## What half mode does

- The real pelvis and legs remain owned by the existing locomotion NN/mover.
- The target is clamped inside a 125 cm sphere around the real lower-policy pelvis,
  then transferred into the existing ghost pelvis frame. Near targets stay unchanged.
  `Set/Get Global Half Attack Target Radius` controls this shared world value in cm;
  `Get NN Attack Target` exposes requested/effective/ghost targets. Full attacks are unaffected.
- A separate **data-only** lower/upper attack history performs Slash in its fixed attack-root frame. There is no additional ghost SkeletalMeshComponent.
- Fresh half attacks seed lower history from original GT Armed/Armed-1. The upper pose uses a fixed mounting orientation and follows real pelvis translation only; real pelvis rotation, running history and root turning do not drive the attack. Targets use the inverse of that same mounting transform.
- Switching back to full body rejoins at the current locomotion carrier instead of moving the actor back to the attack's starting location. It does not restart or phase-match the attack.
- Full body suppresses locomotion stick amplitude through the existing mover. It does not replace the capsule mover or bypass collision.

Radius updates do not reseed either policy or force the Hit latch. See
[AgentHitResponseBlueprint.md](AgentHitResponseBlueprint.md) for pins, units and examples.

The attack's native recurrent history is currently self-fed. Existing physical feedback still operates on locomotion state; it is **not** fed into the Slash ghost. Attack output uses the ordinary shared pose store, so the existing physical follower and optional debug visualization receive it without a second production skeleton.
An active Slash attack owns its selected bones after the existing animation-layer pass; combining competing animation layers on those same bones is not a separate blending feature.

## Locomotion gaze

Use **Set Upper NN Gaze** on the agent:

- **Gaze Yaw Normalized:** `-1..1`, mapping to `-170..170°`.
- **Gaze Pitch Normalized:** `-1..1`, mapping to `-85..85°`.
- `0, 0` is neutral. The exposed class variables store these values; the next locomotion upper-NN step consumes them.

For example, `Yaw = 0.25`, `Pitch = -0.2` requests `42.5°`, `-17°`.
These are locomotion-upper inputs, not additional gaze controls for the trained Slash policy.

## Retained verification

- `Tools/NN/ExportProphecySlashNetworks.py`: unchanged float32 neural-only production exports, geometry contract and source-exact pinning configuration.
- `Tools/NN/ExportProphecySlashPolicy.py`: retained full-transition numerical oracle, not the gameplay model.
- `Tools/NN/AuditProphecySlashOnnx.py`: independent ONNX autoregressive comparison to the exact saved rollout.
- `Tools/NN/AuditProphecySlashUnreal.py` through the editor bridge (outside PIE): legacy audit fixture support; use the source-exact chain checks in SlashFootContactsAndCamera.md for current acceptance.
- `Tools/NN/BenchmarkProphecySlashUnreal.py cpu|gpu <count>` (outside PIE): complete attack-step timing, including native maths and GPU transfers. Tests batch counts up to 100; count 1 also tests resizing between counts.
- `Tools/NN/TestProphecySlashBlueprint.py` (PIE): all 16 families, mid-attack switches, kick rejection and actual rendered-bone readback. It does not force an animation evaluation.
- `Tools/NN/TestProphecySlashMoving.py` (PIE): movement, moving half attacks, gaze setters and 60/30/5 FPS readback.
- `Tools/NN/CaptureProphecySlashLive.py`: optional live-pose images using an actor-following test camera. Never saves the map.

Current source-exact verification and costs are documented in
[SlashFootContactsAndCamera.md](SlashFootContactsAndCamera.md) and
[SlashChainReference.md](SlashChainReference.md). Frozen Walk pinning now uses
60 integration steps and learned Slash pinning uses 4, matching training.
The older four-step audit fixtures under `Saved/SlashParity/` are historical
approximations, not the production source-parity acceptance test.

The immutable 453-transition chain agrees with original Python to **0.034761 mm**
maximum joint-position error with identical Armed/Hit latches. Measured source-exact
CPU policy+geometry cost for 100 attackers is **5.017 ms median per 30 Hz step**;
this excludes physics, rendering and ordinary locomotion work.

For the original unconstrained legs during attacks, set both **Clamp Foot = false**
and **Clamp Calf = false** on the owning manager. Calf-length clamping runs after
pinning and can move a planted foot below the floor. Existing Blueprint setters
work during attacks as well as locomotion.

A possessed player's spring arm now follows horizontal full-attack pelvis travel.
NPCs do not receive a follower unless possessed; half attacks retain the ordinary
locomotion camera. Camera height/rotation/length retain their existing behavior.
