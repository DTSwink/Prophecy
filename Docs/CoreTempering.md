# FK core tempering

**Set Locomotion FK Core Tempering** takes Agent, Enabled (true), and Rotation
(1). One follow value controls all ten FK core bones: spine_01 through spine_05,
neck_01, neck_02, head, clavicle_l and clavicle_r. There are no translation pins.

Each accepted locomotion prediction slerps the joint's previous accepted local
rotation toward its newly predicted local rotation. Rotation0 holds its bend
relative to its parent;1 accepts the prediction unchanged. Intermediate values
follow per NN step, like hand tempering. The pelvis carries the entire chain;
FK retains the authored attachment offsets rather than freezing world positions.

**Blend Locomotion FK Core Tempering to Normal** takes Hold Duration Seconds
(0) and Blend Duration Seconds (1). It holds the current follow value, then
smoothsteps it back to1. One authored second always means60 unpaused game ticks,
independent of FPS or agent time dilatation. Zero blend snaps after its hold.
Repeating Set cancels a return; repeating Blend starts from the current value.

Configure Set during initialization. Each attack end restores that configured
value before On Attack Ended, so the event can start Blend To Normal. All specials
(full/half attack, active parry/dodge) bypass core tempering, just like hand
tempering. A pending unarmed defense still permits ordinary locomotion. Reset
captures configured/current values and restores them while canceling active blends.

The implementation edits the existing ten parent-local rot6 channels in accepted
upper NN state before publication and recurrence. Arms are carried from the raw
candidate clavicles to the adjusted clavicles, preserving their relative pose.
This is needed because the hybrid NN stores arm endpoints in heading space,
rather than as FK descendants. Hand recovery source mixing runs first; core
tempering follows, then spine_05-local hand tempering/reconstruction, then optional
hand inertia. Thus hand tempering references the adjusted torso. Physical targets
and the next NN input use the same corrected pose.

Default/disabled/finished values bypass core interpolation, pose decoding and arm
transport. Only active core tempering adds this work; there is no extra NN
inference, actor tick or persistent timer. Return timing uses the existing blend
clock and retires on completion. Storage is separate from retained agent/runtime
layouts, and the nodes are in their own Blueprint library.

Live Coding patch7 loaded2026-09-23 10:43:54UTC; build succeeded393.11s.
Both nodes reflected and called; pose Blueprint compiled status3 with zero stale
native types/pins and wiring preserved. Six tests passed10:45:10UTC: two
CoreTempering tests plus all four HandRecovery regressions. Coverage includes all
ten channels, shortest-arc interpolation across the quaternion seam, exact0/1
endpoints, unchanged FK offsets, clavicle-local arm transport and accepted-state
encoding, holds/returns at30/60/120FPS, reset and completion retirement.

Owned360-frame PIE captures exercised three agents, existing hand controls and
repeated attacks: `Saved/Diagnostics/CoreTempering-20260923-124531.json` (zero
core follow) and `CoreBaseline-20260923-124823.json` (disabled). In established
locomotion, maximum held local rotation step was0.000039degrees and attachment
offset change0.000020cm, with pelvis steps up to3.93degrees. PHAT readback exposes
nine core bodies; the missing neck_02 is included in the head-to-neck_01 aggregate,
while the native test covers all ten independently.

The first retained attack endpoint can have different intermediate spine offsets
from locomotion FK. The spine_02 offset changes0.52033cm at the first new
locomotion publication in BOTH enabled and disabled captures; this pre-existing
translation handoff is outside the rotation-only control. Analysis reports those
handoff frames separately instead of treating them as established locomotion.
Baseline head-to-neck_01 position also changes normally as neck_02 rotates.
See matching `.validation.json` files for measured bounds. Both owned PIE sessions
ended, with no scene/graph edits, asset saves or restart. Include the live patch in
the next authorized normal editor build before reopening.
