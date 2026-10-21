# Hit impact speed

`Get Hit Impact Speed` is a pure Blueprint node. Call it directly inside a Jolt
Hit event with `Hit Receiver = Self` (or the receiving component). It reads the
current hit automatically: no Hit input is needed, even if your event exposes
split fields. Store the outputs before any Delay or other latent operation.

- `Valid`: the matching native incoming sample is available.
- `Impact Speed`: nonnegative incoming closing speed in **cm/s**, along the contact
  normal, measured before the contact solver responds. Both recipients get the
  same value. Use this as a consistent speed-based input to damage or hit reactions.
- `Relative Velocity` (advanced): receiving body's point velocity minus the other
  body's point velocity, in world space, cm/s. Includes both angular velocities.
  It includes tangential sliding: do not use its magnitude as impact strength.

The measurement accounts for the victim moving towards or away from the blow and
for rotation of the striking limb or sword. Sliding sideways does not count as
closing speed. This is not energy or force: mass, weapon and body-part scaling
remain gameplay choices. Gravity/drives can generate small incoming speeds on
repeated resting/pushing contacts; use a threshold and attack counter if a reaction
should happen only once per attack.

Native pre-solve contact callbacks collect samples only for pairs requesting Hit
events. The existing solved-impulse callback carries the sample into the synchronous
Hit dispatch. Multiple contact points/substeps report the maximum closing speed,
not a sum. No new sweep, per-bone tick scan or NN inference is added; sampling,
contact-cache lookup and synchronization are additional contact-time work.

Outside the matching event, for Chaos events, or without an incoming sample, the
node returns false and zero outputs. It intentionally does not fall back to reading
already-solved velocities or returning an old hit. Collision behavior and the
existing `Normal Impulse` output are unchanged.

## Sword pre-impact state

**October20 correction — contact-only backward extrapolation:** user explicitly
rejected per-sword previous-tick storage. `Get Hit Pre Impact State` now estimates
the five values one full physics tick before the native incoming contact sample.
The proposed previous-tick map and both capture passes have been removed.
No per-body sampling or history runs between hits. Use the node
inside the sword's Hit event with `Hit Receiver = Self` (or the receiving sword
component), before latent actions. Check `Valid` before using its outputs.

- `Velocity`: estimated world cm/s at the rewound sword-component origin.
- `Tip Velocity`: world cm/s at the rewound tip, including angular motion.
- `Angular Velocity Rad`: incoming world radians/s, held constant for the rewind.
- `Location` and `Rotation`: estimated earlier sword-component world pose.

`Tip Distance` is the distance in centimetres along the component's local +Z.
Use the actual component-origin-to-tip distance from the sword's graph. The user's
current input is `Blade Length + Hilt Half Length`; do not replace it with the
older double-hilt recommendation. The graph already uses world-sized lengths;
component scale is not applied again. Tip velocity is calculated on demand as
origin velocity plus angular velocity crossed with the rotated tip offset.

The world publishes one scalar lookback interval, its current `Step` duration.
At contact, constant incoming COM velocity rewinds the COM; inverse world angular
rotation rewinds both orientation and the component's offset about that COM.
This also handles welded sword offsets. Origin/tip velocities are reconstructed
with the rewound lever arms. The same full-step interval applies with collision
substeps; it is not divided by the substep count. This is deliberately **not an
exact previous-tick-boundary sample**: Jolt's speculative/CCD callbacks can sample
different phases, and earlier forces, constraints and collisions are not undone.
It also extrapolates on the first hit without a warm-up tick.

Contact capture uses immutable native component/body offsets, including welded
source-to-carrier transforms. Solver workers do not read UObjects or take extra
body locks. Capture only adds data for Hit-enabled primitive bodies.
Independent, kinematic and welded swords are supported; skeletal-body and ISM
contacts return invalid rather than mislabelling a bone/instance pose as the
component pose. Outside the matching event, invalid tip input, or missing sample:
false and all five outputs cleared. Multiple contacts use the fastest closing
sample, consistently with `Get Hit Impact Speed`.

This addition does not remove or rewire the existing sword bookkeeping. Native
contact-record and body-slot layouts changed, requiring a normal build/restart.

Rewind normal build passed (8 incremental actions,124.62s). The focused native
`SolvedImpulseAndLifetime` test passed11:17:24UTC with zero test errors/warnings:
first-hit rewind without history, translation, world rotation, moving receivers,
kinematic bodies, welded COM lever arms in both body orders, CCD over substeps,
new velocity/spin after a preceding slow tick, and event scope validation.
Editor9572 reopened normally on explosionVFX. Saved Sword SHA verified unchanged
(`5b33859a1260c202053b5fec67bf65fb0a15fa592f388be523a6f6598eb9385a`).
The owned diagnostic Play's first existing sword depth print was **1.054566**
(earlier recorded contact-time result0.911003); incoming Z velocity-732.189798cm/s,
zero angular velocity, rewound origin Z104.137519cm. The node ran through the
user's existing update-current-values wiring; no asset edits or depth clamp.
Ended owned Play. This verifies the reported setup, not a universal depth>=1 rule.
Evidence is kept under
`Saved/Diagnostics/SwordRewind20261020`; the previous necessary shutdown preserved
the user's dirty Sword under `Saved/Diagnostics/SwordPreviousTick20261020`.
`GetHitPreImpactState` retains its reflected function identity and all pins.
`Get Hit Impact Speed` remains actual incoming contact motion, without rewind.
Do not clamp the sword's depth to 1: the contact position can lie behind the tip;
the user's reported depth needs a live comparison rather than a guaranteed result.

Original contact-time implementation validation (before this correction):
normal build11 actions/222.34s; first test exposed a missing
motion-payload swap when the hit queue sorts body pairs. Corrected incremental
build4 actions/16.19s and the same native `SolvedImpulseAndLifetime` test passed
05:18:44UTC with zero errors/warnings. Covers pre-response pose/velocities,
rotational tip speed, moving receivers, kinematic motion, welded swords in both
body orders, CCD, wrong/outside-event receivers, and invalid input. Unreal16632
reopened on explosionVFX; reflected node available and saved asset hashes unchanged.
Evidence: `Saved/Diagnostics/PreHitSword20261020/receipt.json`.

October20 first-collision follow-up: the live Sword graph calls `update current
values` synchronously from ReceiveHit, so placement was correct. The 08:49:20
log explicitly rejects `A_Sword_C_1.sword` from Jolt admission because MACD is
enabled. Its subsequent Chaos Hit has no Jolt sample, so this node returns
invalid/zeros. Changed only placed `A_Sword1.sword` in explosionVFX from
MACD=true/CCD=false to MACD=false/CCD=true. Verified the reconstructed component,
with notify/simulate unchanged. Map is dirty/unsaved; no Play, build or restart
performed. Blueprint defaults and child sword still have MACD enabled; this is
a placed-test-sword correction, not a class-wide change. `Valid` is currently
unconnected in the user's update function. Evidence:
`Saved/Diagnostics/PreHitSwordFollowup20261020/receipt.json`.
