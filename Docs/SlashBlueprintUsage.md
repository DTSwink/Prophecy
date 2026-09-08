# Slash attacks in Blueprint

All nodes belong to **Prophecy Agent**, including `BP_ProphecyManualPoseAgent`.
The agent must already be registered with its locomotion manager and NN inference enabled.
Nothing needs to be added to Blueprint Tick for a stationary attack target.

## Start an attack

Wire an input/event into **Trigger NN Attack**:

- **Target:** your agent reference (`Self` inside its Blueprint).
- **Attack:** a bone-name-style `Name`, for example `slashL`.
- **Target World Location:** the point to strike, in Unreal world centimetres. Use the opponent's bone/socket position if appropriate, not necessarily its capsule centre.
- **Half Attack:** off for full body; on to retain ordinary leg locomotion.
- **Return Value:** true means it started. False means invalid agent/model/name/target, NN disabled, or a kick requested in half mode.

Names are case-insensitive:

`slashL`, `slashR`, `slashLD`, `slashRD`, `slashLU`, `slashRU`, `pike`,
`jabL`, `jabR`, `hookL`, `hookR`, `overL`, `overR`, `headbutt`, `kickL`, `kickR`.

Example: event → **Trigger NN Attack** (`Self`, `slashL`, opponent's chest world position, `Half Attack = true`).
The NN starts from the agent's previous/current pose; it does not play the saved parity rollout.

## During / after the attack

| Node | Use |
|---|---|
| **Set NN Half Attack Enabled** | True switches to upper-only; false switches back to full body. Can be called mid-attack. History, learned Armed/Hit latches and frame count are retained. Kicks reject true. |
| **Set NN Attack Target** | Change the world target of the current attack. Call when your gameplay target moves; the point is not an automatically tracked actor reference. |
| **Stop NN Attack** | Interrupt and return to locomotion. The last published pose feeds the locomotion continuation; there is no reset to an idle seed. |
| **Get NN Attack State** | Returns whether an attack is active, its family, half/full setting, Armed, Hit and 30 Hz policy-frame index. |

Natural completion uses the learned Hit latch plus the original family-specific tail.
Hit here is a **model timing signal**, not confirmation of a physics collision or damage.
An unreachable target may never produce Hit; gameplay can interrupt with **Stop NN Attack**.
Starting another accepted attack replaces the current one.

Full-body root handoff: the capsule remains fixed during the attack, then catches
up with the pelvis's accumulated **horizontal displacement** on natural completion,
`Stop NN Attack`, or a replacement attack. The move uses the existing capsule sweep;
height stays unchanged. Root facing and its locomotion orientation target become the
horizontal direction from the final published pelvis to the ending attack's latest
world target (coincident XY keeps the old heading). Both pose-history frames are
rebased so the bones stay in the same world positions and rotations, without
injecting the catch-up as linear/angular velocity. Explicit Blueprint facing input
can author the next locomotion target normally; zero facing input retains this heading.
The production kinematic mesh and optional debug mesh are refreshed in the handoff
itself, including when Blueprint calls it after their normal update.

Direct full-body-to-full-body replacements retain the two raw lower/upper NN states
and fixed world anchor, resetting only the family/target, latches and attack counter.
This is the continuous-rollout path; presentation corrections do not enter that raw
attack history. Attacks started after locomotion has resumed start from its current pose.

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
- The attack upper pose is transferred relative to the ghost pelvis onto the real pelvis. Real running translation does not drive the ghost's lower history.
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

- `Tools/NN/ExportProphecySlashNetworks.py`: unchanged float32 neural-only production exports, geometry contract and four-step Python reference.
- `Tools/NN/ExportProphecySlashPolicy.py`: retained full-transition numerical oracle, not the gameplay model.
- `Tools/NN/AuditProphecySlashOnnx.py`: independent ONNX autoregressive comparison to the exact saved rollout.
- `Tools/NN/AuditProphecySlashUnreal.py` through the editor bridge (outside PIE): native world-space parity against four-step Python, plus a separate comparison against the unchanged saved rollout; includes rotations, gates and input-pose codec.
- `Tools/NN/BenchmarkProphecySlashUnreal.py cpu|gpu <count>` (outside PIE): complete attack-step timing, including native maths and GPU transfers. Tests batch counts up to 100; count 1 also tests resizing between counts.
- `Tools/NN/TestProphecySlashBlueprint.py` (PIE): all 16 families, mid-attack switches, kick rejection and actual rendered-bone readback. It does not force an animation evaluation.
- `Tools/NN/TestProphecySlashMoving.py` (PIE): movement, moving half attacks, gaze setters and 60/30/5 FPS readback.
- `Tools/NN/CaptureProphecySlashLive.py`: optional live-pose images using an actor-following test camera. Never saves the map.

Test outputs are under `Saved/SlashParity/`. Gameplay runs three small neural models and native geometry, not the old whole-geometry graph. Only active attackers enter the batch. Both pin passes use four integration steps. No quantization, checkpoint edits or viewer changes.

Measured CPU median: **0.12–0.13 ms for one attack step**, **2.91–3.40 ms total for 100 attackers**. GPU was slower for small batches and did not consistently beat CPU at 100, so CPU remains the default. These costs include attack geometry, but exclude rendering, physics and the existing locomotion update.

Across the reference attack, native C++ differs from four-step Python by at most **0.003153 mm** in world position. The four-step approximation differs from the original saved rollout by about **0.915 mm**; event timing remains identical. These are separate checks.

For the longer 30-attack test and the permanent looping reference in `testNN`, see
[SlashChainReference.md](SlashChainReference.md). The native port stays within
**0.100 mm** of same-four-step Python across that chain, and all 30 Hit frames
match the saved source. However, four-step versus original 60-step pinning can
accumulate to **177.652 mm** and changes one Armed frame; do not generalize the
short reference's sub-millimetre approximation error to long sequences.
