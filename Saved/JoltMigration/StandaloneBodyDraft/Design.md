# Standalone body capture and preparation draft

Status: source-only draft, 2026-09-09. No build, automation test, editor process, Training asset capture, native world body creation, or asset save has been performed for this draft. Actual cooked Training hull count, COM, inertia, native wrappers and query-shape layout remain unverified until the fixture is run.

## Promotion scope

Paths below are relative to this draft and mirror the project. Existing source copies requiring a reviewed merge are:

- `Plugins/ProphecyJolt/Source/ProphecyJolt/Public/ProphecyJoltRig.h`: common `FProphecyJoltBodyData` owns physical values; `FProphecyJoltRigBody` derives from it and adds its genuine skeletal identity. Shape records add wrapper-to-leaf native type provenance.
- `Plugins/ProphecyJolt/Source/ProphecyJolt/Private/ProphecyJoltRig.cpp`: shares native shape/filter extraction and the existing compound/COM/inertia preparation through the new private conversion header. The skeletal capture gate still refuses convex/triangle-mesh rigs. No change to servo, joints, world ownership or current rig dynamics.
- `Plugins/ProphecyJolt/Source/ProphecyJolt/Private/ProphecyJoltModule.cpp`: includes prepared standalone shape lifetimes in the existing shutdown guard before Jolt global types/allocators can be released.

New files: public `ProphecyJoltBody.h`, private `ProphecyJoltBody.cpp` and `ProphecyJoltBodyConversion.h`, private `Tests/ProphecyJoltBodyTests.cpp`, and game-module `Source/GameAnimationSample3/Private/ProphecyJoltBodyFixture.cpp`. No Build.cs dependency change is needed: the fixture uses the game module's existing JSON dependencies, and the plugin already depends on the required physics modules. No WorldSubsystem file is part of this draft, so the independent generic-joint/collision draft has no overlapping owner edits.

Active-source SHA256 values at this checkpoint, for merge coordination:

| File | SHA256 |
|---|---|
| Rig.h | `3CA2215654195B4CDB34370BD085A3F6A07C9009F51598687022EC56DBF19153` |
| Rig.cpp | `B268DC9FE477A476F6F54E8220714E63F1D0CFF663B72D7E664D46261ADFD0F6` |
| Module.cpp | `146C968B3D99BD42ABFC17016657731BEA277DA02F91AF63AB5013460CA10451` |

## Public seam

`ProphecyJolt::Body::CaptureLiveBody(UPrimitiveComponent&, FProphecyJoltBodySnapshot&, FString&)` reads a registered, independent, currently simulated Game/PIE primitive body on the game thread under the physics read lock. Async Chaos and welded/skeletal components are refused. Capture is all-or-nothing and performs no source mutation. The snapshot contains no invented bone or Physics Asset. Component identity/world, visual transform and scale remain separate from the unit-scale body-origin frame.

`FProphecyJoltPreparedBody::Build(snapshot, error)` prepares the native shape and captured mass tensor. It creates no Jolt body, joint or world. Failure preserves an earlier valid prepared result. `GetCaptureId()` ties preparation to the immutable capture; a future owner must reject a mismatched snapshot/preparation pair. `GetNativeShape()` and `GetNativeMassProperties()` provide the same native-owner seam used by prepared rigs. The shape pointer is borrowed and valid only while the prepared object remains valid; a world body must take its own Jolt shape reference. `Reset()` releases preparation, and `GetLivePreparedBodyCount()` participates in plugin shutdown protection.

## Geometry and state contract

- Only actual simulation-enabled native shapes become Jolt simulation geometry. Supported native leaves are sphere, box, capsule and cooked convex, with unique FKShapeElem provenance. Query-only/disabled native shape index, type, bounds, flags and both filter-word sets are recorded separately. A simple-and-complex static mesh can therefore retain its query triangle mesh without making that mesh a dynamic simulation collider.
- Convex capture uses `Chaos::FConvex::NumVertices/GetVertex`, not the raw AggGeom input or 1,744 render vertices. Transformed, positive scaled and instanced wrappers are unwrapped in order. Matrix composition bakes the final cooked outer hull into body-origin coordinates once. Component scale, BuildScale and authored convex transform are retained as provenance and never reapplied.
- Native hulls with fewer than 4 or more than 256 vertices fail explicitly. Mirrored/zero scales, scaled non-convex wrappers, probes, unsupported simulated geometry, missing/duplicate authored identities and disagreeing simulated shape channel policies are refused. There is no automatic collider approximation or hull reduction. Jolt convex creation uses zero bevel and hull tolerance; native margins remain recorded provenance.
- Captured values include actual body-origin pose, local COM/principal frame, explicit mass and principal inertia, COM V/W, awake/gravity/CCD/MACD flags, damping, speed caps, collision/filter words, material coefficients/combine modes, source scales and solver settings. Preparation rotates the captured principal inertia into body-origin axes once and offsets shape COM without another parallel-axis adjustment.
- CCD is preserved as an input eligible for the authorized stock Jolt linear-cast mode when the future owner creates the body. MACD is explicitly unsupported. This preparation layer does not implement or silently retune contact offsets, friction combine rules, inertia conditioning or solver iteration semantics.
- Native shape indices and Jolt SubShapeIDs are not UE paint `FaceIndex` values. The future handoff must retain and synchronize the original UE query receiver, including its complex collision/UV materials. This draft does not yet switch simulation ownership or move that receiver.

## Verification entries for the root task

After promotion and compilation, run `Prophecy.Jolt.Body.CookedConvexWrappersAndMass` and `Prophecy.Jolt.Body.NativePrimitiveFramesAndRefusals`, plus the existing foundation suite because rig preparation was factored. The new tests cover cooked tetrahedral vertices with an interior source point, nested nonuniform scale/rotation/translation, actual hull ray hit and an AABB-only miss, offset COM, rotated inertia and units, lifetime/reset/failed-build preservation, instanced margins, primitive centers/capsule axes, wrong native shape identity and mirrored-scale refusal. They have not yet been executed.

The game console entry is:

`Prophecy.Jolt.CaptureTrainingSword <new absolute JSON path>`

It refuses an existing output path, creates a transient physics world, loads only the actual `/Game/_mygame/sword/geometry/Sword_GL01_Training.Sword_GL01_Training` mesh, and creates one native static-mesh body using the current C++ grip transform/scale, 1 kg mass override, CCD and 16/8 solver defaults. It never loads A_Sword, a character or a map, runs construction scripts, steps either physics engine, or saves assets. It captures and prepares the actual body, requires its expected one-convex simulation layout, records native/query geometry and mass data, and re-reads the source body to check capture/preparation left its state unchanged. JSON records success/error and package-dirty flags; errors are also logged. This fixture proves the explicit native defaults only, not Blueprint/placed overrides or held/drop behavior.

The next owner stage must add generation-safe standalone body creation/destruction, preserve captured dynamic state and effective filters, and keep the shared world stepping when only dropped props remain. The later sword adapter must use the actual captured geometry plus the authored six-axis grip frames, restore carried V/W and collision exclusions on drop, and port cut-depth/point-velocity calls. None of those gameplay or joint changes is included here.
