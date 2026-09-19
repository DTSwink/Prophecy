# Agent sword controls

Runtime sword controls for the current manual agents, with Chaos and Jolt ownership.

Held simulated Jolt swords now inherit the hand's magnetisation and authored target,
independently of their fixed grip. `Break Sword Grip Constraint` removes only that
joint for testing; see [independent sword magnetisation](SwordMagnetization.md).

## Right Shift drop freeze correction (2026-09-15)

The automatic mesh receiver introduced a deterministic conflict during native sword handoff. `Drop()` staged release velocity on `UProphecyPhysicsStaticMeshComponent` before reserving its managed Jolt adapter. The virtual velocity setter entered the generic automatic importer, which claimed/froze that same source. The sword controller's subsequent admission then conflicted; restoring the held source invalidated the other adapter and stopped shared physics. Key input runs in the world-tick admission path, unlike the earlier isolated direct-drop check.

Native sword capture/handoff velocity writes now explicitly call `UPrimitiveComponent`, leaving admission to the sword controller. Blueprint velocity nodes retain their normal Jolt dispatch. Generic library/scene admission also respects pending managed ownership; direct duplicate adapters reject a claimed source before mutation. The shared-world binding validation remains enabled.

Verification: Live Coding compile/patch succeeded. `Prophecy.Jolt.SceneCollision.PendingManagedMesh` passed the queued-owner regression, but that test alone missed the virtual-setter problem. The final `Saved/Diagnostics/TestSwordDropKey.py` test starts the unchanged current scene and injects Right Shift through `PlayerController::InputKey`, invoking the existing Blueprint key binding. The sword was released with exactly one active dynamic Jolt adapter and zero pending adapters; the shared world advanced from step 37 to 82 without errors/stopping. Report: `Saved/Diagnostics/SwordDropKey/PIE.json`. The development-only `Prophecy.Sword.DebugDropKey press|release` command supports this input-path test with no tick work. No Blueprint/map edits or saves and no editor restart were required.

All nodes take the **Prophecy Agent** as Target:

- **Equip Sword** (`Simulated = true`): spawns the existing `/Game/_mygame/sword/A_Sword` Blueprint and holds it on `hand_r` of `Get Pose Reference Mesh` (the visible PhysicalMesh for manual agents).
- **Set Sword Simulated**: true = a simulated sword held by a six-axis locked physics constraint to the hand body; false = a child attached to the hand. With a simulated Jolt hand, the sword collider is welded onto that hand body, so contacts act on the hand/arm and the sword cannot stretch away from its grip. The hand's mass and center of mass stay unchanged.
- **Drop Sword**: releases the instance with its current momentum, enables gravity/collision, and returns the dropped actor. It is no longer controlled by the agent.
- **Hide Sword**: despawns only the currently held instance. Dropped instances are unaffected. Equip Sword creates a new held instance.
- **Get Held Sword**, **Is Sword Simulated**: query the held instance and hold mode.
- **Set Sword Inertia Scale (Scale)** / **Get Sword Inertia Scale**: default 1. Scales held mass and rotational inertia together; 0.5 is half the load, 0.25 is a quarter. The fixed hand grip stays rigid. Positive finite values only; the setter returns false on invalid input or an in-progress physics admission. Set once, not on Tick. The preference persists across equips, attached/physical mode changes and backend switches. Dropping restores the ordinary mass captured from Sword Mass Kg at equip, preserving release velocities.

- **Set Sword Attached Inertia Scale (Scale)** / **Get Sword Attached Inertia Scale**: Jolt attached mode only, default **1**. Adds the specified fraction of the captured sword's rotational inertia, measured about the hand's center of mass. **0** leaves the hand's original inertia; **1** includes one sword's rotational inertia; **2, 5, ...** resist rotation more strongly. This does not add hand mass, move its center of mass, add damping, or change the grip. Applies immediately to an existing welded sword and persists through mode changes/equips on this agent. Dropping/removing the sword restores the original hand inertia. Negative/nonfinite values fail without changing the setting. Extremely large values that cannot be represented safely also fail. Separate from **Set Sword Inertia Scale**, which scales mass and inertia of an independently simulated sword. Attached inertia uses the sword mass/inertia captured when the weld was created.

No Tick wiring is required. Agent simulation mode and sword simulation mode are independent: each agent mode can hold either an attached or a constrained sword. The attached inertia setter does work only when its value changes; it does not add per-frame work. A larger value changes contact response but is not a guarantee of jitter-free motion in every driven pose.

`A_Sword` is more than a mesh: its existing cutting and Niagara logic is preserved. Its saved standalone debug defaults (`debug mode=true`, `freeze tick=0`) pause gameplay, so Equip initializes **only the spawned instance** with debug mode off, freeze tick -1, unfreeze tick 0 and gravity enabled, before Blueprint BeginPlay. If its typed decal-manager dependency is absent, Equip creates one in the game world; multiple swords reuse it. No Blueprint defaults or event graph are changed.

Both sword modes collide with the owner's body during locomotion. Full and half NN attacks temporarily suppress owner contacts, including preparation, and every attack exit restores them. The gripping hand is always excluded, because its handle and hand intentionally share space. World/other-agent collision channels are unchanged. These are simulation pair exclusions, not changes to tracing or the disconnected cutting graph. The Jolt attached mode retains a QueryOnly UE receiver; the native sword shape belongs to the hand, with separate per-shape material/channel/exclusion rules. Chaos keeps its existing attached QueryAndPhysics behavior; the new attached-inertia control only applies to Jolt.

Attack lifecycle events update these exclusions without per-frame polling. Jolt keeps the same native grip and warm-start state; only its reference-counted exclusions change. The inertia node uses native proportional mass scaling without recreating either body or joint and updates the UE receiver's mass override for future backend changes.

Validated on the normal 13 September editor build: 35 actual-sword fixture checks passed (`Saved/Diagnostics/SwordInertiaFixture.json`), including attack collision transitions, native linear/angular impulse response at quarter mass/inertia, attached/physical roundtrip, and drop restoration without velocity changes. GenericJoint.CapacityAndAtomicPreflight also passed. No performance benchmark was run.

## Defaults and calibration

`Sword Blueprint`, `Sword Hand Socket`, `Sword Grip Transform`, `Sword Training Mesh`, and `Sword Mass Kg` are Blueprint-editable. The defaults select A_Sword, hand_r, the calibrated Slash grip, the exact training mesh copy, and 1 kg. The mesh override applies only to the known original Sword_GL01 geometry, not arbitrary user replacement meshes.

The grip is copied from the accepted Slash handoff (`Saved/SlashChain/sword_preview.json`, sword record): translation in cm `(-7.111970982, 2.713666069, -0.108021118)`, quaternion XYZW `(-0.020187417, -0.106108461, 0.621049195, 0.776293347)`, scale `(0.837726780, 0.766193508, 1.311941499)`.

The original training matrix also has a small shear (the earlier preview omitted up to 0.300 mm). `PrepareExactSwordMesh.py` factors the residual out of the grip TRS. Editor command `Prophecy.Sword.BakeTrainingMesh` bakes it into a separate `Sword_GL01_Training` mesh, including transformed normals/tangents and a new convex collider. The original sword mesh, materials and Blueprint asset are unchanged. The command refuses to overwrite an existing copy. Save only that new asset after verifying its vertex transform against the source matrix.

The new copy is now saved. `VerifyExactSwordMesh.py` verified all **1,744 vertices** against the original training matrix: maximum error **0.00000495 cm**. Report: `Saved/Sword/exact_mesh_audit.json`.

On 10 September, at the user's request, only the Training copy's simple collision was replaced with a 127-vertex convex for Jolt. The calibrated source mesh, render buffers, materials and complex query triangles remain unchanged. The new convex preserves the source bounds and differs inward from the old source convex by at most 1.911 mm in mesh-local space (-0.922% volume). This retains the existing single convex envelope rather than adding separate blade/guard/handle shapes. Strict Jolt preparation passes after saving and reloading. Evidence and the original asset backup are in `Saved/JoltMigration/SwordHull-20260910/`. The user authorized omitting MACD for Jolt; sword admission disables it while retaining the existing CCD=true. All 28 actual A_Sword manual-step checks pass, including physical/attached equip, both drop paths, momentum, queries and cleanup. See `Docs/JoltFightSetup.md` for the remaining visible-contact and commandlet diagnostic limitations.

## Mode transition continuity

The six directed Kinematic/Half Sim/Sim switches share an outer capture/restore transaction, including nested Half Sim calls. It preserves all rendered bones and simulated body transforms/velocities. Returning to Kinematic blends to the moving animation target over 0.25 seconds, instead of replacing the physical pose immediately. Manual Sim retains non-physical helper-bone local frames so root/IK/twist bones do not reset to the differently oriented reference pose on the following tick. Physics-root carrier offsets are rebased after body restoration.

Constraints can resolve incompatible joint poses in subsequent physics steps. This is distinct from a mode-switch teleport. The held sword constraint is rebound after the final mode state is restored.

A second engine-specific trap is the deferred kinematic **TeleportPhysics** update left by component-transform restoration. If left queued, the next PrePhysics update can overwrite simulated bodies with that frame's animation pose. The transaction clears only this mesh's pending update and immediately synchronizes its kinematic bodies without teleporting its dynamic bodies.

Manual Sim ↔ Half Sim now changes the drive policy directly on the existing dynamic bodies, without bouncing through Kinematic or disabling/re-enabling the body instances. The older route caused a next-step calf rotation even with all joints free, no contacts, no gravity and zero drive strength.

UE's physical-bone blending calculates child translations against unscaled physical parents, then composes them with animated calf scale. A finalized-pose correction uses the actual child body position while retaining visual scale and following non-physical children. This removes the ~2 mm first-frame foot discontinuity without moving any physics body. Remaining small helper-bone changes follow the continuous 0.25-second blend. Attached swords explicitly refresh their component transform after rebinding, including when their relative grip transform has not changed.

## Reproducible tests

- `Tools/NN/TestProphecySword.py`: actual A_Sword instance, attached/constrained holds in three modes, physics toggle, momentum-preserving drop, independent despawn.
- `Tools/NN/TestSwordModeTransitions.py`: all six switches and all 88 rendered bones, immediate readback and following frames. `ISOLATE=True` disables the legacy Blueprint velocity follower for an isolated native test; it does not save Blueprint changes.
- The four `Saved/Sword/transitions_*_final.json` reports passed **24 transition cases**: six directions × attached/constrained swords × isolated force-free/normal gameplay conditions. They assert switch-time pose continuity and record subsequent frames. Worst immediate position change across all 88 bones: **3.2e-13 cm**; rotation roundoff: **0.00000242 degrees**. Sword position/rotation continuity passed too.
- `transitions_scaled_physics_fix.json` isolates the scale correction without a sword. In the force-free test, Sim ↔ Half Sim first-frame differences are below 0.000025 cm. Kinematic handoffs smoothly interpolate helper scale/pose; they do not promise a frozen pose while the animation target changes.
- `hold_drop_simulated_final.json` and `hold_drop_attached_final.json` passed with gravity, floor/holder collision settings and the original agent Blueprint motion control enabled. The other agent's collisions were disabled **only in these transient tests** to distinguish grip behavior from the cutting Blueprint's victim constraints. Both attached and physical drops work; physical-drop linear/angular velocity preservation is asserted. Hide removes the held instance but leaves dropped swords alive.
- `Saved/AttackFists/deformation_audit.json`: the final fist regression passed all 12 checks across the three agent modes; maximum skin-probe error **0.00005766 cm**.

The fixed grip is a physics constraint, not a per-frame teleport: impacts and competing victim-cutting constraints can temporarily deflect it. Original cutting behavior against other agents remains enabled. Older non-final reports include diagnostic failures and must not be presented as final acceptance.

Tests create and end transient PIE sessions. No user Blueprint, map, skeleton, skin material, or animation asset is saved by them.
