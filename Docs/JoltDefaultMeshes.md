# Default Jolt meshes — 15 September 2026

Installed and checked for the user's mesh-only request. Constraint integration was explicitly deferred; the unfinished draft is outside Source in Saved/DeferredJoltConstraints and is not built.

Ordinary Static Mesh components now enter the existing shared Jolt scene automatically. Movable nonsimulating meshes become kinematic colliders, including components attached inside an actor such as the Cube in BP_ProphecyManualPoseAgent. Simulating meshes transfer to the existing independent Jolt body adapter. Original component references, rendering, authored collision channels and UE query geometry remain. No additional per-mesh conversion node is required.

Authored simulated components may still have a scene-component parent at startup. Independent dynamic admission now detaches them at runtime with KeepWorldTransform, matching Unreal's SetSimulatePhysics behavior, after capture/shape validation succeeds. This does not change their saved Blueprint hierarchy. Actual welded bodies remain a separate compound-ownership case. A rejected dynamic source logs a warning and retains its original body instead of aborting the shared scene and fighter startup; physics/collision changes allow a retry.

Kinematic rigid movement updates the same native collider and supplies contact velocity. Geometry is rebuilt for scale/physics recreation, not every movement frame. A stop update clears kinematic velocity after motion ends. Dynamic bodies retain captured collision geometry, mass, velocities and CCD; queued admission freezes the launch and queues physics commands until native ownership is ready.

The project enables its existing Fight Setup automatically in a gameplay world without an explicit setup. An explicit level setup still controls that world, including deliberate Chaos comparisons. `Prophecy.Jolt.DefaultPhysics` defaults to 1 and can disable automatic startup. The Fight Setup's scene participates in the shared physics tick so new dynamic meshes can be discovered even before any character or prop has started simulating.

Standard Blueprint force, impulse, torque, velocity, simulation, mass-override and selected transform/getter calls are routed through a Blueprint compiler extension. It changes intermediate compiled calls, not the authored nodes or component classes. Existing loaded gameplay Blueprints are compiled through it before PIE when necessary; newly compiled/saved Blueprints retain the dispatcher in their bytecode. The dispatcher keeps the existing Chaos fallback when no Jolt body owns the receiver. Dynamic gravity, damping, CCD and hit-notification settings synchronize to Jolt. The existing explicit mesh library remains available and idempotent.

This is a project-level mesh bridge, not a replacement of Unreal's compiled physics backend. Native C++ callers using stock engine components do not pass through the Blueprint compiler; use the existing project physics receiver/dispatcher for those calls. Standalone skeletal ragdolls, constraint components and complete parity for every engine physics API are not supplied by this change. Runtime replacement/rescaling of an already admitted dynamic mesh still requires retiring and recapturing its body. A project-wide cooked-content migration/verification has not been run; older assets must be compiled and saved through the extension before relying on their packaged command dispatch.

Validation:

- Normal builds succeeded: Saved/Diagnostics/BuildDefaultJoltMeshes.log and BuildDefaultJoltMeshesAudit.log. Unreal was restarted after the user saved; no world-subsystem Live Coding reinstancing.
- Prophecy.Jolt.SceneCollision.StandardMovableMeshes passed: automatic ordinary dynamic admission, collision against an ordinary movable nonsimulating Cube, movement without collider replacement, standard dispatched impulse, simulation getter and cleanup. One focused test, no benchmark.
- Current testNN PIE passed: all three BP_ProphecyManualPoseAgent Cube components have live Jolt bodies at matching component positions; they are kinematic and Chaos simulation is off. The existing launch function also produces a Jolt dynamic mesh, with its dispatched simulation getter true and Chaos simulation off. Evidence: Saved/Diagnostics/DefaultJoltMeshes/PIE.json and World.json.
- PIE ended cleanly. Unreal remains open on testNN. No gameplay asset or authored graph was edited or saved by this change.

On-demand native inspection: `Prophecy.Jolt.MeshAudit [component-path-substring]` writes Saved/Diagnostics/DefaultJoltMeshes/World.json. It adds no tick work.

Attached simulated Cube follow-up: Live Coding succeeded; StandardMovableMeshes now reproduces attachment-at-startup and passes. Current PIE audit confirms all three agents select/enable Jolt and all three Cubes are dynamic Jolt bodies with Chaos simulation off. Evidence: Saved/Diagnostics/AttachedJoltMeshes/PIE.json. No restart or authored asset changes.
