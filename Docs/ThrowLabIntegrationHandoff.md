# Throw integration handoff

**November 1 update:** use the [final unaimed bakes and short handoff](../Exports/Throws/FinalNoAim/HANDOFF.md)
when integrating completed100% motion. The evaluator below is for procedural
charge variants; do not reapply its pose edits to the baked animation.

October 30, 2026. For an agent integrating the approved throws into another lab.
Read [ProjectJournal](../ProjectJournal.md) first; preserve live lab settings,
Blueprint wiring and active Play. Keep work lightweight and in the background.

## Source of truth

- Approved lab checkpoint: `a193d263` (pushed). Exact presets and scene library:
  `Labs/ThrowLab/approved/2026-10-29/saved-profile.json`, with hash manifest beside it.
- Clips: **`big-throw`** and **`small-throw`**, in `Labs/ThrowLab/data/clips.json`.
  Do not use the deleted “big throw 2”. Current Big uses Imperial Spear; Small uses Bomb.
- Geometry, binds, colliders and masses: `Labs/ThrowLab/data/objects.json`.
  Reuse these caches and per-clip grip/scale settings. The bomb cache already
  includes its UE component scale; do not scale it up again.
- Mirror nonphysical settings from the approved preset: timing, rotations,
  grip, scale, Half/Aim, slowdown and body shaping. Expose throw controls and
  physical launch adjustments, rather than a second set of animation tuning.

## Reuse the existing evaluator

[Tools/Throws/lab-reference.mjs](../Tools/Throws/lab-reference.mjs) composes the
actual lab algorithms without a viewer/server. This is a **Node reference**
(filesystem imports), not a browser entry point:

```js
import { openReference, model } from './Tools/Throws/lab-reference.mjs';
const sim = await openReference();
try {
  const m = model(sim, 'small-throw', 0.37); // charge fraction 0..1; Big uses 1
  const pose = m.sample(20);               // authored frame, including fractions
  const releaseFrame = m.releaseFrame;    // actual partial-charge release
  const launch = m.launch;                // p, q, v, omega, axis, twist
} finally { sim.dispose(); }
```

Keep one simulator; rebuild the model when charge, target or preset changes,
then sample it for playback. `launch.v` already includes preset amplitude and
charge scaling; `omega` already contains axial twist. Do not apply either twice.
`m.release` is the original full-throw marker, not the shortened release marker.

For a browser lab, reuse `recovery.js`, `core.js`, `vanilla.js`, `attack.js` and
the composition above; use `app.js` as the live integration reference, not as an
importable engine. Bones use `data.names`/`data.parents`; never assume another
lab has the same indices. Poses contain world `points` and quaternion `q` arrays.

## Motion and physics contract

- Lab coordinates are Y-up, meters; quaternions are `[x,y,z,w]`. Linear velocity
  is m/s, angular velocity rad/s. Authored frames use a 60-frame clock; low-level
  clip/projectile sampling takes seconds (`frame / 60`). Native gameplay advances
  one authored frame per unpaused game tick, independently of FPS/time dilation.
- Hand/forearm edits are integer-frame keys, interpolated during playback;
  release may be fractional. Interpolate parent-local rotations then FK.
- Small charge plays the original prefix at normal speed until trigger release.
  Partial throws retain the nearly straight arm arc, quadratic body attenuation,
  clavicle recovery and finite velocity carry at transitions. Preserve these
  existing functions: do not add a generic smoother or hold at the armed pose.
- Target stays fixed in world space. Aim aligns the spear with it at release;
  there is no target homing during flight. Current saved Big aims; Small does not.
- `projectile.js` owns a standalone Jolt world, floor and target, with fixed 120 Hz
  stepping and cached seeking. If the receiving lab already owns physics,
  integrate the launch, shapes and `aerodynamics.js` forces into that world.
  Match render/collider scale, enable gyroscopic rotation and preserve axial spin.
  Do not accidentally create a second collision world or step physics while paused.

## Unreal bridge and remaining work

Native commit `af387e06` adds **Begin Lab Throw → Release Lab Throw**, immediate
**Play Lab Throw**, **Cancel**, and **Get State**. Async pins report Released,
Completed, Cancelled and Failed. Physical inputs add velocity multiplier/world
rotation and optional twist; other settings come from `Content/ThrowLab/Profile.json`.
See [ThrowControls](ThrowControls.md) for node signatures and deliberate re-export.

UE positions/linear velocities: lab `(x,y,z)` → `(x,z,y) * 100`; angular velocity:
`(-wx,-wz,-wy)`. For orientation, first `q = Rx(+90°) * labQ`, then
`UEQ = (-q.x,q.y,-q.z,q.w)`; apply the agent mesh component transform afterward.
Weapon transforms refer to the **lab geometry frame**: reconcile raw mesh
pivots/binds, especially Bomb, before attaching an Unreal component.

The native pose/control pass builds and passes four tests covering 1,392 poses.
**Native projectile attachment, Jolt release/flight, aerodynamics and actual Play
validation remain unfinished.** Consume the exact fractional release transform,
velocity and remaining tick fraction when connecting physics. Lab flight exists;
native pose parity alone does not validate the complete gameplay throw.
