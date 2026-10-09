# Visualize Defense Input Ghost

Call **Visualize Defense Input Ghost** on the **defending agent** each Tick. It
works for both Parry and Dodge, including defense against half attacks.

- **Enabled**, default true: false returns immediately.
- **World Offset**, default `(150, 0, 0)` cm: shifts the entire drawing together;
  use zero to overlay the real actors.
- **Show Previous**, default true: draw both causal samples and motion arrows.
- Advanced **Duration**, default0 seconds, and **Thickness**, default1.
- Return value: true when a completed active defense input was drawn. False
  while waiting to start, before the first completed prediction, after defense
  ends, for invalid agents, when disabled, and in Shipping.

The defender's complete accepted NN pose is green, with the same body shapes
as the attack ghost and skeleton links as a fallback. This includes the upper
body and both legs: Parry uses its accepted locomotion lower body; Dodge uses
its predicted lower body. It is the saved completed defense pose, not the live
physical mesh or a pose remounted onto a newer capsule.

Current attacker pelvis is cyan; current attack collider is yellow. Previous pelvis is
blue; previous collider is orange. Pelvis is a point and orientation axes, not
an invented collider. The box is the one collider encoded for this attack
(`blade`, `lowerarm_l/r`, `calf_l/r`, or `head`). Its label identifies Parry/Dodge,
the collider and the accepted attacker frame. The full attacking skeleton is
omitted; the green full-body ghost is the **defender**, not the attacker.

The two samples are NN policy samples, not consecutive render frames. They come
from the retained `FContext` used by the latest completed defense step, **after**
the optional half-attack pelvis/root horizontal-velocity removal. The original
unfiltered contact box (`NextAttack`) and the attacker's newly sampled bones are
not used. Current and previous points therefore show the motion the defender
actually receives, including modified previous positions.

Collider half-extents come from the training attack geometry already selected
for that defense. The first two supplied axes and their cross product generate
the eight box corners directly; no UE quaternion roundtrip, live sword mesh bounds
or physics PHAT substitution changes the input geometry. Training metres/Y-up
convert once to Unreal cm/Z-up. Dodge's retained local world origin is added once;
Parry's samples are already global. The same conversion and World Offset apply
to every defender bone, attacker pelvis and attack collider. The drawing does not track the defender root after the sample was
taken.

This is an on-demand reader/drawer. No model call, extra pose sampling, debug
cache, timer, delegate, persistent allocation or per-agent background update was
added. Unused nodes perform no work. Debug line/text submission occurs only when
the node is called and a valid completed defense is active.

Focused geometry/filter checks: `Prophecy.NN.Defense.InputGhost` verifies world
origin and offsets, trained box extents/orientation, current/previous filtering,
relative collider motion and that the input context remains unchanged.

## Verification — October 8

Normal Development Editor build succeeded273.72s with automatic all-core/memory
sizing (one worker available at scheduling). All three focused tests passed:
InputGhost, Defense.CombatMath and HalfAttack.ReachSharedTarget. TestNN reopened
with the node reflected, BP status3/native_properties0/pin_types0 and graph
unchanged. Saved the preexisting dirty user BP before closing; no gameplay edits.

Two disposable current-scene replays to absolute220 exercised Parry and Dodge
against the half slashL. The node draws only after a completed defense prediction,
returns false when disabled/inactive, and every call leaves all future/presented
pose values exactly unchanged. Initial harness assertion compared Python wrapper
addresses; replaced with explicit numeric transform comparisons, then both runs
completed. Temporary defense requests were confined to PIE, which was ended.
Receipts: `Saved/Diagnostics/DefenseInputGhost20261008/`.

## Full defender ghost follow-up

The existing node now also draws the full defender in green. It converts all25
bones of the saved `CurrentPose`, using `D.Bones` to map the checkpoint skeleton
to the manager hierarchy and PHAT body names. Dodge restores `WorldOrigin` once
on both body and incoming inputs; Parry is already world-space. Bone rotations
use the same training-to-UE axis convention as the defense pose boundary. Body
shapes reuse the attack ghost's drawing helper; links also cover bones with no
PHAT body. No capsule remount, physical sampling or added inference is used.
`Show Previous` continues to control only the incoming attack samples.

Three native checks pass: FullGhostPose (125 checks covering all upper/lower
bones), InputGhost, and the existing GhostSwordDrawing regression test. Parry
and Dodge live captures both complete through absolute220, with numeric future
and presented poses unchanged by drawing. Screenshots at195 visually confirm
head, torso, both arms and legs alongside the yellow/orange attack boxes. The
probe used offset(-80,0,0) and brief screenshot persistence to keep the drawing
in camera; node defaults and authored Blueprint settings were not changed.
Blueprint graph remained identical. Loaded through Live Coding with no object
changes, no restart; normal DLL rebuild required before a future cold launch.
Receipts: `Saved/Diagnostics/DefenseFullGhost20261008/`.
