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
