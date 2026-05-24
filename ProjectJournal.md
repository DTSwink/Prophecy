# Prophecy Project Journal

Keep this file tight. Preserve only goals, rules, keeper settings, important paths, current working state, and next actions. Full historical archives live in `Docs/old/`.

## Current State

- Project path: `C:\Users\singerie\Documents\Unreal Projects\Prophecy`.
- Unreal project: `GameAnimationSample3.uproject`, Launcher UE `5.7`.
- Git remote: `https://github.com/DTSwink/Prophecy.git`.
- Latest pushed commit should be checked with `git log -1 --oneline origin/main`; avoid treating this journal as the moving hash source.
- Git preservation rule: push everything needed to reconstruct the project if local files are lost. Include source code, journal notes, helper scripts, config, hand-authored data, and small source assets/textures through LFS when needed.
- Do not push bulky or recoverable Unreal output by default: `Binaries/`, `Intermediate/`, `DerivedDataCache/`, screenshots, logs, autosaves, and generated `Content/` assets that can be rebuilt by opening Unreal or rerunning tracked scripts. If an added asset cannot be reconstructed from tracked source/scripts, track it.

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
