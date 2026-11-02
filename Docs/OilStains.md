# Oil bottles and slippery surface patches

October 24, 2026. Implemented in the normal editor DLLs. Work is contained in
`/Game/_mygame/Tests/Oil/M_OilTest`; existing gameplay maps and the running
WeaponWheelLab were left alone. No push or shipping build was requested.

## Use

**Current accepted bottle appearance, October24:** the user approved the liquid
shown in `Transmission/front-plain.png` and explicitly requested no further liquid
changes. Its saved material now uses transmission(.72,.32,.018), opacity0,
roughness.035, specular.45 and screen refraction1.003. Absorption uses a bounded
refracted cylinder chord (radius4.85cm/base.7cm), compensating the engine's
thin-sheet1/NoV term. This is an inexpensive cavity approximation, not traced
multiple-interface optics; extreme tilt/shoulder fill is not an exact optical
volume. No textures, captures, collision or CPU tick were added to the material.
The initial1.035 refraction trial visibly narrowed the liquid; it was rejected.

The remaining broken black lines at the glass base were isolated with glass-only
A/B: unchanged liquid, glass hidden, glass refraction off, softer grazing coverage,
and reduced refraction. Refraction was responsible; changing EdgeCoverage did not
remove the doubled contour. **Glass RefractionStrength .01→.001** removes the
detached rim strokes in front/oblique1200² captures. Every other glass setting,
the accepted liquid, cork, bottle/debris geometry and physics are preserved.
`GlassBase/receipt.json` verifies the protected assets' SHA256 hashes. Only the
glass material was saved for this final correction; no map save or native build.
Current previews: `GlassBase/glass-base-fixed.png` and `glass-base-oblique.png`
under `Saved/Diagnostics/Oil/Bottle/`. Older videos are physics evidence, not the
current optical appearance. The empty bottle wall was not thickened.

Material-editing caveat: deleting native-constructor-loaded liquid expressions
hit Unreal's !IsRooted assertion in the owned offscreen editor before saving.
Recovered in a new owned editor; the upgrade now reconnects existing parameters
and ThinTranslucent output instead of deleting rooted expressions. The small old
disconnected calculation is not evaluated. OilLiquidOpticsVersion2 makes the
upgrade idempotent and preserves subsequent user material edits. The exact
approved liquid was saved before the glass-only A/B; it was not retuned.

Latest October24 correction, after the user's golden-oil reference: cold-spawned
bottles were still using M_OilDroplet. The previous Blueprint-CDO assignment of
OilInside.LiquidMaterial was lost on compilation (native subobject has no editable
Blueprint variable/template). Prior videos therefore do NOT demonstrate the
dedicated oil shader, even though it existed. ProphecyOilLiquid.cpp now supplies
M_OilBottleLiquid as the native default; the constructor lookup is cached, not
per-tick. A deliberate None override still selects the droplet fallback. No new
layout/header change. Normal incremental build:4 actions,57.33s. Cold-launched
StudioPhoto and actual-PIE StudioReview now assert the real material path.

Lighting now covers the whole scene: movable directional1500lux at(-55,-25),
source angle5°, sky intensity10, specified reflection cubemap brightness40,
background emission100 and lighter neutral floor(.22,.225,.23). Strip lights
reduced500/300; fixed EV7 remains. Empty glass now reflects a lit environment
instead of black outside the local light pools. The accepted splash/puddle
material is unchanged. The prior transmission(.99,.45,.015) was rejected as
flat/waxy and is superseded by the accepted material above. Its native1080p
video `Studio/golden-oil-1080p.mp4` remains earlier physics-test evidence only.

October24 studio / smooth-edge revision supersedes the ghost-glass experiment.
The Fab bottle and all20 fragments had reversed render winding. Fixed the saved
meshes without changing collision shapes/material slots, and corrected the final
UE export in PrepareBottle.py. Manifold fracture/volume calculations retain their
original winding. FixBottleWinding.py is idempotent via OilWindingVersion metadata.
This restores the cork's solid top and outward-facing glass surfaces.

BottleMaterials.py is the current recipe. Glass is one-sided Thin Translucent /
Surface Forward Shading: root Opacity0, neutral transmission(1,1,1), roughness.08,
specular.25. SSR is disabled on this material; direct lights/reflection probes
remain. FragmentOpacity controls SurfaceCoverage and refraction fade.
Grazing SurfaceCoverage blends from EdgeCoverage.2 to1 between NoV.02 and.22,
softening the dark contour where the shell's interfaces overlap in projection.
This is an artistic thin-shell approximation, not a physical multiple-interface
transport model. IOR1.52 with RefractionStrength.001 gives effective IOR1.00052; this
is controlled screen-space distortion, not physically traced glass. Full1.52
screen offsets produced duplicate corks and missing offscreen content. Cork is
Default Lit / masked dither, brown(.10,.048,.018), roughness.82, specular.18,
procedural mottling and sparse pores with derivative-filtered edges;
FragmentOpacity fades its mask. Existing accepted splash/puddle materials stay
unchanged. InstallBottle.py preserves existing user materials if already present.

StudioSetup.py saves lighting only in M_OilTest: specified small procedural HDR,
rect/strip lights, fixed EV7, neutral floor, scene-local SSR/GI overrides. The
enclosing background uses a dedicated mesh with no collision geometry and actor
collision disabled: merely disabling its component collision was insufficient
in the review fixture and contaminated the initial physical drop. Removed that
interference; controlled release matches the original tick199 impact again.
No global scalability/config is saved. Capture enables refraction and explicit
TemporalAA show flags (the user's disabled AA otherwise left pixelated edges).

October24 follow-up to the user's enlarged screenshots: old footage was960×720.
The current capture is native1920×1080 with explicit TAA quality6 and CRF16:
`Saved/Diagnostics/Oil/Bottle/Studio/golden-oil-1080p.mp4`, with a1920×1920
hero.png and compact test/receipt JSON. No video upscale. Capture-only AA does
not override the user's saved scalability. At1920×1920, same-camera A/B separated
glass-only, oil-only, refraction-off and specular-off: refraction.04 produced
broken lower-edge patches, reduced at.01; dim grazing shell coverage removes the
remaining dark stroke. The old claim that AA alone fixed all edges was too broad.
StudioReview.py holds/moves the real
bottle for3 authored seconds, then releases it to Jolt; no manual BreakBottle.
ComposeStudioVideo.py adds an explicitly labelled0.4x replay. ClearBottleReview.py
is disabled to prevent accidentally restoring the obsolete glass recipe.

Place `BP_OilBottle` from `/Game/_mygame/OilBottle`. Its native **Bottle** component
uses the existing Jolt static-mesh adapter. It breaks when an incoming Jolt hit
exceeds **Break Impact Speed** (default250cm/s). This is relative closing speed at
the contact before solving, including both objects' rotation; not impulse or
post-bounce speed. Gentle resting contacts do not accumulate toward breakage.
Set **Launch On Play** and **Launch Velocity**, or disable launch and throw it
using the component's existing physics functions. **Break Bottle** also works
explicitly. A `ProphecyJoltFightSetup` actor is required in the world, as in the
other Jolt scenes. The test map already has one.

New placements have **Launch On Play** off. The two test-map demonstrations keep
it on. **Break On Hit** disables automatic breaking, leaving **Break Bottle**
available. **Last Impact Speed** is readable on surviving instances for tuning.
There is no intact-bottle actor Tick or impact polling/timer. Automatic impact
measurement requires Jolt, as does the surface oil system. The separate cosmetic
OilInside component below updates only while the liquid moves or settles.

### Oil inside the bottle

Native **OilInside** is a small collision-free procedural mesh inside the glass,
with a damped free surface. **Liquid Material** defaults to M_OilBottleLiquid,
the accepted chord-absorption material described above. The previous constant-tint
and NoV-squared versions are superseded. Early pale screenshots actually used
the fallback droplet shader; the initial attribution to the NoV term was wrong.
Lighting/background reflections still vary, as expected for transparent oil.
Clearing the override
falls back to **Oil → Droplet Material**. It disappears with its owning bottle
at break; it does not add a fluid simulation, contact body, trace or texture.

Component controls: **Fill Amount**0–1 (default.65), **Slosh Strength**0–2
(default1, horizontal acceleration response), **Slosh Damping**.1–2 (default.4).
Call **Refresh Liquid** after changing fill/material at runtime; Fill Amount0
hides it and disables its tick. Rotation follows gravity with a damped lag.
One authored second remains60 game ticks. Translation/rotation wake it through
the existing component-transform notification; it disables its component tick
after settling. No idle polling/timer. The bottle actor itself remains tickless.

An inscribed48-sided/11-ring cavity keeps the oil inside this specific Fab bottle.
Smooth side normals and rounded lower rings remove the earlier polygon bands;
the actual free surface remains planar. Render winding now matches Unreal.
The fill plane preserves volume even on inversion; ordinary tilts through the
cylindrical body use an exact constant-volume shortcut. Extreme tilts entering
the shoulder/base use12 bounded bisection steps. One fixed-topology draw (maximum
3,168triangles, most unused slots degenerate) is updated only when the surface
changes, with no mesh topology/collision rebuild. This is a cheap visual
approximation, not a fluid-pressure solver. A replacement bottle shape needs a
matching cavity profile. Source: Private/ProphecyOilLiquid.{h,cpp}.

Studio capture measured132 active mesh updates: median0.397ms, p950.569ms,
max0.666ms CPU update/enqueue; max sampled volume error0.000117% of capacity.
This is one moving bottle on the laptop, not GPU or many-bottle performance.
Tick still retires at rest. Native implementation rebuilt normally in4 actions
(one module compile + links/metadata,56.22s); current DLLs include this revision.

Owned tests/capture: Tools/Oil/TestLiquid.py and ComposeLiquidVideo.py; receipts
under Saved/Diagnostics/Oil/Bottle/Liquid. They test conservation, inversion,
settling, movement wake and empty retirement using deliberately scripted bottle
motion. They do not claim the scripted motion is Jolt dynamics. Two low-priority
single-thread encoders, one owned offscreen editor, no gameplay-map saves.

Final liquid verification:9 checks pass; maximum sampled volume error below.05%
of capacity (ordinary tilts approximately.0001%).342 mesh-update measurements
in the busy offscreen editor: median136.6us,95th194.7us,maximum9.426ms. These are
CPU update/enqueue wall times, not a GPU or many-bottle benchmark; stopped oil
has no component tick. Do not extrapolate them to a100-bottle budget. Normal
incremental build and BP save passed. All owned processes are closed. Final
8second two-view preview: Liquid/oil-inside-preview.mp4; temporary captures and
raw view movies cleaned. The video uses controlled motion for visible settling;
inversion and empty retirement are additionally checked in test.json.

**Debris** class/instance variables: **Spawn Fragments** (true), **Fragment
Velocity** (120cm/s radial addition), **Fragment Lifetime** (4 authored seconds,
including fade), **Fragment Fade Duration** (1 second, capped to lifetime), and
**Fragment Meshes** (20 prepared pieces). Zero lifetime or disabling fragments
suppresses them. Zero fade duration gives abrupt expiry. Pieces inherit the
incoming COM/angular motion and the bottle's current effective material slots,
including component overrides/MIDs. They use actual Jolt rigid bodies. One clock
per broken bottle updates two shared material opacity values during the final
fade, then destroys every piece and itself. No fracture work is done at runtime.
Custom replacement materials should expose scalar **FragmentOpacity** to support
fade; otherwise their original appearance is preserved until lifetime expiry,
with a log warning. The supplied glass/cork materials already support it.

Assets are together under `/Game/_mygame/OilBottle`: Blueprint at root,
`Meshes`, `Debris`, `Materials`, and `VFX` (including `NS_OilDroplets`). Small
redirectors remain at previous test paths for existing references/tools. Test
fixtures/map remain under `/Game/_mygame/Tests/Oil`; gameplay maps are untouched.
The source is [Milk Bottle by mokbulsd](https://www.fab.com/listings/adc6b678-4635-4c62-a686-7771d1e8e2ca),
downloaded with the user's explicit Fab EULA approval. The exterior is26cm high
(27.735cm including cork); the separately exported cork was seated on the mouth.
An inner glass cavity and19 watertight Voronoi pieces plus the cork are baked
offline. Glass volume is preserved within0.0001%. Collision uses a128-vertex
bottle hull and at most64vertices per fragment: maximum measured convex inset
1.313mm for the bottle,0.857mm for pieces, with visible geometry unchanged.
Each piece uses a convex collider rather than simulating its concave thin shell.
Oil landing rays ignore actors tagged `OilBottleFragment` before narrow-phase
intersection. This prevents the burst from landing on its own temporary debris
and allocating a mask/decal pair per shard. It does not change physical contacts
or ordinary ray queries. Other meshes, limbs and landscape still receive oil.
Source and attribution: `Tools/Oil/Source/`; deterministic preparation:
`PrepareBottle.py` (numpy/scipy/manifold3d3.5.4), guarded editor installation:
`InstallBottle.py`. Generated geometry JSON is disposable/reproducible.

October24 verification:10 real Jolt gameplay checks pass (gentle contact,
hard hits, automatic/manual modes, exact20pieces/bottle, fragment opt-out,
default and live MID material inheritance, fade and cleanup). Seven existing
query tests pass; filtered-query assertions additionally verify that an ignored
foreground convex reveals the surface behind it, including rays starting inside
that convex, and that unfiltered queries remain unchanged. Final two-bottle
recording has3 coating groups/109patches and cleans to zero at660ticks. Identical
one-time pushes give216.915cm wet-cube travel vs15.134cm dry.20piece physics is an
intentional temporary cost; this is not a many-bottle stress benchmark.
Evidence: `Saved/Diagnostics/Oil/Bottle/` (test.json, defaults.json, bake.json,
FilteredQuery/index.json, Video/recording.json); final24second preview
`oil-bottle-preview.mp4`. Owned test processes are closed; no user editor was
restarted. Earlier null-RHI placement test hit an engine viewport divide-by-zero
before gameplay; offscreen rendered tests replaced it. All final normal DLLs are
current. No shipping test or push was requested.

The **Oil** settings are editable per bottle or in Blueprint defaults:

| Control | Meaning / default |
| --- | --- |
| Radius | Bottle burst spread / direct-spill sampling radius in cm; test bottle150, native180, range10–600 |
| Slipperiness | 1 removes contact friction; 0 leaves it unchanged |
| Hold Duration | 4 authored seconds at full strength, measured from the last landing in a connected puddle |
| Fade Duration | 4 authored seconds fading to completely dry |
| Decal Material | Editable `M_OilPlaceholder`, clear glossy coating; None hides the sheen |
| Tint Material | Optional `M_OilTint`, a very faint yellow color layer; None removes its component/cost |
| Droplet Material | Editable `M_OilDroplet` for the airborne sheet; None hides the sheet, keeping landing logic |
| Droplet Count | 56 collision/coverage samples per bottle, bounded8–64; includes the sheet samples |
| Splash System | Test bottle uses `NS_OilDroplets`; None hides the cosmetic spray. Edit its burst count/size/speed in Niagara |

**Spawn Oil Spill** creates the same effect directly from a location, unit
surface normal and settings. Split the settings pin to expose individual controls.
**Get Oil Amount** returns the current 0–1 fade. As elsewhere in Prophecy,
one authored second is 60 unpaused game ticks; lowering FPS slows the whole effect.
The coating uses **OilCoverage**, **OilAmount**, **OilRoughness** and
**OilSpecular**. OilCoverage is a shared body-local union mask, sampled with
decal UV.yx; threshold at0.5 and multiply by OilAmount in replacements.
The sheen has no Base Color or Normal output. A separate tint material blends
only3.5% toward pale yellow per connected puddle (`OilTint`, `TintStrength`);
existing surface color, patterns and detail remain visible. Touching splats on
the same compatible surface share one mask and fade clock, including separate
bottles. Overlaps do not accumulate tint or retain extra gloss during fading.
New landings refresh that connected puddle; disconnected puddles fade separately.
Irregular edges
and short landing expansion replace the former dark circles. The airborne
material is translucent pale gold with a Fresnel response. Niagara renders the
small cosmetic droplets; the old radial-burst template is no longer assigned.

Bottle breaking now starts a short ballistic liquid burst. Stains and native oil
patches are created only when individual drops hit the actual Jolt surfaces.
There is no initial large footprint and no scripted patch under the character
in the review/demo. Direct Spawn Oil Spill remains an explicit immediate surface
placement API. The detailed diagnostic TestScene can still place deliberate
coverage fixtures; it is not the review recording.

## Physics and cost

Oil changes Jolt's combined friction only at covered contacts. It does not replace
body materials, change mass, disable collisions, or permanently grease an object
that crosses a puddle. Limbs use the same contact path. Full coverage at strength1
gives zero friction; boundary contacts average the covered manifold points.
Overlapping patches use the strongest amount rather than adding friction changes.
Fade restores the body's ordinary combined friction progressively.

The splash uses a filled sheet with a center and three rings. At the default56
samples,49 belong to the sheet and7 form its free fringe. Each sheet sample follows
its own ballistic path and actual surface trace. Overlapping landing radii cover
the interior densely; an irregular ring shape keeps the edge uneven. Sheet points
share an180cm/s launch arc with a small ripple, instead of the former110–200cm/s
center-to-rim speeds that left a nested puddle beneath an airborne rim. The sheet
no longer expires at20ticks. On actual contact, each sample transfers its area
directly to full-size wet coverage and stops drawing the airborne overlay there.
Free fringe drops retain their six-tick landing expansion. The sheet is removed
after its last airborne part lands; it does not sit on top of the wet coating.
Display-only interpolation smooths the rim: at most193vertices/320triangles,
one extra draw, no extra collision queries. Interpolation becomes linear at
landed samples to avoid curve overshoot below the surface. The shared droplet
material must respect vertex-color alpha. Counts below13 use separate drops only.

The former large native instanced droplets and strands are removed. An editable
Niagara system, `NS_OilDroplets`, bursts360 smaller cosmetic sphere particles.
The mesh renderer faces local X along velocity and scales it with speed, making
ellipsoids. `SM_OilDroplet` reduces the engine sphere to12.5% of its triangles;
`M_OilNiagaraDroplet` is separate from the accepted sheet/coating materials.
This is a bounded CPU Niagara burst with no collision module, rigid bodies,
particle readback or extra deposits. Lifetimes are0.52–0.75 authored seconds.
The existing56 native samples still decide landing and staining, including7
free fringe drops. Cosmetic droplets are not individually authoritative impacts.
One manually advanced solo Niagara component runs per burst, at1/60 per game
tick; it is removed on completion (90tick safety cap). Deferred first-use asset
preparation catches up to the current authored age without blocking physics.

The sheet's display now curves upward toward a five-lobed rim: low center,
raised outward petals, then collapse to the actual contact surface. It keeps
the same193vertices/320triangles and traced landing paths. No extra surface
queries or separate strand meshes. The world-down gravity module in Niagara
also works when the effect is oriented to a tilted surface normal.

Bottle droplets have no physical rigid bodies. Only live
airborne drops perform a native segment ray per authored tick; they stop on the
first hit or at120ticks. Flight arrays are released when the last airborne
sample finishes; the independent cosmetic Niagara component also expires.
Each landing creates one small contact patch, skipping
deposits wholly contained in an existing fresh patch. Cost is bounded by the
configured count, with no fluid simulation or GPU readback. Fade is shared within
each connected puddle. A spatial hash finds touching patches on the same native
body, with matching materials and compatible surface planes. Their irregular
outlines are rasterized into one512x5128-bit union mask (256KiB). Overlap writes
coverage rather than adding opacity. One sheen decal and optional color-only
decal share that mask, transform and fade. Masks update only during landings,
six-tick spreading or removal; settled fade changes only the shared scalar.
Moving receivers update one transform per connected group. Global per-world
ownership lets merged puddles outlive any one contributing spill actor; removing
the last patch releases the components, mask and spatial entries.
The earlier performance numbers below exclude these visual costs and the
increase from24 to56 droplets; this is not a claim of zero additional GPU cost.

The explicit direct-spill API still uses nine bounded surface samples. A coplanar
footprint on one body collapses to one contact patch; uneven/interrupted receivers
use up to nine. Settled oil does not raycast.
Body-local spatial buckets make contact lookup local; normal and depth tests
prevent a patch from affecting the underside or another floor. Patches follow
moving receivers and are removed with destroyed bodies. Static patches do not
read body transforms each tick. Only active spill actors tick; expiry removes
patches, decals and ticks. The oil contact listener is removed when no longer
needed by oil or the existing hit/protection systems.

Landscape collision is imported from the actual cooked heightfield triangles,
including its holes, into Jolt's existing static mesh BVH. This happens on collider
admission, not per frame. Fully holed snapshots prepare an empty shape. This uses
body-level physical materials, as the existing static mesh importer does;
different physical friction for individual Landscape paint layers is not added.
Streaming/sculpting large production Landscapes and multiplayer remain untested.

The current cap is 4096 physical patches per world. Spatially concentrated,
overlapping puddles still increase contact lookup, though compatible overlap now
uses one shared rendered mask. Large connected footprints spread the fixed mask
resolution over more area. Separate native bodies or incompatible planes/materials
stay separate; this is not an arbitrary mesh UV atlas. The measurements
below are not a claim that thousands of patches are free. Custom
Niagara/material costs are separate.

## Evidence and replay

Latest airborne revision: `Saved/Diagnostics/Oil/NiagaraFlower/Angles/oil-splash-three-angles.mp4`,
18seconds,1280x720,60fps,1,634,918bytes. Three cameras (overhead,22cm above the
floor,angled), each normal speed then labelled1/3speed replay. All six capture
checks pass. Sampled native cube positions/velocities and landing/coverage/fade
counters exactly match the prior accepted recording. Wet travel224.782719cm,
dry15.133747cm after the same single push. Full decode passed; visual review
confirmed Niagara droplets and the raised rim. `NiagaraFlower/verification.json`
pins source/video hashes. These are authored-speed captures, not a frame-rate
benchmark. No new whole-scene GPU timing claim is made.

`CreateNiagaraSplash.py` authors editable built-in Niagara modules through the
installed Cascade converter editor API (`-EnablePlugins=CascadeToNiagaraConverter`
in that owned setup process only). There is no runtime converter dependency.
Its explicit rebuild flag replaces its generated NS; do not use it over future
user edits without preserving them. `WireNiagaraSplash.py` assigns only the spray
slot, copies rather than mutates a borrowed settings struct, and explicitly saves
the isolated bottle BP/map. `RecordVideo.py -ProphecyOilNiagaraFlower` and
`ComposeAnglesVideo.py --niagara-flower` reproduce this review.

`Prophecy.Jolt.Oil.ContactAndPerformance` plus the three existing StaticBody
tests passed, zero failures/warnings. Native tests cover wet/dry/faded friction,
other bodies/floors/normals, overlap, live friction restoration, unchanged material,
moving/rotated receivers, destruction, stale identities and empty terrain preparation.

On this machine, six alternating passes with 100 awake contact bodies measured
mean **0.148655 ms dry / 0.181468 ms with oil** per full Jolt update: about
**0.033 ms added**. Setup and game-thread velocity writes are excluded; this is
physics cost, not total frame/GPU cost, and predates the revised droplet renderer.
Its flight and decal rendering costs are not included. Spatial lookup averaged 0.048915 µs with
64 patches and 0.056985 µs with 4096 spread-out patches. A body launched at180cm/s
ended the one-second friction test at0 dry,101.52 with90% oil,180 fully oiled.

The real map test runs1800 unpaused ticks: actual bottle hits, static floor,
raised deck, moving/rotated crate and a PHAT mannequin; shared visual/physical
fade and complete cleanup. All64 Landscape comparisons match UE queries:
60 solid hits and4 holes, with no mismatch. Splash components also expire.
Images and compact reports are in `Saved/Diagnostics/Oil/`.

- `Tools/Oil/CreateTestMap.py`: guarded initial asset/map preparation in an owned
  `-ProphecyOilSetup` editor. Refuses completed maps.
- `Tools/Oil/TestScene.py`: guarded `-ProphecyOilCheck` Play test; owns and ends only
  its separate process's Play. `-ProphecyOilFinalize` explicitly saves only this
  test map's bottle placement/editor view. Ordinary replay does not save assets.
- `Prophecy.Oil.Probe [Push|Move]`: explicit non-shipping audit, restricted to this
  map's game world; no background sampler. Push compares wet/dry sliders;
  Move rotates/translates the coated crate.
- Native core: `ProphecyJoltOil.h`, `ProphecyOil.cpp`; editor terrain fixture:
  `ProphecyOilTestMap.cpp`.

Builds used the normal incremental target. `-NoHotReloadFromIDE` bypassed UBT's
shared executable-name mutex from the separate WeaponWheelLab only; no main game
editor was running, no Live Coding was used, and the UI lab was not closed.

## Review videos — October 23

The initial rejected review is `Saved/Diagnostics/Oil/Video/oil-test.mp4`: 30 seconds, 1280x760, 30fps,
1,860,017 bytes. Real synchronized SceneCapture2D views of mesh floor and Landscape;
identical slider/limb push at two seconds, then hold and fade. Placeholder visuals.
Captured every two unpaused game ticks and presented at authored 1x speed; this
is a behavior recording, not a real-time frame-rate benchmark. A separate owned
offscreen editor loaded the saved test map without saving or changing assets.

The revised recording uses `Tools/Oil/RecordVideo.py` with `-ProphecyOilVideo`
and this test map. It records only the actual bottle bursts, with no synthetic
patches or test pushes. `Tools/Oil/ComposeVideo.py` presents mesh then Landscape
at authored1x. `Tools/Oil/RefineAppearance.py` requires `-ProphecyOilRefine` and
edits only the feature's isolated assets/map. It preserves a small initial backup.
Repeated material cleanup is necessary: UE's DeleteAllMaterialExpressions
mutates the array it iterates, leaving some old nodes on its first pass. The
script now asserts zero old nodes and no coating BaseColor/Normal connections.
PNG chunk/CRC
validation strips stale bytes after IEND from Unreal's reused export buffers.
The initial900-frame H.264 fully decoded without errors. The revised recording
also checks airborne-before-stain ordering, multiple landing ticks, fade and
complete cleanup; its receipt is under `Saved/Diagnostics/Oil/Revision/Video/`.

Final revised video: `oil-revised.mp4` in that folder,22s/660frames,1280x720,
30fps,2,006,121bytes. Decoded end-to-end successfully. Camera makes a20degree arc
to show the moving reflection under the test scene's softboxes. All four recording
checks pass; the separate1800tick headless regression also passes all11checks,
including direct planar placement, PHAT limbs, moving receiver, terrain and cleanup.
The final incremental build was4actions/51.42s, normal DLLs current. User editor
and WeaponWheelLab were not closed. Intermediate frames/video streams removed.

Reference: Epic's [decal material documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/decal-materials-in-unreal-engine)
describes separate color/normal/roughness channels. Local UE5.7 material/decal
source was checked as well; no global rendering/scalability changes were made.

## Bright outline correction — October 23

The user accepted the revised liquid/coating but noticed a thin white outline.
`CheckEdge.py` compares the original edge, two smooth ramps, pixel-sized AA,
hard coverage and a narrow ramp at the identical paused240tick pose. Each
shader compilation finishes before capture. Wider ramps made the rim brighter:
DBuffer blends roughness, so the transition passes through intermediate
roughness values that reflect the softbox across a ring. There is no raised
rim geometry, normal map or emissive outline. UE5.7 `DBufferDecalShared.ush`
line509 confirms the roughness interpolation.

`FixEdge.py` changes only the coating opacity expression to
`step(0.0175, edge-length(p))*Amount`. This preserves the old50% footprint and
the existing uniform fade, without the spatial roughness blend. Frozen mesh
and Landscape comparisons retain the gloss with the bright ring removed.
Native physics, droplets, timing, roughness/specular controls and receiver
materials are untouched. No extra texture/pass, native build or user-editor
restart. The initial material bytes and compact application receipt are in
`Saved/Diagnostics/Oil/Edge/`. `RefineAppearance.py` includes this correction
for future asset recreation; do not run that broader script for this narrow fix.

## Fuller splash and tint review — October 23 (before shared coverage)

`Tools/Oil/SplashAppearance.py` (`-ProphecyOilSplash`) edits only the droplet/tint
materials, bottle defaults and isolated map. The sheet fades through vertex alpha,
leading drops emerge as it thins, and shorter droplet stretch avoids long capsules.
The translucent material includes a small warm fill to avoid a dark overlapping
burst in this lab's lighting. This is a cheap authored splash, not a fluid solver.
Clear coating/outline correction is unchanged. Tint is optional and independently
editable. Compile the bottle BP before changing its CDO defaults, construct a
fresh settings value, and explicitly Modify/save: changing the previously read
struct in place before compilation did not persist the new tint reference.

Final incremental build4actions/62.73s passed after the initial6action/136.81s
reflection build. Normal DLLs are current. A cold1800tick scene test passes all12
checks, including tint/coating transforms on moving receivers, saved settings,
PHAT, Landscape and cleanup. The final660tick capture checks sheet creation and
retirement, flight before landing, staggered deposits and complete fade/cleanup.
`RecordVideo.py -ProphecyOilSplash` uses a closer camera for splash readability;
`ComposeVideo.py --splash` produces `Saved/Diagnostics/Oil/Splash/Video/oil-splash.mp4`:
22s,1280x720,30fps,2,148,387bytes. Full decode passed. Current user editor/UI lab
untouched; small receipts/asset backups and final videos retained, transient
captures removed. Native physics-only performance evidence remains as reported
above; no new whole-frame performance claim is made.

## Shared coverage correction — October 23

The subsequent review showed darker yellow overlaps and individual crossing
splat outlines during fading. The old sheen/tint layers alpha-blended separately;
even identical roughness accumulated differently in overlapping faded areas.
`ProphecyOilCoverage.cpp` now owns connected union masks across spill actors.
`UnionAppearance.py -ProphecyOilUnion` updates only the two isolated coating/tint
materials, retaining color, gloss and airborne splash. It is idempotent. Older
appearance recreation tools produce the historical individual shape masks;
run UnionAppearance last after any full recreation.

The final normal incremental build passed4actions/47.44s. A subsequent explanatory
source comment does not change the tested compiled behavior. `UnionCheck.py`
in an owned `-ProphecyOilUnionCheck -nullrhi` editor passes8/8 checks: initial and
final cleanup, cross-actor union, no settled mask rebuild, shared fade, surviving
owner removal, refresh from new liquid and independent disconnected-puddle fade.
`TestScene.py` passes all12 existing checks, including moving receivers, PHAT
limbs, direct flat placement and all64 Landscape comparisons.

`RecordVideo.py -ProphecyOilUnion -ProphecyOilVideo` and `ComposeVideo.py --union`
produce `Saved/Diagnostics/Oil/Union/Video/oil-union.mp4`:22s,1280x720,30fps,
2,067,473bytes. Full decode passed; full-strength and mid-fade frames on both
surfaces were inspected. All recording checks and sheet lifetime checks pass.
112 native patches become8 coverage groups/16 decal components instead of224.
The live-group rebuild count remains122 at ticks120,180 and360; settled fading
does not rerasterize/upload masks. At660 all patches, groups and decals are gone.
Those counters and reduced component count are not a whole-frame FPS benchmark.
The fixed512 masks use about2MiB for those8 groups, excluding render-resource
overhead. Strongly curved/different-body/material charts stay separate.

Compact receipts are `Union/union-check.json`, `scene.json`, and
`Union/Video/recording.json`. Two small material backups remain in `Union/before`;
raw video streams and PNG buffers/check frames were removed. Both user UI labs
were preserved. No user editor restart, gameplay-map change or push.

## Sheet landing and cube physics review — October 23

The latest revision replaces the fixed20tick sheet with the contact-driven
center/three-ring sheet described above. Default56 samples are redistributed
into49 sheet points and7 free drops; the sample/query cap is unchanged. A smoother
render mesh adds no collision samples. The initial version was rejected for a
nested sheet/puddle silhouette: the center landed well before the rim, and its
coating was visible through a differently shaded sheet. Final sheet samples share
the same180cm/s vertical launch with a small ripple; on contact their full area
transfers to the coating and their airborne overlay stops immediately. Only free
drops grow their individual splats. The result is a connected main puddle on the flat
test floor instead of a sparse ring of disconnected deposits. It remains a
ballistic visual approximation, without liquid pressure/viscosity simulation.

Final normal incremental build:4actions,51.46s, normal DLLs current. Final cold
`TestScene.py` run completes1800ticks and passes all12 checks: bottles, oil life,
cleanup, moving surfaces, limbs, direct planar placement, optional splash,
tint/coating alignment and Landscape (60hits +4holes, no mismatches).

`RecordVideo.py -ProphecyOilLanding -ProphecyOilVideo` captures the isolated map
with mesh, Landscape and dry-control views. Both existing cubes receive a single
150cm/s X push at tick180 via `Prophecy.Oil.Probe SlideDemo`; native Jolt handles
all subsequent motion. No continuous drive or artificial oil coverage is added.
After150ticks/2.5authored seconds the wet cube travels224.7827cm versus15.1337cm
dry. It slows normally when leaving the puddle. The recording passes all6 checks
plus sheet creation/retirement, and shows deposits at ticks48,54,60,66,72 with
the last active sheet at60. The two bottles produce109 physical patches in3
coverage groups/6decal components. Mask rebuilds stay at28 from120 through360;
all patches/groups/decals are gone at660. The recorded40.69ms of raster work is
cumulative during formation, not per frame; no new whole-frame timing claim.

`ComposeLandingVideo.py` produces
`Saved/Diagnostics/Oil/Landing/Video/oil-sheet-landing-and-physics.mp4`:
22s,1280x720,30fps,1,826,770bytes. It includes the landing, synchronized wet/dry
cube comparison, fade and Landscape. Full decode and landing/comparison frames
were checked. Receipts: `Landing/Video/recording.json`, `video.json`,
`Landing/verification.json`, `Landing/build.log`, and the final `scene.json`.
Own raw streams and PNGs are removed after review; earlier final videos retained.
No assets, Blueprint wiring or maps changed this revision; both user UI labs
were preserved and owned diagnostic processes exited. Nothing pushed.

## Airborne droplets and three-angle review — October 23

User accepted the stains and asked to restore visible droplets above the sheet.
The final change touches only instance display transforms:38 sheet beads and7
free drops at the default count, within the original56 slots. A trial with
straight connecting strands was rejected and removed. No Niagara system,
additional queries, deposits or physics state. Normal incremental build passed
4actions/47.08s; normal DLLs current. No user editor closure or asset/map edits.

`RecordVideo.py -ProphecyOilAngles -ProphecyOilVideo` records every unpaused tick
through180 at60fps, then continues the owned simulation to660 for lifecycle and
physics verification. Cameras: overhead420cm, near-floor22cm, existing angled
view. `ComposeAnglesVideo.py` shows each at normal speed then a labelled1/3speed
replay. Output `Saved/Diagnostics/Oil/Airborne/Angles/oil-splash-three-angles.mp4`:
18s,1280x720,60fps,1,206,983bytes. Full decode and camera frames checked.

All6 recording checks pass. Against the accepted Landing recording, landing
ticks, sheet retirement, coverage/lifetime counters and every sampled wet/dry
cube position/velocity are identical (maximum delta0). This confirms preserving
the accepted ground/physics pipeline; it is not a new total GPU-time benchmark.
Receipts: `Airborne/verification.json`, `Airborne/Angles/recording.json` and
`video.json`. Raw clips/PNGs cleaned; final videos and compact evidence retained.
Both user UI labs preserved; owned capture exited. Nothing pushed.
