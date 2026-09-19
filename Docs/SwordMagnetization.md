# Independent simulated-sword magnetisation

A held **simulated Jolt sword** now has its own linear/angular velocity servo, in
addition to the fixed hand grip. It inherits the gripping hand's accepted drive
packet (`hand_r` with the default socket): global strength multiplied by the hand's
current per-body scales, enable state, gravity compensation, timing and authored
target trajectory. Profile blends and attack overrides therefore apply through the
same hand settings. Disabling the hand/global magnetisation removes the sword target
on the next normal publication; no stale independent strength is retained.

The target is the **authored hand target**, with the existing socket/grip and captured
sword-body-origin offset applied. It never chases the displaced simulated hand.
The offset is applied after hand-target interpolation on each Jolt substep, so a
rotating hand carries the sword along the rigid arc instead of interpolating a
separate straight chord. The ordinary servo retains COM/origin compensation and
captured velocity caps. Mass, collision geometry, CCD and solver counts are unchanged.

Use **Break Sword Grip Constraint** with **Agent = Self** after equipping/enabling
a simulated Jolt sword. It removes just the fixed grip joint. The sword remains held,
collidable and independently magnetised; owner-hand/attack exclusions are retained.
Return Value is false for no sword, an attached/kinematic sword, non-Jolt ownership
or pending/failed admission. Repeating it on an already broken grip is safe.
Switch sword simulation off then on (or drop and re-equip) to restore the grip.
An explicit backend/hand rebind also recreates it. **Drop Sword** releases the drive
and ownership as usual; this diagnostic node does not drop the sword.

Attached/kinematic swords do not register this drive. Native bindings are sparse
and event-owned, removed on release, mode change, body/hand destruction and world
teardown. The shared servo collects only active hand targets; no new per-agent tick,
NN inference, separate physics listener or constraint recreation per frame is added.

This implements the missing drive; it does not establish that all contact-related
jitter is eliminated. Scene contact quality remains for user testing.

Validation (2026-09-19): Live Coding compiled and loaded without an editor restart.
`Prophecy.Jolt.Sword.IndependentHandMagnetization` and
`Prophecy.Jolt.Sword.AttackCollisionPhases` passed in isolated actual-asset worlds.
The independent test removes the grip, verifies target tracking, global-times-hand
linear and angular strengths, hand/global disable and dropped-sword drive removal.
It uses the normal shared step/publication path. No user Blueprint or map was edited.
