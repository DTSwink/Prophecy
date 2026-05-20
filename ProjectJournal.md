# Prophecy Project Journal

Keep this journal compact. Only record context worth preserving across a fresh conversation window: goals, rules, current architecture, keeper settings, important paths, and next actions. Full historical journal archives live in `Docs/old/`.

## Core Goal

- Project path: `C:\Users\singerie\Documents\Unreal Projects\Prophecy`
- Unreal project: `GameAnimationSample3.uproject`, stock Launcher UE `5.7`.
- Absolute goal: performance. This is a full Roman-age battle sim with at least 100 active characters and room to scale.
- Optimize across animation, AI, movement, rendering, LOD, update frequency, memory layout, and runtime data flow.
- Use regular C++ classes as the foundation. Prefer source, config, data, scripts, and generated assets that Codex can edit directly.
- Avoid high-overhead UE gameplay frameworks such as Behavior Trees and `AIController` for mass logic unless a UE feature proves faster than a reasonable custom system without forking the engine.

## NN Animation

- User's NN training work lives at `C:\Users\singerie\Documents\Cursor\stepper`.
- Current usable checkpoint folder: `C:\Users\singerie\Documents\Cursor\stepper\training\runs\20260518_034323_big_mixedk_doubleae_oldfootslide_continue_from_last\checkpoints`.
- Training data uses a UEFN-style 30 FPS skeleton. Prefer `SKM_UEFN_Mannequin` over Manny.
- Runtime path: exported fixed-batch ONNX at `Content\Prophecy\NN\stepper_checkpoint_last_b100.onnx`.
- `FProphecyNNPoseStore` and `UProphecyNNPoseAnimInstance` provide the thin native pose path. Current benchmark uses UE NNE ORT CPU because DirectML was slower for this 100-agent MLP batch.
- Default crowd benchmark target: 100 agents, 30 Hz NN update, LOD3 visual mannequins, batched pose work where possible.

## Benchmark Actor

- Main implementation: `Source\GameAnimationSample3\Private\ProphecyNNCrowdBenchmark.cpp`.
- Header: `Source\GameAnimationSample3\Public\ProphecyNNCrowdBenchmark.h`.
- Launch with `-ProphecyNNBenchmark`; useful profiles include `CharactersFloorShadows` and `GrassField`.
- Useful visual modes include `Skeletal`, `InstancedFull`, `Instanced`, and `InstancedLite`.
- `InstancedLite` is a non-skeletal proxy path using one instanced static mesh component and batched transform updates.

## Launch Rules

- Run Unreal captures in the background by default so they do not cover the user's work.
- Use a properly quoted `.uproject` path as the first argument and include `-RenderOffscreen`.
- Quote decimal PowerShell arguments, e.g. `"-ProphecyNNWarmup=0.75"` and `"-ProphecyNNScreenshotSeconds=2.8"`, or PowerShell may split stray `.75` arguments into the run.
- Always show captures in chat when visual work is being judged.
- Single-character captures can use `-ProphecyNNClosePreview=1`; add `-ProphecyNNFrontPreview` when the MetaHuman faces the positive-Y camera side.
- Visual debugging rule: when a visual problem is ambiguous, temporarily isolate or exaggerate the relevant variable so the failure becomes obvious. Clearly label these changes as diagnostic inspection aids, not final art direction, gameplay behavior, or performance settings.

## Rendering State

- Benchmark render profile disables Lumen GI/reflections, fog, AO, SSR, contact shadows, virtual shadows, auto exposure, motion blur, bloom, and DOF for stable performance-focused tests.
- Controlled benchmark setup disables pre-existing map light and sky light components before spawning benchmark lighting.
- Full dynamic character shadows are the visual truth reference. Root/Limbs fake shadows must be generated to match that light direction, not the other way around.
- Root/Limbs fake shadows use max-composited world-space masks so overlapping shadows cap instead of stacking darker.
- No-grass Root/Limbs use a 256x256 ground mask through `M_ProphecyGrassGround`.
- Grass Root/Limbs use a 512x512 grass mask sampled by the grass material, plus a subtle ground underlay for sparse distance coverage.

## Grass

- Current grass path is opaque HISM blade clusters, not Niagara. Niagara can load, but the stock tested system did not render usable grass.
- Current keeper grass: about 58,492 HISM patch instances and about 4.173M visual blades (`44` standard, `176` dense).
- Grass is dense near the formation and fades into terrain farther out; avoid visible full/few/no-grass bands.
- Unified grass wind uses cheap patch-level WPO from object/world position, not per-blade noise and not a separate near/far wind system.
- Current wind keeper: `bend=14cm`, `lift=0`, `speed=0.85`, `gust=0.55`, `world_freq=0.00062`.
- Latest clean pre-tree grass+wind confirmation: `97.68 FPS` at 1280x720. Capture: `Saved\ProphecyNN_GrassWind_UnifiedFinal_v1.png`.
- Do not repeat the extreme diagnostic grass density unless necessary; the first extreme pass used about 99k patches / 9.5M blades and took roughly 45s to load.

## Terrain

- Playable middle remains flat because the NN agents are trained on flat terrain.
- Far hills are runtime low-poly grass terrain outside the playable plane, using the same shared world-space terrain material as the flat plane so the join can match.
- Hill form is readable through a baked 1024x1024 world-space terrain color texture (`TerrainBakedColorTexture`), avoiding polygon-shaped vertex shading and dynamic shadow cost.
- Fog/aerial perspective caused blue patches on grass/hills, so the benchmark render profile currently sets `r.Fog=0` and no distance-fog actor is spawned.
- Current terrain keeper capture: `Saved\ProphecyNN_TerrainHills_BakedTextureShade_v1.png`; hidden-blades benchmark reported `168.46 FPS`.

## Trees

- The previous distant-hill 3,000-tree wind pass is archived only; it is not the current direction.
- Current direction: trees belong in the playable area as a tall European spooky forest around the formation.
- Current implementation uses generated low-poly static tree meshes in HISM components, default `TreeInstanceCount=420`, with a central corridor kept open for the battle formation/camera.
- Trees are static for performance: tree wind is off by default and dynamic tree shadow casting is off.
- Tree shadows are simulated cheaply by baking each tree into static grass/ground receiver masks, then dynamic character masks start from that precomputed tree-shadow layer.
- Tree material asset is still named `M_ProphecyTreeVertexWind`, but for the playable forest it is now used as a cheap static vertex-color material with no WPO connection.
- Current visual capture: `Saved\ProphecyNN_PlayableForest_v5.png`. It shows the playable-area forest and darker mood; clean no-screenshot performance acceptance still needs to be rerun after context refresh because the pass was interrupted.

## MetaHuman Character Tiers

- UE 5.7 local MetaHuman plugins are enabled through `MetaHumanCharacter` and `MetaHumanSDK`, with `RigLogic` already present.
- Production source character is the assembled MetaHuman `/Game/MetaHumans/Kellan/BP_Kellan`, not the generated placeholder.
- Kellan has real synthesized head/body materials, clothing materials, body textures, head LOD1/3/5 textures, and groom assets. This is the source of truth for character-tier experiments.
- Reference level: `/Game/Prophecy/MetaHumanPipeline/LVL_MetaHumanProductionReference`, created by `Saved\ProphecyCreateProductionMetaHumanReferenceLevel.py`.
- Verified front render: `Saved\ProphecyMetaHumanProductionReference_Kellan_FrontCamera_2K.png`; close crop: `Saved\ProphecyMetaHumanProductionReference_Kellan_FrontCamera_CloseCrop.png`.
- Kellan inspection script: `Saved\ProphecyInspectKellanProductionComponents.py`. Current `LODSync` reports `num_lods=4`, `forced_lod=-1`; Body and Face drive LOD, clothing/grooms are passive.
- The old `/Game/Prophecy/MetaHumans/ProphecyPlaceholder/BP_ProphecyPlaceholder` remains a test harness only. Because the local engine lacks the optional texture synthesis payload, it produces flat placeholder skin and must not be used for production visual judgment.
- Next MetaHuman tier path: Tier 0/1 uses assembled Kellan BP; mid tiers should force MetaHuman/LODSync levels and simplified materials; far tiers should be generated from assembled Kellan assets as impostor/proxy data. Do not tint or manually hide material mismatches.

## UE Python Material Gotchas

- In UE 5.7 Python material scripts, `MaterialExpressionComponentMask` inputs often need pin name `"None"`, not `"Input"`.
- Vertex color connections were reliable through the default output pin `""` when `"RGB"` did not update as expected.
- Main material generation script: `Saved\ProphecyCreateGrassMaterials.py`.

## Useful Commands

Build:

```powershell
& "C:\Program Files\Epic Games\UE_5.7\Engine\Build\BatchFiles\Build.bat" GameAnimationSample3Editor Win64 Development -Project="C:\Users\singerie\Documents\Unreal Projects\Prophecy\GameAnimationSample3.uproject" -WaitMutex -NoHotReload
```

Regenerate procedural materials:

```powershell
& "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "C:\Users\singerie\Documents\Unreal Projects\Prophecy\GameAnimationSample3.uproject" -run=pythonscript -script="C:\Users\singerie\Documents\Unreal Projects\Prophecy\Saved\ProphecyCreateGrassMaterials.py" -unattended -NoSplash -NoSound
```

Clean playable forest benchmark to rerun next:

```powershell
& "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe" "C:\Users\singerie\Documents\Unreal Projects\Prophecy\GameAnimationSample3.uproject" -game -RenderOffscreen -Unattended -NoSplash -NoSound -windowed -ResX=1280 -ResY=720 -ForceRes -ProphecyNNBenchmark -ProphecyNNBenchmarkExit -ProphecyNNProfile=GrassField -ProphecyNNTrees=1 -ProphecyNNTreeWind=0 -ProphecyNNGrassWind=1 -ProphecyNNContactShadowVariant=Root "-ProphecyNNBenchmarkSeconds=8.0" "-ProphecyNNWarmup=2.0"
```
