# Imperial Spear pike — October 30, 2026

Complete and saved. Normal build `build-ccd.log` succeeded; an isolated copy of
those DLLs passed native and actual Blueprint Play checks, followed by a disk
reload of the saved asset. The private retained cut state has new spear fields:
do not Live Code this layout change. Owned work/evidence:
`Saved/Diagnostics/SpearPike20261030/delivery.json`.

The separate `/Game/_mygame/spear/A_Spear` duplicates the current A_Sword behavior
and preserves its accepted-hit pike conditions, friction, cut records and cleanup.
Its slash admission branch is disconnected before hit cancellation or cut setup.
Optimised cut handling is mandatory for this copy. The original A_Sword asset and
saved maps are not edited.

`Prophecy.Spear.PassThrough` opts into the native spear lifecycle. Z travel is
free in both directions, including matter0 after five frames. Withdrawal still
releases when the tip clears the entry wound. Forward release waits for the
**whole spear, including its pommel**, to clear the target's far face, using
`Pike Target Thickness Cm = 15`. Thickness is a world-centimetre assumption,
not a trace of the actual victim. Weapon rear extent and scale are cached once
on admission. No extra actor tick, query or feature loop is introduced.

The default mesh-local scale is the live Big Throw lab setting:
`(0.8623427588789339, 0.8834927125312151, 0.7619161867885869)`.
The imported FBX is converted from metres to centimetres before applying it.
Source length 225.223121 cm gives about171.601 cm overall. Local +Z points toward
the blade; the pivot is the moved grip. Imported mesh breadth is X; the copied
Blueprint's width helper and blood edge use X instead of the sword's Y.

Mesh: `/Game/_mygame/spear/SM_ImperialSpear`, with the original43,494 triangles,
17 UCX convex hulls and sockets. Material: `M_ImperialSpear`, BaseColor multiplied
by imported cavity vertex colors; ORM RGBA means AO/roughness/metallic/specular;
DirectX normal map with no second green flip. The spear's Stain Blade callback
uses this material rather than replacing it with the sword's material. Body
mass1.2kg matches the existing Throw Lab spear definition.

Unreal imports `Exports/ImperialSpear/Unreal/SM_ImperialSpear.fbx`. The original
FBX is retained. Strict Jolt hull creation rejected three authored UCX inputs:
six nearly redundant points were removed across hulls03/12 (largest measured
plane deficit0.0683mm), and hull16's0.15313mm-radius tip ring collapsed to its
centre without shortening the blade. All17 hulls now prepare in actual Unreal
Jolt tests. Render/control points, polygons, normals, tangents, UVs, vertex colors,
material slots and four sockets match the source exactly after the FBX roundtrip.
The repair does not change the shared solver's zero hull tolerance.

The new copy disables the sword's inherited unconditional +X test launch and
per-frame diagnostic prints. Big Throw owns launch velocity. CCD is enabled;
MACD is disabled because the existing Jolt adapter does not support it. Initial
collision object type is Sword, matching the existing flesh-exit restoration.
The copy-only finishing script sets these defaults and three node enable states;
the native installer handles the pike wiring and dimensions. No original sword
nodes or defaults were changed.

This is a spawnable spear actor for the existing Big Throw release work. The
separate throw control/pose port's projectile attachment, release and flight
integration remains a separate pending item in [ThrowControls](ThrowControls.md).
Spawn `A_Spear`; retain actor scale1 because the accepted Throw Lab scale is
already stored on its physical mesh component. Local+Z is its forward axis.
The throw controller should supply its release velocity rather than relying on
the inherited sword's removed diagnostic launch.

Verification completed October30:

- Native `Prophecy.Spear.PassThroughGeometry`, `Prophecy.Spear.NativeLifecycle`,
  `Prophecy.Jolt.HitEvents.CleanPike`, and
  `Prophecy.Jolt.Constraints.PikeWoundCorrection`: all pass. The native lifecycle
  test also confirms the original sword still stops at its hilt.
- Actual Blueprint/Jolt Play: forward exit0.2333s, withdrawal0.2s, side collision
  with zero cuts, authored matter0 resistance for2.9667s with axial motion Free,
  and flesh exit0.25s after whole-weapon clearance. Flesh reaches full blade
  stain, retains the spear texture and restores the Sword collision channel.
  Forward/withdrawal fixtures alone use zero resistance to isolate clearance;
  saved defaults remain100/10/1. All five start with zero unsolicited velocity.
- 3,991 Blueprint pins compared: nine intended connection changes, none unexpected.
  Three diagnostic nodes disabled and verified again after disk reload.
- Saved scale/material/CCD/thickness/tuning checks pass. Original A_Sword,
  PoseAgent, TestNN, explosionVFX, Throw Lab state and profile hashes unchanged.
- 17 strict Jolt collision hulls prepare; FBX visible geometry, shading, UVs,
  vertex colors, material slots and sockets exactly match the source.

Play was headless: physics, material bindings and blood-depth callbacks are
verified, not rendered Niagara appearance. Only owned diagnostic Play/editor
was closed. Shared Main Menu and other agents' builds were left alone. Later
whole-checkout build retries stalled under RAM/disk paging and were cancelled;
the spear's native source retains the successful normal-build implementation.
Final Blueprint-only corrections need no further C++ build. This evidence does
not certify unrelated source changes made by concurrent agents after that build.

Sources: `ProphecyJoltConstraintRuntime.cpp`, `ProphecyOptimisedSwordCut.inl`,
`ProphecySpearCutGeometry.h`, `ProphecySpearCutTests.cpp`, and the copy-only editor
installer `ProphecySpearSetup.cpp`. Tools are in `Tools/SpearAsset/`.

Storage follow-up October30: the owned editor is closed. Disposable NativeHost
data and `Intermediate/SpearCollisionLab` total about625MiB;580.66MiB is the
owned host's generated `NativeHost/Intermediate` cache. A no-link traversal
confirmed four junctions in NativeHost, including one back to this diagnostics
folder. Never recursively traverse the full host for cleanup without unlinking
those first. Automatic approval review rejected both whole-host cleanup and
the narrower verified cache-only deletion with "blocked by policy"; nothing
was removed. Asset/source/test receipts remain intact. No other agent's cache
or active build was touched.
