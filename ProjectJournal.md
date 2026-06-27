# Prophecy Project Journal

Keep this file tight. Preserve only goals, rules, keeper settings, important paths, current working state, and next actions. Full historical archives live in `Docs/old/`.

## Current State

- Project path: `C:\Users\singerie\Documents\Unreal Projects\Prophecy`.
- Unreal project: `GameAnimationSample3.uproject`, Launcher UE `5.7`.
- Git remote: `https://github.com/DTSwink/Prophecy.git`.
- Latest pushed commit should be checked with `git log -1 --oneline origin/main`; avoid treating this journal as the moving hash source.
- Git preservation rule: push everything needed to reconstruct the project if local files are lost. Include source code, journal notes, helper scripts, config, hand-authored data, and small source assets/textures through LFS when needed.
- Do not push bulky or recoverable Unreal output by default: `Binaries/`, `Intermediate/`, `DerivedDataCache/`, screenshots, logs, autosaves, and generated `Content/` assets that can be rebuilt by opening Unreal or rerunning tracked scripts. If an added asset cannot be reconstructed from tracked source/scripts, track it.

## Blood VFX Runtime Stain Renderer

- 2026-06-25 decision: stop trying to auto-author Blueprint/Niagara graph nodes from Python. UE 5.7 exposes the Niagara Data Channel runtime API to Python/C++, but the K2 `Write Data Channel` node and normal graph pin/node mutation APIs are not exposed enough for safe automatic Blueprint graph edits.
- 2026-06-25 decision: prototype the cheap persistent blood renderer as native runtime source in `GameAnimationSample3`, not an external plugin. The project already has a runtime C++ module and already depends on Niagara.
- 2026-06-25 decision: avoid deferred decals for the heavy stain path. Thousands of decals are the performance problem being investigated, so the prototype renders small stain triangles through one preallocated procedural mesh component.
- 2026-06-25 decision: avoid runtime `AddInstance`/`UpdateInstanceTransform` for the prototype. The user measured progressive hitches there, so `AProphecyBloodStainRenderer` preallocates triangle slots and rewrites vertex data in batches.
- Runtime class: `Source\GameAnimationSample3\Public\ProphecyBloodStainRenderer.h`.
- Runtime implementation: `Source\GameAnimationSample3\Private\ProphecyBloodStainRenderer.cpp`.
- Editor wiring commandlet: `Source\ProphecyEditor\Private\ProphecyWireBloodStainCommandlet.cpp`, run with `-run=ProphecyWireBloodStain`.
- Integration options:
  - Direct Niagara export callback: spawn/use `AProphecyBloodStainRenderer` as the object assigned to the export data interface callback handler user parameter.
  - Existing Blueprint callback path: from `Event Receive Particle Data`, call `AddBloodParticleDataToWorld(Data, Simulation Position Offset)`. The renderer assumes `FBasicParticleData.Position` is hit position and `FBasicParticleData.Velocity` is hit normal, matching the current `NS_bloodsplat` convention.
- Current renderer defaults: `MaxStains=30000`, `DefaultRadiusCm=7`, `ParticleSizeToRadius=0.5`, `SurfaceOffsetCm=0.35`, vertex-color material fallback `/Game/Prophecy/Materials/M_ProphecyBloodVFX_Surface`.
- Verification: `GameAnimationSample3Editor Win64 Development` builds successfully. `Saved\ProphecyVerifyBloodStainRenderer.py` loaded the reflected classes, spawned a temporary renderer, accepted 24 synthetic stains, flushed the procedural mesh, and destroyed the actor without errors.
- Wiring verification: `UnrealEditor-Cmd -run=ProphecyWireBloodStain` succeeded and saved `/Game/_mygame/blood2/A_DecalManager`. It inserted `AddBloodParticleDataToWorld` into the existing `ReceiveParticleData` exec chain before the prior Blueprint logic, so the old graph can keep running while the native renderer receives the same hit batch.

## Blood Runtime Texture Painting

- 2026-06-26 decision: current long-term path for large static/Nanite surfaces is per-component render-target mask painting, not decal spam and not runtime vertex painting. This preserves Nanite/static mesh geometry and moves persistent blood to a material-sampled texture mask.
- Fast iteration path: keep the editor open through `Saved\StartProphecyEditorBridge.ps1` on port `8765` and run editor Python scripts through `/python`; avoid cold boot commandlets for every visual ping.
- Project setting enabled in `Config\DefaultEngine.ini`: `[/Script/Engine.PhysicsSettings] bSupportUVFromHitResults=True`.
- Generated material/validation script: `Saved\ProphecyCreateBloodTexturePaintingAssets.py`.
- Generated assets:
  - `/Game/Prophecy/BloodTexturePainting/MF_BloodPaintMaskBlend`
  - `/Game/Prophecy/BloodTexturePainting/M_BloodBrush_Circle`
  - `/Game/Prophecy/BloodTexturePainting/M_BloodPaint_RuntimeTest`
  - `/Game/Prophecy/BloodTexturePainting/M_Test_BloodMaskBlend_Clean`
  - `/Game/Prophecy/BloodTexturePainting/M_Test_BloodMaskBlend_FullBlood`
  - `/Game/Prophecy/BloodTexturePainting/BP_BloodPaintManager`
- Runtime manager source:
  - `Source\GameAnimationSample3\Public\ProphecyBloodTexturePaintManager.h`
  - `Source\GameAnimationSample3\Private\ProphecyBloodTexturePaintManager.cpp`
- Runtime manager actor: `AProphecyBloodTexturePaintManager`. Existing Blueprint/Niagara hit handling should call `TryPaintFromHit(HitResult, BrushRadiusWorld, Intensity, OverrideMaterialSlot=-1)`. It validates `StaticMeshComponent`, calls `FindCollisionUV`, lazy-allocates one `RGBA8` RT per component/material slot, swaps to a blood-enabled MID, queues stamps, and flushes with one `BeginDrawCanvasToRenderTarget` / `EndDrawCanvasToRenderTarget` per RT.
- Clean objects still use their original material. First paint swaps only the hit slot to a blood-enabled material template. Production meshes should map clean materials to blood-enabled equivalents through `BloodEnabledMaterialPairs`; the generated `M_BloodPaint_RuntimeTest` is only a proof/template and does not preserve arbitrary original material graphs.
- Current proof uses UV0 because Engine basic cube/plane meshes have predictable UV0. Production paintable assets should use a unique non-overlapping paint UV channel, usually UV1, and set both manager `PaintUVChannel` and the blood material texture coordinate accordingly.
- Milestone A/B/C/D/E/F and preliminary G visual evidence:
  - `Saved\BloodTexturePainting\BrushRT_white_disk.png`
  - `Saved\BloodTexturePainting\MF_BloodPaintMaskBlend_clean_vs_fullblood.png`
  - `Saved\BloodTexturePainting\M_C_RT_after_first_hit.png`
  - `Saved\BloodTexturePainting\M_C_Mesh_debug_mask.png`
  - `Saved\BloodTexturePainting\M_C_Mesh_final_blood.png`
  - `Saved\BloodTexturePainting\M_D_Nanite_RT_after_hit.png`
  - `Saved\BloodTexturePainting\M_D_Nanite_blood_hit_result.png`
  - `Saved\BloodTexturePainting\M_E_RT_batched_stamps.png`
  - `Saved\BloodTexturePainting\M_E_Mesh_batch_debug_mask.png`
  - `Saved\BloodTexturePainting\M_F_BudgetLimit_triggered.png`
  - `Saved\BloodTexturePainting\M_F_BudgetLimit_triggered.txt`
  - `Saved\BloodTexturePainting\M_G_stat_unit_clean.png`
  - `Saved\BloodTexturePainting\M_G_stat_unit_100_painted.png`
  - `Saved\BloodTexturePainting\M_G_stat_unit_1000_painted.png`
  - `Saved\BloodTexturePainting\M_G_burst_stamping_stats.png`
  - `Saved\BloodTexturePainting\M_G_editor_stress_1000_painted.png`
  - `Saved\BloodTexturePainting\M_G_editor_stress_summary.json`
- Validation logs: `FindCollisionUV` returned changing UVs on the test plane (`0.15/0.225`, `0.5/0.5`, `0.85/0.775`). Runtime proof accepted a center hit at UV `(0.5, 0.5)`, created one `512x512` RT, flushed one stamp, then flushed five queued debug stamps in one pass to the same RT (`states=1 queued=0 flushed=5 dropped=0 unsupported=0`).
- Nanite proof: generated `/Game/Prophecy/BloodTexturePainting/SM_BloodPaint_NaniteCube` from the engine cube and enabled Nanite with `fallback_relative_error=0`, `fallback_percent_triangles=1`. The first screenshot failed visually because UE had to set `bUsedWithNanite` on the generated materials during capture. `Saved\ProphecyCreateBloodTexturePaintingAssets.py` now sets `MATUSAGE_STATIC_MESH` and `MATUSAGE_NANITE` on generated surface materials before saving; rerun then produced a visible Nanite blood hit.
- Budget proof: validation forced `MaxActivePaintRTs=1`; first object paint was accepted, second object paint was rejected without allocating another RT. The manager logged `paint budget exceeded`, reported `states=1 queued=0 flushed=1 dropped=0 unsupported=1 estMB~1.0`, and the screenshot shows only the first target painted.
- Milestone G editor stress proof: `Saved\ProphecyValidateBloodTexturePaintingRuntime.py` can capture `clean`, `100`, `1000`, and `burst` performance phases with prompt-named PNGs. The editor pass spawned 1000 test cubes, then painted per-object `64x64` RT masks. Recorded timings in `M_G_editor_stress_summary.json`: spawn clean grid `9.014s`, queue 100 stamps `0.015s`, flush 100 `0.0008s`, queue remaining 900 `0.100s`, flush remaining 900 `0.0095s`, queue 512-stamp burst into one RT `0.0034s`, one capped burst flush `0.00035s`. The burst correctly processed 64 stamps and left 448 queued, matching `MaxStampsPerRTPerFrame=64`.
- Milestone G caveat: automation created files named `M_G_stat_unit_*.png` and overlays the manager counters/timings onto the screenshots, but UE viewport `stat unit`/`stat gpu` text was not captured by the camera screenshot path. Treat this as editor stress/batching evidence, not final packaged gameplay/GPU profiler proof.
- 2026-06-26 live test note: accepted-hit spam from `bDebugPrintHits` and on-screen debug messages is not representative of paint cost and should be off for perf testing. Runtime manager source now defaults debug hit printing/drawing off and adds `SetDebugMode(bEnabled, bShowMask)` for one-switch Blueprint control after the next C++ rebuild. The live scene manager was also reset to quiet mode with `DebugPrintHits=false`, `DebugDrawHitLocations=false`, `DebugShowMaskOnPaintedMaterials=false`, `FlushEveryTick=true`, `DefaultBrushSizePixels=28`, and RT heuristic restored to `256/512/1024`.
- Write-overhead diagnosis: the burst frame cost is expected to come from UV lookup traces/`FindCollisionUV`, first-hit RT allocation + clear + material swap, and render-target flush work (`BeginDrawCanvasToRenderTarget`/brush draws/`EndDrawCanvasToRenderTarget`). The cost is worst when a burst touches many different components/RTs in one frame; many stamps on one RT are cheaper because they batch into one canvas pass up to `MaxStampsPerRTPerFrame`.
- 2026-06-26 queue guarantee: `MaxStampsPerFrame` and `MaxStampsPerRTPerFrame` are write-rate throttles, not deletion limits. Accepted stamps beyond the per-frame budget remain queued in `PendingStampsByStateKey` and are reported as `deferred` until later flushes draw them. Transient canvas/RT failures now defer the queue instead of clearing it.
- 2026-06-26 editor material automation: `AProphecyBloodTexturePaintManager` now has editor-only auto-generation checkboxes. With `bEditorAutoCreateBloodMaterials=true`, unmapped plain `UMaterial` assets are duplicated into `/Game/Prophecy/BloodTexturePainting/Generated`, blood mask nodes are injected before BaseColor/Roughness, the material is saved if `bEditorSaveGeneratedBloodMaterials=true`, and the clean->blood pair is cached in `BloodEnabledMaterialPairs`. `bUseDefaultBloodMaterialTemplateForUnmappedMaterials` now defaults false so the system does not silently use the generic test material. Smoke test generated `_Engine_BasicShapes_BasicShapeMaterial_BloodPaint` from the engine basic material and painted a centered RT stamp.
- 2026-06-26 material instance automation: `UMaterialInstanceConstant` assets are now supported by recursively generating a blood-enabled parent material, duplicating the source instance, reparenting the duplicate to the generated parent, and saving the generated instance. Real-scene test on `rock3` (`/Game/Fab/Megascans/3D/Rock_shopk/Medium/shopk_tier_2/Materials/MI_shopk`) generated both the Fab parent blood material and `MI_shopk_BloodPaint`; the RT write and visible stain were confirmed on the rock.
- 2026-06-26 overwrite-prompt guard: generated blood materials are now treated as reusable cache assets by default. Missing generated materials are still created automatically, but existing generated materials are only regenerated if both `bEditorAutoUpdateBloodMaterials` and `bEditorAllowGeneratedMaterialOverwrite` are enabled. This avoids overwrite dialogs during live fountain/blood tests.
- 2026-06-26 shared blood surface function: generated blood-enabled materials now call `/Game/Prophecy/BloodTexturePainting/MF_BloodPaintSurface` for the blood-only surface values: base color, roughness, specular, metallic, and world-position noise tint. The generated materials blend those outputs over the original material with `BloodMaskRT * BloodIntensity`; the paint manager only feeds `BloodMaskRT`, `BloodIntensity`, and `DebugShowBloodMask`. Existing generated paint materials were rebuilt after the C++ compile, including the engine basic shape material and `MI_shopk`/Fab parent cache. Future edits inside `MF_BloodPaintSurface` propagate through normal Unreal material recompilation without regenerating every paint material.
- Current limitations/caveats:
  - Static/Nanite static mesh path only. Skeletal, landscape, ISM/HISM unique per-instance masks, and overlapping/repeating UV assets need fallback.
  - Multi-material meshes can pass `OverrideMaterialSlot`; C++ also tries `GetMaterialFromCollisionFaceIndex`, but production assets still need validation.
  - Debug mask view is lit and slightly blue because the proof material is Default Lit; the exported RT is the authoritative black/white mask check.
  - Nanite fallback-mesh UV validation has only been proven on the generated Nanite cube. Test with a real Nanite rock/tree asset before relying on it for hero foliage/rocks.
  - Full performance proof still needs real profiler captures from PIE/standalone/packaged gameplay: clean scene, 100 painted objects, 1000 painted objects, and heavy burst with visible `stat unit`/`stat gpu` or an exported stats trace.

## Product Goal

- Build a full Roman-age battle sim with at least 100 active characters in view and room to scale.
- Performance is the hard constraint. Optimize animation, AI, movement, rendering, LOD, update frequency, memory layout, and runtime data flow together.
- Use regular C++ classes as the foundation. Avoid high-overhead UE gameplay frameworks such as Behavior Trees and `AIController` for mass logic unless a UE feature proves faster than a reasonable custom system.

## Core Runtime

- Main benchmark actor: `Source\GameAnimationSample3\Private\ProphecyNNCrowdBenchmark.cpp`.
- Main header: `Source\GameAnimationSample3\Public\ProphecyNNCrowdBenchmark.h`.
- Launch with `-ProphecyNNBenchmark`.
- Useful profiles include `CharactersFloorShadows` and `GrassField`.
- Useful visual modes: `Skeletal`, `InstancedFull`, `Instanced`, `InstancedLite`, `MetaHuman`.
- `InstancedLite` is a non-skeletal proxy path using one instanced static mesh component and batched transform updates.

## NN Animation

- User NN work lives at `C:\Users\singerie\Documents\Cursor\stepper`.
- Current usable checkpoint folder: `C:\Users\singerie\Documents\Cursor\stepper\training\runs\20260518_034323_big_mixedk_doubleae_oldfootslide_continue_from_last\checkpoints`.
- Runtime ONNX path: `Content\Prophecy\NN\stepper_checkpoint_last_b100.onnx`.
- Training data uses a UEFN-style 30 FPS skeleton. Prefer `SKM_UEFN_Mannequin` over Manny.
- `FProphecyNNPoseStore` and `UProphecyNNPoseAnimInstance` provide the thin native pose path.
- Production crowd NN inference should run on UE NNE ORT DirectML (`NNERuntimeORTDml`) on GPU. CPU inference (`NNERuntimeORTCpu`) is debug/fallback only.
- Audit reference with floor/lights: empty scene `114.58 FPS`, 100 invisible moving agents on CPU `72.05 FPS`, 100 invisible moving agents on DirectML/GPU `98.80 FPS`.
- Default benchmark target: 100 agents, 30 Hz NN update, DirectML GPU inference, batched pose work where possible.

## MetaHuman Tiers

- Production source character is assembled MetaHuman `/Game/MetaHumans/Kellan/BP_Kellan`.
- The old placeholder MetaHuman is only a test harness and must not be used for production visual judgment.
- User-facing tier names are only `Full`, `Mid`, and `Far`. Clothing/face/groom switches are diagnostics or implementation details.
- Current `Far`: Kellan BP at MetaHuman/LODSync far LOD, body driven by `UProphecyNNPoseAnimInstance` with reference translations preserved, grooms hidden, clothing follows body pose, no real dynamic character shadows.
- Latest 1280x720 DirectML audit for 100 moving agents, no grass/trees/shadows: invisible `205.23 FPS`; `Far` normal `112.08 FPS`; `Far` clothes hidden `143.10 FPS`; `Far` body-only diagnostic `161.77 FPS`.
- Conclusion: `Far` clears the 80 FPS stripped benchmark target, but clothes remain a major graphics cost. Next serious optimization is a generated/baked `Far` asset with fewer components/materials.

## Rendering And Scenery

- Benchmark render profile disables Lumen GI/reflections, fog, AO, SSR, contact shadows, virtual shadows, auto exposure, motion blur, bloom, and DOF for stable tests.
- Controlled benchmark setup disables pre-existing map light and sky light components before spawning benchmark lighting.
- Scenery sky uses UE physical stack: `ASkyAtmosphere`, atmosphere-enabled `ADirectionalLight`, movable real-time `ASkyLight`, and `AVolumetricCloud` with the engine simple volumetric cloud material.
- Fog/aerial perspective caused blue patches on grass/hills, so the benchmark profile currently sets `r.Fog=0` and no distance-fog actor is spawned.
- Playable middle remains flat because NN agents are trained on flat terrain.
- Far hills are runtime low-poly grass terrain outside the playable plane, retinted/lowered to sit behind the darker grass.
- Current scenery keeper before dirt WIP: `Saved\LiveShots\stable_live_control_after_settle.png` and older `Saved\ProphecyNN_GrassPhotoPass_v5.png`.

## Grass And Ground

- Current grass path is opaque HISM blade clusters, not Niagara.
- Keeper grass count: about 58,492 HISM patch instances and about 4.173M visual blades (`44` standard, `176` dense).
- Current photo-match pass uses taller/varied blade clusters, `8` dense low filler blades per tile, and `5600cm` dense mesh radius.
- `M_ProphecyGrass_UnlitField` uses blade UV height for a dark-root/bright-tip gradient, then applies light per-instance tint. It no longer relies on runtime mesh vertex color for blade color.
- Blood staining uses one runtime `1024x1024` world-space mask shared by ground and grass. Drops max-compose into the mask so repeated drops in the same place do not add visual/perf cost. Grass blood keeps the coherent stain shape but uses a dark-root/crimson-tip gradient (`BloodGrassRootColor`, `BloodGrassColor`) so stained blades preserve the normal blade value structure.
- Grass must be dense close to camera and fade into terrain without visible full/few/no-grass bands.
- Distant grass color targets `ProphecyGrassContinuationColor` beyond the visible field; `Saved\ProphecyLiveShot.ps1` leaves distant grass controls unset unless explicitly overridden. Current dirt distance fade keeper is `DirtFadeStartCm=1500`, `DirtFadeRangeCm=900`.
- Current grass/plane blending motivation: do not make the outer grass match the plane first. The inner grass is the art keeper; make far grass read as a continuation of that inner grass, then later make the plane continue the finished full grass field. Do B&W high-contrast seam crops after each pass.
- Far grass LOD knobs are command-line tunable for fast visual iteration: `ProphecyNNGrassFarTargetSpacing`, `ProphecyNNGrassFarCoverage`, `ProphecyNNGrassFarScaleXYMin/Max`, `ProphecyNNGrassFarScaleZMin/Max`, and `ProphecyNNGrassDenseMeshRadius`. `Saved\ProphecyStartLivePreview.ps1 -ExtraArgs` can pass them without editing the script.
- Do not use material opacity to blend far grass. The far edge should fade by progressively spawning fewer grass instances, which is cleaner visually and cheaper for FPS. A far-only opaque material light multiplier is allowed to keep the outer silhouette from becoming a monocolor strip; keep the inner grass untouched before touching the plane.
- The far-plane sine grain helps the far/top plane match the grass color, but causes repeatable close/mid-plane stripes at grazing angles. Keep it at `GroundGrassGrainStrength=0.55` and gate it by distance with `GroundGrassGrainFadeStartCm=12000`, `GroundGrassGrainFadeRangeCm=3000` so it is absent close and ramps in only for the far plane.
- Plane/grass transition polishing should hide hills and leave accepted grass alone. The plane now has a distance-matched `GroundFarGrassBlend*` layer tied to the same `15000..18000cm` grass fade window, blending the far floor toward `ProphecyGrassContinuationColor` instead of hardcoding a separate horizon tint.
- Keep the top/far fake-grass illusion on the plane with `GroundGrassImpostorStrength=0.95`, anisotropic scale `GroundGrassImpostorWorldXCm=8000`, `GroundGrassImpostorWorldYCm=18000`, and the previous wider `GroundGrassImpostorStartCm=8000`, `GroundGrassImpostorRangeCm=7000`. The repeatable lower-plane pattern was the periodic sine grain being active too close, not this far impostor.
- Dirt must survive that far-plane continuation only in the close dirt window. `M_ProphecyGrassGround` reapplies the existing `dirt_alpha` after the plane impostor/far-grass color chain, before blood, so close dirt remains visible while the distance fade still returns to the accepted green plane blend.
- Current accepted dirt nudge: `DirtColor=(0.58,0.40,0.21)`, `DirtTextureStrength=0.85`, keeping the same dirt geometry/fade but making the close dirt slightly less dark and more brown.
- Distant hills should use the same ground material path as the far plane, not a separately color-baked green. This keeps hill color tied to `GroundBaseColor` and the shared grass-grain handles so changing the plane color carries to the hills; skip the old baked terrain texture path when that shared ground material is active.
- Hill self-shadow rides on vertex color inside the shared ground material via `GroundVertexShadeStrength`. The plane leaves it at `0`; hills set it to `1`, with flat normals baking shade `1.0` and only slopes/self-occluded curves darkening.
- Current seam keeper: real grass spawn cull at horizon `18000cm`, dense mesh radius `18000cm`, far grass coverage `0.72`, outer density fade `start=17750cm`, `range=250cm`, `end_inset=250cm`, distant grass color blend `start=15000cm`, `range=3000cm`, far-only light `start=33000cm`, `range=11000cm`, `view_strength=0.50`, `world_light=(0.62..1.10)`, far root lift `start=5400cm`, `range=3000cm`, `strength=0.60`, `color=(0.130,0.275,0.052)`, ground base `(0.135,0.285,0.058)`, plane periodic grain `strength=0.55` gated by distance `12000..15000cm`.
- Current grass-edge finding: keep the real `18000cm` cull and no opacity cutoff, but bring the existing distant grass color blend into the last `3000cm` before the cull. This removes the inner darker shell by sharing the continuation color instead of adding another cutoff or touching near grass geometry.
- Current grass-edge finding: the distance-kill material proved the black jagged shell follows any artificial cutoff. The accepted fix is actual spawn culling around `18000cm` plus the existing plane material behind it; do not reintroduce material opacity/cutoff as the final grass fade.
- Unified grass wind uses cheap patch-level WPO from object/world position. Current wind keeper: `bend=14cm`, `lift=0`, `speed=0.85`, `gust=0.55`, `world_freq=0.00062`.
- `Saved\ProphecyLiveShot.ps1` now does a two-step settle before screenshots. Use it for visual captures; premature screenshots can show unsettled dark/brown artifacts.
- Ground material generator: `Saved\ProphecyCreateGrassMaterials.py`.
- Source dirt/ground PNGs tracked through LFS: `Saved\ProphecyGrassGroundNoise.png`, `Saved\ProphecyDirtPatchMask.png`.

## Dirt Baseline

- User asked to remove/hide grass and inspect dirt pattern. Use `-ProphecyNNGrass=1 -ProphecyNNHideGrass=1` so the grass-ground material stays active while blades are hidden.
- The original dirt pattern is intentionally restored for now: spotty/patched, not diffuse.
- Revert confirmation capture: `Saved\LiveShots\dirt_spotty_revert_confirm_01.png`.
- Diffuse dirt experiment was rejected/reverted. The rejected captures were `Saved\LiveShots\dirt_hidden_grass_diffuse_01.png` and `Saved\LiveShots\dirt_hidden_grass_diffuse_strength085.png`; they were too faint and should not be treated as keeper art.
- Next action if returning to dirt: start from the restored spotty baseline and design a better diffuse layer deliberately, while preserving the accepted close grass geometry.

## Trees

- Tree work is on hold.
- Previous 3,000 distant-tree pass is archived only.
- Current direction is a tall European spooky forest around the playable area, with a central corridor kept open.
- Current implementation uses generated low-poly static tree meshes in HISM components, default `TreeInstanceCount=420`.
- Tree wind and dynamic tree shadow casting are off by default. Tree shadows are simulated by baking trees into static grass/ground receiver masks.

## Visual Workflow Rules

- Always show captures in chat when visual work is being judged.
- User cannot rely on the assistant's visual judgment or claims alone. Always show the actual screenshot/crop/result after visual changes so the user can judge with evidence.
- Before coming back or idling on any visual task, explicitly inspect the latest normal and exaggerated evidence and ask: "is there still a visual problem?" If yes, keep working or state the remaining problem plainly; do not say it is good/done just because a requested operation technically ran.
- For scenery iteration, use scenery-only runs with agents disabled unless the task is explicitly about characters or performance with agents.
- When a visual problem is ambiguous, isolate or exaggerate the variable so the failure becomes obvious. Label these as diagnostic aids, not final art direction.
- Do not hide problems with unrelated tints or occluders; solve the underlying material/geometry/runtime cause.

## Useful Commands

## Runtime Blood Texture Painting

- If surfaces turn into Unreal's blue/grey checker/default material when touched by the blood fountain, treat it as a generated blood material compile failure, not a paint-mask issue.
- 2026-06-26 diagnosis: current log showed `MF_BloodPaintSurface` still requiring stale function input `OriginalRoughness`, so generated blood materials compiled to Default Material.
- Fix direction: recreate `MF_BloodPaintSurface` from scratch in `Saved\ProphecyCreateBloodTexturePaintingAssets.py`, then rebuild generated blood materials.
- Material generation rule: for source materials using `MP_MaterialAttributes`, preserve the original full MaterialAttributes graph by feeding it into `SetMaterialAttributes` input 0 and override only BaseColor/Roughness/Specular/Metallic with the blood mask. Do not replace complex/Fab material graphs with fallback constants.
- 2026-06-26 follow-up: C++ build succeeded, `MF_BloodPaintSurface` was recreated, generated blood materials were rebuilt, and the latest log no longer contains the old `Missing function input`, `Failed to compile Material`, or `Default Material will be used` blood-paint failures. Existing brush/runtime helper materials are now reused by the asset script to avoid Unreal crashing while deleting rooted material expressions.
- 2026-06-26 floor metallic debug follow-up: the runtime floor was not using the old grass-ground path; its source material was `/Engine/EditorMeshes/ColorCalibrator/M_GreyBall.M_GreyBall`. The paint manager generated `/Game/Prophecy/BloodTexturePainting/Generated/_Engine_EditorMeshes_ColorCalibrator_M_GreyBall_BloodPaint`, but it was initially only in memory and logged a missing Nanite usage warning. The generated material was force-recompiled/saved through the editor bridge and added to `Saved\ProphecyRebuildBloodPaintGeneratedMaterials.py` source materials so future rebuilds include it.

## Useful Commands

Build:

```powershell
& "C:\Program Files\Epic Games\UE_5.7\Engine\Build\BatchFiles\Build.bat" GameAnimationSample3Editor Win64 Development -Project="C:\Users\singerie\Documents\Unreal Projects\Prophecy\GameAnimationSample3.uproject" -WaitMutex -NoHotReload
```

Regenerate procedural materials:

```powershell
& "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "C:\Users\singerie\Documents\Unreal Projects\Prophecy\GameAnimationSample3.uproject" -run=pythonscript -script="C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\ProphecyCreateGrassMaterials.py" -unattended -NoSplash -NoSound
```

Start fast scenery preview:

```powershell
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\ProphecyStartLivePreview.ps1" -ResX 1280 -ResY 720
```

Request a settled live screenshot:

```powershell
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\ProphecyLiveShot.ps1" -Name "shot_name" -SettleSeconds 1.25 -Wait
```

## 2026-06-26 - Blood GPU Fake-Fluid Post Process
- Enabled persistent CustomDepth stencil in config with `r.CustomDepth=3`.
- Baked `NS_bloodsplat` defaults to render custom depth with stencil value 42.
- Enabled `Allow Custom Depth Writes` on translucent `M_blood_final`.
- Generated PP materials for stencil debug plus Extract -> BlurH -> BlurV -> Composite under `/Game/_mygame/blood2/PP_Fluid`.
- Kept the existing `_PPM_blood` as scratch/debug and avoided depending on DecalManager stencil nodes.
- Created assets: /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_StencilDebug42, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_Extract, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_BlurH, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_BlurV, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_Composite

## 2026-06-26 - Blood Fake-Fluid Current State
- Replaced the fragile multi-pass User Scene Texture display path with a single post-process material for the active effect: `/Game/_mygame/blood2/PP_Fluid/M_PP_Blood_Composite`.
- The active material performs the Photoshop-style operation directly in one pass: sample original scene + stencil 42, blur the isolated blood layer, smoothstep its alpha, then paste the layer back at full strength.
- `AProphecyBloodFluidPostProcessController` now activates only `BloodCompositeMID` for fluid mode, or only `BloodStencilDebugMID` for stencil debug.
- Added editor-preview support to the controller: it ticks in editor viewports and can auto-tag placed/dropped `NS_bloodsplat` Niagara components with CustomDepth enabled and stencil value 42.
- Current A/B captures: raw `Saved/BloodFluidAB/A_raw_singlepass_layer_blur_1782500710.png`, fluid `Saved/BloodFluidAB/B_fluid_singlepass_layer_blur_1782500716.png`.
- Added `Saved/ProphecyBloodFluidABTest.py` as the explicit A/B harness. `raw` removes all blood PP blendables so the original sphere/cylinder look is visible, `stencil` enables only the white stencil mask, and `fluid` restores Extract -> BlurH -> BlurV -> Composite for the fake-fluid blob look. Off mode really removes the blendables so it is useful for both visual and perf comparison.

## 2026-06-26 - Blood GPU Fake-Fluid Post Process
- Enabled persistent CustomDepth stencil in config with `r.CustomDepth=3`.
- Baked `NS_bloodsplat` defaults to render custom depth with stencil value 42.
- Enabled `Allow Custom Depth Writes` on translucent `M_blood_final`.
- Generated PP materials for stencil debug plus Extract -> BlurH -> BlurV -> Composite under `/Game/_mygame/blood2/PP_Fluid`.
- Kept the existing `_PPM_blood` as scratch/debug and avoided depending on DecalManager stencil nodes.
- Created assets: /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_StencilDebug42, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_Extract, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_BlurH, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_BlurV, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_Composite

## 2026-06-26 - Blood GPU Fake-Fluid Post Process
- Enabled persistent CustomDepth stencil in config with `r.CustomDepth=3`.
- Baked `NS_bloodsplat` defaults to render custom depth with stencil value 42.
- Enabled `Allow Custom Depth Writes` on translucent `M_blood_final`.
- Generated PP materials for stencil debug plus Extract -> BlurH -> BlurV -> layer-style Composite under `/Game/_mygame/blood2/PP_Fluid`.
- Kept the existing `_PPM_blood` as scratch/debug and avoided depending on DecalManager stencil nodes.
- Created assets: /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_StencilDebug42, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_Extract, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_BlurH, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_BlurV, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_Composite

## 2026-06-26 - Blood GPU Fake-Fluid Post Process
- Enabled persistent CustomDepth stencil in config with `r.CustomDepth=3`.
- Baked `NS_bloodsplat` defaults to render custom depth with stencil value 42.
- Enabled `Allow Custom Depth Writes` on translucent `M_blood_final`.
- Generated PP materials for stencil debug plus Extract -> BlurH -> BlurV -> layer-style Composite under `/Game/_mygame/blood2/PP_Fluid`.
- Kept the existing `_PPM_blood` as scratch/debug and avoided depending on DecalManager stencil nodes.
- Created assets: /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_StencilDebug42, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_Extract, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_BlurH, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_BlurV, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_Composite

## 2026-06-26 - Blood GPU Fake-Fluid Post Process
- Enabled persistent CustomDepth stencil in config with `r.CustomDepth=3`.
- Baked `NS_bloodsplat` defaults to render custom depth with stencil value 42.
- Enabled `Allow Custom Depth Writes` on translucent `M_blood_final`.
- Generated PP materials for stencil debug plus Extract -> BlurH -> BlurV -> layer-style Composite under `/Game/_mygame/blood2/PP_Fluid`.
- Kept the existing `_PPM_blood` as scratch/debug and avoided depending on DecalManager stencil nodes.
- Created assets: /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_StencilDebug42, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_SceneCopy, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_Extract, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_BlurH, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_BlurV, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_Composite

## 2026-06-26 - Blood GPU Fake-Fluid Post Process
- Enabled persistent CustomDepth stencil in config with `r.CustomDepth=3`.
- Baked `NS_bloodsplat` defaults to render custom depth with stencil value 42.
- Enabled `Allow Custom Depth Writes` on translucent `M_blood_final`.
- Generated PP materials for stencil debug plus Extract -> BlurH -> BlurV -> layer-style Composite under `/Game/_mygame/blood2/PP_Fluid`.
- Kept the existing `_PPM_blood` as scratch/debug and avoided depending on DecalManager stencil nodes.
- Created assets: /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_StencilDebug42, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_Extract, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_BlurH, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_BlurV, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_Composite

## 2026-06-26 - Blood GPU Fake-Fluid Post Process
- Enabled persistent CustomDepth stencil in config with `r.CustomDepth=3`.
- Baked `NS_bloodsplat` defaults to render custom depth with stencil value 42.
- Enabled `Allow Custom Depth Writes` on translucent `M_blood_final`.
- Generated PP materials for stencil debug plus Extract -> BlurH -> BlurV -> layer-style Composite under `/Game/_mygame/blood2/PP_Fluid`.
- Kept the existing `_PPM_blood` as scratch/debug and avoided depending on DecalManager stencil nodes.
- Created assets: /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_StencilDebug42, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_Extract, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_BlurH, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_BlurV, /Game/_mygame/blood2/PP_Fluid/M_PP_Blood_Composite
