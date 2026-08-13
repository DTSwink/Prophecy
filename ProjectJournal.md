# Prophecy Project Journal

**NON-NEGOTIABLE: NEVER DO, IMPLEMENT, CHANGE, TEST, OPTIMIZE, VALIDATE, OR EXPAND ANYTHING THE USER DID NOT EXPLICITLY ASK FOR. NEVER INFER MISSING INTENT OR DETAILS. IF ANYTHING MATERIAL IS UNCLEAR OR UNSPECIFIED, STOP AND ASK THE USER BEFORE ACTING.**

**NON-NEGOTIABLE UNREAL WORKFLOW RULE: USE LIVE CODING FOR UNREAL C++ CHANGES. NEVER CLOSE OR RESTART UNREAL UNLESS THE USER EXPLICITLY AUTHORIZES IT. IF LIVE CODING IS UNAVAILABLE, BLOCKED, OR FAILS, STOP AND ASK THE USER BEFORE CLOSING OR RESTARTING THE EDITOR.**

> **NON-NEGOTIABLE JOURNAL RULE — FINISHED STATE ONLY**
>
> Keep only durable, verified project state: current goals, rules, keeper settings,
> important paths, completed implementation state, real remaining risks, and the
> next actionable handoff. Never append investigation logs, research notes,
> intermediate measurements, failed attempts, speculative diagnoses, or a
> turn-by-turn account of the work. Replace obsolete state instead of accumulating
> history. Put historical detail in `Docs/old/` only when it is genuinely useful.

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

- 2026-07-16 MetaHuman bridge incident and permanent rule: never call
  `MetaHumanCharacterEditorSubsystem.try_add_object_to_edit()` before or after
  opening a MetaHuman Character asset interactively. The MetaHuman asset editor
  owns that registration. A bridge probe registered
  `/Game/_mygame/MetaHumans/test_UEFNFit` while no MetaHuman editor was open;
  the later normal editor open attempted to register it again, and UE logged
  `TryAddObjectToEdit ... already added` followed by the misleading
  `failed to create editing state. The asset may be corrupted` message. The
  asset was not corrupted; the subsystem contained an orphan editing state.
  For interactive use, load the asset and call only
  `AssetEditorSubsystem.open_editor_for_assets()`. For a genuinely headless
  MetaHuman API operation, record whether the script itself successfully added
  the character, wrap all work in `try/finally`, and call
  `remove_object_to_edit()` in `finally` only when that script owned the
  registration. Never remove a registration owned by an open asset editor.
  Recovery for this exact warning is: confirm that no MetaHuman editor is open,
  check `is_object_added_for_editing()`, remove the orphan registration, then
  open the asset normally. Do not resave, delete, duplicate, or rebuild the
  character merely because this warning says "may be corrupted." Recovery was
  verified in the incident session: the orphan registration was removed and
  `AssetEditorSubsystem.open_editor_for_assets()` then opened `test_UEFNFit`
  successfully with the editor owning the new registration. References:
  `https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MetaHumanCharacterEditorSubsystem?application_version=5.7`,
  `https://dev.epicgames.com/documentation/unreal-engine/API/Editor/UnrealEd/UAssetEditorSubsystem/OpenEditorForAssets`.
- Bridge cancellation is not transactional. A client timeout, cancelled shell
  command, or disconnected HTTP request does not undo Python that already began
  on Unreal's editor thread. Stateful bridge scripts must therefore be
  idempotent or use `try/finally` cleanup; never rely on cancelling the request
  as rollback. `Tools/ProphecyEditorBridge.py` now marks an unstarted timed-out
  queue item as cancelled so it cannot execute later, and quietly handles
  disconnected response sockets. Code already claimed by the editor thread
  still cannot be safely interrupted, so destructive or registration-changing
  operations require explicit ownership and cleanup.
- 2026-07-07 side-chat note: Rokoko Motion Library fight FBXs could not import directly to Unreal because the downloaded files contain `AnimStack`/`Skeleton`/`Hips` data but no `Geometry`, `Mesh`, or `Deformer` data. Rokoko Legacy copied the same files into `C:\Users\singerie\Documents\SmartsuitStudioProjects\kjb\MotionLibrary` byte-for-byte and its export path created/opened empty output folders instead of baking usable Body Mesh FBXs.
- To get the clips into UE, Blender 5.1 was used as a converter. `Saved/ConvertRokokoMotionLibraryForUnreal.py` imports each MotionLibrary FBX, adds a tiny weighted carrier mesh, and exports converted files to `Saved/RokokoCarrierFBX`. `Saved/ImportRokokoCarrierAnimationsToUnreal.py` imports them to `/Game/_mygame/Rokoko/FightAnimations_Carrier`. This first carrier set imported eight `_Anim` clips plus a carrier skeleton, but its source `Hips` reference pose sat effectively at ground level, causing IK Retargeter warnings that the source pelvis was near the ground and launching the UEFN target far away.
- A second rooted conversion was created in `Saved/ConvertRokokoMotionLibraryForUnrealRooted.py` and imported with `Saved/ImportRokokoRootedCarrierAnimationsToUnreal.py`. It exports to `Saved/RokokoCarrierRootedFBX` and imports to `/Game/_mygame/Rokoko/FightAnimations_CarrierRooted`. It adds a ground `Root` bone, raises `Hips` to about `89 cm` in the reference pose, subtracts that same offset from Hips animation translation, imports eight `_Anim` clips, creates `IK_RokokoRooted_Xsens`, sets `Hips` as retarget root, and creates `RTG_RokokoRooted_to_UEFN`.
- Current open issue as of the side chat: the rooted retarget preview no longer disappears, but the target pose is visibly contorted. Likely cause is still source skeleton/reference-pose or bone-axis conversion, not missing animation data. Inspect the Blender-converted rooted FBX before adding more retargeter tweaks; the first sanity check showed suspicious spine/limb reference transforms after export/import, so the next fix should preserve the original Rokoko rest pose orientation while providing a valid ground root/pelvis height for Unreal.

- Hard research gate for Unreal work: before answering or implementing any nontrivial engine, animation, rendering, physics, MetaHuman, asset-pipeline, or performance question, first run a focused web survey. Check current Epic documentation/API pages and UE 5.7 engine source, then search Epic forums/issues and credible examples for the same workflow or failure mode. Unreal is widely used; assume an established tool, pipeline, or known limitation may already exist.
- Record the useful sources and the standard Unreal route considered in this journal. Do not begin a bespoke C++/Python replacement until the built-in or documented route has been identified and there is a concrete reason it cannot satisfy this project's behavior, performance, or automation constraints.
- Research is not a one-time checkbox. If the first visual/runtime validation contradicts the implementation model, stop stacking local patches and search the exact symptom again before changing more code. A successful compile, skeleton-number audit, or plausible explanation is never a substitute for the relevant visual/runtime test.
- For skeletal-mesh conversion and MetaHuman work specifically, investigate Epic's supported rigging, IK Retargeter, Skeleton Editing, Skin Weight Profiles/Transfer, Mesh Modeling, and MetaHuman assembly/export paths before modifying reference skeletons or skin weights manually. Never promote a converted mesh until the reference pose and representative extreme animations both pass side-by-side against the source skeleton.
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
- Accepted Run policy source is epoch 47200 from `C:\Users\singerie\Documents\Cursor\stepper\training\runs\20260617_234645_ik_ik_full_RESUME_best47200_k32fixed_s05_rootaccelx01_i_e8b756b3\checkpoints\20260617_234645_ik_ik_full_RESUME_best47200_k32fixed_s05_rootaccelx01_i_e8b756b3_init.pt`, SHA-256 `CCC03FEE15E825EBCBCD24F9E71934D515B5133E760114ABE664445042D379C1`. Accepted rollout is `C:\Users\singerie\Documents\Cursor\stepper\training\ik\rollout_traces\20260618_final_policy_runF`. Accepted Walk source is `C:\Users\singerie\Documents\Cursor\stepper\training\runs\20260608_222748_ik_resume_inertiax10_latest\checkpoints\20260608_222748_ik_resume_inertiax10_latest_latest.pt`, SHA-256 `5FE44CA120CF79BF34CDCAA4F7227C205A35039322541AAB2E100637A9176A3`; `training/ik/official_walk_omni_baseline.json` is the Git authority selecting it.
- `Tools/NN/ExportProphecyLowerBodyPolicy.py` exports the 152-input/43-output raw policies. Run uses `Content/locomotion/NN/prophecy_lower_body_run_b100.onnx` plus `prophecy_lower_body_runtime.json`, ONNX SHA-256 `75D9907B6FD62534CD4DC4FC7ED05C9E2DD32D1C173D4530044965887359C209`. Walk uses `prophecy_lower_body_walk_b100.onnx` plus `prophecy_lower_body_walk_runtime.json`, ONNX SHA-256 `C20D3C2BC04528409CB2D680AEE50A5FAC95C98DA3529EC25103F36D9CB868BE`. Native C++ retains each policy's exact seed geometry, deterministic recurrent cleanup, root rebase, pin semantics, foot-roll integration, and lower-body IK contract. Run uses continuous independent sigmoid pins; Walk uses its trained legacy selected-foot logit rule without the Run height gate.
- Added transient `AProphecyNNLocomotionManager` plus `UProphecyNNLocomotionWorldSubsystem`. Opening `/Game/locomotion` and entering PIE auto-spawns one transient manager and 100 transient no-tick `AProphecyAgent` pawns; none are saved into the level and crowd pawns receive no controller. Contiguous `[100,152]` NNE batches run only the policy needed by a homogeneous crowd and both policies only for a mixed Walk/Run crowd; gait seeds are staggered. `AProphecyAgent` is intentionally an `APawn`, not `ACharacter`, so the one player agent can be possessed without giving the unpossessed crowd `CharacterMovementComponent`, `AIController`, Behavior Tree, or per-agent actor-tick overhead.
- Added `UProphecyNNLocomotionAnimInstance`. Default upper body is reference-pose stiff while pelvis/legs use the NN pose. Optional arbitrary compatible `UAnimSequenceBase` overlay drives pelvis and upper body, reapplies NN legs, and blends in/out with `OverlayBlendSeconds`.
- Agent identity is a stable `{index,generation}` `FProphecyAgentHandle` resolved by the manager. The manager owns intent and simulation state; an agent pawn is the occasional gameplay/debug/event shell. Its 30 cm radius, 86 cm half-height capsule exposes the authoritative low point as the root position while the mesh stays grounded with an equal negative local Z offset.
- `AProphecyAgent` has explicit `Kinematic` and `Physical` modes. Kinematic is the default and keeps its `UPhysicalAnimationComponent` disabled. Physical mode uses one world-space pelvis target plus the Physics Asset's joint angular drives; child limbs travel under Chaos torque/impulses rather than independent world targets. Only promoted agents pay the physical-animation component tick and skeletal physics cost. Physical hit notifications default off and are independently opt-in, with a multicast event for gameplay to decide whether a hit should promote another agent; no automatic promotion policy is hard-coded.
- Before each 30 Hz NN step, only physical agents copy the finalized component-space pelvis/leg/foot/toe transforms from the skeletal mesh. Those actual transforms are converted back into the model's 41-value recurrent state, including signed toe hinge state, so the next inference consumes physical reality rather than the prior target. The capsule low point remains the authoritative root. Leaving physical mode through the manager performs a final sample before returning to kinematic prediction.
- NN current, previous, published, next, and physical-sample states are fixed contiguous `[100,41]` buffers. Published and sampled nine-bone transforms are fixed contiguous `[100,9]` buffers. The former per-agent state arrays and per-step transition/next-state allocations are gone. Pose-store entries retain their bone-name layout and transform capacity, and animation proxies copy a snapshot only when its revision changes instead of every render frame.
- Runtime and visual verification succeeded: NNE selected `NNERuntimeORTDml` on the RTX 4060 Laptop GPU, 100 agents moved stably between the cubes, and both stiff-upper-body and relaxed-idle overlay poses rendered without exploded IK. Captures include `Saved/Screenshots/WindowsEditor/NNLocomotionClose.png`, `NNLocomotionAgentPaused.png`, `HighresScreenshot00002.png`, and `HighresScreenshot00003.png`.
- The agent/physical foundation builds with UE 5.7 UHT/UBT. A 20-second, 601-frame headless `/Game/locomotion` run using NullRHI and `NNERuntimeORTCpu` started all 100 agents and one physical agent, then exited cleanly without invalid-body, Chaos, NaN, ensure, assertion, or fatal diagnostics. Its fixed-30-FPS warmed per-step timings were input plus one physical resample `0.1177 ms`, CPU inference `0.5474 ms`, output/foot-roll/IK `4.0077 ms`, and pose-store publish `0.1357 ms`; this NullRHI/CPU run is a structural benchmark, not a replacement for the rendered DirectML baseline. Physics collision state must be enabled before applying named physical-animation settings; UE 5.7 `USkeletalMeshComponent::ForEachBodyBelow` requires that ordering.
- Normal UBT build succeeded after avoiding Live Coding. Live Coding had crashed while applying a patch, so continue using normal `Build.bat ... -NoHotReloadFromIDE` for this work.
- Initial 60 FPS ceiling diagnosis: project fixed-rate/VSync controls were disabled correctly, but UE 5.7 editor source (`UEditorEngine::GetMaxTickRate`) also limits laptops to 60 while Windows reports battery operation. Setting `r.DontLimitOnBattery=1` changed the PIE startup line from `max tick rate 60` to `max tick rate 0`. This CVar still needs to be added permanently to the contained manager/subsystem and rebuilt; it was applied through the live bridge for the uncapped measurements.
- Warm capped baseline was about `51.50-52.04 FPS`; overlay run was `49.16 FPS`. The observed overlay cost for 100 agents was roughly 2.3-2.9 FPS, about 0.9-1.1 ms/frame in this editor test. Overlay sample used `/Game/Characters/UEFN_Mannequin/Animations/Idle/M_Relaxed_Stand_Idle_Loop`.
- Uncapped default-visual baseline: `51.38 FPS`; per 100-agent 30 Hz NN step: input `0.1972 ms`, DirectML inference `2.8215 ms`, native output/foot-roll/IK `5.6899 ms`, pose-store publish `0.1947 ms`.
- Forcing mesh LOD index 3 (mesh LOD2) did not help in this sample: `47.38 FPS`. Hiding all 100 skeletal components also did not remove the plateau: `51.85 FPS`, with step timings input `0.2121 ms`, inference `1.6222 ms`, native output `6.5190 ms`, store `0.2265 ms`. Therefore do not assume skeletal rendering alone explains the current ~51 FPS result.
- Startup temporarily took 964 seconds because earlier low-disk Zen 507 failures left 11,885 shaders uncached. After disk space was restored, Zen reported healthy and the shader pass completed/stored successfully. Do not delete DDC or shader caches before the next benchmark.
- Next runtime-performance session: first add and build permanent `r.DontLimitOnBattery=1`; then remeasure the dense-buffer agent foundation and profile the ~51 FPS plateau with Unreal Insights/stat unit in foreground versus standalone/game launch. Verify whether editor/viewport/power-state overhead dominates before changing the production four-step foot-roll/IK math or adopting `USkeletalMeshComponentBudgeted`/Animation Budget Allocator. Re-run warmed baseline and overlay with the same camera and power state.
- Physical-mode tuning and visual validation remain pending: author/verify the production Physics Asset and drive values on the final character, inspect hits/recovery in a rendered PIE session, and measure the cost for the intended player/nearby-agent promotion budget. Built-in route references: `https://dev.epicgames.com/documentation/unreal-engine/physics-components-in-unreal-engine`, `https://dev.epicgames.com/documentation/en-us/unreal-engine/physics-driven-animation-in-unreal-engine`, `https://dev.epicgames.com/documentation/unreal-engine/creating-a-physical-animation-profile-in-unreal-engine`, `https://dev.epicgames.com/documentation/en-us/unreal-engine/physics-sub-stepping-in-unreal-engine`, and UE 5.7 `PhysicalAnimationComponent.cpp` / `SkeletalMeshComponentPhysics.cpp`.

## 2026-07-12 - Perpetual Ball Reach Test And Upper-Body Motion Limit

- Added `AProphecyDoubleReachBallTest` and the placeable Blueprint
  `/Game/_mygame/locomotion/BP_ProphecyDoubleReachBallTest`. It creates six
  invisible collision walls, two visible physics spheres, and a spawned
  `BP_ProphecyDoubleReachCharacter` whose left/right targets continuously follow
  the spheres.
- The spheres use no gravity, zero linear/angular damping, CCD, zero-friction and
  restitution-1 physical material overrides, disabled sleep stabilization, and a
  constant-speed guard. The invisible walls block only physics bodies; the balls
  ignore the mannequin and each other. Bounds, sphere radius, speed, initial
  offsets/directions, transition duration, and optional debug bounds are exposed.
- Added the dedicated map
  `/Game/_mygame/locomotion/L_DoubleReachBallTest`. Open it and press Play: the
  harness camera automatically becomes the view target and frames the complete
  test. Target-marker cubes are hidden, while the test-only mannequin forces bone
  refresh so visibility heuristics cannot silently pause the procedural pose.
- Added an optional temporal upper-body motion-limit pass to the native animation
  proxy. The deterministic target-only solver still selects the desired pose; the
  presentation pass applies frame-rate-independent half-life smoothing plus hard
  speed limits to the six shared body parameters, then analytically solves the
  arms again from the filtered torso against the current targets. This avoids bone
  stretching and keeps hand pursuit responsive, but intentionally introduces
  previous-frame state in the presentation layer.
- Exposed controls on both the character and animation instance:
  `bEnableUpperBodyMotionLimit` (default true),
  `UpperBodySmoothingHalfLife` (default `0.075 s`),
  `MaxPelvisTranslationSpeedCmPerSecond` (default `180 cm/s`), and
  `MaxSpineAngularSpeedDegreesPerSecond` (default `240 deg/s`). Set the enable
  checkbox false to recover the exact unsmoothed Markovian output.
- Eight-second A/B audit used the same perpetual-ball setup at `260 cm/s`. Without
  the pass, maximum single-frame displacement was `13.00 cm` pelvis, `20.43 cm`
  upper spine, and `27.49 cm` head. With the pass it fell to `2.65 cm`, `3.39 cm`,
  and `5.14 cm`. Hand spikes fell from `11.22/17.00 cm` to `4.33/4.33 cm`, matching
  the spheres' own per-frame travel rather than a solver branch acceleration.
- Normal closed-editor UBT succeeded. Actual PIE verification confirmed the saved
  map camera, perpetual sphere motion, hidden marker cubes, forced test-only bone
  refresh, and continuous reach. Visual capture:
  `Saved/Screenshots/WindowsEditor/HighresScreenshot00008.png`.
- Added independent `MaxHandVelocityCmPerSecond` and
  `MaxElbowVelocityCmPerSecond` controls to the character and native animation
  instance. Defaults are `300 cm/s` and `360 cm/s`; `0` disables either limit.
  Active hand targets are advanced with a constant-speed component-space limit,
  initialized from the current animated hand whenever that arm enters reach.
- Elbows are constrained after the final mode blend. Each elbow moves toward its
  natural IK result at the configured speed, then projects onto the exact feasible
  two-bone elbow circle. This preserves the hand endpoint and both arm segment
  lengths while suppressing pole/branch travel. With a deliberately low
  `120 cm/s` elbow setting, both-arm PIE p95 speeds were `100.0` and `116.7 cm/s`;
  upper-arm and forearm length variation remained approximately `1e-13 cm`.
  Feasible-circle motion caused rare world-space peaks above the requested value,
  which is unavoidable when shoulder/hand constraints themselves move faster.

## 2026-07-14 - MetaHuman UEFN-Proportion Assembly

- The original MetaHuman Character `/Game/_mygame/MetaHumans/test` is preserved.
  The editable fitted copy is `/Game/_mygame/MetaHumans/test_UEFNFit`; its final
  fitted MetaHuman assembly is
  `/Game/MetaHumans/test_UEFNExactFull/BP_test_UEFNExactFull` with body mesh
  `/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh`.
- `/Game/_mygame/MetaHumans/SKM_test_UEFNJointCarrier` retains the full MetaHuman
  skeleton and carries the 78 same-named reference joints from
  `/Game/_mygame/SKM_UEFN_Mannequin`. Editor rebuild commands live in
  `ProphecyEditorModule.cpp`: `Prophecy.MetaHuman.RemoveRigs` and
  `Prophecy.MetaHuman.SetBodyJointsFromCarrier`.
- Exact regeneration data is tracked in
  `Tools/MetaHuman/skeleton_snapshots.json`; refresh it from an open editor with
  `Tools/MetaHuman/export_skeleton_snapshots.py`. It contains the full 88-bone
  UEFN and 342-bone fitted MetaHuman reference hierarchies, local/global
  translations, quaternions, scales, asset paths, and fit recipe.
- Direct-animation body:
  `/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody`. It uses the actual
  `/Game/_mygame/SK_UEFN_Mannequin` Skeleton asset, has the 78 shared deforming
  bones in exact UEFN hierarchy/local reference transforms, and leaves the 10
  UEFN attachment/weapon/IK auxiliaries skeleton-only. The current local build
  transfers LOD0 weights from the UEFN mannequin with
  `FSkeletalMeshOperations::CopySkinWeightAttributeFromMesh`, prunes 264
  MetaHuman-only bones, and regenerates all three LODs.
- Direct full character:
  `/Game/_mygame/MetaHumans/BP_test_UEFNDirect`. Its Body component uses the
  direct UEFN-skeleton mesh. Its separate MetaHuman Face component retains facial
  bones and `Face_AnimBP`; the construction script reinitializes that AnimBP after
  components attach so it copies the UEFN-driven body pose by bone name.
- `Tools/MetaHuman/build_uefn_direct_metahuman.py` is the authoritative build and
  audit entry point. Run it through `UnrealEditor-Cmd.exe -run=pythonscript`; use
  `--reuse-existing` for a non-destructive audit. Generated `Content/` assets are
  intentionally recoverable from the tracked C++ commands, script, and snapshot.
- Structural verification without any IK Retargeter: both the UEFN mannequin
  and the direct MetaHuman played
  `/Game/Characters/UEFN_Mannequin/Animations/Sprint/M_Neutral_Sprint_Loop_F_L_20`
  directly at automatic LOD2. The tested main-chain component pose matched within
  `0.06445 cm` at the compressed left-foot sample, the face/body head position was
  exact, and the clean commandlet audit passed with zero errors/warnings.
- The direct body is not production-ready. Sprint frames look clean, but the
  demanding climb pose
  `/Game/Characters/UEFN_Mannequin/Animations/Traversal/Climb/M_Neutral_Traversal_Climb_Start_2_5_run_F_Lfoot`
  at `2.0 s` exposes broken wrist deformation at LOD0 and automatic LOD. The
  runtime pose still matches all 78 shared bones (maximum sampled translation
  delta `0.06251 cm`, rotation delta `0`, face/head delta `0`), so the remaining
  blocker is skin weighting, not animation, LOD selection, or face attachment.
- Weight audit of the transferred body found zero vertices jointly influenced by
  `lowerarm_*` and `hand_*`; 226 vertices per side remain rigidly lower-arm
  weighted. This hard seam is consistent with transferring from the segmented
  UEFN mannequin surface. Global normal-aware inpainting changed unrelated arm
  weights, and a narrow 57-vertex lower-arm/hand blend per wrist still failed the
  same climb pose; neither experiment is a valid final fix.
- Visible UEFN/MetaHuman shoulder contours are not a joint-length metric. The
  fitted head, neck, clavicle, and upper-arm pivots are concentric to within
  `0.000045 cm`; the higher orange UEFN shoulder cap is mesh volume/skinning.

## 2026-07-15 - MetaHuman body on untouched UEFN skeleton: Blender plan

- Scope decision: the character only needs the MetaHuman mesh skinned to the
  untouched `/Game/_mygame/SK_UEFN_Mannequin` skeleton. No RigLogic, no DNA,
  no facial animation, no MetaHuman runtime features. Faces are static
  swappable meshes.
- In-engine pose-fit weight reduction (per-vertex NNLS against 52 sampled
  poses) was abandoned. Two findings worth keeping:
  - Playing UEFN animations on the MetaHuman skeleton through compatible
    skeletons diverges from the real UEFN mannequin pose (up to ~9 cm on twist
    pivots, ~15 cm/37 deg on fingers), so it is not a valid ground truth and
    also not a valid runtime path for extreme poses.
  - Independent per-vertex solves have no spatial smoothness and produce fins
    and webbing even when per-vertex error is ~0.3 cm mean. Details in
    `Docs/ACTIVE_MetaHuman_UEFN_Hand_Fix.md`.
- New pipeline (Blender 5.1, headless, scripts under `Tools/MetaHuman/`):
  1. Export from the editor as FBX: fitted body
     `SKM_test_UEFNFit_BodyMesh` (342 bones, original MetaHuman weights, its
     78 shared bones already sit at exact UEFN reference transforms), the
     MetaHuman face mesh, `SKM_UEFN_Mannequin`, and climb/cliff/sprint/slide
     test animations. Then close the editor.
  2. In Blender, keep the original continuous MetaHuman skinning and fold
     each MetaHuman-only vertex group into its nearest surviving UEFN
     ancestor bone (wrist_inner/outer -> hand/lowerarm, `*_half` -> parent
     phalanx, correctives -> parent). Shared twist bones
     (`upperarm_twist_*`, `calf_twist_*`, `thigh_twist_*`) keep their
     original weights. Smooth only the vertices whose weights changed.
     Delete non-UEFN bones, export FBX.
  3. Iterate visually inside Blender: apply the exported UEFN test
     animations to the reduced armature and render headless Workbench stills
     of wrists/shoulders/knees before touching Unreal again.
  4. Reimport onto the untouched UEFN Skeleton asset, rebuild the direct
     body/BP, rerun the LOD0 + Auto screenshot audits on the demanding climb
     and cliff-catch poses.
- Static-face decision (no facial animation): do not carry MetaHuman DNA,
  RigLogic, facial joints, `Face_AnimBP`, or facial/neck corrective rigs into
  the runtime character. Keep one UEFN-rigged Body component and a separate,
  swappable Head skeletal-mesh component on the same untouched UEFN Skeleton.
  The Head component follows the Body with Leader Pose; no retargeter or face
  animation evaluation is required.
- Multiple MetaHuman faces can be made automatic after one canonical head rig:
  1. Generate every face from a duplicate of the same unrigged MetaHuman base
     body. Change only the face and use **Align Neck to Body** so the neck seam,
     upper-chest/shoulder surface, and body proportions remain canonical.
  2. Assemble/export each generated Face mesh. Require the same MetaHuman
     topology and LOD. Verify vertex count/order; when FBX triangulation or
     split vertices changes indices, match the standard MetaHuman UVs instead.
  3. Rig one canonical Face mesh to the untouched UEFN skeleton. Fold every
     facial joint influence into `head`; retain carefully authored transition
     weights for `head`, `neck_02`, `neck_01`, upper spine, and clavicles over
     the neck/shoulder patch. The face above the transition can be rigid to
     `head`, but the neck/shoulder patch must not be rigid.
  4. Stamp the canonical weights onto every same-topology face by vertex index
     (or UV correspondence), normalize/prune, and import each Head mesh onto
     the same UEFN Skeleton asset. This is the per-face automation step; the
     skinning is not regenerated independently for every identity.
  5. At runtime swap only the Head skeletal mesh/materials/grooms and reapply
     Leader Pose to the Body. Keep the full matching UEFN reference hierarchy
     in every Head export so follower bone indices/transforms cannot diverge.
- Acceptance requirements for every face: neck/shoulder vertices outside the
  editable face mask must remain identical to the canonical template; no seam
  in reference pose; no separation, collapse, or sliding under extreme head
  yaw/pitch/roll plus raised-shoulder/climb poses. A different topology requires
  surface-proximity transfer and a new visual audit, so it is not automatically
  safe.
- MetaHuman Creator can auto-generate its own joints, RBFs, and skin weights,
  but it cannot directly auto-rig onto the raw 88-bone UEFN skeleton: Epic's
  joint-import workflow requires a MetaHuman hierarchy/naming convention. Use
  Creator only to generate aligned face geometry, then apply the canonical UEFN
  head-weight template. References:
  `https://dev.epicgames.com/documentation/metahuman/metahuman-creator-from-template-tool-in-unreal-engine`,
  `https://dev.epicgames.com/documentation/metahuman/body-conform-examples?lang=en-US`,
  `https://dev.epicgames.com/documentation/metahuman/head-controls?application_version=5.7`,
  `https://dev.epicgames.com/documentation/unreal-engine/working-with-modular-characters-in-unreal-engine?application_version=5.7`.
- Measurement-comparison rule: read numeric body values on the unrigged
  MetaHuman Character through **Head and Body > Body Params**; enable **Show
  Measurement** and keep **Scale Ranges by Height** consistent. These values are
  parametric rest-state measurements and do not require an animation pose.
  Body Conform and Import Joints are not comparison tools because they mutate
  the character. For a visual UEFN-pose comparison, duplicate the character,
  create a rig on the duplicate, then use **Window > Preview Scene Details >
  Animation Controller: AnimSequence > Body Animation Type: SpecificAnimation**
  with a one-frame animation created from the UEFN mannequin reference pose.
  MetaHuman Creator previews user animations through its built-in MetaHuman IK
  retarget assets; rigging disables the Head and Body tools, so record the
  measurements first or retain the unrigged source duplicate. References:
  `https://dev.epicgames.com/documentation/metahuman/metahuman-creator-body-params-tool-in-unreal-engine`,
  `https://dev.epicgames.com/documentation/metahuman/navigating-metahuman-creator-in-unreal-engine`,
  `https://dev.epicgames.com/documentation/unreal-engine/animation-editors-in-unreal-engine`.
- Blender agent best practices (do not reinvent):
  - Use **MetahumanToManny** add-on for MetaHuman weight cleanup (twist
    rename, toe fold, finger bulges, seam weld). Script:
    `Tools/MetaHuman/blender_metahuman_to_uefn.py`.
  - **FBX scale**: set scene `unit_settings.scale_length = 0.01` (1 BU = 1
    cm). Export with `apply_scale_options='FBX_SCALE_UNITS'`. Do **not**
    `transform_apply` + `FBX_SCALE_NONE` on skeletal meshes — that was the
    100× import bug.
  - **Weight transfer**: only works with meshes in the **same world-space
    position**. Cross-mesh transfer from UEFN mannequin failed because the
    body blend is ~144 world units tall while a fresh FBX import is ~1.66 m.
    Prefer in-place fold (MetahumanToManny / ancestor merge), not
    mannequin→body projection.
  - **Headless**: `blender --background --python script.py`; validate with
    Workbench renders before reimporting to UE.
  - Shared export helper: `Tools/MetaHuman/blender_ue_export.py`.

## 2026-07-17 - Verified Sequencer pose export to Blender

- The saved FK fit is `/Game/_mygame/MetaHumans/NewLevelSequence`, frame 0,
  bound to actor `test_UEFNFit_ExportedBody5`. The actor's fitted Skeletal Mesh
  was originally transient and disappears after an editor restart. Restore it
  in memory from `Saved/BlenderExchange/Body_MH342.fbx`, assign it to that
  actor, reopen/refresh the sequence, and never save the transient import or
  level assignment.
- Do not use `export_fbx_from_control_rig_section` as the deform-skeleton
  export for this workflow. In UE 5.7 it produced the 342 FK controls as FBX
  null/control objects with per-control actions, not a skinned bone animation.
  The supported usable route is `SequencerTools.export_anim_sequence`: bake
  the evaluated Skeletal Mesh binding to a transient `AnimSequence`, then
  export that AnimSequence as FBX with no preview mesh. Scripts:
  `Tools/MetaHuman/export_saved_fk_pose_from_unreal.py` and
  `Tools/MetaHuman/blender_assemble_modified_metahuman.py`. References:
  `https://dev.epicgames.com/documentation/en-us/unreal-engine/python-scripting-for-animating-with-control-rig-in-unreal-engine`,
  `https://dev.epicgames.com/documentation/en-us/unreal-engine/fk-control-rig-in-unreal-engine`,
  `https://dev.epicgames.com/documentation/en-us/metahuman/animating-metahumans-with-control-rig-in-unreal-engine`.
- Final Blender file:
  `Saved/BlenderExchange/MetaHuman_BodyHead_SequencerModifiedPose.blend`.
  It contains the fitted 342-joint Body and full Face as two separately skinned
  meshes, both in the evaluated Sequencer pose. The pose remains a pose; it is
  not applied as a new rest skeleton, no weights were changed, and FBX
  automatic bone orientation stayed disabled.
- Audit results: Body 8,568 vertices/341 Blender bones plus the FBX root object;
  Head 4,069 vertices/874 Blender bones plus the FBX root object; zero
  unweighted vertices; maximum weight-sum error below `4.7e-8`; 31 shared
  Body/Head bones match in the pose within `0.0000171 cm` and `0 deg`; Blender
  matches the Unreal component-space sample within `0.000562 cm`. Evaluated
  world height is `1.69190 m`. Front, side, three-quarter, and head/shoulder
  Workbench renders were inspected and show a continuous aligned head/shoulder
  patch and symmetric fitted limbs.

## 2026-07-19 - Manual-rigging Blender handoff

- Final working file:
  `Saved/BlenderExchange/ManualRig_CleanWorkingRig_with_NativeExportRig.blend`.
  It contains the fitted UEFN reference mesh, `ally2_Body_Mesh`, and
  `ally2_Face_Mesh` in the approved modified pose. The source handoff
  `ManualRig_UEFN_Posed_with_ally2_Meshes.blend` remains unchanged.
- The file deliberately contains two UEFN armatures. Use
  `UEFN_WORKING_CLEAN_RIG` for bone selection and manual weight painting. It
  was imported with Blender Automatic Bone Orientation, fitted to the approved
  pose as its working rest state, and then given continuous anatomical
  parent/child tails. Fifty primary joins across the spine/head, arms, legs,
  and fingers validate with a zero tail-to-child-head gap. Twist, IK, weapon,
  and attachment bones are retained but hidden by default for clarity; use
  `Alt-H` if they are intentionally needed while weighting.
- `UEFN_NATIVE_EXPORT_RIG` is the hidden authoritative UEFN armature. Its FBX
  rest matrices have maximum recorded change `0.0`; it was not auto-oriented,
  reparented, reposed as rest, or otherwise edited. Use this armature—not the
  clean working armature—for the final skeletal-mesh export to Unreal/UEFN.
  Never export both armatures.
- The working and native armatures contain the same 87 Blender bone names and
  the same parent hierarchy. Weight groups authored against the clean rig can
  therefore be used with the native rig without renaming. The connected tails
  and `use_connect` flags are Blender-only visual/authoring aids and are not an
  export-skeleton modification.
- Verified Blender 5.1.1 audit: 6,009 UEFN reference vertices; maximum clean
  versus native fitted-mesh world delta `3.51e-7 m` (RMS `1.21e-7 m`); maximum
  working versus native joint-head delta `5.02e-7 m`; identical bone-name sets;
  and zero native rest-matrix delta. No native or MetaHuman geometry or weights
  were modified. Full machine-readable results are in
  `Saved/BlenderExchange/ManualRig_CleanWorkingRig_Audit.json`.
- Visual checks:
  `Saved/BlenderShots/ManualRig_CleanWorkingRig_Viewport.png`,
  `ManualRig_CleanWorkingRig_Front.png`, and
  `ManualRig_CleanWorkingRig_Side.png`. The viewport check confirms continuous
  shoulder-elbow-wrist and hip-knee-ankle chains. The front and side overlays
  confirm the fitted UEFN limb silhouettes still follow the MetaHuman closely;
  remaining differences are expected surface volume and anatomy differences.
- Rebuild/open scripts:
  `Tools/MetaHuman/blender_build_clean_uefn_working_rig.py` and
  `Tools/MetaHuman/blender_open_clean_working_rig.py`.
- Rationale: Blender FBX bone tails are a Blender visualization convention,
  while Unreal identifies the skeleton by joint hierarchy, names, and bind/rest
  transforms. A single auto-oriented armature is convenient to edit but unsafe
  as the authoritative Unreal export skeleton. Keeping a clean authoring copy
  beside an untouched native copy provides normal Blender bones without losing
  the exact UEFN skeleton identity.
- References:
  `https://dev.epicgames.com/documentation/unreal-engine/fbx-skeletal-mesh-pipeline-in-unreal-engine`,
  `https://dev.epicgames.com/documentation/unreal-engine/fbx-import-options-reference-in-unreal-engine`,
  `https://docs.blender.org/manual/en/latest/addons/import_export/scene_fbx.html`.

## 2026-07-20 - Four mesh-only MetaHuman Blender sources

- Final files under `Saved/BlenderExchange/FourCharacters/`:
  `BP_boss_Meshes.blend`, `BP_Enemy_Meshes.blend`,
  `BP_girl_Meshes.blend`, and `BP_savagee_Meshes.blend`.
  Each file contains exactly two scene objects named `<character>_Body_Mesh`
  and `<character>_Face_Mesh`. There are no armatures, UEFN objects, Armature
  modifiers, animations, or inherited vertex groups.
- The placed level actors were resolved through the live editor rather than by
  guessing from blueprint names. Source assets were:
  - `BP_boss`: `SKM_test_UEFNFit2_BodyMesh` and
    `SKM_test_UEFNFit2_FaceMesh` under `/Game/_mygame/MetaHumans/boss/`.
  - `BP_Enemy`: `SKM_test_UEFNFit1_BodyMesh` and
    `SKM_test_UEFNFit1_FaceMesh` under `/Game/MetaHumans/test_UEFNFit/`.
  - `BP_girl`: `SKM_test_UEFNFit5_BodyMesh` and
    `SKM_test_UEFNFit5_FaceMesh` under `/Game/_mygame/MetaHumans/girl/`.
  - `BP_savagee`: `SKM_test_UEFNFit3_BodyMesh` and
    `SKM_test_UEFNFit3_FaceMesh` under `/Game/_mygame/MetaHumans/savagee/`.
- Technique: Unreal `SkeletalMeshExporterFBX` exports Body and Face assets
  separately at LOD0 without morph targets or animation. Blender imports both
  with the same non-auto-oriented FBX convention as the verified manual-rig
  handoff. Their shared reference joints are checked before the rigs are
  removed. Each mesh is detached while preserving its evaluated world matrix;
  then the identity Armature modifier, source armature, wrapper, and vertex
  groups are removed. The output keeps the established `0.01` world scale so
  appending into the manual-rig scene preserves alignment and human size.
- Verification: all four files were saved and reopened with exactly two mesh
  objects and zero armatures/UEFN-named objects. Body meshes have 8,568
  vertices; Face meshes have 4,065 or 4,067 vertices. Heights are
  `1.7171-1.7444 m`. Maximum body/face shared-joint translation disagreement is
  `2.44e-7 m`; maximum geometry change from stripping the rest-pose rigs is
  `7.16e-7 m`. Front and side renders for every character were inspected and
  show aligned head/neck/shoulder surfaces, intact limbs, and no malformed or
  exploded geometry. Evidence is under
  `Saved/BlenderShots/FourCharacters/`; full results are in
  `Saved/BlenderExchange/FourCharacters/BlenderMeshFiles_Audit.json`.
- Rebuild scripts:
  `Tools/MetaHuman/probe_four_character_meshes.py`,
  `Tools/MetaHuman/export_four_character_meshes.py`, and
  `Tools/MetaHuman/blender_build_four_character_mesh_files.py`. The Unreal
  export step modifies and saves no Unreal package, blueprint, actor, or level.
- References:
  `https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/SkeletalMeshExporterFBX?application_version=5.7`,
  `https://dev.epicgames.com/documentation/unreal-engine/fbx-skeletal-mesh-pipeline-in-unreal-engine`,
  `https://docs.blender.org/manual/en/latest/addons/import_export/scene_fbx.html`.

## 2026-07-23 - Reusable Ally2-to-Boss skin-weight transfer

- Immutable source file:
  `C:/Users/singerie/Documents/Blender/forcodex.blend`. Verified result:
  `C:/Users/singerie/Documents/Blender/forcodex_BossWeighted.blend`. The
  original was not overwritten.
- Target `boss` is now parented to `UEFN_WORKING_CLEAN_RIG.001` and has one
  Armature modifier targeting that rig. All 11,374 target vertices are
  weighted; there are zero unknown/non-UEFN groups, no vertex has more than
  eight influences, and maximum normalized-weight error is `4.29e-8`.
- Body weights come from `ally2_Body_Mesh` via world-space nearest-face
  barycentric interpolation. This is the scripted equivalent of Blender
  Transfer Weights with `Nearest Face Interpolated`, all source layers, name
  matching, and Replace mode. Source vertex weights are normalized first
  because the source object retained weights from two compatible rig layers.
- A body-only transfer is insufficient because `boss` includes a head while
  the rigged Ally2 Body stops at the collar. The head/neck region therefore
  uses `ally2_Face_Mesh` as a second spatial source. MetaHuman facial groups
  are collapsed to UEFN `head`; Neck A/Adams-apple groups to `neck_01`; Neck B
  groups to `neck_02`; shoulder helper groups to their matching
  spine/clavicle/upper-arm UEFN bones. Body and face transfers blend smoothly
  across the shared collar interval (`Z 1.365845-1.445845 m`), avoiding a hard
  neck seam.
- The reproducible implementation is
  `Tools/MetaHuman/blender_transfer_boss_weights.py`. It can be rerun
  headlessly and always writes a separate result. The output also contains a
  Blender text block named `BOSS_WEIGHT_TRANSFER_README`.
- The imported Boss FBX carried custom split normals and stale sharp-edge
  flags. They appeared smooth in the rest pose but exposed individual
  triangles after armature deformation. The reusable script now removes the
  `custom_normal` and `sharp_edge` attributes, clears per-edge sharp flags,
  and enables smooth shading on every polygon before saving. A new frame-29
  stress render confirms continuous shading through the deformed neck,
  shoulders, torso, hips, and limbs; geometry and skin weights are unchanged.
- Verification: the output was saved, closed, and reopened headlessly. It
  retained 87 UEFN-named groups, one correct Armature modifier, the correct
  armature parent, and the saved frame `0-29` rig action. Frame 0 was visually
  inspected and is anatomically intact. The intentionally extreme frame-29
  stress pose moves 11,359 vertices by more than 1 mm and visibly carries the
  head, torso, fingers, arms, knees, ankles, and feet with the rig. Audit data
  is in `Saved/BlenderExchange/BossWeightTransfer_Audit.json`; renders are
  under `Saved/BlenderShots/BossWeightTransfer/`.
- Blender UI reproduction for a body-only mesh: put both meshes in the same
  rest pose and overlapping world transform; select the weighted source first
  and the unweighted target last; enter Weight Paint on the target; choose
  `Weights > Transfer Weights`; in the operation panel select all/by-name
  source layers, destination by name, `Nearest Face Interpolated`, and
  `Replace`; then run Normalize All, Clean near `0.0001`, and Limit Total to
  eight before adding the target's Armature modifier. For a combined
  body-plus-head mesh, use the script because the required second source and
  collar blend are not a reliable one-click operation.
- References:
  `https://docs.blender.org/manual/en/latest/sculpt_paint/weight_paint/editing.html`,
  `https://docs.blender.org/manual/en/latest/modeling/modifiers/modify/data_transfer.html`.

## 2026-07-23 - Boss mesh imported on the native UEFN skeleton

- Immutable Blender source:
  `C:/Users/singerie/Documents/Blender/bossfinalsave.blend`. The Unreal-ready
  clean scene is
  `Saved/BlenderExchange/BossUEFN/Boss_UEFN_ExportClean.blend`, containing
  exactly `SKM_Boss_UEFN` and the authoritative native FBX rig `root.001`.
  `bossfinalsave.blend` was not overwritten.
- The authoring mesh is fitted to the MetaHuman-shaped working rig, while
  direct UEFN animation requires the original mannequin bind pose. Do **not**
  inverse-skin vertices or manually reposition edit bones. Both approaches
  previously produced visible mesh/bone offsets or damaged the neck, wrists,
  and feet.
- Correct conversion method (2026-07-24): duplicate the exact Boss-bound
  `UEFN_WORKING_CLEAN_RIG.001`; clear its pose/action; disconnect every bone
  only on that temporary copy; and point the existing Boss Armature modifier
  to it. Import a second copy of the native UEFN FBX with Blender Automatic
  Bone Orientation, then apply the same Blender-only primary-chain
  connections used by the fitted working rig. Pose the temporary disconnected
  driver to those target rest matrices. The existing Armature modifier—not a
  vertex solver—then moves the already well-skinned Boss mesh into the native
  UEFN reference pose.
- Bake the modifier's evaluated result, normalize and limit the existing
  UEFN-named weights to eight influences, clear the untouched authoritative
  native rig to its true rest pose, and rebind the baked mesh to that rig at
  identity. Discard both temporary rigs. No source vertex, source edit-bone,
  or source-weight correction is used. Swapping to the temporary driver
  changes the fitted surface by at most `3.59e-7 m`; the driver reaches the
  target matrices within `1.64e-5` Blender matrix units; final native-rig
  rebinding changes the baked surface by at most `2.67e-7 m` (RMS
  `1.26e-7 m`).
- The Automatic Bone Orientation target must receive the same connected-tail
  convention as the fitted working rig before matrices are copied. Using the
  raw auto-oriented target directly is the specific error that twisted and
  displaced the feet. Trying to copy native matrices onto the still-connected
  fitted armature is also invalid because connected children cannot accept
  independent joint translations.
- The conversion preserves the source topology exactly: 11,374 vertices and
  22,068 polygons. It performs no seam snapping, welding, inverse skinning, or
  other geometry edit. Smooth shading is restored by clearing stale custom
  split normals/sharp-edge data, but skin/material appearance must still be
  checked in Unreal with the original material instances.
- The combined mesh has eight stable polygon material regions: Body, Teeth,
  EyeL, EyeR, EyeShell, Lacrimal, Eyelashes, and FaceSkin. Unreal reuses the
  original Boss Body and Face material instances from the assembled
  MetaHuman rather than accepting basic FBX-generated materials. This keeps
  the skin and underwear textures and preserves the original material-slot
  order.
- Blender's FBX exporter is told the scene is in centimeters, so the native
  armature/mesh transforms are promoted by `100` in the isolated export scene.
  This produces the correct Unreal size without relying on an Unreal import
  scale override. Final Unreal bounds are approximately `101.06 x 34.69 x
  167.47 cm`.
- Final FBX:
  `Saved/BlenderExchange/BossUEFN/SKM_Boss_UEFN.fbx`. A cold Blender reimport
  verifies one mesh, one armature, all 87 expected Blender bone names in the
  exact native order/hierarchy, 11,374 vertices, no unknown groups, no
  unweighted vertices, normalized weights, and at most eight influences.
- The latest FBX was cold-reimported into a factory-started Blender 5.1.1 and
  visually inspected in neutral, idle, sprint, climb, and cliff-catch poses.
  The neck/shoulders remain continuous; both wrists, hands, ankles, and feet
  remain attached and anatomically oriented. This 2026-07-24 regeneration has
  not yet been imported into Unreal, so the older persistent
  `/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN` asset is not evidence for
  the latest file and should be replaced/reimported before Unreal validation.
- Reproducible scripts:
  `Tools/MetaHuman/blender_prepare_boss_uefn_export.py`,
  `Tools/MetaHuman/blender_prepare_boss_uefn_export_driver.py`,
  `Tools/MetaHuman/blender_validate_boss_uefn_fbx.py`,
  `Tools/MetaHuman/blender_render_boss_uefn_animation_audit.py`,
  `Tools/MetaHuman/import_boss_uefn_to_unreal.py`,
  `Tools/MetaHuman/run_boss_uefn_live_import.py`, and
  `Tools/MetaHuman/audit_boss_uefn_in_unreal.py`, plus
  `Tools/MetaHuman/audit_boss_fixed_neutral_in_unreal.py`. Machine-readable audits are
  under `Saved/BlenderExchange/BossUEFN/`; Blender and Unreal visual evidence
  is under `Saved/BlenderShots/BossUEFN/` and
  `Saved/CodexLiveShots/BossUEFN/`.
- References:
  `https://dev.epicgames.com/documentation/en-us/unreal-engine/skeleton-assets`,
  `https://dev.epicgames.com/documentation/en-us/unreal-engine/fbx-skeletal-mesh-pipeline-in-unreal-engine`,
  `https://dev.epicgames.com/documentation/en-us/unreal-engine/fbx-import-options-reference-in-unreal-engine`,
  `https://dev.epicgames.com/documentation/unreal-engine/fbx-material-pipeline-in-unreal-engine`.

## 2026-08-06 - Physics-simulated Potence rope retraction

- `/Game/_mygame/assets/hanging/A_Potence.ShrinkRope` now calls the native
  `Update Potence Rope Physics` helper on each of its existing terminal paths.
  No unrelated Blueprint graph or level logic was changed.
- Retraction is normalized `0..1` and continuously bidirectional. `joint`
  remains kinematic; `joint1` through `joint27` keep their original full-size
  bodies and constraint frames and remain dynamic for the whole session. The
  helper reels that stable chain above the wood by moving only the kinematic
  root target along the reference-rope direction. This avoids the near-zero
  constraint lever arms that caused the free tip to correct by a full segment.
- While this helper owns the root, the runtime component uses
  `EKinematicBonesUpdateToPhysics::SkipAllBones`; otherwise the skeletal
  pre-physics update restores the root to its reference pose and alternates
  against the reel target. Dynamic child bodies still feed their simulated
  transforms back to the skeletal pose.
- Bodies fully reeled above the anchor retain their solver/mass topology but
  receive an empty Chaos shape filter, so they collide with nothing. Expansion
  restores normal BodyInstance filters in place. No body or constraint is
  destroyed, recreated, rescaled, or converted to kinematic.
- Do not replace the in-place filter changes with
  `FBodyInstance::SetCollisionEnabled`: that API can recreate skeletal instance
  bodies when crossing the physics/no-physics boundary and invalidate cached
  body/constraint pointers.
- Runtime rendering and physics now use the same single
  `UProphecyRetractableSkeletalMeshComponent` named `SKM_RopeHang`. It keeps the
  original `SKM_RopeHang` asset, `MI_RopeHang`, and Physics Asset; no procedural
  tube, poseable mesh, hidden physics duplicate, or second Blueprint component
  is created. In `FinalizeBoneTransform`, fully consumed bones collapse to the
  fixed reference anchor and only their local Z scale approaches zero. The
  active boundary bone receives the fractional Z scale, while X/Y stay exactly
  `1` and all later bones keep scale `1,1,1`. This render-pose edit occurs after
  Chaos supplies the simulated bone transforms and does not resize the PHAT
  bodies.
- Live `/Game/mybasic` diagnosis sampled the Blueprint's unchanged automatic
  Amount every frame. The old implementation produced 12 tip corrections over
  5 cm in eight seconds, with a `10.57 cm` maximum physics step and `9.30 cm`
  unexplained after accounting for velocity. The events occurred when the
  active segment advanced; disabling collision retirement did not remove them,
  while holding constraint frames fixed removed all of them.
- Final auto-shrink validation recorded 309 post-physics samples over six
  seconds: zero steps over 5 cm, zero velocity residuals over 3 cm, a uniform
  `0.378 cm` maximum root step, `1.16 cm` maximum rendered-tip step, and
  `2.99 cm` maximum physics step with only `0.58 cm` residual. A separate
  459-sample `0 -> 0.45 -> 0` cycle had zero hard events in either direction;
  the root returned exactly and the physics tip returned within `0.13 cm`.
  Median frame delta was `17.69 ms`. PIE tests paused PCG transiently and did
  not save or modify the Blueprint or level.
- The final single-component installation was recovered after the editor OOM,
  refreshed, and compiled with Blueprint status `3` (up to date). A PIE smoke
  test at Amount `0.35` confirmed `joint` was kinematic, `joint1`-`joint9`
  stayed simulated with render scale `1,1,0.001`, `joint10` stayed simulated at
  `1,1,0.55`, and `joint11` onward stayed simulated at `1,1,1`. The component
  retained Query and Physics collision, the original mesh/material, and was the
  only rope-render component. Only `A_Potence` was saved; the level was not.
- A later noose test exposed an obsolete branch still present in `ShrinkRope`:
  it replaced the correct component asset at runtime with
  `SKM_RopeHang_Shrink` and installed `ABP_RopeHang_Shrink`, despite the editor
  template still showing the original mesh. This made the noose follow the real
  `joint27` physics body while a legacy mesh rendered elsewhere, which looked
  like a second invisible rope. `ShrinkRope` is now reduced from 15 nodes to its
  function entry, the existing `SKM_RopeHang` reference, and one
  `UpdatePotenceRopePhysics` call.
- `A_Potence` now calls `Weld Noose To Rope End` once from BeginPlay, after both
  Chaos actors exist. It disables the obsolete external `PhysicsConstraint`,
  snaps the noose body origin to `joint27`, and performs one simulated-body
  weld. The noose collision becomes part of the terminal rigid body; there is
  no second rope, compliant solver joint, or per-frame attachment correction.
  The terminal vertex ring of the existing `SKM_RopeHang` mesh is weighted
  rigidly to `joint27`. A moving-collision and full `0 -> 0.6 -> 0` retraction
  test both measured a `0.0 cm` attachment gap.
- `PHAT_RopeHang` stores per-body Chaos overrides for `joint` through
  `joint27`: 12 position, 2 velocity, and 24 projection solver iterations. The
  cached runtime rope state applies the same values once so already-instanced
  bodies and live upgrades are configured consistently. These settings are
  local to the 28 controlled rope bodies and do not alter project-wide solver
  settings, the Physics Asset's locked linear/angular limits, collision shapes,
  masses, or constraint frames. An identical swept
  `SandboxCharacter_CMC` contact that previously accumulated `9.48 cm` of
  downward error at the terminal body now measured `0.000 cm`; the kinematic
  root remained fixed within `0.000 cm`. The validation capture recorded
  `19.24 ms` median and `22.14 ms` p95 frame deltas, and a bidirectional shrink
  capture recorded `20.67 ms` median and `25.58 ms` p95 with no hitch-sized
  frame. Only transient PIE actors were moved for these tests; the Blueprint
  and level were not changed or saved.
- Implementation:
  `Source/GameAnimationSample3/Private/ProphecyPhysicsConstraintBlueprintLibrary.cpp`
  and
  `Source/GameAnimationSample3/Public/ProphecyPhysicsConstraintBlueprintLibrary.h`,
  plus
  `Source/GameAnimationSample3/Private/ProphecyRetractableSkeletalMeshComponent.cpp`
  and
  `Source/GameAnimationSample3/Public/ProphecyRetractableSkeletalMeshComponent.h`.
- References:
  `https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/FBodyInstance`,
  `https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/USkeletalMeshComponent`.

## 2026-08-06 - PIE startup hitch profile

- A 90-second CSV capture and a focused Unreal Insights CPU/task trace show
  that PIE world creation is not the long freeze: `StaticDuplicateObject`
  took `0.330 s` and total PIE startup took `0.893 s`. The large hitches occur
  in the first runtime frames.
- The primary stall is PCG execution. One captured frame took `8.208 s`;
  `UPCGSubsystem::Tick` spent `5.848 s` synchronously executing
  `FPCGSplineSamplerElement::Execute`. Two other spline-sampler jobs occupied
  worker threads for `8.893 s` and `4.663 s`, causing Game, Render, and RHI
  thread waits. This is the source of the multi-second startup freezes.
- The original `PCG_Dirt` and `PCG_SplineGrass` volume components are
  deactivated and set to Generate On Demand, but their eight local components
  in four `PCGPartitionActor`s are still activated and set to Generate On
  Load. They therefore execute when the duplicated PIE world initializes.
- The level also contains 25,089 ISM instances; 24,969 are PCG-owned grass
  instances. They add first-frame scene registration and draw-command/PSO
  work, but the trace distinguishes this from the dominant spline-sampling
  stall.
- Secondary findings: `A_Potence_C_1` currently emits the Blueprint message
  `haiiii 0.5` every frame, indicating an unnecessary per-frame Print String;
  automatic PSO precaching produced sub-100 ms spikes but not the multi-second
  freezes. The editor used roughly 17-18 GB private memory with only about
  2.2-2.5 GB of free physical RAM and 4.5 GB free on C:, which can amplify
  waits. Do not delete DDC or shader caches before the next benchmark.
- Evidence:
  `Saved/Profiling/CSV/Profile(20260806_180739).csv` and
  `C:/CodexProfiles/pie_startup_deep.utrace`.
- References:
  `https://dev.epicgames.com/documentation/en-us/unreal-engine/using-pcg-generation-modes-in-unreal-engine`,
  `https://dev.epicgames.com/documentation/unreal-engine/pcg-runtime-generation-debugging-in-unreal-engine`,
  `https://dev.epicgames.com/documentation/unreal-engine/unreal-insights-in-unreal-engine`,
  `https://dev.epicgames.com/documentation/unreal-engine/pso-precaching-for-unreal-engine`.

## 2026-08-08 - Boat-local water cutout prototype

- The user-created masked test material
  `/Game/_mygame/assets/boat/StaticMeshes/NewMaterial` now removes water using
  an authored footprint texture rather than `DistanceToNearestSurface`.
  `/Game/_mygame/assets/sand/M_Water` was not modified.
- LOD 0 of `SM_Boat_Inside` was extracted from its 999 vertices / 739
  triangles and projected in local XY into the 512x512 mask
  `/Game/_mygame/assets/boat/StaticMeshes/Generated/T_BoatInside_WaterMask`.
  The texture is non-sRGB, Masks-compressed, bilinear, and clamped. It retains
  the blockout's tapered silhouette at roughly 0.7 cm per texel along its long
  axis; this is not a box approximation or a Global Distance Field sample.
- `NewMaterial` contains 19 standard expressions. It transforms Absolute
  World Position into the test blockout's local XY with parameterized origin
  and world-to-local basis vectors, performs one mask texture sample, and
  connects `OneMinus(mask.r)` to Opacity Mask. The graph recompiled and saved
  without material errors. Analytical samples measured opacity `0` at the
  footprint center/bow/stern and `1` outside both its side and bow bounds.
- The standalone level actor `SM_Boat_Inside` was left in the level but its
  mesh component was made invisible, non-shadow-casting, and collision-free so
  the cutout can be inspected. The already-dirty `/Game/mybasic` level was not
  saved. `NewMaterial` was already assigned to the `SM_SkySphere` level actor
  as well as `ocean`; that pre-existing assignment was deliberately untouched.
- The current parameter defaults match the standalone test actor transform.
  For a moving boat, update `BoatMask_Origin`,
  `BoatMask_WorldToLocalX`, and `BoatMask_WorldToLocalY` on a water MID, or
  migrate those three values to an MPC driven by the boat. The mask texture and
  UV bounds remain constant, so movement requires no rebake and only one
  texture sample remains in the pixel shader.
- A recoverable empty-material backup is at
  `/Game/_mygame/assets/boat/StaticMeshes/_CodexBackups/NewMaterial_PreBoatMask_20260808_022307`.
- References:
  `https://dev.epicgames.com/documentation/en-us/unreal-engine/utility-material-expressions-in-unreal-engine`,
  `https://dev.epicgames.com/documentation/unreal-engine/runtime-virtual-texturing-in-unreal-engine`,
  `https://dev.epicgames.com/documentation/unreal-engine/virtual-texturing-settings-and-properties-in-unreal-engine`,
  `https://dev.epicgames.com/documentation/unreal-engine/material-inputs-in-unreal-engine`.

## 2026-08-08 - Optimized gentle boat-wave physics force

- Added the Blueprint-callable native node `Apply Gentle Boat Wave Forces`
  (`UProphecyPhysicsConstraintBlueprintLibrary::ApplyBoatWaveForces`). It is
  intended to be called once from Tick on the boat's simulated primitive.
- The node replaces independent random impulses with a deterministic,
  continuous three-component directional wave spectrum. Seeded phase and
  frequency/direction spread prevent obvious repetition without generating
  random values each frame.
- It evaluates the spatial wave slope across four virtual hull corners and
  analytically accumulates the result into one vertical force and one physical
  roll/pitch torque. Smooth two-frequency horizontal drift plus linear/angular
  damping prevents unbounded random-walk velocity; optional low-frequency yaw
  remains acceleration-based and mass-independent.
- Runtime work is allocation-free and stateless: three `SinCos` evaluations,
  two slower sine evaluations, one yaw sine, and at most three Chaos calls per
  active boat per frame. Unreal maintains per-frame forces across enabled
  physics substeps.
- Tunable inputs include overall strength, heave acceleration, base frequency,
  frequency spread, wave/drift directions, direction spread, wavelength, hull
  half-dimensions, rocking response, drift acceleration/frequency,
  horizontal/vertical/angular damping, yaw acceleration, seed, time scale,
  phase offset, and optional bone name.
- Live Coding compiled and reflected `ApplyBoatWaveForces` successfully. A
  reflection call against the live 309.8 kg `BP_Boat.SM_Boat` body returned
  success; the validation strength was only `0.001` and produced no measurable
  transform or velocity delta. `BP_Boat` itself was not edited or wired.
- References:
  `https://developer.nvidia.com/gpugems/gpugems/part-i-natural-effects/chapter-1-effective-water-simulation-physical-models`,
  `https://repository.tudelft.nl/file/File_87c46363-97ef-4bbb-a540-3050546f907d?preview=1`,
  `https://dev.epicgames.com/documentation/unreal-engine/physics-sub-stepping-in-unreal-engine`.

## Unreal collision, navigation, and village crowd

- Integration ownership is explicit: Unreal owns physical truth and the
  standalone/core side owns intent. The current standalone slice contains the
  persistent Unreal collision snapshot, static navigation, and the village
  crowd runtime. PIE now exchanges the placed manager's agent roots and intent
  with that same standalone runtime through fixed binary shared memory.
- Added the editor console command `Prophecy.ExportSelectedSimCollision`. It
  exports only selected actors, so the user can provide the relevant-object
  list incrementally. Each exported object carries actor GUID plus component
  name, actor label/class, collision source, world-space vertices, and indices.
- `Prophecy.ExportSelectedSimComplexCollision` is the explicit override for
  selected static and instanced mesh components. It exports their underlying
  `UStaticMesh::GetPhysicsTriMeshData` even when component collision is disabled;
  it does not change or save asset collision settings. The normal command keeps
  respecting each component and `UBodySetup` collision mode.
- Snapshot schema is `prophecy.unreal-collision.v1`; coordinates are meters in
  the sim convention (X/Y ground plane, Z up). Static Mesh Components resolve
  `UBodySetup::GetCollisionTraceFlag()`: sphere/box/capsule/convex simple
  collision is exported when applicable, while `UseComplexAsSimple` uses
  `UStaticMesh::GetPhysicsTriMeshData`. Blueprint actors work through their
  contained Static Mesh Components. Instanced Static Mesh Components export one
  object per instance using the exact instance world transform and underlying
  mesh `UBodySetup`; this permits explicitly requested PCG debug geometry to use
  its authored asset collision even when the generated component has runtime
  collision disabled. Unsupported or absent collision is listed in warnings
  rather than approximated silently.
- The two `/Game/mybasic` landscapes are now a persistent manual bake, not a
  launch-time rebuild. `StandaloneSim/tools/bake_landscape_collision.cpp`
  finds each exact dominant flat rectangle, replaces only that rectangle with
  one plane quad, and copies every triangle outside it unchanged. It runs only
  when the user explicitly asks for a landscape rebuild.
- The main plane is at `Z=0 m` and retains 102,870 exact shore/boundary
  triangles. `Landscape2` is at `Z=0.0250104 m` and retains 14,630. The saved
  `StandaloneSim/data/unreal_collision.json` also contains the exact transformed
  `ocean`, `ocean2`, `waterline`, and `waterline2` quads from `/Game/mybasic`.
  It additionally contains the ten prior actors from the Outliner folder
  `houses` plus `tent`, with no house-export warnings. The five central
  `SM_house_*` actors now use their explicitly exported underlying complex
  meshes; the five cabin Blueprints retain their configured complex-as-simple
  collision, and `tent` uses its forced complex mesh at 3,341 triangles. Folder
  `Hay` contributes 11 forced-complex static mesh actors at
  1,136 triangles each, for 12,496 triangles total and no warnings.
  The six `BP_SplineFence*` actors in folder `Splines` drive `PCG_Fence`; its
  seven generated ISM components contribute 628 exact complex instance meshes
  and 2,224,099 triangles. The 15 actors in `mountains1` and 16 actors in
  `mountains2`, now including `slave mountain`, contribute 31 exact complex
  meshes and 226,218 triangles. No
  fallback geometry, simplification, or fence/mountain warning was used. The
  complete cache is 701 objects, 4,158,798 triangles, and 600,112,418 bytes. No
  cutoff, smoothing, decimation, or height approximation is applied to retained
  landscape or house geometry.
- Landscape hole/material masks are not represented and remain two explicit
  cache warnings; the debug surface is not a replacement for Unreal physics.
- The raylib viewer auto-loads `StandaloneSim/data/unreal_collision.json` or an
  explicit `--environment-collision` path. Workspace builds prefer the canonical
  source cache and portable builds fall back to their packaged copy. The JSON is
  authoritative; an unchanged snapshot loads prelit immutable mesh buffers from
  the versioned 101,457,513-byte `unreal_collision.json.rendercache` sidecar after
  validating the JSON byte size and write time. A missing or stale sidecar performs
  the JSON parse, static lighting, and GPU preparation once, then refreshes the
  sidecar. Measured launch through the eighth rendered frame fell from 30.128
  seconds without the sidecar to 1.061 seconds with it. An open
  viewer checks the chosen file signature at two hertz, waits for a changed write
  to remain stable for half a second, builds replacement immutable 16-bit GPU
  chunks, and swaps them atomically while retaining the previous valid scene on
  an invalid write. No flat detection, shore extraction, environment allocation,
  geometry rebuild, or lighting occurs during simulation ticks or normal frames.
  Flat landscape planes render dirt brown, retained shore triangles render sand
  yellow, water-plane quads render water blue, `Hay1` through `Hay11` use hay
  yellow RGB `(228,190,58)`, other collision uses muted blue-grey, and complex
  mountain meshes use warm rock grey RGB `(218,210,210)`.
  At cache load, each static mountain triangle receives one flat color from its
  real geometric face normal: 68% ambient, 24% two-sided directional detail,
  and up to 8% upward sky fill. This preserves the exact complex geometry while
  exposing its facets and keeping back-facing ranges readable. The GPU cache
  splits only mountain render vertices per triangle; no lighting, geometry work,
  or update occurs during normal frames. Other surfaces retain their existing
  smooth vertex-normal ambient-plus-diffuse bake. Both use `/Game/mybasic` actor
  `DirectionalLight`, whose snapshot forward vector is
  `(0.4863177, -0.1161780, -0.8660241)`. Collision is drawn two-sided for debug
  cameras inside shells. `sim_core` never touches it.
- Verification: Unreal 5.7 and the Release viewer build successfully. The
  initial real export verified `SM_house_7` at 684 simple-collision triangles;
  the final canonical cache replaces all five `SM_house_*` entries with fresh
  forced-complex exports while leaving the other 696 objects unchanged.
  `Landscape2` at 80,850 raw triangles, and the main landscape at 290,322 raw
  triangles. `Saved/SimCollisionTests/houses-shaded.png` confirms two-sided
  house visibility and static directional-light shading.
  `Saved/SimCollisionTests/complex-fences-mountains-live.png` confirms the final
  complex fence geometry in the running viewer. The refreshed
  `mountains2` export contains 16 objects and 158,313 triangles with zero
  warnings; `slave mountain` contributes 98,647 of those triangles.
  `Saved/SimCollisionTests/slave-mountain-live.png` confirms its distinctive
  arch in the actual viewer. The later tent-plus-Hay complex export contains 12
  objects and 15,837 triangles with zero warnings.
  `Saved/SimCollisionTests/tent-hay-live.png` confirms the added geometry in the
  actual viewer. The final persistent cache is 600,112,418 bytes; the viewer
  loaded all `701 objects, 4158798 triangles, 2 warnings`; the watched refresh
  completed in the same viewer process and returned it to a responsive state.
  The default camera remains centered in the house area, so that capture does
  not frame the distant mountain folders. A focused static-cache check at
  `Saved/SimCollisionTests/mountain-detail-cached.png` confirms the lighter
  per-triangle mountain facets. The two warnings remain the existing landscape
  mask warnings. A watched-copy timestamp change while the viewer remained open
  separately logged the expected successful live reload.
- Static navigation is a separate manual bake generated by
  `prophecy_navigation_baker`; launches never rebuild it. The baker reads the
  same canonical complex-collision cache, corrects the sim-to-Recast winding
  change, rasterizes at 10 cm horizontal and 5 cm vertical resolution, and
  writes the compact `StandaloneSim/data/mybasic.navbin` Detour artifact. The
  measured `/Game/mybasic` `my guy` profile is fixed at 0.30 m capsule radius,
  1.72 m capsule height, 0.30 m maximum climb, and 44.765083-degree maximum
  slope. The selected grid represents those as exactly three radius cells,
  thirty-five height cells (1.75 m), and six climb cells. The exact horizontal
  bench-top source triangles in the dense-village houses and tent source
  triangles rising above that climb allowance are marked nonwalkable before
  rasterization. The static bake preserves the real attic stairs without adding
  a synthetic vertical link.
- Raised/open entrance validation samples three capsule-width horizontal rays
  0.75 m above the lower surface. Four current entrance links pass that check.
  The viewer-only navigation layer is toggled with `N` or the layers toolbar
  button: exterior-connected navigation is green, disconnected walkable islands
  use distinct colors, white lines expose navigation triangles, and accepted
  entrance links are orange. Hidden navigation performs no draw work and none of
  this debug data enters `sim_core`. The baker disables 423 house-roof and
  tent-exterior polygons across all five `BP_LogCabin*` houses, all five
  `SM_house_*` houses, and `tent` while retaining covered interior floors and
  stair surfaces. Disabled polygons are ignored by Detour, the inspector, and
  the debug renderer. The current 3,096,236-byte bake retains four entrance
  links. It contains a validated
  `SM_house_5` attic to `SM_house_7` attic test: start
  `[-24.1243, 2.12001, 3.3]`, goal `[8.24065, -3.89999, 3.55]`, 60 Detour
  corridor polygons, and 25 straight-path corners. The path
  descends the retained `SM_house_5` stair surfaces, crosses the exterior, and
  ascends the retained `SM_house_7` stair surfaces; no artificial vertical link
  is present. `--navigation-test` shows a looping walking skeleton, cyan route,
  blue start, and pink goal. The route and endpoint proof remain x-rayed through
  roofs so the two interior endpoints stay visible. Agent depth bypass is a
  separate persisted Camera option named `X-ray agents`; it defaults off, so
  structures normally occlude both test and regular agents. These are viewer-only
  diagnostics.
- `CrowdRuntime` loads the same `mybasic.navbin` once and owns one shared
  Detour navmesh, query, proximity grid, asynchronous path queue, and 100-agent
  crowd. It enumerates only the roofless connected village component: 701
  destination polygons, including 40 elevated attic polygons. Agents retain Detour path corridors, choose deterministic random
  destinations at least 6 m away, request an attic destination every fifth
  assignment, and replace a destination on arrival. Crowd steering uses turn
  anticipation and sampled obstacle-avoidance steering. The sampled sidestep is
  kept when it still advances toward the path; otherwise the path direction
  restores full forward intent. Avoidance never sets speed to zero, assigns
  traffic priority, or imposes a hard capsule barrier, so agents may overlap and
  pass through. A one-time wall-distance pass records 300 constrained polygons
  in 166 bottleneck zones for diagnostics only. A navmesh-constrained 10 cm
  forward corridor step clears an agent still below 0.25 m/s for one second,
  before the 1.5-second jam threshold, without stopping another agent.
  Navigation, stall detection, and avoidance update at a fixed
  15 Hz inside the 30 Hz simulation; their scratch storage is persistent and
  displayed positions extrapolate across the intervening tick.
  Baking, artifact loading, target-pool construction, and rendering are one-time
  or debug costs and are excluded from the runtime metric.
- `--navigation-crowd-test` with
  `StandaloneSim/data/village_crowd_debug.json` renders those 100 agents in the
  real village and displays rolling navigation/avoidance time, completed trips,
  attic assignments, active jams, and preventive clears.
  Locomotion pose phase comes from cumulative travelled distance and facing is
  retained through velocity dips, so turning cannot restart Walk or Run.
  Regular agents spawned with `B` and `R` remain rendered alongside the crowd.
  `X-ray agents` applies to this test
  and remains off by default, so houses and other structures normally occlude
  agents. The deterministic behavior probe confirms distant head-on agents
  sidestep by 0.3090 m and pass, while agents initialized face-to-face keep at
  least 1.7444 m/s forward progress and pass with a 0.1344 m minimum separation.
  The current deterministic five-minute Release benchmark kept all 100 agents
  active, completed 1,472 trips with 315 attic assignments, and averaged 0.2459
  ms per 30 Hz simulation tick. Active 15 Hz solves averaged 0.4918 ms. It had
  zero detected jams, zero corner stalls, and zero preventive corridor clears.
  The minimum sampled near-level center separation was 0.0047 m, confirming
  nonblocking overlap. The regression fails if either behavior case fails, any
  jam/corner stall occurs, or average cost reaches 0.5 ms. The
  automated 100-agent crowd regression and the existing
  deterministic/settings/telemetry tests all pass.
- `prophecy_collision_replacer` performs a label-scoped cache replacement after
  an explicit partial Unreal export, preserving every object outside the selected
  labels and recomputing summary counts. `prophecy_navigation_inspector` reads
  the binary artifact without rebuilding it and reports connectivity, entrance
  endpoints, and component height ranges. Both are manual development tools.
- Free and follow camera rotation moved from left-drag to right-drag. Right-drag
  now runs the same yaw/pitch path and persisted sensitivity as the former
  left-drag binding; it no longer pans or exits follow. Left-drag has no camera
  action, while ordinary left-click selection and paused agent translation/turn
  editing remain unchanged. The Cam options tab exposes the existing persisted
  `look_sensitivity` setting as `Sensitivity`; the obsolete Pan row is hidden.
  `Saved/SimCollisionTests/hay-yellow-camera-options.png` confirms the yellow
  hay rendering and the visible sensitivity control.
- Viewer screenshots are bound only to printed `P`; there is no toolbar camera
  button. Captures persist under
  `%LOCALAPPDATA%\ProphecyStandaloneSim\screenshots\` as
  `screenshot-NNNNNN.png`, continue after the highest existing number across
  launches, and visibly stamp camera position, yaw, pitch, and FOV into each
  image. The current screenshot number stays at the lower right, and a brief
  light white flash confirms a successful save.
- Focused Unreal references checked before implementation:
  `https://dev.epicgames.com/documentation/en-us/unreal-engine/simple-versus-complex-collision-in-unreal-engine`,
  `https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/FKAggregateGeom`,
  `https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/UBodySetup`,
  `https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Landscape`,
  and UE 5.7 local source for `BodySetupCore.cpp`, `BodySetup.cpp`,
  `StaticMesh.h`, `AggregateGeom.h`, and `LandscapeCollision.cpp`.

## 2026-08-10 - Agent MACD And Foot-Roll/Physics Cost

- `AProphecyAgent` exposes a runtime per-agent MACD switch, and the manager
  exposes the same operation through stable agent handles. Agents still start
  kinematic, but Physical promotion now applies MACD by default unless it was
  explicitly disabled. UE 5.7's inherited `UPrimitiveComponent::SetAllUseMACD` only reaches
  the default skeletal body, unlike the skeletal override for CCD, so the agent
  deliberately applies `FBodyInstance::SetUseMACD` to every body in its
  `USkeletalMeshComponent::Bodies` array. The setting survives mode changes and
  is reapplied when the agent enters Physical mode.
- Exact UE 5.7 Chaos behavior: `p.Chaos.Solver.UseMACD` globally permits MACD and
  defaults on; an individual collision pair uses MACD when either particle has
  its runtime MACD flag. MACD expands motion-aware broadphase bounds and informs
  the narrow phase. It targets moderate-speed misses; Epic still specifies CCD
  for reliable high-speed collision. Per-agent switching is therefore valid,
  but agent-agent MACD is disabled only when both participants are off. Change
  the flag at state/LOD boundaries rather than every tick because each changed
  rigid body uses a physics-scene write operation.
- Added benchmark-only command-line controls
  `-ProphecyNNFootRollSteps=N`, `-ProphecyNNPhysicalAgents=N`, and
  `-ProphecyNNPhysicalMACD=0|1`. The production and exporter default is 4 foot-roll
  steps. Zero now means no roll integration or pin blend while retaining the
  final cheap ground-penetration clamp. Benchmark output also records actual
  wall milliseconds per frame after warmup.
- The representative `/Game/_mygame/SKM_UEFN_Mannequin` uses
  `/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin`: 22 bodies, 18 capsule
  shapes, four box shapes, and 21 skeletal constraints. No convex or triangle
  collision is present. Every body currently inherits the world-solver default
  of eight position, two velocity, and one projection iteration. Current
  Production Physical mode creates one world-space pelvis target and drives the
  21 existing Physics Asset joints toward the animated local pose with angular
  torque. `PerBodyWorld` remains available only as an explicit debug comparison.
- Current project Chaos settings retain enhanced determinism on, asynchronous
  physics off, and substepping off. UE 5.7 already defaults to task-graph physics,
  task-based parallel island groups, and enabled physics/collision parallel
  loops. No Chaos optimization setting was changed during the investigation.
- Matched 100-agent, 30 Hz, NullRHI, CPU-NNE measurements over 450 warmed NN
  steps gave output/foot-roll/IK costs of: 64=`3.9268 ms`, 32=`2.0806 ms`,
  16=`1.1268 ms`, 8=`0.6923 ms`, 4=`0.4140 ms`, 2=`0.3149 ms`,
  1=`0.2455 ms`, 0=`0.1693 ms`. Relative to 64, the measured output-stage
  savings are respectively 0%, 47.0%, 71.3%, 82.4%, 89.5%, 92.0%, 93.7%, and
  95.7%. This is about `0.0587 ms` per added roll step across all 100 agents per
  NN update, plus about `0.169 ms` fixed output work.
- Three matched wall-time samples at 64 roll steps produced medians of
  `6.7576 ms/frame` for 100 kinematic agents, `39.7478 ms/frame` for 100 physical
  agents with MACD, and `44.3810 ms/frame` for 100 physical agents without MACD.
  All-physical with MACD was 5.88x the kinematic frame cost (+32.99 ms/frame);
  keeping the crowd kinematic saved 83.0% relative to all-physical. MACD-on was
  10.4% faster than MACD-off in this workload's medians, so this test provides
  no evidence that disabling MACD saves time. The machine had concurrent work,
  so retain the medians and direction, not sub-millisecond differences, until a
  clean rendered target-hardware profile is run.
- Normal UE 5.7 UHT/UBT succeeded after selecting the production four-step
  foot-roll default. A no-override headless launch reported
  `foot_roll_steps=4`. All retained benchmark runs completed without invalid
  bodies, Chaos errors, NaNs, ensures, assertions, or fatal diagnostics. The
  focused built-in references were Epic's `FBodyInstance::SetUseMACD`, Blueprint
  `Set Use MACD`, `UPrimitiveComponent::SetAllUseMACD`, and local UE 5.7 source
  in `BodyInstance.cpp`, `PrimitiveComponentPhysics.cpp`,
  `ParticlePairMidPhase.cpp`, and `PBDRigidsEvolutionGBF.cpp`.

## 2026-08-10 - Selectable Joint-Torque Drive And Chaos Settings Audit

- Physical agents have a selectable drive topology. `RootAndJointTorque` is now
  the production/default mode: Physical Animation creates only one world-space
  target and constraint for `pelvis`, while the existing 21 Physics Asset
  constraints explicitly use swing/twist angular position and velocity drives.
  `bUpdateJointsFromAnimation` supplies each constraint's animated local target.
  Nominal 1000/100 angular drive values use the same UE 5.7 Chaos 1.5 stiffness
  and damping conversion factors as the original Physical Animation route.
- The torque topology remains a real articulated simulation. Child limbs have no
  independent world target and cannot teleport to the NN target: Chaos applies
  joint drive impulses/torques through the chain, so bodies physically travel,
  collide on the way, and propagate contact/error through their parent joints.
  The UEFN topology falls from approximately 44 solver particles and 43
  constraints per Physical agent to 23 particles and 22 constraints. Kinematic
  mode disables both joint motors and joint-target updates.
- The manager accepts the debug/benchmark selector
  `-ProphecyNNPhysicalDrive=World|Torque`, applies it before any agent is
  promoted, and records `drive=world|torque` in startup and benchmark logs. No
  selector retains the production `RootAndJointTorque` default.
- The accepted matched stress test used 100 Physical UEFN agents, MACD on, four
  foot-roll steps, CPU NNE, NullRHI, 30 Hz simulation, a three-second warmup,
  and 450 measured frames in interleaved world/torque order. Per-body world
  runs were 61.1221, 65.0087, and 67.3470 ms/frame, median 65.0087. Active
  joint-torque runs were 35.6307, 19.6709, and 51.4665 ms/frame, median 35.6307:
  a 45.2% total wall-time reduction. A concurrent CPU workload caused large NNE
  inference spikes. Subtracting only the manager's separately logged build,
  inference, output, and store stages left medians of 63.0669 versus 26.2257
  ms/frame, a 58.4% reduction in the non-manager engine/physics residual. This
  is a CPU/headless topology result. The user subsequently approved this route
  as the production default; `PerBodyWorld` remains selectable for debugging.
- `Docs/ChaosPhysicsOptimizationReport_UE5_7.md` now uses the exact intended
  capacity reference: 100 simultaneously simulated authored UEFN agents,
  pelvis + joint-torque drive, MACD on, four foot-roll steps, CPU NNE, and 30 Hz.
  Independent high-priority A-B-B-A Chaos captures measured a 3.4% solver-CPU
  gain from task-based result push, 3.1% from the Partial-Jacobi collision
  solver, and 5.0% with both. The combination remains a test candidate because
  Partial Jacobi can alter contact behavior; neither CVar was saved.
- Async Chaos at 30 Hz did not increase physical-agent capacity: total solver
  CPU per captured second was 0.9% worse, although end-of-physics waiting fell
  70.4% because work moved off the waiting thread. Fully simulated bodies using
  `PhysicsOnly` collision were also slower than `QueryAndPhysics`, so the
  production collision mode remains unchanged. Enhanced determinism remains on;
  disabling it screened 2.6% slower on this reference.
- UE 5.7 UHT/UBT passed with the active swing/twist torque route. Accepted
  replicated runs completed without Physics/Chaos warnings, ensures, assertions,
  or fatal errors. No project or engine Chaos setting was changed. The project
  collision configuration now adds the dedicated `ProphecyAgentCapsule` and
  `ProphecyAgentLimb` object channels;
  `Config/DefaultEngine.ini` now has SHA-256
  `D57AD4709A184A443EAA49943952CA2401034E173E94FF60D0E931C45DDD21C2`.

## 2026-08-11 - Production Lightweight Agent Wiring

- `AProphecyAgent` is the production lightweight shell: an unticked `APawn`
  with one capsule, one skeletal mesh, and a Physical Animation component that
  ticks only in Physical mode. It remains Blueprintable. The manager exposes an
  `AgentClass` Blueprint property and spawns that class without overwriting its
  skeletal mesh, so a Blueprint subclass can use another mesh on the same
  skeleton while retaining the batched NN/animation path. Capsule dimensions,
  mesh placement, drive strengths, hit events, overlays, LOD, shadows, and the
  other existing properties remain Blueprint-configurable. Agent components do
  not affect navigation.
- Production defaults are four foot-roll integration steps, pelvis + joint
  torque, and MACD for a promoted Physical agent. Mode selection remains only
  the explicit `SetAgentSimulationMode` switch through a stable
  `{index,generation}` handle. No player/nearby/hit promotion policy exists yet.
- Collision uses dedicated `ProphecyAgentCapsule` and `ProphecyAgentLimb` object
  channels. A Kinematic agent disables skeletal collision and uses its capsule,
  which blocks Kinematic capsules and Physical limbs. A Physical agent's capsule
  ignores every agent capsule and limb and blocks only static environment
  collision; its simulated limbs block the world, Kinematic capsules, and other
  Physical limbs. Therefore Kinematic-to-Physical contact resolves against the
  limbs, never the Physical capsule.
- `Prophecy.Agent.RuntimeContract` validates the production defaults,
  Blueprintability, explicit Physical/Kinematic transitions, and every required
  capsule/limb response pair in a physics-enabled preview world. The test and a
  final normal UE 5.7 UHT/UBT build pass without errors.
- `Docs/AgentSimulationCostAudit.md` records the current matched 0/50/100
  Physical-agent audit with 100 total authored agents at 30 Hz. Median total
  CPU/headless wall cost is 5.021/14.552/29.894 ms per frame; median Chaos solver
  cost is 0.238/4.983/12.663 ms. All-Physical resampling adds only about 0.144 ms,
  four-step output/IK remains 0.44-0.47 ms for the full batch, and pose publishing
  remains 0.14-0.15 ms. Concurrent CPU load produced wide ranges, which the
  report preserves. The audit did not modify `mybasic`, the bridge, or any Chaos
  optimization CVar.

## 2026-08-11 - Physics Backend Research Decision

- `Config/DefaultEngine.ini` is no longer excluded by the project `.gitignore`,
  so the production collision-channel configuration is trackable while the
  other project config files remain ignored.
- `Docs/PhysicsBackendResearch_2026-08-11.md` records the final Chaos/Box3D
  decision. No Chaos or engine setting was changed. UE 5.7 has no newly verified
  CVar gain beyond the existing 5% task-push + Partial-Jacobi candidate. The
  remaining legitimate Chaos candidates are intra-agent collision-pair pruning
  and a separate UE 5.8 parallel-constraint-solver evaluation.
- Box3D's official 14-body articulated-human benchmark measured 1.948 ms for 90
  and 2.618 ms for 120 active ragdolls with four workers on this machine, at 60
  Hz with four substeps. This supports likely raw capacity for 100 Prophecy
  agents but is not an exact 22-body proof.
- Box3D core supports limited spherical joints, target-rotation springs, torque,
  contacts, and transform resampling, so the intended physical animation is
  technically possible. The current Box3DUnreal plugin is not a drop-in
  replacement: it lacks SkeletalMesh/PhysicsAsset/Physical Animation support and
  Chaos-to-Box3D interaction. Production remains on Chaos pending an explicitly
  requested exact Box3D agent benchmark and skeletal pose-sync prototype.

## 2026-08-11 - Actor/Pawn Agent Decision

- The production agent remains an unticked, unpossessed `APawn`. Three
  interleaved headless benchmarks of 100 bare instances found no measurable
  steady-frame or spawn-time penalty versus `AActor`; the tiny timing difference
  changed sign between runs and remained inside measurement noise. `APawn` adds
  128 bytes per instance in this UE 5.7 build (12.5 KiB for 100 agents), which is
  accepted in exchange for direct possession support without another class
  architecture.

## 2026-08-11 - Blueprint Agent and Manager Authoring

- `/Game/_mygame/MyAgent` is a compiled Blueprint child of `AProphecyAgent` and
  currently overrides the inherited skeletal mesh with
  `/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN`. Both the native class and
  `MyAgent` have Actor Tick disabled. The batch manager stores the subclass as
  `AProphecyAgent` and executes its per-frame movement, NN, pose, and simulation
  work in native C++; the Blueprint shell adds no scheduled Blueprint VM work
  unless Blueprint logic is later put on Tick or called by the runtime.
- A live 15-sample interleaved spawn check of 100 transient instances measured
  975.9 ms for the native class and 1017.8 ms for the current Blueprint median.
  The 41.9 ms per-100 difference is one-time editor spawning, sits inside broad
  overlapping ranges, and also includes the different skeletal-mesh defaults;
  it is not a measurable steady-frame Blueprint cost. All transient actors were
  destroyed and map/content dirty-package state remained unchanged.
- `AProphecyNNLocomotionManager` is already Blueprintable and exposes `CrowdSize`,
  `AgentClass`, update frequency, foot-roll steps, movement settings, and initial
  physical-mode settings. A Blueprint child can be placed in `mybasic` and set to
  spawn `MyAgent`. Its top-level `Sim Bridge` switch controls the PIE bridge, and
  `PlayerAgent` assigns the one externally controlled agent. `CrowdSize` counts
  villagers only; the assigned player is additional.
- Epic's supported hybrid route remains the chosen one: native C++ owns hot batch
  work while Blueprint subclasses provide defaults and event-driven customization.
  References: `https://dev.epicgames.com/documentation/en-us/unreal-engine/coding-in-unreal-engine-blueprint-vs-cplusplus`,
  `https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-ticking-in-unreal-engine`.

## 2026-08-11 - PIE Sim Bridge

- The saved `/Game/mybasic` manager has `Sim Bridge` enabled, `CrowdSize=20`,
  `/Game/_mygame/MyAgent` as its agent class, and `myPlayer` assigned as the
  additional player. Disabling `Sim Bridge` prevents the standalone process from
  launching. Ending PIE requests shutdown and closes the process.
- PIE creates a per-run GUID-named shared-memory block and launches the existing
  `prophecy_viewer` in paired village-navigation mode. The bridge uses a fixed
  versioned POD layout with sequence locks; it performs no JSON serialization.
  Bridge-launched viewers open unfocused at the bottom of the desktop Z order;
  ordinary standalone launches remain unchanged.
- The sim owns random village and attic route planning for the 20 villagers and
  publishes only locomotion mode, root-relative speed-stick direction/amplitude,
  world-relative orientation yaw, and speed/turn scales during play. Its root is
  used once for each villager's initial spawn. Unreal then advances the exact
  shared native walk/run mover at 30 Hz, generates the same eight future roots for
  the NN input, and owns the final capsule low point. Capsule sweeps provide the
  physical correction; Unreal feeds the resolved low point, measured physical
  displacement velocity, facing, and one-shot static-world contact back to the
  planner. Paired debug rendering uses that Unreal physical root instead of the
  planner's projected root. The player occupies the final active crowd slot,
  participates in neighbor avoidance, and feeds its Unreal root to the sim, but
  the sim never moves it.
- Visual actor yaw applies the UEFN mesh's local `+Y` forward convention to the
  mover's `[sin(yaw), cos(yaw)]` convention. Policy-local vectors cross the
  training-to-UEFN boundary as `(X,-Y,Z)`, and policy-local rotations cross as
  `S*R*S` with `S=diag(1,-1,1)`. The inverse physical-state sample uses the same
  reflection. A clean Editor Development build and live PIE inspection of
  controlled villagers verified that the reference-pose upper body and inferred
  lower body share one heading, both toe offsets remain on their authored side,
  and the prior stretched feet are gone; current foot/toe local-translation
  differences from the skeleton reference were at most `0.419 cm` in the sampled
  moving villagers. Bridge visualization extrapolates with measured capsule
  velocity, not desired mover velocity, so a blocked capsule cannot create a
  false move-and-snap debug jitter.
- `AProphecyAgent::bIsPlayer` is native, `BlueprintReadWrite`, displayed as
  `Is Player`, and defaults false. The saved `myPlayer` instance is true, and the
  manager also enforces true when registering its assigned player. Its current
  stable handle is `{index:20, generation:1}`; spawned villagers remain false.
- Unreal Editor Development and standalone Release builds pass with the shared
  mover compiled from the same `sim_core` implementation. A bridge launch test
  kept the pre-existing Chrome window foreground before and after PIE while the
  viewer opened responsive behind it. PIE launches exactly 20 villagers plus the
  fixed externally controlled player, and shutdown remains cooperative through
  the shared block.

## 2026-08-11 - Lower-Body Runtime Parity

- At the 30 Hz policy endpoints, the flat `/Game/locomotion` CPU test reproduces
  the committed RunF reference over all 74 predictions. Maximum error was
  `0.00000644 m` in a reconstructed lower-body position, `0.0000496` in a
  reconstructed basis component, `0.00000596` in the published recurrent state,
  and `0.0000147` in the raw policy output. The production four-step Run route
  separately matches an exact four-step replay to `0.00000602 m`; compared with
  the original 60-step archive, the intentional four-step approximation
  accumulates at most `0.00201 m`.
- Walk uses the accepted June checkpoint and the committed `WalkF` seed clip,
  not a retrained or altered network. Across all 119 predictions at the
  production four steps, maximum error was `0.00000486 m` in a rendered
  lower-body position, `0.0000162` in a rendered basis component,
  `0.0000111` in recurrent state, and `0.0000208` in raw output. Walk pin
  probabilities/decisions matched within `5.96e-8`.
- Initial visual placement now translates world-root histories without treating
  spawn placement as a collision correction. Normal successful capsule motion
  no longer rebases recurrent pose state every render frame; only a real sweep
  displacement or yaw discrepancy does. Ground correction now uses the raw
  lowest foot-contact point instead of a value already clamped to zero. These
  changes preserve the trained inputs and outputs while removing the prior
  recurrent jitter and ineffective below-ground lift.
- Rendered frames now use the same pose-display contract as Stepper Model Viewer.
  Each policy publication carries the immediately consecutive previous/current
  component-space transforms for pelvis, both thighs, calves, feet, and toes,
  plus both exact component-to-world transforms. At render time Unreal linearly
  blends every joint's absolute-world position and uses the mathematical polar
  factor of the viewer's linear rotation-matrix blend before rebuilding the
  local hierarchy. The former local-track interpolation plus ankle-only IK is
  removed; knees and every other lower-body joint follow the viewer trajectory.
  This changes no trained network, recurrent state, foot-roll rule, mover, or
  capsule motion.
- `Tools/NN/AuditProphecyAbsoluteMotion.py` is the retained absolute-world
  regression and now requires every visible lower-body joint, not only ankles
  and policy endpoints, to pass. The final CPU/NullRHI RunF audit at 60 FPS had
  `0.00371 mm` maximum capsule-root error, `2.0258 mm` maximum error across all
  nine visible lower-body joints, `0.5011/0.7934 mm` left/right calf maxima, and
  `2.0251 mm` maximum ankle error. At 30 FPS the audit renders the exact consecutive
  integer policy frames and stays within `0.00388 mm` at the root and `2.0258 mm`
  across all visible joints. At 5 FPS it renders exact policy frames
  `7,13,19,...,73`, six policy steps apart, and stays within `0.00170 mm` at the
  root and `2.0250 mm` across all visible joints. All pass the explicit `2.1 mm`
  tolerance required by the production four-step foot roll.
- The NN/mover remains a fixed 30 Hz stream independent of render frequency.
  Above 30 FPS, rendering interpolates the previous/current exact policy poses.
  At 30 FPS, every rendered pose is an exact policy pose. Below 30 FPS, the
  manager advances all required 30 Hz policy steps and renders only the newest
  completed exact pose; it does not interpolate stale poses. Therefore 60 FPS
  shows one midpoint between policy frames, while 5 FPS shows every sixth policy
  frame with interpolation alpha `1`.
- Production remains at four foot-roll integration steps. The temporary parity
  loader and collision overrides remain removed. A normal UE 5.7 Editor
  Development build passes.
- `/Game/locomotion` is the retained flat interactive locomotion test. It keeps
  a selectable `LocomotionTestManager` actor in the level so `Camera
  Sensitivity` can be edited in the normal Details panel before PIE. The world
  subsystem reuses that placed manager instead of spawning a duplicate, and the
  manager configures itself before locomotion initialization with exactly one
  Kinematic agent, no sim bridge, and a `2 m/s` Walk default. A transient
  third-person camera follows the capsule low point; raw mouse movement orbits
  it using the manager's live-editable `Camera Sensitivity` property, and
  holding either Shift key changes intent and policy to the `5 m/s` Run.
  Releasing Shift returns to Walk. The one-agent lane has no crowd offset, so
  its route is exactly `Cube -> Cube2 -> Cube`. Its capsule is teleported to the
  intended low point before the first swept update, keeping the bottom at
  `Z=0` instead of spawning embedded in the floor. Only the two route-marker
  collisions are disabled for this test world. No camera/input components are
  added to production agent pawns, and `mybasic` is unchanged.

## 2026-08-12 - Walk Viewer Is the Unreal Pose Authority

- The standalone viewer and trained networks remain unchanged. Walk parity uses
  only the approved June checkpoint selected by
  `prophecy_lower_body_walk_runtime.json` and its committed `WalkF` seed clip;
  the later `20260811_195921` checkpoint is an upper-pose experiment and is not
  a locomotion runtime input.
- `/Game/locomotion` no longer enables Unreal animation update-rate skipping or
  visibility-based pose skipping. Its single skeletal mesh always evaluates the
  existing NN anim proxy, so Unreal cannot add a second sampling/interpolation
  layer over the viewer-matched 30 Hz publications. Production crowd maps retain
  their existing update-rate optimization.
- `Tools/NN/AuditProphecyAbsoluteMotion.py --walk` now selects Walk explicitly
  and executes the unchanged Stepper Model Viewer pipeline as the reference for
  recurrent rollout, legacy pinning, four-step foot roll, FK, exact integer
  frames, and between-frame position blending. The retained CPU/NullRHI tests
  pass at 5/30/60 FPS. Maximum capsule-root error is `0.0442 mm`; maximum error
  across pelvis, thighs, calves, feet, and toes is `0.3196 mm`. At 5 FPS Unreal
  renders exact six-policy-step jumps; at 30 FPS it renders exact policy frames;
  at 60 FPS it includes the viewer-equivalent midpoint.
- A normal UE 5.7 Editor Development build passes. Normal PIE confirms one
  `UProphecyNNLocomotionAnimInstance`, update-rate optimization disabled, and
  `AlwaysTickPoseAndRefreshBones` in `/Game/locomotion`.

## 2026-08-12 - Fed Future-Root Floor Debug

- `AProphecyNNLocomotionManager` can draw the exact current root frame and all
  eight future-root samples encoded into one agent's NN input. The white marker
  is the input root, the connected colored markers are samples 1-8, and the
  white/yellow arrows show their fed yaw directions.
- The display decodes the already normalized and clamped input values written by
  `BuildInputBatch`; it does not run a second prediction and cannot affect the
  mover, inference, capsule sweep, or pose. `bShowFutureRootDebug` and
  `FutureRootDebugAgentIndex` expose the display and selected agent. It remains
  off by default in every map, including the flat `/Game/locomotion` test. When
  off, input construction performs no debug decoding or caching and rendering
  makes no debug draw calls; the disabled path is only the feature-toggle branch.

## 2026-08-12 - Optional Final Foot Reach Clamp

- `AProphecyNNLocomotionManager` exposes `Clamp Foot`, default off, plus `Foot
  Clamp Length Multiplier`, default `1.0`. When enabled, the final presentation
  pose constrains each settled foot to at most `(authored upper-leg length +
  authored lower-leg length) * multiplier` from that leg's thigh bone; for
  example, `1.5` permits one-and-a-half times the authored total leg length.
- The clamp runs while building the final previous/current component-space poses,
  after NN output, pinning, foot roll, and ground correction. It updates the
  displayed calf/foot/toe chain but does not alter recurrent NN state, mover
  state, capsule motion, or trained-network inputs/outputs.

## 2026-08-12 - Direct Run/Walk Pose Handoff

- Run and Walk consume the existing previous/current recurrent poses directly;
  gait changes do not reseed, phase-match, search, or add a transition system.
- Each published pose retains the one-bit gait identity used to produce it.
  Rendering reconstructs the previous pose with its previous gait geometry and
  the current pose with its current gait geometry before the existing global
  interpolation. This adds two booleans per agent, no allocations, no inference,
  and no additional per-agent update pass. The optional foot clamp is unrelated
  and remains unchanged.

## 2026-08-12 - Force-Driven Physical Agent

> Superseded controller snapshot retained by explicit request. The current
> controller and solver settings are recorded in the following section.

- `AProphecyAgent` Physical mode keeps the existing NN/mover pose as intent and
  uses Chaos to produce the realized body pose. The pelvis follows its authored
  world position and rotation through forces and torques; it is not teleported,
  made kinematic, or attached to a world constraint. Physics Asset SLERP motors
  drive the articulated child joints from the immutable authored pose store.
- The retained root gains are position `40000`, velocity `400`, orientation
  `60000`, and angular velocity `500`. Joint acceleration-drive gains are spring
  `16000` and damping `253`. The controller includes gravity-force and
  gravity-moment compensation so gravity does not make the pelvis roll while
  joint reaction torque remains physical.
- Physical activation removes presentation-only bone scale before creating the
  Chaos bodies. The six leg constraints use the full authored articulation
  range, and current/previous joint targets provide angular-velocity
  feed-forward. Physical agents always evaluate their pose and do not use
  visibility/update-rate skipping.
- Skeletal contacts are temporarily disabled as requested: the mesh keeps its
  22 simulated bodies and 21 constraints but ignores World Static, World
  Dynamic, and Pawn. The managed capsule remains the root support on static
  ground. Ground/limb contacts can be restored after the controller itself is
  accepted visually.
- The retained one-frame parity command copies one exact Kinematic pose into all
  22 Chaos bodies, clears controller forces/torques and every SLERP motor, rolls
  exactly one physics frame with gravity/contact disabled, then reports every
  body. With the production constraint mode, maximum translation is
  `0.000015 cm` (`0.00015 mm`) and maximum rotation is `0.02655 degrees`.
- `/Game/locomotion` now provides the current long-horizon controller test. When
  agent 0 is Physical, its recurrent NN state remains the uninterrupted
  Kinematic rollout: realized Chaos limb transforms are deliberately not fed
  back into that test agent's next inference. The Physical body still follows
  the authored pose through the same pelvis force/torque and joint motors.
  Production physical agents outside this simple test retain physical-state
  feedback.
- A collision-free Kinematic reference is rendered beside the Physical agent
  with the engine's green debug material. It uses the exact authored pose and
  route in a parallel world-space lane. The test accumulates original-frame
  position and rotation errors for all nine published bones and logs running
  mean and maximum values every two seconds, so drift is measurable across an
  arbitrary run rather than only one frame. The current Physical controller is
  not yet visually accepted; the comparison exposes substantial limb drift and
  foot sliding. Foot-roll integration remains four steps. `Initial Physical
  Agent Count` is respected and clamped to the map's one available managed
  agent.

## 2026-08-12 - Absolute-World Physical Magnetization

- Before this change, each Physical agent used `16` position iterations, `4`
  velocity iterations, and `4` projection iterations. The pelvis was driven by
  a world-space force/torque while six lower-body joints used Chaos SLERP
  motors. That exact pre-change configuration is retained above as the
  superseded `Force-Driven Physical Agent` snapshot.
- The retained 100-agent, fixed-60-Hz benchmark changed only the per-body solver
  counts to `4/1/0`. Median Chaos solver time fell from `8.8491 ms` to
  `6.5327 ms` (`26.2%`), measured joint-pass work fell from `2.0496 ms` to
  `0.4826 ms` (`76.5%`), and total frame time fell from `33.6923 ms` to
  `27.0620 ms` (`19.7%`). These are now the default Physical-agent counts.
- The current lower-body controller no longer uses joint motors. Pelvis,
  thighs, calves, and feet receive one acceleration-mode world force and one
  acceleration-mode world torque toward their finalized authored world
  transforms. Chaos constraints remain only for physical articulation and
  impacts. The upper body remains animation-driven until its targets are
  authored, and skeletal ground contacts remain temporarily disabled as
  previously requested.
- The manager is an explicit tick prerequisite of each managed agent and its
  skeletal evaluation. It completes the 30-Hz NN step and publishes one
  finalized pose before the Physical force pass. The controller targets that
  exact interpolated pose; it does not extrapolate a private next pose from
  authored linear or angular velocity.
- The temporary Kinematic follower, comparison ghost, comparison pose store,
  and Physical-versus-Kinematic accumulator have been removed. Every Physical
  agent now samples its realized Chaos pelvis, thigh, foot, and toe transforms
  before each 30-Hz inference and uses consecutive physical samples as the
  current/previous recurrent state.
- The temporary Ctrl Physical toggle and Kinematic comparison actor are not part
  of the current `/Game/locomotion` test. Physical switching will be authored
  explicitly by the user from the future-pose Blueprint surface below.

## 2026-08-13 - Manual Future-Pose Blueprint Agent

- `/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent` is the current single
  test agent. In `/Game/locomotion` it retains the existing automatic test setup.
  It can also be placed directly in any map with `Auto Possess Player` enabled:
  on PIE it creates the one-agent locomotion runtime, registers that exact placed
  pawn as agent `0`, preserves its placed root transform, and creates the orbit
  camera. It does not spawn a duplicate agent. The runtime remains one Kinematic
  agent with no comparison or Physical agent.
- With an empty Blueprint Event Graph, the manager continues moving the capsule
  root but automatic skeletal evaluation is disabled, so every limb remains at
  its unchanged local pose while the complete skeleton follows root motion.
- `Read NN Future World Pose` is Blueprint-pure and exposes the nine published
  bone names, the exact next 30-Hz authored transforms in world space, the
  current presentation-interpolated world transforms, and interpolation alpha.
  It reads the existing pose publication and performs no extra inference.
- `Apply NN Pose Kinematically(Delta Seconds)` is the explicit Blueprint-callable
  skeletal evaluation step. Calling it from Blueprint Tick reproduces the
  existing Kinematic presentation. The manager is its tick prerequisite, so a
  Blueprint can read the newly published future targets first, drive custom
  Physical bodies, and then optionally call the Kinematic application in the
  same frame.
- The single-agent test uses camera-relative `Z/S/Q/D` digital stick input:
  `Z` forward, `S` backward, `Q` left, and `D` right relative to the horizontal
  camera view. Diagonals are normalized. Translation direction and facing are
  independent: the stick authors velocity direction while horizontal camera yaw
  authors the orientation target every frame. This permits strafing and backward
  locomotion, and rotating the camera with zero stick authors turn-in-place while
  speed amplitude remains zero. Camera sensitivity defaults to `10`. Shift retains
  the existing Walk/Run selection.
  Automatic Cube-to-Cube intent is disabled in this interactive test but retained
  by the absolute-motion audit.

## 2026-08-13 - Manual Physical Follower Checkpoint

- `/Game/_mygame/locomotion/BP_ProphecyManualPoseAgent` contains the accepted
  Blueprint physical-follower checkpoint. Its kinematic target is evaluated
  before correction, and every simulated body receives additive linear and
  angular delta velocity once per frame. Linear correction uses the rigid-body
  velocity at the tracked bone's world point, including angular motion around
  the center of mass; the spring helpers subtract current velocity exactly once.
- The one-agent locomotion test enables the existing final calf-length pass at
  multiplier `1.0`, so the published target has the same rigid lower-leg length
  as the Physics Asset before Chaos follows it. The general manager property
  remains Blueprint-editable and off by default outside this test.
- `prophecy.Physical.AuditManualFollower 1` enables the retained, off-by-default
  numeric audit. At the beginning of each PrePhysics tick it compares each
  simulated body with the exact target saved after the preceding PrePhysics
  tick, reporting root-world and pelvis-relative per-body position/rotation
  mean, RMS, and maximum errors. The normal disabled path performs no sampling
  or logging.

## 2026-08-12 - Fast Unreal C++ Iteration Rule

- Batch Blueprint-visible API changes into one reflected-header edit. Once the
  nodes/properties exist, controller experiments must change implementation in
  `.cpp` files only whenever possible. Editing a `UCLASS`, `USTRUCT`,
  `UPROPERTY`, or `UFUNCTION` declaration invokes UHT and rebuilds dependent
  unity files; a `.cpp`-only Live Coding change recompiles only its translation
  unit.
- Keep Unreal open and use Live Coding. Stop PIE for the compile but do not
  restart the Editor unless Live Coding explicitly cannot load the change.
- A newly added or structurally changed reflected node/property is the explicit
  exception: save assets, close the Editor once, run one normal Editor build,
  then reopen. After the reflected surface exists, return to `.cpp`-only Live
  Coding iterations. Do not repeatedly restart Unreal for implementation work.
- Do not force additional compiler parallelism or disable unity builds on this
  16-GB workstation during an Editor session. With approximately 2 GB free,
  UnrealBuildTool intentionally schedules one compiler process to avoid paging;
  forcing concurrency would trade compilation for disk thrashing.
