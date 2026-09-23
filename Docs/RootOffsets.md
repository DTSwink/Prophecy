# Root-only offsets

With [per-agent time dilation](AgentTimeDilation.md), root offsets remain immediate spatial changes. Velocity setters/magic values use agent-local seconds; velocity readbacks and window timestamps use world seconds. At multiplier2, a local100cm/s command produces200cm/s world motion.

`Add Root Offset` takes an Agent and a world-space vector in centimetres. It translates the actual root low point and the complete root-window history/prediction by that amount while preserving the skeleton's current world pose. It uses the existing pose-preserving root rebase used by root bounds.

`Add Root Angle Offset` takes an Agent and Yaw Degrees in Unreal's convention. It adds that yaw to every window orientation and the mover's facing target, while preserving window world positions and world-space linear/angular velocity. This is a yaw-only upright locomotion root. A later explicit facing input can choose another target.

These are one-shot, unswept changes of the root's coordinate frame. Both recurrent NN frames, publication histories and cached poses are accounted for; they do not rotate the current character pose or reset the policy. Normal locomotion, balancing, bounds and collision handling continue afterward, so a later frame can move the root again. They do not change world targets such as attack targets, foot pins or the magic cube, or teleport Jolt bodies.

Available after root-window initialization with inference enabled, including half attacks and active defense. Return false during full attacks or external simulation-bridge control. Invalid inputs are rejected; zero is a no-op. No added tick, timer, retained state or inference work when unused.

The older `Set Locomotion Root Window Location` keeps its original semantics: it translates the NN world pose along with the root. Use the new offset node for the root-only operation.

Validation script: `Saved/Diagnostics/TestRootOffsets.py` (owned PIE only). It checks raw/continuous windows, target and displayed bones, momentum, repeated offsets and invalid inputs; no scene asset changes.

Passed2026-09-21:18 operations across kinematic and physical modes with magic linear/angular velocity. Maximum window position error0.000008cm and yaw error0.000013degrees; immediate bone-position and velocity error0. Six subsequent frames remained finite. Active defense/half-attack rebasing is implemented but not covered by this scene check. Loaded through Live Coding; include in the next approved normal editor build before restarting.

Live Coding archived existing library self defaults during reload. The event-only editor command `Prophecy.Editor.RepairLibraryDefaults` restores those unlinked defaults to their canonical library CDOs, checks other values/connections and compiles without saving. This session repaired86 references; final Blueprint status3, all other values/wiring preserved.

## Velocity setters

`Set Root Velocity` assigns the mover's world XY velocity in cm/s. `Set Root Ang Velocity` assigns its world Z angular velocity in degrees/s. Both offer `Add to Current` (default false) and leave the other channel and both magic sets unchanged. The upright planar mover ignores linear Z and angular X/Y; use the existing magic velocity nodes for independent XYZ translation.

These set current momentum without moving the root or changing the current pose. Subsequent policy updates rebuild the window using normal smoothing, steering, balancing, damping and speed limits. They are not persistent overrides. Angular assignment also updates the stopping/facing target; setting it to zero cancels mover rotation at its current heading. Adding zero is a no-op. Existing yaw safety cap (less than180degrees per policy step) remains.

They return false before initialization, while inference is disabled, during a full attack or external bridge control. No new retained state or tick work. `Get Root Velocity` still reports the combined applied mover-plus-magic velocity; its angular output remains radians/s, unlike the new degrees/s setter. Setting mover velocity to zero does not clear magic velocity.

Focused validation: `Saved/Diagnostics/TestRootVelocitySetters.py` checks overwrite/add, channel isolation, preserved magic values, zero stopping, high yaw rate capping and unchanged pose/root during assignment in an owned PIE session.

Passed2026-09-21 17:45UTC after Live Coding patch15. Both reflected setters loaded and pose-agent Blueprint compiled successfully. The runtime check included both magic channels and six follow-up frames. No scene/Blueprint wiring changes or asset saves; only the diagnostic PIE ended.
