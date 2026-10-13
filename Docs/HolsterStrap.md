# Cosmetic holster strap

October 13, 2026. This is a separate reusable asset, not a replacement of the
character's existing cube holster or its D/S setup.

## Editable Animation Blueprint — current setup

**Placed holster/SIE follow-up:** fixed the distance gate using the wrong camera
in Simulate In Editor. SIE now uses the world's rendered editor-view locations
(any nearby view permits simulation); before the first rendered view the
distance decision is deferred. Ordinary Play still uses the player viewpoint.
The15-tick check, hysteresis and other gates remain unchanged. The placed actor
`BP_HolsterWithStrap_C_1` also retained the old native Anim Class override; it now
uses ABP_HolsterStrap with exact placement preservation. The level was not saved.
Same placed-actor120-sample SIE capture: running0→120 samples, tip component-space
motion~0→29.078cm, parent-follow error0; identical145.153cm holster fall. No Jolt
or rigid-body changes. Native compile and Live Coding reload succeeded; editor
outside Play. Current dirty TestNN/holster BP/AnimBP were preserved. Evidence:
`placed-sim-before.json`, `placed-sim.json`, `placed-sim-verification.json`,
`placed-anim-fix.json` in the evidence directory. Normal DLL build remains due
before cold launch.

Open `/Game/_mygame/assets/holster/Animated/ABP_HolsterStrap`, go to AnimGraph,
and select **AnimDynamics**. This is Unreal's built-in animation editor with a
3D preview and Details panel, not PhAT. The editor is opened with that node
selected. **Body Definitions** holds the five joints and their individual
angular limits, target axes, inertia boxes and joint offsets. Spring, damping,
gravity and solver settings are on the same node. Compile and Save after tuning.
Preview Live and Show Angular Limits start enabled.

**Joint constraints are now linked**, as requested. Edit **Constraint Setup**
under any Body Definition; all five receive that joint's full constraint setup
(angular/linear limits, target axes and target). Sizes, pivots and bone names
remain individual. Initial linking used the current strap_01 values, already
±65 degrees on all five. Spring/damping are already shared node settings.
Compile and Save after edits. The visible node comment identifies the linkage.
It is an editor property-change listener scoped to this asset and enabled by
saved `HolsterSharedConstraints` metadata; no polling or game-frame overhead.
The editor preview receives the linked constraints too. An optional console
command `Prophecy.Editor.HolsterAnimBlueprint UnlinkLimits` stops propagation.
`Tools/HolsterStrap/LinkConstraints.py` sets up the linkage and saves only this
Animation Blueprint. Property-change event checks from all five source indices
pass and preserve geometry; the asset compiles successfully. See
`linked-limits-test.txt` and `limits-before.txt` in the evidence directory.

The graph is Reference Pose → Local to Component → AnimDynamics → Component to
Local → Output Pose. The holster Blueprint's Strap uses this graph in Play;
BeginPlay now respects its assigned Anim Class. Node settings are authoritative:
the component's old Stiffness/Damping/Max Bend Angle/Gravity fields apply only
to the legacy native fallback. Component enable/distance/global gates still work.

The user abandoned the directional leather trial. Both the new graph and native
fallback restore the previous uniform ±65-degree bounds, with spring20 and
engine damping0.77687 (the previous rate1.5 converted to the engine fraction).
No curl-only or narrow sideways limits remain. There is no Physics Asset; PhAT
does not control this animation solver. Mesh, material, collision-free behavior,
and the user's holster placement/rigid Simulate Physics setting are preserved.

Live Coding compile/reload succeeded without an editor restart. Saved only the
new Animation Blueprint and the connected holster Blueprint, preserving its
current user edits. TestNN remains dirty and untouched. A336-sample owned Play
test confirms the actual `ABP_HolsterStrap_C` instance, finite moving poses,
exact fixed root, manual/distance/global disable and re-enable, reference-pose
restoration and500cm teleport handling. Dynamic anchor residual≤.24821cm.
Native Blueprint health: status3, native_properties0, pin_types0. Outside Play.
This verifies the interface and runtime connection, not artistic leather motion.
Normal DLLs still need rebuilding before a cold launch; no push.

Creation is reproducible with `Prophecy.Editor.HolsterAnimBlueprint Create`
(never overwrites an existing graph) and `Tools/HolsterStrap/CreateAnimBlueprint.py`.
The latter connects/saves the holster Blueprint and checks placement preservation.
Evidence: `anim-blueprint.txt`, `probe-animbp.json`, `verification-animbp.json`,
`before-animbp-placement.json`, `animbp-finish.json` under
`Saved/Diagnostics/HolsterStrap20261013/`.

## Assets and use

`/Game/_mygame/assets/holster/Animated/BP_HolsterWithStrap` combines the rigid
static holster and its child `Strap` (`ProphecyHolsterStrapComponent`). Attach
and position the whole Blueprint, or copy both components to the intended
holster actor. Both share the original asset origin and material, with identity
relative transforms. The original extracted static mesh is preserved.

Select `Strap` to tune **Holster Strap** properties:

- **Strap Enabled** / node **Set Holster Strap Enabled**: false restores the
  reference pose and disables the component tick entirely. True resets dynamics
  and resumes only if eligible.
- **Max Simulation Distance**, default 1500 cm: distance from the local player's
  camera. Zero removes distance culling. An active strap exits at 1650 cm and
  returns at 1500 cm to prevent repeated switching at the boundary.
- **Stiffness**, default 20: angular spring strength.
- **Damping**, default 1.5: exponential decay rate, converted to the engine's
  damping fraction as `1-exp(-rate)`; higher values settle faster.
- **Max Bend Angle**, default 65 degrees: per-joint angular bounds.
- **Strap Gravity Scale**, default 1.
- **Reset Holster Strap**: clears dynamics after an explicit reset/teleport.
- **Is Strap Simulating**: current eligibility state.

Console variable `prophecy.HolsterStrap 0` disables simulation globally; `1`
allows enabled nearby straps again. Distance and global gates are checked every
15 component ticks. Culled components retain that lightweight check but return
before skeletal animation update/evaluation. Manual disable removes the tick
altogether. These switches remove simulation work; they do not remove rendering
cost. The strap is not automatically hidden or replaced by a static LOD.

## Implementation

Five AnimDynamics bodies drive `strap_01` through `strap_05`; `strap_root` anchors
the wrapped leather and `strap_tip` follows the end. Only 1118 vertices are
skinned, with 4935 vertices remaining static (9326 total triangles, unchanged).
The cloth and sword are absent. Original UVs and SwordMat1 are retained.

The Animation Blueprint evaluates reference pose → AnimDynamics. No Control
Rig, collision/overlaps, physics asset, Jolt body or contact queries are used.
AnimDynamics is an animation-local solver; the component follows its parent's
completed transform in PostUpdateWork. It responds to gravity and limited parent
acceleration. Translation jumps over 100 cm or rotation jumps over 90 degrees
reset the simulation. There is no accumulated catch-up when re-enabled.

Geometry and bone translations are baked in centimetres before export, with
unit bone/object scale; no inherited 100× root scale. The Blender source and two
FBXs are in `C:/Users/singerie/Downloads/HolsterStrap/`.

`Tools/HolsterStrap/BuildRig.py`, `VerifyRig.py`, `ImportAssets.py` and
`CreateBlueprint.py` reproduce the asset. Generated-asset replacement requires
an explicit command flag. `Probe.py` owns a temporary Play fixture and records
bone transforms and enable/cull/teleport transitions; `AnalyzeProbe.py` checks
real movement, anchor stability and the reference pose when disabled.

Official engine description:
https://dev.epicgames.com/documentation/unreal-engine/animation-blueprint-animdynamics-in-unreal-engine

## Original asset verification (before the editable-graph migration)

Rig checks pass: original rest shape within 0.000000031 m; 823 anchored vertices
unchanged during bending. Native build succeeded. First live test caught an
invalid damping input; corrected to the fraction required by AnimDynamics.
The spring target uses the positive imported bone axis (the exported chain runs
along negative Y). Inertia boxes use a 2 cm minimum thickness, independently of
the visible leather, to avoid unstable axial inertia. None of these boxes collide.

Moving and stationary owned-Play tests each pass 336 samples, covering manual
off/on, distance off/on, global off/on and a 500 cm teleport. All poses remain
finite; fixed `strap_root` position is exact. The first dynamic joint has up to
0.2483 cm constraint error in the moving fixture; this is an approximate animation
solver, not an exact joint constraint. The 823 wrapped-leather vertices use the
fixed root. Rest-pose restoration error is below 0.000000001 cm. Manual disable
removes the component tick; automatic gates retain only eligibility checks.
No new NaN reports after the final reload. A further 936-sample stationary test
passes, including ten extra seconds to settle: late tip travel is below
0.000683 cm per tick (no sustained jitter).

This verifies numerical behavior, not an artistic motion review or a crowd/FPS
benchmark. The character's current cube holster has not been replaced. The new
Blueprint is saved and opened for inspection, outside Play. Original agent graph
matches the pre-build audit byte-for-byte; saved user packages match their backup
hashes; native BP health is clean and no dirty packages remain.

One normal build/restart introduced the native classes. Subsequent layout-safe
Live Coding fixes are loaded in editor PID17712. **Normal DLLs need rebuilding
before a cold launch.** Existing open Blender file was not changed. No Git push.
Evidence: `Saved/Diagnostics/HolsterStrap20261013/`, notably `verification-moving.json`,
`verification-still.json`, `rig-verification.json` and `finish.json`.
