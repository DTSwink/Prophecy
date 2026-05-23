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
- Distant grass color now targets `ProphecyGrassContinuationColor` and starts beyond the main grass field by default; `Saved\ProphecyLiveShot.ps1` leaves `grass_distant_color` unset unless explicitly overridden. Current dirt distance fade keeper is `DirtFadeStartCm=1500`, `DirtFadeRangeCm=900`.
- Current grass/plane blending motivation: do not make the outer grass match the plane first. The inner grass is the art keeper; make far grass read as a continuation of that inner grass, then later make the plane continue the finished full grass field. Do B&W high-contrast seam crops after each pass.
- Far grass LOD knobs are command-line tunable for fast visual iteration: `ProphecyNNGrassFarTargetSpacing`, `ProphecyNNGrassFarCoverage`, `ProphecyNNGrassFarScaleXYMin/Max`, `ProphecyNNGrassFarScaleZMin/Max`, and `ProphecyNNGrassDenseMeshRadius`. `Saved\ProphecyStartLivePreview.ps1 -ExtraArgs` can pass them without editing the script.
- The current dark-band hypothesis is far blade roots compressing into a horizontal value band. Fix it with shared far-only root/base lift handles (`GrassFarRootLiftStartCm`, `GrassFarRootLiftRangeCm`, `GrassFarRootLiftStrength`, `GrassFarRootLiftColor`) before touching the plane or accepted inner grass.
- The far plane needs its own grass-continuation grain because the stock ground noise mips into a flat band at horizon angles. Use shared ground handles (`GroundGrassGrainStrength`, `GroundGrassGrainWorldCm/Frequency`, `GroundGrassGrainDarkColor`, `GroundGrassGrainLightColor`) to make the plane read as a continuation after the outer grass is matched.
- Current seam keeper: dense mesh radius `18000cm`, far root lift `start=5400cm`, `range=3000cm`, `strength=0.60`, `color=(0.130,0.275,0.052)`, ground base `(0.135,0.285,0.058)`, plane grain `strength=0.55`, `world=360cm`, dark `(0.070,0.195,0.032)`, light `(0.165,0.340,0.072)`.
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
