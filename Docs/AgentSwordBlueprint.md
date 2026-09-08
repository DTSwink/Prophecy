# Agent sword controls

Implemented and tested on the current manual agents in `testNN`, loaded using Live Coding. A separate clean-start build has not been verified; the editor was left open and unrelated unsaved assets were preserved.

All nodes take the **Prophecy Agent** as Target:

- **Equip Sword** (`Simulated = true`): spawns the existing `/Game/_mygame/sword/A_Sword` Blueprint and holds it on `hand_r` of `Get Pose Reference Mesh` (the visible PhysicalMesh for manual agents).
- **Set Sword Simulated**: true = a simulated sword held by a six-axis locked physics constraint to the hand body; false = a non-simulated child attached to the hand.
- **Drop Sword**: releases the instance with its current momentum, enables gravity/collision, and returns the dropped actor. It is no longer controlled by the agent.
- **Hide Sword**: despawns only the currently held instance. Dropped instances are unaffected. Equip Sword creates a new held instance.
- **Get Held Sword**, **Is Sword Simulated**: query the held instance and hold mode.

No Tick wiring is required. Agent simulation mode and sword simulation mode are independent: each agent mode can hold either an attached or a constrained sword.

`A_Sword` is more than a mesh: its existing cutting and Niagara logic is preserved. Its saved standalone debug defaults (`debug mode=true`, `freeze tick=0`) pause gameplay, so Equip initializes **only the spawned instance** with debug mode off, freeze tick -1, unfreeze tick 0 and gravity enabled, before Blueprint BeginPlay. If its typed decal-manager dependency is absent, Equip creates one in the game world; multiple swords reuse it. No Blueprint defaults or event graph are changed.

While held, the sword ignores only its owner's physics bodies (including the capsule). This prevents its existing cutting graph from creating competing constraints against the holder's thigh/forearm. Chaos pair-specific, reference-counted collision suppression leaves world and other-agent collisions/cutting enabled; Drop removes just these owned suppression entries. It does not globally clear other cutting constraints' collision filters.

## Defaults and calibration

`Sword Blueprint`, `Sword Hand Socket`, `Sword Grip Transform`, `Sword Training Mesh`, and `Sword Mass Kg` are Blueprint-editable. The defaults select A_Sword, hand_r, the calibrated Slash grip, the exact training mesh copy, and 1 kg. The mesh override applies only to the known original Sword_GL01 geometry, not arbitrary user replacement meshes.

The grip is copied from the accepted Slash handoff (`Saved/SlashChain/sword_preview.json`, sword record): translation in cm `(-7.111970982, 2.713666069, -0.108021118)`, quaternion XYZW `(-0.020187417, -0.106108461, 0.621049195, 0.776293347)`, scale `(0.837726780, 0.766193508, 1.311941499)`.

The original training matrix also has a small shear (the earlier preview omitted up to 0.300 mm). `PrepareExactSwordMesh.py` factors the residual out of the grip TRS. Editor command `Prophecy.Sword.BakeTrainingMesh` bakes it into a separate `Sword_GL01_Training` mesh, including transformed normals/tangents and a new convex collider. The original sword mesh, materials and Blueprint asset are unchanged. The command refuses to overwrite an existing copy. Save only that new asset after verifying its vertex transform against the source matrix.

The new copy is now saved. `VerifyExactSwordMesh.py` verified all **1,744 vertices** against the original training matrix: maximum error **0.00000495 cm**. Report: `Saved/Sword/exact_mesh_audit.json`.

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
