# Prophecy Project Journal

Keep this file tight. Preserve only goals, rules, keeper settings, important paths, current working state, and next actions. Full historical archives live in `Docs/old/`.

## Current State

- Project path: `C:\Users\singerie\Documents\Unreal Projects\Prophecy`.
- Unreal project: `GameAnimationSample3.uproject`, Launcher UE `5.7`.
- Git remote: `https://github.com/DTSwink/Prophecy.git`.
- Latest pushed commit should be checked with `git log -1 --oneline origin/main`; avoid treating this journal as the moving hash source.
- Git preservation rule: push everything needed to reconstruct the project if local files are lost. Include source code, journal notes, helper scripts, config, hand-authored data, and small source assets/textures through LFS when needed.
- Do not push bulky or recoverable Unreal output by default: `Binaries/`, `Intermediate/`, `DerivedDataCache/`, screenshots, logs, autosaves, and generated `Content/` assets that can be rebuilt by opening Unreal or rerunning tracked scripts. If an added asset cannot be reconstructed from tracked source/scripts, track it.

## Blood Work Ledger

- Goal: keep blood visually rich without drowning the scene in thousands of expensive deferred decals. The current architecture has several purpose-built paths rather than one universal renderer.
- Benchmarking: `AProphecyBloodRendererBenchmarkActor` compares DecalComponents, ISM, HISM, mesh-decal ISM, and the procedural renderer through `-ProphecyBloodBenchmark`; `Saved\RunBloodRendererBenchmarks.ps1` captures JSON/screenshot evidence. This drove the move away from decal spam and runtime instance churn.
- Cheap particle/VFX stain path: `AProphecyBloodStainRenderer` receives Niagara/basic particle hit data, preallocates procedural triangle stain slots, batches vertex rewrites, and exposes `AddBloodHit`, `AddBloodParticleData`, and world helper nodes. `ProphecyWireBloodStainCommandlet` wires `/Game/_mygame/blood2/A_DecalManager` so existing `ReceiveParticleData` can also feed the native renderer.
- Runtime texture-paint path: `AProphecyBloodTexturePaintManager::TryPaintFromHit(Hit, BrushRadiusWorld, Intensity, OverrideMaterialSlot)` is the precision path for static/Nanite mesh stains. It resolves UVs, allocates one mask RT per component/material slot, swaps that slot to a blood-enabled MID, queues brush stamps, and flushes RT writes under `MaxStampsPerFrame` and `MaxStampsPerRTPerFrame`.
- Project requirement for texture painting: `bSupportUVFromHitResults=True` in physics settings. Static meshes use collision UV / face-material lookup where available; production assets should prefer unique non-overlapping paint UVs.
- Paint material pipeline: `Saved\ProphecyCreateBloodTexturePaintingAssets.py` creates/rebuilds brush/test assets and `MF_BloodPaintSurface`; `Saved\ProphecyRebuildBloodPaintGeneratedMaterials.py` refreshes generated variants. Generated `_BloodPaint` materials live under `/Game/Prophecy/BloodTexturePainting/Generated` and preserve source materials by overriding only BaseColor/Roughness/Specular/Metallic through `BloodMaskRT * BloodIntensity`.
- Material automation: the manager can auto-generate blood-enabled materials for plain materials and material instances, cache clean->blood pairs, save generated assets, avoid overwrite prompts unless explicitly allowed, and reuse generated materials by default. Complex `MP_MaterialAttributes` graphs are preserved through `SetMaterialAttributes`; normal-map layering is still a future regeneration/update task.
- Texture-paint validation: milestone scripts in `Saved\ProphecyValidateBloodTexturePaintingMilestones.py` and `Saved\ProphecyValidateBloodTexturePaintingRuntime.py` proved brush RT output, UV variation, first-hit material swap, batched stamps, RT budget rejection, Nanite fallback UV painting on the generated Nanite cube, and editor stress with 100/1000 painted objects plus a capped 512-stamp burst.
- Texture-paint perf rule: many stamps on one RT are cheap because they batch into one canvas pass; bursts across many components are expensive because they trigger many UV lookups, allocations/material swaps, and RT flushes. Debug hit printing/drawing must stay off for meaningful perf tests.
- Skeletal/skinned support: `TryPaintFromHit` now accepts `UMeshComponent` hits, including skeletal meshes. The first CPU-skinned approach was removed because `GetCPUSkinnedVertices()` was too slow; the current fallback caches LOD0 reference-pose triangles/UVs by skinned asset and uses `Hit.BoneName` plus current/reference bone transforms to estimate the hit UV.
- Skeletal caveat: large stamps can bleed across UV islands because the renderer writes a 2D circle into the material RT. Current mitigation estimates UV density and caps skinned stamp diameter to 48 RT pixels; exact island-aware painting would require heavier unwrap/capture/mask work.
- Fake-fluid blood path: `AProphecyBloodFluidPostProcessController` drives a screen-space post-process composite over blood Niagara/stencil objects. It tags `NS_bloodsplat` components for CustomDepth stencil 42, uses `M_PP_Blood_Composite`, and can switch to `M_PP_Blood_StencilDebug42`.
- Fake-fluid debug: `/Game/_mygame/blood2/PP_Fluid/M_PP_Blood_DebugStages` exposes stages 0-7 from raw scene through stencil mask, isolated layer, blur/gating, threshold/softness, and final depth-aware composite. This is a visual wet/blob layer, not the precise persistent mesh-stain storage.
- Grass/ground blood: the scenery path uses one runtime `1024x1024` world-space mask shared by ground and grass. Drops max-compose into the mask so repeated drops in the same area do not add visual or CPU cost; grass uses a dark-root/crimson-tip response to preserve blade value structure.
- Foliage/floor decal grid path: `UProphecyFoliageDecalGridComponent` is the foliage-only runtime decal-count reducer. It takes floor hits, snaps them to a 2D grid, spawns only missing square decals, then incrementally merges complete 2x2 blocks into larger decals under scan/check/merge/time budgets. Debug nodes draw active bounds; `BoundsHeightCm` only affects visualization.
- Foliage grid current fix: tile keys are now leaf-cell origins, not fixed quadtree coordinates, so sliding 2x2 groups can merge even when they straddle the old even/odd boundary. `OccupiedLeafKeys` prevents duplicate cells after merging. Use `... Ref` Blueprint nodes when Live Coding temporarily treats the component reference as a `LIVECODING_*` class.
- Instanced foliage/PCG direction: for large rocks/trees, promote the hit instance only when needed. Use `Hit.Item` and `GetInstanceTransform(..., WorldSpace=true)`; do not use the ISM component transform as the instance transform, and do not remove instances unless index churn is handled.
- Active division of labor: fake-fluid PP for the big wet VFX look, texture painting for precise persistent mesh stains, procedural mesh for cheap particle-derived surface marks, foliage grid decals for foliage-only floor stains, and world-space grass mask for grass/ground coloration.
- Remaining blood risks: real packaged/PIE profiler captures are still needed; skeletal painting is approximate; landscape and unique per-instance ISM/HISM masks are not solved; generated blood normals are not wired; Nanite proof has only been validated on the generated Nanite cube and should be retested on real hero rocks/trees.

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

## 2026-06-30 - Runtime Stain Material Pipeline Handoff

- Runtime entry point is `AProphecyBloodTexturePaintManager::TryPaintFromHit(Hit, BrushRadiusWorld, Intensity, OverrideMaterialSlot)`. It accepts `UMeshComponent` hits, resolves a paint UV, computes a render-target draw size from world brush radius and UV density, and queues a `FProphecyBloodPaintStamp`.
- Each painted component/material slot owns one `FProphecyBloodPaintState`: original material, blood material instance, `BloodRT` render target, RT resolution, and usage stats. `EnsurePaintState` creates the RT, creates a MID from the generated blood material template, sets `BloodMaskRT`, sets `BloodIntensity=1`, and applies the MID to the hit mesh slot.
- Stamps are flushed into `BloodRT`; the material reads `BloodMaskRT` and multiplies it by `BloodIntensity` to decide where the stain affects the surface.
- Shared blood appearance lives in `/Game/Prophecy/BloodTexturePainting/MF_BloodPaintSurface`. Current outputs are `BaseColorOut`, `RoughnessOut`, `SpecularOut`, and `MetallicOut`; it has no normal-map output yet.
- `M_BloodPaint_RuntimeTest` is the default standalone/template material loaded by the paint manager. `M_BloodBrush_Circle` is the brush draw material used to paint the mask RT.
- Generated variants live in `/Game/Prophecy/BloodTexturePainting/Generated` with suffix `_BloodPaint`. `EditorEnsureBloodMaterialTemplate` duplicates the source material/instance and injects the shared blood-surface function plus mask/intensity/debug parameters.
- For normal materials, the generated graph currently captures original BaseColor/Roughness/Specular/Metallic, lerps them against the blood-surface outputs using the saturated blood mask, and reconnects those material properties.
- For materials using `MP_MaterialAttributes`, the generated graph currently keeps the original full attributes as input 0 of `SetMaterialAttributes`, extracts the original attributes through `GetMaterialAttributes`, and overrides only BaseColor/Roughness/Specular/Metallic. This preservation rule is important for Fab/complex source materials.
- Current generated variants do not capture or reconnect `MP_Normal`. A blood normal-map feature must add a `UseBloodNormal` static switch and `BloodNormalTexture` texture parameter, layer blood normal over the original normal only inside the blood mask, and connect the final normal both for regular property graphs and `SetMaterialAttributes` graphs.
- Because existing `_BloodPaint` variants were generated without any normal connection, adding blood normals requires a one-time regeneration/update of generated variants. After that, appearance tweaks inside `MF_BloodPaintSurface` can propagate through material recompilation.

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

## 2026-06-28 - Blood Fluid Debug State And Unreal Workflow

- Active fake-fluid blood post process is still a screen-space layer reconstruction over the normal scene, not a true separate blood render layer. It uses `PostProcessInput0`, `CustomStencil == 42`, `SceneDepth`, `CustomDepth`, `BlurRadius`, `Threshold`, `Softness`, and `BlurSampleQuality`.
- Added `/Game/_mygame/blood2/PP_Fluid/M_PP_Blood_DebugStages` and the controller property `Prophecy|Blood Fluid PP|Debug > Debug Stage`. Stage `7` is the current/original PP behavior.
- Debug stages:
  - `0`: raw scene passthrough.
  - `1`: custom stencil mask only.
  - `2`: scene isolated by stencil.
  - `3`: scene isolated by stencil and red/blood signal.
  - `4`: blurred stencil footprint with flat blood color.
  - `5`: blurred footprint with red/blood signal gating.
  - `6`: threshold/softness applied to the blurred layer.
  - `7`: stage 6 plus depth occlusion/source preservation, matching the current composite behavior.
- Current interpretation of the editor-vs-PIE debug: the blur footprint can exist while color differs because alpha/coverage comes from stencil/redness blur and color is reconstructed from `PostProcessInput0`; stage 6 is the useful breakpoint for diagnosing that mismatch.
- Runtime stain architecture direction: keep screen-space fake-fluid for the big wet/blood volume, but use runtime texture painting for precise mesh stains. Large PCG rocks/trees can be promoted on hit: read the hit `InstancedStaticMeshComponent` and `Hit Item` instance index, get the instance transform in world space, spawn a stainable actor at that transform, and suppress the original instance by per-instance hide if available or by updating that instance transform/scale. Do not remove instances unless index churn is explicitly handled.
- For instanced mesh hits, never use the ISM component transform as the rock/tree transform; use `GetInstanceTransform(HitItem, WorldSpace=true)`.

## 2026-06-28 - Runtime Texture Paint / Skeletal Mesh State

- `AProphecyBloodTexturePaintManager::TryPaintFromHit` now honors `BrushRadiusWorld`; brush draw size is converted to render-target pixels instead of always using `DefaultBrushSizePixels`.
- Runtime texture painting now accepts `UMeshComponent` and supports both static and skeletal/skinned mesh components. Generated blood-paint materials include skeletal mesh usage.
- The first skeletal implementation worked but was too slow because `USkinnedMeshComponent::GetCPUSkinnedVertices()` flushes/CPU-skins the mesh; we removed that hot-path call.
- Current skeletal fallback builds a cached LOD0 reference-pose triangle/UV table per skinned asset and indexes candidate triangles by influencing bone. Runtime hits use `Hit.BoneName`, the current bone transform, and the reference pose transform to find the nearest cached triangle and UV.
- Large brush stamps on skeletal meshes can still bleed across packed UV islands because the active renderer stamps one 2D circle into the material RT. Cheap mitigation added: estimate UV density from the matched triangle and cap skinned mesh stamp diameter to 48 RT pixels. This avoids scene captures, UV-island masks, and extra draw passes, but it is not as exact as an unwrap/capture workflow.
- Verification: UHT processed cleanly; Live Coding produced `UnrealEditor-GameAnimationSample3.patch_10`; UBT ended with `Result: Succeeded`. UBA still logged memory-pressure retries before succeeding, so keep disk/pagefile headroom available during Unreal compiles.

## 2026-06-28 - Foliage Floor Decal Grid

- Added `UProphecyFoliageDecalGridComponent`, a Blueprint-spawnable component intended to live on `A_DecalManager`.
- New Blueprint entry point: call `AddFloorHitToGrid(Hit, RadiusCm)` from the floor-hit branch. It validates the floor normal, snaps the stain footprint to a tight 2D XY grid, and spawns square decal components only for covered cells that are not already occupied by an active same-size tile or a merged parent tile.
- There is no opacity/intensity argument anymore; this path assumes the decal material is already opaque/authoritative and only uses the configured material/color.
- Optional grid bounds are exposed with `bLimitGridSize`, `GridOrigin`, `GridSizeCells`, and `CellSizeCm`. When enabled, floor hits outside the configured grid are ignored.
- The cleanup/merge path is budgeted and incremental. The component owns a timer (`MergeProcessIntervalSeconds`) that calls `ProcessPendingMerges()`. It scans only active stained tiles, never the whole map grid, and checks at most `MaxStainedPointsScannedPerPass` active keys while sweeping back and forth through the active list.
- Complete 2x2 blocks are queued and then replaced with one parent decal under `MaxMergeChecksPerPass`, `MaxMergesPerPass`, and `MergeBudgetMs`.
- Runtime control nodes are exposed for the merge/remesh pass: `StartMergeProcessing`, `StopMergeProcessing`, `SetMergeProcessingEnabled`, and `IsMergeProcessingEnabled`. The `bAutoProcessMerges` checkbox is the initial BeginPlay behavior.
- Added Blueprint Function Library wrapper nodes for easier graph discovery: `Add Floor Hit To Foliage Decal Grid`, `Set Foliage Grid Merge Processing Enabled`, and typed/ref variants for active decal access and bounds debug drawing.
- Added debug draw nodes for the active decal bounds: `Draw Active Foliage Grid Decal Bounds`, `Draw Foliage Grid Decal Bounds`, and `Draw Foliage Grid Decal Bounds Ref`. They draw each current active decal projection box from the real decal component transform/size, optionally color-coded by merge level, so child boxes should disappear and larger parent boxes appear as remeshing progresses. `BoundsHeightCm` only changes the debug box height; it does not change the real decal projection depth. Set it to `0` to visualize the full decal depth.
- Live PIE investigation of an apparent merge stall showed the merge timer was still active, `PendingMergeCount` was `0`, and there were no complete candidates under the old fixed quadtree phase. Some visually adjacent 2x2 blocks straddled the global even/odd parent boundary, so the old `floor(child / 2)` parent rule could never merge them.
- Updated the remesher key model so tile `X/Y` are leaf-cell origins at every merge level. `TryEnqueueParentMerge` now checks the four possible parent positions around each child, allowing sliding 2x2 merges instead of only global even/even quadtree merges. `OccupiedLeafKeys` tracks stained leaf cells so duplicate hits stay blocked even after the visible decals merge upward.
- After the structural Live Coding change, `A_DecalManager` briefly hit a Blueprint type mismatch between `LIVECODING Prophecy Foliage Decal Grid Component 2` and the normal component class. The actor wrapper nodes were removed. Use the `... Ref` nodes when the graph has a component reference that Live Coding temporarily treats as a different class; they accept `UObject*` and call the grid component by reflection when needed. Restarting the editor still normalizes class names.
- Exposed tuning knobs include `CellSizeCm`, `MaxCellsPerHit`, `MaxActiveDecals`, `MaxMergeLevel`, projection depth/offset, decal material/color, fade screen size, active-scan budget, merge budget, and stats/debug counters.
- This is a runtime decal-count merger, not a mesh bake. For foliage-only staining, the receiving materials/render setup still needs to make foliage receive the decal effect while the floor ignores it or uses a harmless response.
- Verification: direct Live Coding UBT with `-NoUBA` succeeded after adding/refining the component and again after adding the bounds debug nodes. The open editor was memory-stressed earlier, so restart the editor if the new component or nodes do not immediately appear in Blueprint search.

## 2026-07-11 - Full-Body Reach Target Space Fix

- `CR_Reach` worked in the Control Rig editor but the right arm missed the yellow runtime target because the `ABP_Reach` Control Rig pin writes a control value in the control's offset frame. The ABP correctly converted the yellow `Cube1` location from world space to mesh/component space, but `_target_hand_r` still had a non-identity control offset, so the same vector produced a different rig-global target.
- Normalized only the initial/current offset transforms of `_target_hand_r` and `_target_hand_l` to identity while preserving their initial/current editor transforms. The five RigVM model node lists remained byte-for-byte equivalent at the API level; no Forward Solve, IK, pelvis, spine, or arm graph logic was changed.
- `ABP_Reach` previously converted only `Target Hand R Location` from world space to mesh space. Added the equivalent `Inverse Transform Location` path for `Target Hand L Location`, sharing the skeletal mesh component-to-world transform.
- Added the idempotent editor command `Prophecy.FixReachTargetSpace` in `ProphecyEditorModule.cpp` for the ABP graph migration. It finds the existing target nodes, adds the missing left conversion through Unreal's graph schema, and compiles the Anim Blueprint without touching the character's G-toggle chain.
- PIE verification after invoking the character's generated G input event: yellow cube world location and the right target transformed back to world differed by approximately `0.000001 cm`; the ABP mesh-space input and `_target_hand_r` rig-global position also differed by approximately `0.000001 cm`.
- Visual verification capture: `Saved/Screenshots/WindowsEditor/HighresScreenshot00001.png`.
- Live Coding finished successfully after the editor command was added. Both `ABP_Reach` and `CR_Reach` were explicitly saved through the live Python bridge.

## 2026-07-12 - Accepted Double-Reach Gym And Unreal Port

- The accepted local reference is
  `C:\Users\singerie\Documents\Cursor\stepper\training\slashes2\reach_ik_gym.html`
  generated by `make_reach_ik_gym.py`. It supports animation-independent left,
  right, and both-hand full-body reach with planted feet, static balance,
  deterministic elbow poles, exact analytical limb solves, and a target-only
  shared body solve. It has no previous-pose feedback, target filtering, springs,
  temporal regularization, or branch-dependent search.
- The two-hand solver uses a shared six-parameter posture, continuous engagement,
  fixed damped-least-squares refinement, and a continuous feasibility trust gate.
  The global continuity audit evaluates 12,428 poses over rear, side, low, high,
  and cross-body paths; current worst refined visible-joint displacement is
  `0.00238 m`, worst refined acceleration is `0.00243 m`, with zero leg or
  balance error. The accepted low-target variant keeps the full `0.72 m` pelvis
  drop while smoothly limiting spine pitch to `1.15 rad`, avoiding the nearly
  horizontal torso seen in SS14.
- Runtime direction: port the exact equations into a shared native C++ solver and
  a custom skeletal-control AnimGraph node. The node consumes the current source
  animation pose, supports Off/Left/Right/Both modes, and internally applies a
  smootherstep reach alpha so entering or leaving reach has zero endpoint velocity
  and acceleration. It should evaluate the source once, work in component space,
  emit only affected bones, allocate nothing per frame, and remain worker-thread
  safe. Establish golden parity against gym fixtures before replacing the current
  finite-difference body Jacobian with an analytic form.
- Requested demonstration asset: a simple UEFN-mannequin character Blueprint in
  `/Game/_mygame/locomotion` that can play a selected animation or smoothly enter
  one- or two-hand reach mode. Reach targets and transition controls must be easy
  to manipulate from Blueprint. Behavior parity comes before optimization; native
  AnimGraph execution is the intended shipping path once parity is established.

## 2026-07-12 - Native Double-Reach Runtime Prototype

- Added a worker-thread-compatible native runtime port of the accepted gym solver:
  `UProphecyDoubleReachAnimInstance`, its proxy, `AProphecyDoubleReachCharacter`,
  and `EProphecyDoubleReachMode` (`Off`, `Left`, `Right`, `Both`). The proxy samples
  the selected source animation once, solves in component space, and emits only the
  affected component-space bone transforms. Fixed-size and inline storage avoid
  per-frame heap allocation.
- The port preserves the deterministic target-only six-parameter body solve,
  planted feet, static balance, low-target upright limit, analytical limbs,
  deterministic elbow poles, and two-hand DLS refinement. It has no previous-pose
  feedback, target smoothing, temporal search, or hidden pose history.
- Source animation and solved reach endpoints are blended with quintic
  smootherstep over `TransitionDuration`. Initial proxy state is explicitly
  initialized as `Off -> requested mode`, so an actor placed in `Both` begins its
  smooth transition on the first PIE run without requiring a live mode toggle.
- Created and saved
  `/Game/_mygame/locomotion/BP_ProphecyDoubleReachCharacter`. It uses
  `/Game/_mygame/SKM_UEFN_Mannequin`, defaults to
  `M_Neutral_Stand_Idle_Loop`, exposes visible left/right target cubes, and starts
  in animation-only mode. Reach controls are available both as properties and as
  Blueprint-callable functions: `SetReachMode`, `SetReachTargetsWorld`,
  `SetLeftReachTargetWorld`, `SetRightReachTargetWorld`, and `SetBaseAnimation`.
- Deterministic PIE verification with the idle frame frozen: `Left` hand error was
  effectively zero; `Right` was `1.88 cm`; `Both` was effectively zero on the left
  and `3.31 cm` on the right. Across all modes, planted-foot drift stayed below
  `0.008 cm`. Animation-only playback was also verified to advance the selected
  animation normally.
- The `Off -> Both` transition was sampled for 39 consecutive frames over
  `0.634 s`. First and final joint steps were effectively zero, confirming no mode
  entry/exit discontinuity; maximum adjacent-frame displacement was `1.39 cm` for
  the pelvis, `4.06 cm` for the head, `6.58 cm` for the left hand, and `8.65 cm`
  for the right hand during the intentional 0.35-second, roughly one-meter reach.
- Visual verification capture:
  `Saved/Screenshots/WindowsEditor/HighresScreenshot00005.png`. The mannequin shows
  a balanced two-hand pose with bent knees, upright torso, planted feet, and both
  target cubes at the hands.
- `stat dumpframe` measured the complete test skeletal-mesh component at roughly
  `0.06-0.11 ms` in settled `Both` mode and `0.04-0.14 ms` in animation-only mode
  in the same PIE scene. At one actor the native solver cost is currently within
  normal frame-to-frame measurement noise. Keep the native proxy path; Epic's
  animation guidance recommends avoiding Blueprint Event Graph work and retaining
  parallel animation evaluation for performance.
- Normal closed-editor UBT with `-NoHotReloadFromIDE -NoUBA` succeeded. Do not use
  Live Coding for this port: earlier genuine crashes were stale patch-loader access
  violations. A separate startup crash report is only a handled ensure from
  `/Game/_mygame/NewFunctionLibrary`: `Ang Spring` already contains the implicit
  `__WorldContext` entry pin when reconstruction tries to add it again. The ensure
  reports through CrashReportClient but the editor continues running; it is
  unrelated to the reach runtime.

## Unreal Bridge / Assistant Working Rules

- 2026-07-07 side-chat note: Rokoko Motion Library fight FBXs could not import directly to Unreal because the downloaded files contain `AnimStack`/`Skeleton`/`Hips` data but no `Geometry`, `Mesh`, or `Deformer` data. Rokoko Legacy copied the same files into `C:\Users\singerie\Documents\SmartsuitStudioProjects\kjb\MotionLibrary` byte-for-byte and its export path created/opened empty output folders instead of baking usable Body Mesh FBXs.
- To get the clips into UE, Blender 5.1 was used as a converter. `Saved/ConvertRokokoMotionLibraryForUnreal.py` imports each MotionLibrary FBX, adds a tiny weighted carrier mesh, and exports converted files to `Saved/RokokoCarrierFBX`. `Saved/ImportRokokoCarrierAnimationsToUnreal.py` imports them to `/Game/_mygame/Rokoko/FightAnimations_Carrier`. This first carrier set imported eight `_Anim` clips plus a carrier skeleton, but its source `Hips` reference pose sat effectively at ground level, causing IK Retargeter warnings that the source pelvis was near the ground and launching the UEFN target far away.
- A second rooted conversion was created in `Saved/ConvertRokokoMotionLibraryForUnrealRooted.py` and imported with `Saved/ImportRokokoRootedCarrierAnimationsToUnreal.py`. It exports to `Saved/RokokoCarrierRootedFBX` and imports to `/Game/_mygame/Rokoko/FightAnimations_CarrierRooted`. It adds a ground `Root` bone, raises `Hips` to about `89 cm` in the reference pose, subtracts that same offset from Hips animation translation, imports eight `_Anim` clips, creates `IK_RokokoRooted_Xsens`, sets `Hips` as retarget root, and creates `RTG_RokokoRooted_to_UEFN`.
- Current open issue as of the side chat: the rooted retarget preview no longer disappears, but the target pose is visibly contorted. Likely cause is still source skeleton/reference-pose or bone-axis conversion, not missing animation data. Inspect the Blender-converted rooted FBX before adding more retargeter tweaks; the first sanity check showed suspicious spine/limb reference transforms after export/import, so the next fix should preserve the original Rokoko rest pose orientation while providing a valid ground root/pelvis height for Unreal.

- For nontrivial Unreal/engine technical questions, look up current external references before settling on an answer or implementation. Prefer Epic/Unreal official docs, UE 5.7 engine source, API references, and relevant Epic forum/issue threads; do not rely on memory alone for Unreal internals, performance behavior, or edge-case APIs.
- Prefer the live-editor Python bridge for targeted Unreal operations. It uses `remote_execution.py` from `C:\Program Files\Epic Games\UE_5.7\Engine\Plugins\Experimental\PythonScriptPlugin\Content\Python` and executes Python in the open editor through `RemoteExecution.run_command(..., exec_mode=MODE_EXEC_FILE)`.
- Use `UnrealEditor-Cmd.exe -run=pythonscript` for clean headless asset-generation scripts when live viewport state does not matter. Use the live bridge when the task depends on the currently opened level, PIE/editor world, selected actors, or current visual state.
- Visual work rule: do not claim a visual fix without showing or inspecting an actual screenshot/crop. For editor/PIE mismatch work, capture both modes from the same camera/view before drawing conclusions.
- `HighResShot ... filename="..."` through the correct world is the reliable Unreal-rendered capture path. Desktop/window screenshots are only a fallback and can capture the wrong foreground app.
- Pressing Play is allowed when the user asks for PIE verification, but first confirm the current visual/camera when that is the variable under test. PIE creates a copied world, so controller/MID/material parameter state must be checked in the PIE world, not only the editor world.
- Keep Unreal edits surgical: one hypothesis, one small change, one visual check. Do not redesign a working editor effect to fix PIE until the exact mismatch stage is isolated.
- When adding debug tools, keep the production material intact when possible; add separate debug materials/properties and default them to the production-equivalent state.
- Avoid pushing bulky/recoverable Unreal data unless explicitly requested. Track scripts, C++ source, and irreplaceable assets; skip `Binaries`, `Intermediate`, `DerivedDataCache`, autosaves, logs, and accidental content copies.
- Live Coding patch link failure note: `ProphecyEditor` hit `LNK2011: precompiled object not linked in` while linking `UnrealEditor-ProphecyEditor.patch_0.exe`, specifically through `ProphecySeedMetaHumanCommandlet.cpp.obj`. `Source/ProphecyEditor/ProphecyEditor.Build.cs` now uses `PCHUsageMode.NoPCHs`, and `ProphecySeedMetaHumanCommandlet.cpp` explicitly includes `Editor.h` for `GEditor`. Verification: Live Coding UBT with `-NoUBA` succeeded after this change.

## 2026-07-11 - NN Locomotion Runtime Checkpoint (Stopped Early)

- Work paused early at the user's request so the laptop could be used. PIE was stopped. The performance investigation is not finished and the 120 FPS target has not been reached.
- Accepted lower-body policy source is epoch 47200 from `C:\Users\singerie\Documents\Cursor\stepper\training\runs\20260617_234645_ik_ik_full_RESUME_best47200_k32fixed_s05_rootaccelx01_i_e8b756b3\checkpoints\20260617_234645_ik_ik_full_RESUME_best47200_k32fixed_s05_rootaccelx01_i_e8b756b3_init.pt`, SHA-256 `CCC03FEE15E825EBCBCD24F9E71934D515B5133E760114ABE664445042D379C1`. Accepted rollout is `C:\Users\singerie\Documents\Cursor\stepper\training\ik\rollout_traces\20260618_final_policy_runF`.
- `Tools/NN/ExportProphecyLowerBodyPolicy.py` exports the 152-input/43-output raw policy to `Content/locomotion/NN/prophecy_lower_body_run_b100.onnx` plus `prophecy_lower_body_runtime.json`. ONNX SHA-256 is `75D9907B6FD62534CD4DC4FC7ED05C9E2DD32D1C173D4530044965887359C209`. Native C++ retains the deterministic recurrent cleanup, root rebase, foot-roll integration, and lower-body IK contract.
- Added transient `AProphecyNNLocomotionManager` plus `UProphecyNNLocomotionWorldSubsystem`. Opening `/Game/locomotion` and entering PIE auto-spawns one transient manager, 100 skeletal components, and no persistent crowd actors. A single `[100,152]` NNE DirectML batch drives all agents between actors labeled `Cube` and `Cube2`; gait seeds are staggered.
- Added `UProphecyNNLocomotionAnimInstance`. Default upper body is reference-pose stiff while pelvis/legs use the NN pose. Optional arbitrary compatible `UAnimSequenceBase` overlay drives pelvis and upper body, reapplies NN legs, and blends in/out with `OverlayBlendSeconds`.
- Runtime and visual verification succeeded: NNE selected `NNERuntimeORTDml` on the RTX 4060 Laptop GPU, 100 agents moved stably between the cubes, and both stiff-upper-body and relaxed-idle overlay poses rendered without exploded IK. Captures include `Saved/Screenshots/WindowsEditor/NNLocomotionClose.png`, `NNLocomotionAgentPaused.png`, `HighresScreenshot00002.png`, and `HighresScreenshot00003.png`.
- Normal UBT build succeeded after avoiding Live Coding. Live Coding had crashed while applying a patch, so continue using normal `Build.bat ... -NoHotReloadFromIDE` for this work.
- Initial 60 FPS ceiling diagnosis: project fixed-rate/VSync controls were disabled correctly, but UE 5.7 editor source (`UEditorEngine::GetMaxTickRate`) also limits laptops to 60 while Windows reports battery operation. Setting `r.DontLimitOnBattery=1` changed the PIE startup line from `max tick rate 60` to `max tick rate 0`. This CVar still needs to be added permanently to the contained manager/subsystem and rebuilt; it was applied through the live bridge for the uncapped measurements.
- Warm capped baseline was about `51.50-52.04 FPS`; overlay run was `49.16 FPS`. The observed overlay cost for 100 agents was roughly 2.3-2.9 FPS, about 0.9-1.1 ms/frame in this editor test. Overlay sample used `/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Relaxed_Stand_Idle_Loop`.
- Uncapped default-visual baseline: `51.38 FPS`; per 100-agent 30 Hz NN step: input `0.1972 ms`, DirectML inference `2.8215 ms`, native output/foot-roll/IK `5.6899 ms`, pose-store publish `0.1947 ms`.
- Forcing mesh LOD index 3 (mesh LOD2) did not help in this sample: `47.38 FPS`. Hiding all 100 skeletal components also did not remove the plateau: `51.85 FPS`, with step timings input `0.2121 ms`, inference `1.6222 ms`, native output `6.5190 ms`, store `0.2265 ms`. Therefore do not assume skeletal rendering alone explains the current ~51 FPS result.
- Startup temporarily took 964 seconds because earlier low-disk Zen 507 failures left 11,885 shaders uncached. After disk space was restored, Zen reported healthy and the shader pass completed/stored successfully. Do not delete DDC or shader caches before the next benchmark.
- Next session: first add and build permanent `r.DontLimitOnBattery=1`; then profile the ~51 FPS plateau with Unreal Insights/stat unit in foreground versus standalone/game launch, verify whether editor/viewport/power-state overhead dominates, and only then optimize the native 30 Hz cleanup/IK or adopt `USkeletalMeshComponentBudgeted`/Animation Budget Allocator. Re-run warmed baseline and overlay with the same camera and power state. Exact native-vs-pushed-rollout numeric parity instrumentation is also still pending.
