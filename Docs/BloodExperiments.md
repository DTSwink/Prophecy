# Blood experiment scene — October 20, 2026

Current user state: the user has removed the fountain. Do not recreate it in
their map. The rectangle merger was developed in the independent
[BloodDecalLab](../Labs/BloodDecalLab/README.md). The user explicitly requested
production integration on October20; the adapter below supersedes the old square
merger. The setup description farther below records the earlier created scene.

## First wound ray — October21, fixed and saved

Only Fountain001 in `/Game/_mygame/blood2/NS_bloodwound` changed. Collision now
references `/Game/Prophecy/BloodTexturePainting/Modules/WoundCollisionSync`.
Its private WoundQuerySync function uses PerformCollisionQuerySyncCPU instead
of the stock asynchronous call. All versions of these project copies are patched;
engine assets are untouched. Collision alias/input pins retained. First emitter
CPU Trace Vector Length Multiplier is1 (previously5). Local space, spawn rate,
speed850cm/s, lifetime/User.length, channels, export values and other emitters
remain authored. No gravity, sword Blueprint or physics changes.

The old collision result was stale by the time the moving head was painted.
A_DecalManager recovers a HitResult with a +/-1cm trace along the exported normal;
100/100 original sampled first-emitter exports missed. Temporary5cm search was
insufficient and removed. With synchronous collision,100/100 captured exports
hit bone head using the original +/-1cm trace. No additional runtime traces or
frame hooks; existing Niagara queries are synchronous for this emitter only.
This is a correctness fix, not a measured FPS improvement.

Current scene verification: head pike at0.233333319s, collision/queued paint at
0.283333316s (three game ticks after pike, two after first particles). Paint flush
is the following tick. First emitter alone, other Niagara transiently disabled,
produced an actual head stain using the ordinary callback. Same-view capture
with BloodIntensity0 removes the dark-red patch: sample(37,0,0) becomes orange
(228,95,18). Both emitters with normal callback start painting at the same time.
All owned tests ended; transient observers/isolation are absent from production.

Saved: two project modules, NS_bloodwound, A_DecalManager. Original +/-1 normal
retrace restored; scalar B=1 repaired to double when removing the experimental
select. Active graph links/tuning unchanged. Removed select can remain in raw
live object exports until GC but is absent from Graph.Nodes. User A_Sword edits
remain dirty. No map save/restart.

Installer: Tools/Blood/ConfigureWoundRay.py, existing console
Prophecy.Blood.WireExperiment, ProphecyBloodExperimentSetup.cpp. Editor dependencies
Niagara/NiagaraEditor added. Layout-safe Live Coding loaded after API/link repair
retries; runtime-asset installer build85.64s, final idempotence guard build109.16s.
Re-running installer leaves all saved assets clean and preserves future tuning.
Normal editor DLL remains stale for next cold launch.
Saved Niagara assets are the runtime implementation; no installer needed in Play.
Tools/Blood/TestWoundRay.py refuses existing Play. Compact evidence/backups in
Saved/Diagnostics/WoundRay; first-only baseline/sync samples, ordinary callback
tests, painted/clean head views, graph diff and save receipt. Multi-MB raw exports
and failed attempts cleaned after comparison. NS graph diff contains only the
Fountain001 Collision FunctionScript change; multiplier is a parameter-store edit.

## Sword depth stain — October21, installed

`A_Sword` has callable **Blood > Stain Blade(Depth, Seed)**, ADDITIVE:
0 adds nothing,0.5 covers at least tip to halfway,1 covers tip to hilt.
Writes Max(previous depth,Clamp(input,0,1)); smaller calls never erase blood.
The previous scalar read is an impure Blueprint call and must be on the execution
chain before the write. No automatic hit-event wiring. All24 other authored
graphs preserved verbatim across migration; compiled status3 and saved.

Seed refinement: integer Seed defaults0; MakeRandomStream(Seed) -> first
RandomFloatFromStream gives a repeatable variation, captured while previous
depth is0 and locked once positive. Same seed yields the same base angle in
[-20,+20] degrees and lateral waves at every depth; depth only translates the
edge along the blade. This lock prevents changing seeds from erasing/rearranging
accumulated coverage. Different swords can share an agent seed. New Seed pin
added to the user's existing handle-cuts call with its old pins/defaults/links
retained (only cached tooltips refreshed);23 other graphs verbatim.

Mask code: `Tools/Blood/SwordDepthEdge.ush`, copied into the material custom node.
Measured blade width is local Y [-3.5,+3.5]cm (local X is thickness). Offset is
Y*tan(angle)+.22*sin(1.1Y+phase)+.08*sin(2.8Y+1.731phase), multiplied by
abs(componentScaleY/componentScaleZ). Thus nonuniform scale does not increase
the base angle beyond20deg; wave amplitude is slight, <=.30 local cm before
scale compensation. Waves depend on Y/seed only; positive-depth coverage is
monotone.0 remains empty and1 explicitly covers the whole blade to hilt.
Existing paint-mask union/shading unchanged. Two sines/one tangent in the
material; no texture sample, trace, timer or tick added. No visual Play test.
Seed material/Blueprint saved after status3 and preservation checks. One editor
Live Coding compile action173.52s passed/no restart; no new runtime native state.
Tools: `SeedSwordDepth.py --material`, then `SeedSwordDepth.py`,
`CheckSwordDepthGraph.py --seed`, `SaveSwordDepth.py --seed`.

The function now uses existing sword blood template
`/Game/Prophecy/BloodTexturePainting/Generated/_mygame_sword_geometry_M_Sword_BloodPaint`.
Its mask is Saturate(Max(existing BloodMaskRT * BloodIntensity, blade-depth mask));
shared blood surface shading and original paint connections remain. Original
M_Sword untouched. Initial M_Sword_BloodDepth companion is superseded/unused by
the upgraded function. Local blade-Z mask uses existing blade length and
current=false hilt location converted through component transform/scale;
PreSkinnedPosition passes through VertexInterpolator for pixel-shader use.

Each call reads the current slot0 MID instead of trusting a stale cache. Already
painted swords retain the identical MID and RT. Clean swords create a MID from
the enhanced blood template. Paint manager recognizes the unique BladeBloodDepth
plus BloodMaskRT parameter pair as already paint-enabled: later collision paint
reuses the same MID and allocates its ordinary RT. ClearRuntimePaintState(true)
detaches that RT to the template default if the original/restored MID is the same
object, retaining the independent depth layer. Other materials use original
resolution paths. Arbitrary replacement materials without the blade parameters
are not supported. No traces/stamps/tick or physics edits added by Stain Blade.
No visual Play test was performed in the user's scene.

Installer: `Source/ProphecyEditor/Private/ProphecySwordBloodSetup.cpp` console
`Prophecy.Blood.InstallSwordDepth`, guarded against Play/existing function;
tools `Tools/Blood/*SwordDepth*.py`. Evidence/backup:
`Saved/Diagnostics/SwordBloodDepth` (receipt, pre-edit asset, before/after export).
Initial install Live Coding4actions454.5s. Additive migration: runtime/editor
2actions168.12s, then editor-only execution wiring repair1action77.38s; both
patched successfully, no restart. Normal DLLs remain stale: NEXT NORMAL BUILD
must incorporate the paint-manager resolver/reset changes before cold launch.
Saved Blueprint uses ordinary nodes; installer itself is not a runtime dependency.
Material migration tool `UpgradeSwordDepthMaterial.py`, Blueprint migration
`UpgradeSwordDepth.py`, checker `CheckSwordDepthGraph.py --additive` and targeted
save `SaveSwordDepth.py --additive`. Receipt records no visual Play test.

## Invisible mesh shadows — October21, user verified

User's existing active Fountain001 mesh renderer in
`/Game/_mygame/blood2/NS_bloodsplat2` now overrides its material with
`/Game/_mygame/blood2/M_Blood_ShadowOnly`: Masked, Niagara mesh usage enabled,
ShadowPassSwitch Default0/Shadow1 into OpacityMask. It renders only in the shadow
pass. Sprite renderer keeps M_blood_final for visible blood. Existing Engine Cube,
mesh scale.01 and all other authored renderer/emitter values retained; export diff
checked (only material plus ChangeId/rapid-iteration cache refresh). Material and
NS saved. User explicitly confirmed it works. Reproducible installer:
`Tools/Blood/InstallShadowOnlyMaterial.py`; evidence `Saved/Diagnostics/BloodShadows`.
For speed-dependent shadow size, mesh uses Particles.Scale (Scale Mesh Size by
Speed), separately from the sprite's Particles.SpriteSize. No extra scaling change
was made during the later pike task.

## Separate skeletal brush — October20 installed and verified

User requested a separate size for skeletal receivers. Placed **the decal manager**
(`A_DecalManager`) now exposes **Blood Paint > Skeletal Brush Radius**, default3cm.
The ordinary object's existing `brush radius` is currently2cm, preserved.
Pure skeletal-component cast/select feeds the ordinary receiver TryPaintFromHit
node6; floor node31 and instanced-mesh node5 remain unchanged. Original radius
still feeds the select's non-skeletal option. Four added nodes; all490 existing
authored pins preserved, exactly three data-pin link changes, no execution
changes. New Blueprint compiled status3 and saved; opened its editor.
Actual owned wound Play accepted127 hits: skeletal radius3, static radius2.
Test ended its own Play. Final editor14720 on explosionVFX, no dirty packages,
reflection status3/native_properties0/pin_types0. Preserved A_Sword and
NS_bloodsplat2 post-save hashes still match. Normal DLLs are current.

Existing editor setup helper is now additive/idempotent; no retained native
layout/API changes. Live Coding repeatedly exhausted commit memory.
User authorized saving their
Blueprints and restarting Unreal. Cancelled the stalled compiler; its abandoned
LiveCoding wait required matching-PDB recovery of the compile-cancelled flag
(no patch loaded). Then saved dirty A_Sword and NS_bloodsplat2, with prior-byte
backups and post-save hashes; A_DecalManager had already been preserved/saved.
Normal minimal builds passed: editor helper54.93s, callback fix75.79s, corrected
ordinary-path installer64.29s; each one compile unit plus link/metadata.
Clean-close request exposed a separate callback shutdown assertion: UObject-array
shutdown removed the listener before module shutdown removed it again. Fix uses
the existing atomic Enabled flag to unregister once and skips dead-object delegate
cleanup; no retained layout change. Included in normal DLL and isolated headless
Unreal startup/shutdown check exited0, without the assertion.
Tools/Blood/InstallSkeletalBrush.py, VerifySkeletalBrush.py, TestSkeletalBrush.py;
CheckSkeletalBrushGraph.py and InspectSkeletalBrushFinal.py verify preservation.
Saved/Diagnostics/SkeletalBloodBrush holds compact exports, receipts and backups.

## Actual floor paint — October20 repaired and visually verified

User followed the manual wiring advice; fresh inspection confirmed floor hits now
reach TryPaintFromHit. Two remaining problems were demonstrated in owned Play:
the engine template floor UV0 is tiled outside0–1 (accepted hits around7.84,−4.25
were drawn outside the RT), and the user's floor pair selected generated
M_ProcGrid instead of an MI preserving MI_ProcGrid's overrides.

Asset-only repair: placed Floor now uses project-owned
`/Game/Prophecy/BloodTexturePainting/SM_ExperimentFloor_PaintUV`, an18KB duplicate
of the engine mesh with normalized box UV0. Geometry, collision shape, transform
and original clean MI_ProcGrid remain unchanged; its grid appearance uses world
position rather than UV0. Engine source asset untouched. Existing manager pair
now selects generated `_Engine_OpenWorldTemplate_LandscapeMaterial_MI_ProcGrid_BloodPaint`,
with source scalar/vector/texture/static-switch/base-property settings retained.
Generated parent M_ProcGrid_BloodPaint force-saved too: its loaded clean package
initially had no file, so a dirty-only save was insufficient.

Verified actual wound emission in owned Play: floor hits now around0.784,0.525;
empty baseline mask became16 nonzero pixels, max255. With all foliage-grid
projectors hidden, surface stain visibly renders below the injured mannequin.
800×700 controlled capture: original material vs zero blood intensity is
pixel-identical (max/mean difference0); enabling painted mask changes3,843pixels.
All3 receiver states accepted, unsupported0. Original1024floor RT retained;
no native code, extra runtime work, build or restart. User's corrected Blueprint
wiring was preserved/saved, not rewritten. Map and material/mesh assets saved,
editor outside Play, no dirty packages at final inspection.
Tools: `RepairFloorPaintAssets.py`, `ProbeFloorPaint.py --capture` in Tools/Blood.
Compact evidence/backups: Saved/Diagnostics/FloorPaintFix (repair/probe receipts,
before-mask/floor-mask, painted/empty-mask/original captures and image-metrics).
`Prophecy.Blood.WireExperiment` now installs only the separate skeletal-radius
control above, preserving the user's corrected floor execution path.

### Earlier diagnosis and manual attempt (superseded above)

User explicitly clarified that the rectangle decals are intended for foliage;
the missing effect is the painted blood stain produced by the earlier fountain.
The decal projection repair below fixes a separate issue and does **not** resolve
this request.

Fresh read-only inspection of the live original A_DecalManager graph confirms
`NewFunction.K2Node_IfThenElse_0.then` routes to floor-grid node
`K2Node_CallFunction_10`, whose `then` is unconnected. `TryPaintFromHit`
(`K2Node_CallFunction_31`) is reached only from the failed ISM cast on the non-floor
branch. Floor hits never reach mesh paint. This separation was retained by the
experiment setup/consolidation helper. Do not attribute the omission to Niagara
or the injury emitter.

The current Floor uses MI_ProcGrid, absent from the placed paint manager's six
prepared material mappings; automatic generation is disabled. Correct repair
requires both floor painting alongside existing foliage output and a preserving
blood-enabled material pair for MI_ProcGrid. No wiring/material edits performed
in this clarified investigation. Editor outside Play, no dirty packages.
Evidence: `Saved/Diagnostics/InjuryBlood/manager-current.txt` and
`floor-paint-inspection.json`; read-only tool `Tools/Blood/InspectFloorPaint.py`.
October20 follow-up re-inspected the live graph and mappings: both omissions still
present. Opened A_DecalManager for the user's requested manual repair using
`Tools/Blood/OpenFloorPaintFix.py`. Current labels: "the decal manager",
"BloodPaintManager"; Floor still MI_ProcGrid. No wiring/material/settings changes
or Play performed. Manual repair: floor-grid exec output also calls existing
TryPaintFromHit; generate the preserving floor material with editor auto-create,
then persist its clean/blood pair on the editor-world paint manager for cooking
(PIE-generated actor array changes alone do not persist).

Subsequent callback clarification: user placed/selects a new `NS_bloodsplat`.
Its User.decal_callback referenced the A_DecalManager Blueprint asset rather than
the scene instance. Assigned the existing A_DecalManager_C_1, now labelled
**the decal manager**, through a scoped editor transaction; export confirms both
OverrideParameters.UObjects and InstanceParameterOverrides reference that actor.
No emitter tuning changes; map was deliberately left unsaved/dirty, then preserved
and saved with the user's NS edits for the necessary callback-service restart below. This does not
repair the separate floor-paint omission above. Evidence `selected-callback.txt`;
script `assign-current-callback.py` in the same diagnostic directory.

## Automatic Niagara callback — October20 installed and verified

User requests automatic setup for every spawned blood NS. New native
`ProphecyBloodNiagaraCallbacks` listens for Niagara component creation and binds
its activation delegate. Construction notifications only enqueue weak references;
the game-thread task observes completed objects and catches already-active spawns.
Activations/reused pools resolve `User.decal_callback` if the asset exposes that
object parameter. Valid explicit interface callbacks are retained; missing,
Blueprint-asset, CDO or wrong-world actor references are replaced with the world's
unique actor implementing the callback interface and owning a foliage grid
(the existing A_DecalManager). No manager is spawned automatically; ambiguous
levels require an explicit assignment.

Manager lookup is cached per world. Missing managers wait on world actor
initialization/creation events. No world/Niagara scan every frame, particle loop,
component tick or polling timer. A single initial component catch-up and teardown
scans manage delegate lifetime. Unfinished loaded objects are skipped; world/level
initialization catches loaded and streamed actor components once. Unrelated
Niagara systems remain unchanged.
No engine/plugin source modifications.

New reflected delegate receiver and startup state require a normal build/reopen.
Current user explosionVFX and NS_bloodsplat edits saved after pre-save backups;
receipt `Saved/Diagnostics/BloodAutoCallbacks/preservation.json`.
Normal incremental build passed (12 actions,365.77s); the additional loading guard
passed a one-translation-unit/four-action build59.82s. Editor26512 reopened
on explosionVFX with normal UI flags. Normal DLLs now incorporate the earlier
sword/skeleton and decal-depth Live Coding changes too.

Owned Play passed all10 checks: placed actor points to the PIE manager; automatic
spawn, delayed activation, incorrect Blueprint-asset correction, explicit valid
callback preservation, first pooled activation, attached component, unrelated
system untouched, same pool component reused, and cleared callback rebound on
reuse. Two initial diagnostic attempts ended cleanly after Python API mismatches;
the corrected script passed without native-code changes. Source/test:
`Source/GameAnimationSample3/Private/ProphecyBloodNiagaraCallbacks.{h,cpp}`,
`Tools/Blood/VerifyAutoCallbacks.py`; evidence
`Saved/Diagnostics/BloodAutoCallbacks/runtime.json`.
No streamed-level or packaged-runtime execution test performed.

Final editor outside Play, no dirty packages, correct explosionVFX map.
Post-save SHA256 values for map, NS_bloodsplat, A_DecalManager and A_Sword all match
the preservation receipt; reflection status3/native_properties0/pin_types0.
`Tools/Blood/InspectAutoCallbacksFinal.py` records the final read-only checks.
The actual floor-paint issue was subsequently repaired and verified as described
in the opening section above.

## Injury fountain invisible floor stains — October20

**Scope correction:** this section describes foliage-projector visibility only,
not the painted stains the user meant. See the unresolved investigation above.

The injury emitters correctly reference the live BloodDecalManager. Owned
explosionVFX Play recorded63 accepted floor cells,12 merged decals and no rejected
paint hits. Floor ReceivesDecals is enabled. The coloured debug rectangles showed
occupancy but did not establish that the material rendered visibly.

Root cause was the rectangle adapter's projection-depth placement: with120cm
depth and2cm surface inset, the receiver was58cm from the projector centre
(60cm half-depth). Unreal's DeferredDecal.usf depth fade
`saturate(4 - 4 * abs(normalizedDepth))` therefore reduced opacity to~0.133.
Moving the same live projectors onto the floor made the blood visible, without
changing the material, Niagara system or callback. Comparison captures are in
`Saved/Diagnostics/InjuryBlood`.

Correction centres each projector at the receiver plane plus the requested
surface offset, clamped to one quarter of projection depth so the receiver
stays inside the full-opacity region. Debug outlines still sit on the receiver
plane. XY rectangle coverage, material, pooling and budgets are unchanged;
no new per-frame work or retained layout. The regression now checks full-opacity
depth placement for zero, default and oversized offsets.

Installed through one-action Live Coding build134.49s; reload completed
13:16:19UTC with no object changes. `Prophecy.Blood.RectangleIntegration`
passed13:16:41UTC, zero warnings/errors. Final owned Play captured19 actual
injury-generated decals atZ1.5 over the floor atZ−0.5; `projection-fixed.png`
visually confirms the dark red floor stains. This final capture uses the loaded
code without runtime repositioning. No assets/materials/emission tuning/wiring
changed or saved. Sword graph remains identical. Editor29912 remains on
explosionVFX, outside Play, no dirty packages.
**Superseded build state:** the automatic-callback normal build above incorporated
this change; normal DLLs are current.
Scripts: `Tools/Blood/InspectInjuryBlood.py`, `ProbeInjuryBlood.py`,
`InspectInjuryMaterials.py`, `CompareInjuryProjection.py` (`--verify` captures
loaded behavior), `LoadInjuryProjectionFix.py`, `TestInjuryProjectionFix.py`.

## Rectangle integration — October20

The existing `UProphecyFoliageDecalGridComponent` and its Blueprint library retain
their names, pins and settings. No Blueprint graph rewiring or manager replacement
is needed: Add Floor Hit now feeds the rectangle occupancy adapter directly.
Source: `ProphecyDecalRectangles.inl` and `ProphecyDecalRectangleMesher.h` beside the
existing component implementation. The kernel is byte-identical to the tested lab.

- A dirty region partitions into rectangles; repeated occupied hits do no remeshing.
  Regions are at most32×32 cells. MaxMergeLevel values below5 reduce that region
  size; values5+ use32. This is bounded greedy partitioning, not a global optimum.
- Actual Hit receiver component/instance, plane normal and plane height separate
  occupancy. Direct position/normal calls use their own plane identities.
  Sloped planar floors use an orthonormal receiver basis. This remains a stationary
  floor projector system; arbitrary curved surfaces and moving receiver paint
  belong to the existing mesh-paint path.
- Correct half-extents replace doubled projectors. Existing material, color, sort,
  fade-screen size, cell size, origin and padding are preserved. Surface offset
  is now clamped within the full-opacity depth region (see the injury-fountain
  repair above). Debug outlines match actual padded widths and label
  **width × height cm**.
- Existing merge interval/budget and per-pass limits bound dirty-region processing.
  At most16 new components are registered per pass. Hidden pooled preparation
  retains the old complete footprint until replacement is ready; components
  are reused. The timer is removed when idle or capacity-blocked; no component tick.
  A budget is soft, since a single allocation/publication can exceed it.
- MaxActiveDecals caps owned projectors, region count and surface count. At capacity,
  pending occupancy is retained and reported instead of evicting old blood.
  Raising the cap and calling Process/Start processing resumes it.
  MaxStainedPointsScannedPerPass is retained for asset compatibility but no scan is
  needed. Changing cell size/origin/region size starts a fresh grid on the next hit.

Stored native layout changed, so this required a normal build/restart.
Preserved the user's dirty explosionVFX and A_Sword, with pre-save backups and
post-save hashes; A_DecalManager asset is untouched. Six-action incremental normal
build111.80s passed. `Prophecy.Blood.RectangleIntegration` passed10:40:53UTC with
zero errors/warnings: actual projector coverage/half-extents, rectangular hole,
negative cells, repeated hits/reuse, separate receivers/heights, sloped floor,
capacity recovery, cold allocation cap and cleanup. Normal editor29952 reopened
explosionVFX. A brief owned Play exercised the actual placed original manager:
16 cells became one102×25.5cm projector (100×25cm occupancy with the user's1.02
padding). Owned Play ended; no graph/asset changes from verification. Saved map,
sword and original manager hashes match the preservation receipt. No GPU or
production frame-time improvement is claimed from these functional checks.
Compact evidence: `Saved/Diagnostics/BloodRectangleInstall`.

Reopen October20: incremental target already up to date (2.64s, no compilation).
Editor29912 opened explosionVFX normally; remote check confirmed outside Play,
no dirty packages and the existing rectangle-manager settings. No assets changed.

Map: `/Game/explosionVFX`. The `Blood Experiment` Outliner folder contains:

**Current manager consolidation — October20, 04:59 UTC:** user requested that
the sword and blood effects share the original manager. `A_DecalManager` now has
the same two repaired execution routes and disconnected per-hit print as the
experiment copy. The placed experiment instance was replaced by
`BloodDecalManager` of the original class; all nine Blueprint variable values and
22 editable floor-grid settings were preserved. Sword's existing class lookup
returns exactly one actor, with valid paint-manager and floor references.
No placed Niagara components remained at migration, so no callbacks needed
redirection. New emitters should reference this placed BloodDecalManager.
The old experimental Blueprint asset and its unsaved edits remain untouched.
The original manager Blueprint is compiled/saved; explosionVFX is deliberately
initially left dirty, then saved with the user's current edits for the subsequent
October20 pre-impact-node restart. The replacement is now persisted in the map.
No Play started, no visual staining retest, no sword wiring edit, no restart.
One-action editor-helper Live Coding passed136.38s/reloaded04:57:53UTC; normal
DLLs were stale until the subsequent pre-impact-node normal build.
`Prophecy.Blood.WireExperiment` is now a legacy-named command
that repairs the original manager. Before/after authored-pin comparison confirms
only the intended ten pin changes (including disconnected reroutes).
Evidence: `Saved/Diagnostics/BloodManagerConsolidation/receipt.json`.

The setup below describes the earlier experiment fixture; the user has since
removed its emitters and the manager replacement above supersedes its class/name.

- `BloodFountain`: placed Niagara actor using the existing `NS_bloodarc`, with
  a RotatingMovement component (yaw rate 45 degrees/second). The component's user
  parameters control spawn rate (500), velocity (500 cm/s), arc angle (45 degrees)
  and duration. Duration is 86400 game seconds for sustained experiments, not an
  infinite-loop modification of the shared Niagara asset. `User.decal_callback`
  references the placed experiment manager.
- `BloodExperimentManager`: `/Game/Prophecy/BloodExperiments/BP_BloodExperimentManager`,
  copied from the current `A_DecalManager`. References the current Floor and
  BloodPaintManager. The original Blueprint is unchanged.
- `BloodPaintManager`: existing BP_BloodPaintManager with its prepared material
  pairs, plus the prepared BasicShapeMaterial pair. Automatic material generation
  and mask-debug display are disabled.
- `BloodFluidRendering`: copied from the old `vfxmap` fluid controller, retaining
  its appearance settings. Blood particles use custom-depth stencil 42.
- Three BasicShapeMaterial blocks for vertical-surface paint experiments.

The old `/Game/vfxmap` still exists, but had no placed fountain. Its managers and
fluid settings were inspected read-only. Current A_DecalManager's ordinary mesh
paint execution was disconnected: failed ISM casts went to the floor grid, and
the actual floor branch ended at a disconnected reroute. The dedicated copy
routes floor equality to AddFloorHitToFoliageDecalGrid and failed ISM casts to
the already-wired TryPaintFromHit node. Existing ISM promotion remains unchanged;
per-hit diagnostic printing after the floor call is disconnected in this copy.

Editor-only command `Prophecy.Blood.WireExperiment` reproduces these graph edits
on the dedicated copy only. Source:
`Source/ProphecyEditor/Private/ProphecyBloodExperimentSetup.cpp`.
One-action Live Coding build passed (213.59 seconds), reload completed
03:29:00 UTC, Blueprint compiled status 3. No runtime native class/layout changes
or editor restart. The normal editor DLL now predates this helper; use the minimal
normal build before the next cold launch.

Runtime checks use actual Niagara exports, not synthetic blood-hit calls. Rotation,
sustained emission, floor-grid cells and two painted mesh states were observed,
with zero unsupported paint hits. This is functional validation, not a frame-time
benchmark. The existing floor grid can accumulate many cells under continuous
emission; no performance improvement or universal material support is claimed.
New receiver materials still need a clean/blood material pair on the manager.

Compact setup scripts and runtime counters:
`Saved/Diagnostics/BloodSetup20261020/`. A small pre-change map backup is retained.
Temporary text exports of the source map, Niagara and Blueprint were removed
after inspection. No shared Niagara/Blueprint, existing bomb or character tuning
was intentionally edited. User changes made during setup were preserved.

Follow-up: the user's new NS_bloodsplat had User.decal_callback set to the Blueprint asset, not the placed actor. Corrected both component override stores to the placed BloodExperimentManager; export verified. Emission tuning unchanged, no Play started; map deliberately left dirty for the user's current editing session. Select the Outliner actor for this object parameter, not the Content Browser Blueprint.
