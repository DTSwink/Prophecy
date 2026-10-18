# Bomb fuse and prepared fragmentation

October18 installed and verified in the interactive editor, on explosionVFX.

## Fragment fade — installed and verified, no restart

Light Bomb Fuse adds Fragment Fade Duration, default1 authored second. Fragments
retain their original material until the final fade window of Fragment Lifetime,
then opacity interpolates1→0. Duration0 retains abrupt expiry; duration longer than
lifetime is clamped to the whole lifetime. Lifetime/cleanup timing is unchanged.
One new non-ticking optional component holds settings and the shared MID, preserving
the existing bomb/controller native layouts for Live Coding. The existing cleanup
tick performs one opacity write per explosion, not20 per-fragment ticks. Physics
continues through fading; expiry destroys all pieces and the cleanup owner.

Real translucent companion M_BombFragmentFade/MI_BombFragmentFade is derived from
the imported glTF material family without changing original assets. At detonation,
current bomb textures/scalars/vectors (including dynamic overrides) copy into one
shared MID. The current Bomb and PressureBomb share the prepared static shader
configuration. Arbitrary alternative shader families/static permutations are not
automatically recompiled: translucent materials may supply FragmentOpacity directly;
otherwise the runtime warns and preserves their original appearance/expiry. It does
not silently replace a different material with the bomb shader. Fully opaque versus
translucent rendering can differ during fading, especially shadows/sorting.

Minimal Live Coding5 compile actions passed452.06s; reflection reload completed
16:07:27UTC (one new fade class, changed library,19 unchanged classes). No existing
native component/Agent/world layout changes. Existing unrelated Niagara deprecation,
duplicate-test and .voltbl diagnostics occurred; reload and verification succeeded.
The user briefly started Play during compilation, then explicitly stopped it before
reload. Native20-argument call verified; current A_Bomb package pins refreshed by
reloading only its clean preserved package. Blueprint compiles, saved bytes match
the preservation receipt, agent reflection status3/native_properties0/pin_types0.
No wiring edits or unrelated saves. Original materials unchanged; two derived assets
saved in the already cooked BombGenerated directory. All nine effective static
switches match Bomb and PressureBomb; live scalar/vector/texture values copy at detonation.

Prophecy.Bomb.FuseAndDetonation passes16:07:51UTC including shared material/no extra
tick, half opacity, exact zero endpoint, physical fragments and cleanup, plus existing
fuse/VDB/force/toggle cases. Owned rendered Play check passed239 samples with current
PressureBomb: lifetime4s/fade2s stays solid through tick120, fades121–239, destroys240.
Solid/half screenshots inspected: actual transparency and retained green material.
Fragments were deliberately spread/frozen for this visual comparison only; production
physics remains unchanged. No claim of arbitrary shader/static-permutation support.

Editor6904 remains on explosionVFX/outside Play. User dirty explosionVFX and newly
authored NewNiagaraSystem left untouched. Base DLLs need minimal normal build before
the next cold launch, including this fade and preceding fragment-toggle/impact patches.
Evidence Saved/Diagnostics/BombFragmentFade; preparation CreateFragmentFadeMaterial.py
and owned visual check VerifyFragmentFade.py under Tools/BombFuse.

Fragment toggle follow-up: Light Bomb Fuse adds Spawn Fragments, defaulttrue.
False skips loading the20 prepared meshes and spawning debris/cleanup controller;
the VDB and physical blast still execute for timed and instant detonation.
The existing Fragments array carries the choice (empty means no debris), so this
adds no retained native storage and can load via Live Coding without restart.
Live Coding3 actions passed286.30s; patch_0 and reflection reload completed
15:22:44UTC. Native test passes15:23:03UTC for enabled/default20 fragments and
disabled timed/instant paths, including VDB and actual physical force. No cleanup
controller is created for an empty fragment list. Native19-argument call accepted;
Python wrapper doc remains stale after Live Coding, so use reflected call_method.
Existing A_Bomb needed its old pin list refreshed: reloaded only its clean,
freshly preserved package, then compiled successfully15:25:12UTC and reopened its
asset tab. No editor restart or manual wiring edits. User map/PressureBomb dirty
state preserved. Handled RigVM/MTAccessDetector ensures and .voltbl diagnostics
occurred during reload; subsequent verification passed. Minimal normal build
required before next cold launch because base DLL predates this checkbox.
Evidence: Saved/Diagnostics/BombFragmentsToggle (preservation, native-reflection,
build-summary, verification-log and final-status). Editor6904 remains open.

## Flexible fuse extension — installed and verified

Current extension reuses UProphecyHolsterStrapComponent's native five-body
AnimDynamics solver, collision-free and separate from the bomb's original collider.
New SK_BombFuse preserves original triangles/UV0, fixes the shell to the root,
and skins only the fuse. UV1 still controls progressive clipping. The separate
body slot takes the original component's current material; its pointer is checked
while active, so body material changes now follow during the burn too.

- Set Bomb Fuse Stiffness prepares flexibility before ignition or changes the
  spring while burning. Default20, zero floppy, higher stiffer (cap10000).
- Light Bomb Fuse adds optional Fuse Sparks, advanced Spark Rotation Offset,
  and Instant Explosion. Null sparks means no Niagara allocation or fallback.
  +X points outward along the current deformed fuse at the burn cut. Tracking
  happens after skeletal evaluation; only two ring centers/four skin transforms
  are evaluated per active spark update. It uses the same weights as the mesh.
- Hide Bomb Fuse permanently clips all fuse geometry for that runtime instance,
  stops dynamics and destroys its spark component. It does not cancel a timer.
  Calling stiffness or ignition again cannot reveal it. Hidden/unlit components
  stop ticking; a later timer call resumes only the timer/controller.
- Instant Explosion is synchronous, ignores burn speed (zero accepted), and can
  override an ongoing timer. A fresh instant explosion skips flexible mesh and
  Niagara creation. It still uses all VDB/force/fragment settings.

Dynamics inherits the strap's distance/global gates and teleport reset. The tiny
cosmetic chain retains its full length internally while rendering is clipped;
this is secondary animation, not a contact-capable rope simulation. On normal
detonation the spark system is deactivated and its existing particles may finish;
permanent hide destroys it immediately. Use finite particle lifetimes in effects.

Build: saved user's current A_Bomb and PressureBomb plus generated skeleton,
then native-layout restart. Repeated Slate shutdown error occurred after saves;
editor exited itself. Six-action normal build succeeded in139.46s, incorporating
all earlier bomb Live Coding patches. Editor6904 open on explosionVFX normally.
User dismissed the startup low-drive-space dialog; no further restart or patch.
Receipt/build/rig/probe evidence: Saved/Diagnostics/BombFuseFlexible. Reproducible
asset tools: BuildFlexibleRig.py (background Blender), ImportFlexibleRig.py.
Verification:323 owned Play samples,179 spark alignment samples; maximum tip
error4.72e-7cm, minimum outward tangent dot0.9999999999999987. Soft/stiff samples
show different motion; fixed root exact, all poses finite. Permanent hide stops
skeletal ticking, removes Niagara and remains hidden through stiffness/ignition
calls; timer can be overridden by synchronous instant detonation. Empty Niagara
creates no emitter. Body material follows the user's PressureBomb override.
Rendered flexible-burning.png and hidden-fuse.png reviewed. The white particles
are the temporary engine Fountain template used only in the owned test, not an
effect assigned to the user's Blueprint or a default fallback.

Combined native test passes15:07:42UTC, including physical force, full20-fragment
material/velocity checks, cleanup, timing and the new controls. Caveat: the first
isolated test immediately after cold startup failed its20 fragment-velocity
assertions. The unchanged binary passed after Play initialization; a separate
actual Play fixture checked all20 velocities directly (max error3.11e-5cm/s).
Cold isolated-world initialization is suspected, not proven; retain both outcomes
in automation-results.txt. The first visual probe sampled a moved actor on a
paused screenshot frame; the probe now samples advancing game time, without
changing runtime tracking, and the full run passes. These are not runtime fixes.
User A_Bomb/PressureBomb saved bytes match the pre-build preservation receipt;
no graph wiring or tuning edits. Agent reflection status3/native_properties0/
pin_types0/wiring_preserved1. All owned Play sessions ended; no dirty packages.
Earlier implementation notes below are historical where superseded here.

Requested node: Light Bomb Fuse, accepting the original CC0 bomb StaticMeshComponent,
fuse burn speed (world cm per60 unpaused ticks), fragment radial launch velocity
(cm/s), all Start Explosion controls and all Spawn VDB Effect controls. Detonation
follows the moving bomb's current shell centre; no stale ignition location. The
original actor is consumed, with20 closed shell fragments and one VDB spawned.
Fragments inherit the original body's linear/angular point velocity and receive
the selected radial velocity. Advanced Fragment Lifetime defaults8 authored seconds.

Material inheritance follow-up: fragment spawning reads the original component's
effective material slot0 at detonation and assigns that same material to all20
pieces. This respects mesh defaults, component overrides, and dynamic instances,
including replacements made after ignition. No per-frame polling, copying or new
material instances. Each fragment keeps the material referenced after the original
actor is destroyed. The burning visual still uses the prepared fuse material;
arbitrary body-material replacement is not mirrored onto that masked visual.
Loaded through implementation-only Live Coding patch_1 (one compile action,
198s), reload14:36:40UTC/no object changes. Combined test passes14:37:05UTC
with a dynamic instance replaced after ignition and identity checked on all20
fragments. Editor remains explosionVFX/outside Play/no dirty packages. No restart
or assets/wiring edits. Minimal normal build required before the next cold launch
to incorporate both this runtime correction and the earlier baker correction.

The original imported mesh/material and user A_Bomb graph remain unmodified.
Ignition attaches a visual-only derived mesh while retaining the original collider;
GPU masking follows baked curved-fuse distance in UV1. Vertex colors stay white
to preserve glTF shading; opacity-mask cutoff is .333 (the source used zero).
No emissive burn front or emitter: user explicitly deferred Niagara until later.
At original scale its exposed length is9.83355cm, default burn speed2cm/s.
Uniform/nonuniform scale is accounted for at ignition; subsequent scaling does
not change that already selected burn duration. Repeat ignition is rejected.

Twenty shell pieces are prepared offline from the actual outer triangles, with
.22cm inner thickness and closed boundary walls, original UVs/material, and cooked
convex collision. No runtime fracture/mesh cooking or per-tick geometry changes.
Debris uses UE rigid bodies/CCD and ignores PhysicsBody collisions to prevent
adjacent pieces exploding against each other; world/Pawn collision remains enabled.
The physical blast uses the existing Jolt Start Explosion contract on already
admitted bodies, including PhysicalMesh; it does not create or drive a Jolt world.
Blast fires before fragments are created so their launch speed is not double-hit.
Travelling blast arrival continues to use the original simulation clock.

New generated assets: /Game/_mygame/BombGenerated, explicitly cooked.
Tools/BombFuse/PrepareGeometry.py consumes the read-only exported LOD0 mesh and
writes compact Geometry.json plus ProphecyBombGeometry.h. BakeAssets.py invokes
the editor-only native asset builder; CreateMaterial.py copies the entire glTF
material override chain and adds the mask without altering imported assets.
VerifyMaterial.py finalizes UV1 masking, disables emission and saves derived materials.
Runtime loads/pins required assets at ignition, with no disk load at detonation.
Controller retires on consumption; one debris cleanup controller retires at expiry.

Physical blast port: the five-file production.patch from the retained October18
explosion bundle was applied cleanly to main. The separate impact-event extension
remains PAUSED and was not copied. This wrapper includes VDB AND physical force,
as explicitly clarified by the user.

Build/save status: current A_Bomb and explosionVFX edits saved before the required
normal native-layout restart. Backup/receipt in Saved/Diagnostics/BombFuse. Editor
hit a shutdown window-destruction error after successful saves and exited; no
force-kill used. Normal minimal build passed (33 dependency actions,538.92s,
including installing the physical explosion library and shared Jolt state).
The final editor-only mesh-baker correction (UV1 instead of vertex-color progress)
loaded with layout-safe Live Coding patch_0:1 compile action,208.32s. Patch/reload
completed, no object changes detected. Live Coding emitted .voltbl linker diagnostics
but reported success; subsequent actual bake and tests passed. Base runtime DLL
includes all runtime behavior, but predates this baker correction: perform the
minimal normal build before the next cold launch. No further restart needed now.

Verification after final rebake:
- Prophecy.Bomb.FuseAndDetonation passes at14:24:59UTC: invalid/repeated ignition,
  authored-tick fuse endpoint, actual native Jolt blast,20 simulated fragments
  with selected radial velocity, one VDB, fragment cleanup, delayed wave arrival.
- All20 prepared shell meshes have closed manifold edges.
- Owned rendered Play captures show original appearance, progressively shortened
  fuse with no glow, and outward fragments/VDB. Visual test completed and ended.
- Editor6804 remains on /Game/explosionVFX, outside Play, no dirty maps/content.
- Original mesh/material and preserved A_Bomb/map hashes unchanged. Agent BP
  reflection native_properties0/pin_types0/status3/wiring_preserved1.

Evidence in Saved/Diagnostics/BombFuse: verification-log.txt, visual-result.json,
fuse-start.png, fuse-half.png, detonation.png, geometry-verification.json,
final-status.json and preservation-verification.json. Source preparation is
reproducible with Tools/BombFuse; no packaged-build validation claimed.
No user Blueprint wiring added: connect the original StaticMeshComponent to Bomb
and call once. Defaults are documented in ProphecyBombLibrary.h.
