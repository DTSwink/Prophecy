# Native physical-animation experiment

## Existing pose agent: three runtime modes

On `BP_ProphecyManualPoseAgent`, call **Set Simulation Mode** with Target `self`:

- **Kinematic**: existing NN kinematic presentation.
- **Half Sim**: the same `PhysicalMesh` evaluates the NN and Unreal physical animation drives its collidable PHAT bodies. This is real physics, not a 50% visual blend. No replacement pawn, extra mesh, manager or Blueprint Tick setup.
- **Sim**: existing absolute-world magnetization. The original `Physical` enum name/value1 remains compatible with saved Blueprint pins; its display name is now Sim. Half Sim is appended as value2.

BeginPlay Half Sim calls wait automatically for the first published NN pose. `Get Simulation Mode` reports the active mode. Existing locomotion, gaze, attacks and feedback tolerances are retained, not reset to the experimental standalone class's open-loop defaults.

In Half Sim, `Set All Body Magnetization`, `Set Body Magnetization` and `Set Body Magnetization Below` set native drive strength scales. Linear/angular `0.5` halves stiffness, damping and configured force caps; `0,0` disables pull without disabling colliders. `Physical Drive Settings` and `Set Physical Drive Strength Multiplier` also apply. Native automatic custom magnetization is suppressed only in Half Sim; explicit Blueprint velocity setters can still override physics and should not run in that mode.

The Half Sim controller uses the native experiment's free angular axes and retained rigid linear anchors. On exit it restores the pre-Half-Sim mesh configuration and joint profiles. Sim↔Half Sim transitions preserve existing simulated body transforms and velocities. Kinematic returns to the authored NN pose normally. The fixed-length PHAT versus variable-length NN geometry limitation below still applies.

`Tools/NN/TestProphecyHalfSimulation.py` is the PIE-only mode regression; its report is `Saved/NativePhysical/pose_agent_three_modes.json`. The standalone class below remains available as the original isolated fixture.

Verified live on `testNN`'s existing `BP_ProphecyManualPoseAgent_C_1`: all six directed mode transitions, 726 frame samples, unchanged component count (empty inherited Mesh plus existing PhysicalMesh), retained NN animation in Half Sim/Kinematic, real named-body simulation in Half Sim/Sim, and native target error at most `1.14e-13 cm` across 228 Half Sim samples. Sim↔Half Sim sampled body position/linear/angular velocity changes were exactly zero at the switch. This is a mode-wiring test, not a new crowd/FPS or contact-tracking benchmark. Live Coding installed the enum/function changes without an editor restart or asset save.

Contained class: `ProphecyNativePhysicalAgent` (child of `ProphecyAgent`). Production `BP_ProphecyManualPoseAgent`, `testNN`, NN models, mover and custom magnetization are unchanged. This is an alternative test class, not a production migration.

## What it runs

One skeletal mesh evaluates the normal NN animation instance. Unreal's `PhysicalAnimationComponent` reads its pre-physics animation buffer, drives its PHAT bodies, and renders those simulated bodies at physics blend weight **1**. No target skeletal mesh, leader-pose mesh, custom magnetization, substep follower, body teleport correction or visual blend conceals the physics.

Order: NN manager publishes → same mesh evaluates animation → native physical-animation targets update → Chaos simulation/contact → same mesh renders physics.

The root capsule remains the existing kinematic/swept mover. `ComponentTransformIsKinematic` holds the mesh's carrier to that capsule; **individual PHAT bodies, including pelvis, simulate**. `Is Simulating Physics` with no bone returns false in this mode; supply `pelvis` or another PHAT bone.

Native physical animation still creates a small kinematic target and drive constraint per controlled body. One skeletal mesh does not mean physics constraints disappear; no crowd-performance advantage is claimed.

## Try it without changing production

Create a Blueprint child of `ProphecyNativePhysicalAgent`, place it in a separate test level without an existing NN manager, then Play. It creates the normal simple NN manager with its own lane, explicitly selects accepted July5 latest Walk, retains the inherited spring arm/camera, and starts physical. Run/Upper use the existing manager's accepted defaults.

Alternatively set a separate manager's `Agent Class` to this class and `Initial Physical Drive Mode` to `PerBodyWorld`; also select the July5 Walk model/contract paths on that externally configured manager. Do not mix two NN managers in one world: their pose-store IDs overlap. A nonmanual placed test pawn is not automatically discovered by an already-existing manager; explicitly assign its `Player Agent`, or let that manager spawn the class.

Input is deliberately not newly bound. Use inherited `Set Locomotion Input` (e.g. World Move Input `(0,1,0)`, Run false, Facing World Direction `(0,1,0)`, Speed/Turn Scale `1`). `Stop Locomotion Input` stops it. Existing gaze, attacks, data-pose and animation-layer APIs remain available through the inherited agent; this test does not rewrite them.

The C++ fixture console command `Prophecy.NativePhysical.Spawn` only runs in PIE with **no existing NN manager**. It creates a transient agent and collision-only floor away from the production scene. Ending PIE restores the untouched editor world. The numerical harnesses operate only on that named fixture.

## Runtime nodes

| Node | Use |
|---|---|
| `Set Native Physical Simulation` | True uses same-mesh native physics; false uses ordinary NN kinematic rendering. Use this wrapper for this class so contact settings and cached body strengths are reapplied. |
| `Set Native Body Strength` | Bone `FName`, independent linear/angular multipliers of the baseline `Physical Drive Settings`. Invalid/non-PHAT names or negative/nonfinite scales return false. |
| `Set Native Body Strength Below` | Parent bone, linear/angular scales, Include Parent; returns number of changed PHAT bodies. Traverses the skeleton, including parents without bodies. |
| `Set Native Contacts And Gravity` | Runtime collision/gravity toggles. No-contact calibration keeps a valid physics state, with channel responses Ignore. Contacts on blocks WorldStatic, WorldDynamic and PhysicsBody; own capsule is ignored. |
| `Set Native Use Authored Angular Limits` | True restores PHAT angular limits. False frees angular rotation for NN calibration. **Linear joint anchors stay as authored.** No asset is edited. |
| `Get Native Physical Animation` | Access to the actual UE component and native Apply Settings/Profile/Strength nodes. Bind is already done—do not rebind it each Tick. |
| `Get Native Body Sample` | Named body's native target, actual Chaos transform, linear/angular velocity, mass and physics blend weight. Read after physics. Returns false until wrapper-managed native targets initialize, or for nonsimulated bones/outside the driven subtree. Directly rebinding the exposed native component bypasses this wrapper's initialization guard; do not sample during that operation. |

For half-strength right arm: `Set Native Body Strength Below`, Parent Bone `upperarm_r`, Linear Scale `0.5`, Angular Scale `0.5`, Include Parent true. Use `0,0` for limp **but still collidable**, `1,1` to restore. Calls are absolute baseline multipliers: calling half twice does not quarter strength. Reducing only linear gain leaves angular drives and joint forces active.

`Physical Drive Settings` exposes stiffness, damping and optional force limits. `Set Physical Drive Strength Multiplier` controls the whole native component. Native settings/profile calls are also available, but overrides applied directly there are not cached by this test class's wrappers. Do not mistake `Physics Blend Weight` for strength: it changes rendered animation/physics blending, not drive compliance.

This experiment initially uses large physical-feedback tolerances to isolate drive behavior from NN feedback. The baseline is set before Blueprint BeginPlay; explicit Blueprint feedback setters then win. Use inherited feedback setters to opt into physical feedback. PHAT swapping is not a separate validated feature of this experiment: after an inherited swap, call `Set Native Physical Simulation(true)` to rebuild native target constraints and restore wrapper strengths.

## Known geometry/limit differences

The original mannequin PHAT contains locked knee/elbow twist axes that conflict with NN rotations. This test class defaults `Native Use Authored Angular Limits` **off**. Turning it on restores anatomical PHAT limits, but can make the motors fight those limits. With limits off, a disabled limb can rotate beyond anatomical ranges; this is an explicit calibration choice, not a production ragdoll profile.

NN forearm targets sometimes shorten: running target elbow→hand distance reached about **11.6 cm**, while the PHAT forearm stays about **22.2 cm**. Real fixed-length articulation cannot occupy both target endpoints simultaneously. The test keeps those linear anchors intact; it does not detach hands or alter the NN. Expect residual hand position error against the raw target.

An isolated causal probe freed wrist linear joints temporarily: hand mean running error fell below **0.09 cm**, confirming the geometric conflict. Those free wrist joints were **not** kept. Freeing angular limits alone reduced calf mean angular error from about **36–47°** to **0.3–1.2°**, with foot mean position errors about **0.13–0.23 cm** in that probe. Raw-target hand error remained about **2.9–3.6 cm**.

## Verification

- Live Coding used; no editor restart or production BP/map save.
- `Tools/NN/TestProphecyNativePhysical.py`: one retained NN anim instance, one skeletal component, 22 named simulated bodies, blend weight1; walk/run at 60/30/5 caps, contacts/gravity off and on, runtime arm impulses. Native targets versus independent data-only source matched to **8.2e-14 cm / 5.4e-6 degrees** in the initial audit. That initial audit used the native manager's older Walk default; final test-class setup explicitly selects accepted July5 latest. The Run-based geometry/limit probes use the unchanged accepted Run model.
- A cap is not an achieved rate: initial 60-cap cases averaged roughly **28–32 FPS** under the instrumented workload. Actual 5 FPS was verified. No claim of an achieved 60 Hz or crowd-performance benchmark.
- `Tools/NN/TestProphecyNativeContacts.py`: final class, identical stationary hand target; solid box contact increased mean hand error from **0.0021 cm to 12.40 cm**, disabling contact returned it to **0.0021 cm**. Capsule stayed fixed. This proves real contact response, not just collision flags.
- `Tools/NN/TestProphecyNativeStrength.py`: final class, identical constant hand force, arm scale1 →0.5 →1 changed force-direction deflection **2.61 →4.78 →2.58 cm**. Force is applied once per distinct game frame. The separate initial impulse test at scale0 displaced the hand over **70 cm**, while the torso stayed driven; restoring1 recovered.
- `Tools/NN/ProbeProphecyNativeJointLimits.py`: separates angular-limit and forearm-length conflicts; restores all runtime constraints.

Reports are under `Saved/NativePhysical/`. They are diagnostics, not production acceptance of perfect NN tracking. No claim that contact-constrained bodies stay identical to an obstructed target.

Final-patch repeat: `accepted_july5_free_angular.json` completes all16 cases without invariant/cleanup failures, using accepted July5 latest and default free angular limits. Mean right-foot error is **0.12–0.21cm walking /0.26–0.50cm running** across tested caps/contact modes; mean right-hand error remains **1.20–1.50cm walking /2.53–3.43cm running** from fixed-length geometry. `smoke.json` passes live physical↔kinematic switching, restored PHAT/free angular-limit switching with unchanged linear anchors, rejected invalid bone/negative strength, and safe sampling while target creation is deferred.

## Engine references

[Epic's supported setup](https://dev.epicgames.com/documentation/en-us/unreal-engine/applying-a-physical-animation-profile-in-unreal-engine?application_version=5.7): bind the physical animation component, apply settings/profile, then enable simulated bodies. [Physics-driven animation](https://dev.epicgames.com/documentation/en-us/unreal-engine/physics-driven-animation-in-unreal-engine) distinguishes physics blend weight from motor strength.

UE5.7 source: `Engine/Private/PhysicsEngine/PhysicalAnimationComponent.cpp` reads `GetEditableComponentSpaceTransforms` before physics blending; local simulation disables linear drives. This class enforces world-space drives. `SkeletalMeshComponentPhysics.cpp` documents named-body simulation checks with `ComponentTransformIsKinematic`. Calibration uses Ignore responses, not NoCollision, because NoCollision removes valid simulation bodies.
