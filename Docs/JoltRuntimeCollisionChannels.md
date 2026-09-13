# Runtime collision channels

Use the existing Unreal nodes on the participating primitive component: `PhysicalMesh` for a character, the registered mesh/root for a sword or other Jolt body, and the static/instanced component for imported scenery.

- `Set Collision Response to All Channels` and `Set Collision Response to Channel` synchronize to Jolt before the next coordinated physics step.
- `Set Collision Object Type` synchronizes too, including custom channels. This setter does not broadcast Unreal's collision-settings event, so the adapters also compare the current object channel.
- Channel changes through collision presets synchronize. Verified presets: `Ragdoll` on the actual character, `BlockAllDynamic` on a moving body, and `BlockAll` on static/ISM/HISM receivers. A preset requesting QueryAndPhysics restores only Unreal's query representation while Jolt retains simulation ownership.
- Both bodies must answer Block to the other's object channel to create a physical contact. Ignore and Overlap are nonblocking. Begin/End Overlap events remain deferred by the user's instruction.

This covers channel policies. It does not add general `Set Collision Enabled` mode switching; NoCollision/PhysicsOnly presets and their different query/simulation ownership requirements are outside this change. GetCollisionEnabled continues to expose the UE query proxy's state while Jolt is active.

Native filter changes retain body handles, velocities, poses, joints and PHAT self-collision suppressions. They invalidate affected contact caches and wake bodies in the changed collider's bounds, including a sleeping body losing support. Unchanged policies do not wake bodies. Character policies use UE's own `BuildBodyFilterData` so PHAT overrides combine with component responses. Static instance changes also propagate the template channel policy into retained UE instance bodies; their native actor filters otherwise retain old settings.

Implementation: `UProphecyJoltWorldSubsystem::UpdateBodyCollision`, the character/body pre-step adapters, and the static scene reconciler. The update validates the complete handle/profile batch before applying it. `ReadBodyCollision` reports the effective native Block/Ignore policy for diagnostics.

Validation on 2026-09-11: normal Editor build succeeded; eight isolated headless checks passed. New checks cover actual 22-body character filters, moving Block → Ignore → Block contacts, custom object channels, presets, UE trace responses, static/ISM/HISM identity retention, rejected-batch atomicity, and waking a sleeping body when its floor stops blocking. Existing body publication/callback and instance-promotion/cleanup checks also passed. Evidence: `Saved/Diagnostics/CollisionChannels/Build-Final.log`, `Tests-Final.log`, and `Report-Final/index.json`. No new packaged or visual verification is claimed.

During the first compile Unreal exited with a DXGI viewport/notification access violation, before the collision patch loaded. With the user's approval, the 01:33 `BP_ProphecyManualPoseAgent_Auto5.uasset` was restored over the older saved asset. Both versions and the crash log are preserved in `Saved/Diagnostics/CollisionChannels/CrashBackup-20260911-0157`.
