# Joint damping snapshots and angular-limit restoration

`Save Physical Profile Snapshot` includes inbound PHAT joint angular damping,
alongside magnetization and feedback tolerance. Each bone retains all four
walk/run and drawn/sheathed profile values. Saving during an attack captures the
underlying locomotion settings, not the temporary zero damping. Existing saved
snapshots made before damping support must be saved again to include damping.

Damping nodes:

- `Set Jolt Joint Locomotion Damping Below` (four values plus Parent Bone/Include Parent)
- `Blend Jolt Joint Angular Damping`
- `Blend Jolt Joint Angular Damping Below`
- `Blend Jolt All Joints Angular Damping`
- `Blend Joint Angular Damping To Snapshot`
- `Blend Joint Angular Damping Below To Snapshot`
- `Blend All Joint Angular Damping To Snapshot`
- `Get Jolt Joint Angular Damping`

The ordinary blends accept Walk/Run/Both and Drawn/Sheathed/Both selectors,
defaulting to Both. Snapshot returns restore all four saved profiles. Timelines
use smoothstep and the shared60-game-tick duration convention; zero duration is
immediate. Replacement starts from the current blend value. Full and half attacks
use zero added damping and resume the underlying profiles afterward. Damping is
for the named bone's inbound joint, e.g. lowerarm_l means elbow; pelvis has no
inbound anatomical joint. The sword grip is not included. A live Jolt rig is
required to change damping; snapshots can capture default zero before simulation.

The debug print adds `/ D=value` without units, or `D=n/a` for a bone without an
inbound joint. Values are the effective settings applied by the agent damping
nodes; direct low-level subsystem writes are outside the agent profile API.
Completed uniform blends discard their timeline/context entry. Retained values
are used to restore configured damping if the rig is recreated, with no repeated
joint writes for an unchanged rig. Default zero allocates no applied-value entry.

`Blend To Authored Angular Limits` restores every anatomical PHAT joint from its
current angular settings, preserving joint frames, rotation offsets and linear
limits. Free axes begin at180 degrees; locked destinations approach zero and
become Locked only at the end. Already-authored free axes remain free. The
Jolt intermediate range stays within its supported0.5..179.5 degree interval,
remaining Free above that interval and reaching exact authored modes at completion.
A new blend starts from the currently narrowed limits; ordinary immediate limit setters
cancel the pending restore. Duration1 means60 unpaused game ticks, independent of
FPS/time dilation. Duration0 restores immediately. Works with Jolt and Chaos.

The limit timeline uses an active-only world callback. The existing Jolt target
publisher still requires the agent tick to remain enabled while its automatic
target pipeline is active; disabling that tick stops the Jolt rig. Completion,
cancellation, agent destruction and world cleanup remove the blend work. This narrows actual joint
ranges; it does not teleport bones. Physics still has to resolve poses outside
the progressively narrowing limits.
