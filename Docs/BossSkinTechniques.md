# Boss mesh and skin techniques

Current reference — 2026-09-08. This consolidates the work retroactively; successful AO repairs do **not** mean every normal or color seam is solved.

## Status and scope

| Technique | Status | Purpose |
|---|---|---|
| Preserve fitted joints, convert bone axes once at export | Verified and published | Match the Blender Boss shape/rig while retaining the UEFN animation contract |
| Average paired collar normals, fade correction inward | Partial candidate, not an accepted complete fix | Reduce mesh-normal discontinuity without changing geometry |
| Correct decoded bent-normal fallback | Published; user accepted | Remove triangle/UV-shaped Material AO patches |
| Fade head AO and bent normals from body-neutral collar | Published; user accepted | Remove the remaining head/body Material AO boundary while retaining face AO |
| Transfer body collar color into head UVs and fade to original head BaseColor | Wrapped-UV correction published; user accepted | Smooth the Unlit/BaseColor boundary without repainting the face |
| Weld collar and share geometric normals/skin weights | Published; numerically verified, user visual check pending | Close the neck join and keep it closed when skinned |
| Normal-texture rebake | Not performed | Separate follow-up only if final normal-map shading still shows a boundary |

## Assets and safety boundaries

- Keeper: `/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN_Fitted`.
- Blender source: `C:/Users/singerie/Documents/Blender/bossfinalsave.blend`, mesh `boss`, rig `UEFN_WORKING_CLEAN_RIG.001`.
- Actual body instance: `/Game/_mygame/MetaHumans/boss/Body/Materials/MI_Body_Baked_VT`.
- Actual head instance: `/Game/_mygame/MetaHumans/boss/Face/Materials/MI_Face_Skin_Baked_LOD3_VT`.
- Boss-only corrected ancestry and generated masks: `/Game/_mygame/MetaHumans/BossUEFN/Materials/AORepair`.
- Material fixes retain the mesh's existing material assignments. Original shared MetaHuman master/function, source textures, Blender file, rig, UVs and skin weights are not edited by these fixes.
- Save only the intended material/texture assets. Do not save unrelated dirty maps, Blueprints or the mesh to publish a material change.

## 1. Fitted skeleton import

Keep fitted joint positions and surface; convert axes using the saved paired working-rest/native-pose rigs:

`fitted_rest * inverse(working_rest_rotation) * paired_native_pose_rotation`

Do not replace fitted joints with stock mannequin joints or use an arbitrary hidden reference rig. The shared Skeleton remains unchanged; no recurring retargeting pass is added.

Verified: 88 bones, 11,374 vertices; surface error at most 0.000253 mm, joint error at most 0.00539 mm. Idle/walk/run NN poses and independent CPU skinning checked. This is not full attack/PHAT certification.

Scripts in `Tools/MetaHuman`: `export_boss_uefn_fitted.py`, `publish_boss_uefn_fitted.py`, `test_boss_uefn_fitted.py`, `verify_boss_uefn_fitted.py`. Full contract: `Docs/BossUEFNImport.md`.

## 2. Mesh-normal collar candidate — incomplete

Match the 46 paired collar vertices, average their normals, and fade the corrective rotation over two inner topology rings. This changes 245 vertex normals, not positions, weights or UVs. Maximum paired-normal angle dropped from 28.90 degrees to about 0.006682 degrees, but visible shading defects remained. Numerical normal agreement is not proof of a seam-free final shader.

The normals-only reimport was left in memory without saving the keeper. Do not present it as an accepted complete repair. Source also has nonzero collar position gaps (mean 1.107 mm, maximum 6.673 mm); this technique does not weld them.

Script: `boss_collar_normals.py`; exporter option `--repair-collar-normals`. Audit: `Saved/BossSeamAudit/20260908/collar_normals_candidate.json`. Mesh backup: `Saved/BossShading/20260908/Backup/SKM_Boss_UEFN_Fitted.uasset`.

## 3. Correct the bent-normal fallback

`MF_skin_bentNormalsAO` used `(0.5, 0.5, 1)` as a fallback **direction**, not as encoded texture RGB. That tilted the decoded tangent-space direction about 35 degrees and exposed UV/tangent boundaries in Material AO. The neutral direction must be `(0, 0, 1)`.

Corrected only `MF_skin_bentNormalsAO_BossAO` and its isolated `M_skin_unified_baked_BossAO` ancestry. Existing Boss leaf instances were reparented to the corrected ancestry, retaining their overrides. Shared MetaHuman assets remain unchanged.

Scripts: `fix_boss_bent_normal_fallback.py`, `publish_boss_ao_fix.py`. Report: `Saved/BossShading/20260908/ao_fix_publication.json`. Original leaf backups: `Saved/BossShading/20260908/Backup/AOMaterials`.

Epic's explanation: https://forums.unrealengine.com/t/metahuman-uv-seam-skin-tone-inconsistency-with-static-lighting-settings/2652500

Do not hide this shader defect by enabling static lighting globally, increasing shadow bias or adding geometry.

## 4. AO collar fade

Generate `T_Boss_NeckDistance`: a 1024-square linear grayscale mask. Head-surface edge distances from the 46-vertex collar are rasterized into head UVs; red stores centimeters divided by 10. Add UV-gutter padding. This mask stays attached to the deforming skin.

`alpha = saturate((mask.R * 10 - neutral_border_cm) / max(fade_width_cm, 0.01))`

Use alpha to blend from scalar AO 1, bent normal `(0,0,1)` and bent-normal Z 1 at the collar into the original respective outputs farther up the head. This is head-only; the body remains on its neutral path. Default neutral border: **0.2 cm**. Default transition width: **5 cm**. Beyond the band, original face AO remains unchanged.

In the actual head material instance, group **Boss Neck AO**:

- `Use Boss Neck AO Fade`: enabled. Disable to restore the prior head AO path.
- `Neck AO Fade Width Cm`: 5.
- `Neck AO Neutral Border Cm`: 0.2.
- `Boss Neck Distance Mask`: `T_Boss_NeckDistance`.

Scripts: `bake_boss_neck_ao_mask.py`, `add_boss_neck_ao_fade.py`. Mask files: `Saved/BossShading/20260908/NeckFade`. Audit found alpha 0 at all 122 collar UV samples and alpha 1 at all 14,564 samples beyond 5.5 cm. Front/back AO captures and user confirmation accepted this AO result, not all other shading channels.

## 5. BaseColor collar fade — published

**New pending correction:** the user identified faint vertical/radial streaks in the saved wrapped-color transfer. Its nearest-collar-segment extension repeats collar texture variations through the fade band. `bake_boss_neck_color_diffusion.py` replaces that approach with original head texture plus a harmonic surface extension of the body-minus-head boundary color difference. It uses two virtual subdivisions only for baking (no live mesh changes), 184 boundary samples, correction fixed to zero beyond5.2cm. Numerical boundary mean absolute linear-RGB error0.00279, maximum0.02587; harmonic residual<1e-14. This is not proof of visual acceptance. `preview_boss_neck_color_diffusion.py` has assigned `T_Boss_NeckColorMatched` ONLY to the active transient preview head; saved production material still uses the old target. User should check streaks before promotion. AO/normal/specular test state is unchanged. Reports in `Saved/BossShading/20260908/NeckColor/color_diffusion.json`.

**Current coverage:** the user requested reverting the75%-neck extension. Reverted and saved the original surface-distance blend: `Neck Color Neutral Border Cm=0.2`, `Neck Color Fade Width Cm=5`, using `T_Boss_NeckDistance`. The height-progress texture is unused; its scripts/reports describe a rejected experiment, not current settings. Accepted wrapped body-color transfer, AO and stitching are unchanged.

The head color transition is enabled and saved on the actual head material. The unsafe attribute-node construction was replaced with Unreal's existing `/Engine/Functions/MaterialLayerFunctions/MatLayerBlend_OverrideBaseColor`. Readback confirmed color fade true, AO fade true, color width 5 cm, and body color fade false. No material compile errors were found in the current editor log. User performs the visual check; no visual acceptance is claimed.

The body is textured, so the target is **not a single skin-color constant**. Sample the existing body's `T_Body_BC_VT` along the 46 corresponding collar segments, then extend these local colors into head UVs. Texture sampling/interpolation is done in linear RGB; the resulting `T_Boss_NeckBodyColor` is stored as sRGB with BC7 compression and padded UV gutters.

**Source addressing is essential:** Blender body UVs occupy U=[1,2], while the actual UE body texture uses `TA_WRAP` in both axes. Interpolate the source UV along each edge, then use `fract(UV)` before sampling the exported body image. The first implementation mistakenly clamped U to 1 and sampled darker texture-edge background; the user correctly rejected the resulting dark collar. That version was disabled, the texture regenerated with wrapping, then the corrected texture and enabled head instance were saved. AO stayed enabled throughout.

The corrected offline audit compares 230 corresponding collar samples: mean absolute linear-RGB error 0.000954 versus 0.079499 with the old clamp (about 83x smaller). Maximum per-channel errors are about 0.0312/0.0198/0.0210 from raster/filtering differences. This validates the transfer mapping, not final rendered seam elimination. Corrected version awaits user visual acceptance. Reproduction/check/update: `bake_boss_neck_color.py --cached-geometry` (checks source SHA), `check_boss_neck_color_transfer.py`, `publish_boss_neck_color_texture.py`. Audit: `wrapped_transfer_check.json` next to `publication.json`.

Reuse the AO distance mask, with independent color width/border parameters:

`new_base_color = lerp(transferred_body_collar_color, original_final_head_base_color, alpha)`

The engine override function receives the original material, transferred color, and `1 - alpha` as its override mask. It replaces BaseColor and passes the existing CustomData1 through; normal, roughness, AO and the other attributes retain their existing paths. Face color outside the band remains on its original path. This is a static head-only feature, not Blueprint Tick logic.

Controls in the actual head material instance, group **Boss Neck Color**:

- `Use Boss Neck Color Fade`: enabled. Disabling restores the original BaseColor path.
- `Neck Color Neutral Border Cm`: 0.2.
- `Neck Color Fade Width Cm`: 5.
- `Boss Neck Body Color`: generated color-transfer texture.
- `Boss Neck Distance Mask`: shared distance texture, with independent AO/color fade parameters.

Scripts: `bake_boss_neck_color.py`, `add_boss_neck_color_fade.py` (now uses the engine function and refuses duplicate publication). Generated texture/audits: `Saved/BossShading/20260908/NeckColor/T_Boss_NeckBodyColor.png`, `color_transfer.json`, `publication.json`. Saved assets: generated color texture, Boss-only master, actual head instance. No map, mesh or Blueprint was saved by the color publication.

The transfer assumes the current neutral body color adjustments. If the body texture or its material color adjustments change, regenerate the transfer or account for those adjustments. Compression, mips and lighting can affect the perceived boundary: user visual validation remains required. These scripts are guarded one-shot publication scripts, not commands to rerun blindly over an already-published graph.

## Diagnostic and publication rules learned

User-observed interactive tests after stitching: vertex-only skin normals removed the WorldNormals seam; additionally disabling specular removed the remaining Lit separation; additionally disabling head `Use Bent Normal` removed the mid-head MaterialAO split while scalar AO stayed enabled. These are **temporary preview-only diagnostic materials**, not saved fixes. The actual skin material still retains its original normal/specular/bent-normal behavior. Active test is `no_specular_no_bent_normal`; `boss_normal_test['stop']()` restores the original preview materials. Do not confuse a successful isolation test with a published shading repair. The later75%-neck color coverage change is saved independently of these overrides.

1. Inspect Lit, Unlit/BaseColor, WorldNormals and **Material Ambient Occlusion** independently. A Lit-only edge is not automatically a shadow problem. Ordinary AO and Material AO are not interchangeable buffers.
2. The earlier shadow-terminator explanation did not account for the user's exact seam and was withdrawn. A different capture changing when shadows are disabled is insufficient proof.
3. A SceneCapture AO showflag did not exclude shader/bent-normal AO. Inspect the actual Material AO output.
4. Manual postprocess SceneCaptures need `always_persist_rendering_state=True`; use a copied `PostProcessSettings` snapshot (`.copy()`), because the getter is a live reference. Warm up captures before exporting.
5. Capture raw signed normals to floating-point HDR, then remap `normal * 0.5 + 0.5` for display. Direct RGBA8 capture can clamp negative components. Export display images as RGB if unused alpha is zero.
6. UE 5.7's static-switch setter can return false after succeeding; verify the getter and saved instance. Verify the actual mesh-referenced material, not only an isolated test copy.
7. Dynamically populated material-attribute nodes are unsafe to construct blindly through Python without a graph node. GetMaterialAttributes outputs failed to rebuild; assigning SetMaterialAttributes `attribute_set_types` crashed with undersized `Inputs` (`MaterialCachedData.cpp:730`). The successful replacement calls the engine's serialized BaseColor override function; never replay the unsafe setter sequence.
8. Keep source/geometry audits separate from final GPU shading validation. Agreement of imported corner normals/tangents alone cannot rule out a shader defect.

9. Recovery can restore an unfinished, invalid material graph even when its script never saved it. This happened to the Boss master and caused a GetMaterialAttributes PostLoad assertion on restart. We backed up that exact recovered file to `Saved/BossShading/20260908/Backup/ColorCrashRecovery/M_skin_unified_baked_BossAO_recovered_bad.uasset`, restored the pre-color `M_skin_unified_baked_BossAO_Auto1.uasset`, then successfully published the corrected graph. Other recovered user assets were not rolled back. Do not restore the old broken Auto3 master over the corrected saved material.

The published AO and color fades use only material texture sampling/math for enabled head instances; neither adds CPU Tick, skeleton evaluation or runtime texture baking. GPU cost has not been benchmarked.

## 6. Stitched collar and shared geometric normals

Published on the existing `SKM_Boss_UEFN_Fitted`, without an extra Content Browser mesh. Source `.blend` stays untouched: the operation runs only in an export copy. The source has 46 corresponding collar positions, of which **three are already shared**; merge only the other **43** pairs. Never pass a vertex-to-itself entry to BMesh `weld_verts`: it can delete adjacent faces.

Each pair uses the midpoint position and the normalized average of its skin weights. Keep all per-corner UVs and polygon material assignments. Smooth the boundary normals to a shared direction and fade the normal correction through two interior topology rings, then preserve those custom normals through the weld/export/import. Material/UV boundaries may still produce separate GPU vertices; matching positions, weights and normals are what keep those copies coherent.

- Source vertices: 11,374 → 11,331; all 22,068 faces retained.
- 46 shared manifold collar edges; no geometry changes outside the collar vertices.
- Maximum original gap 6.673 mm; midpoint movement per side at most 3.337 mm.
- All 88 reference bones unchanged; existing material assignments, PHAT setting, accepted AO and color fixes retained.
- Imported verification: 46 positions checked, **zero collar gap**, maximum geometric-normal angle about **0.00000121 degrees**; maximum export/import position discrepancy 0.00000860 cm.
- Twenty synthetic affine-bone skinning tests: zero join gap. This is a numerical deformation check, not animation visual certification.
- No normal textures rebaked. Matching geometric normals alone does not prove the final World Normals buffer is seam-free; that view also includes normal-map contributions. User visual check pending.

Scripts: `stitch_boss_collar.py`; `export_boss_uefn_fitted.py -- --stitch-collar`; `import_boss_stitched_collar.py`; `verify_boss_stitched_collar.py`. Export, audits and publication: `Saved/BossUEFNCompatible/20260908_Stitched`. Exact pre-stitch Unreal mesh backup: `Saved/BossUEFNCompatible/20260908_Stitched/Backup/SKM_Boss_UEFN_Fitted.uasset`. Do not blindly rerun one-shot exporters/importers over that backup.

References checked: [Blender weld operator](https://docs.blender.org/api/5.2/bmesh.ops.html), [Epic FBX import options](https://dev.epicgames.com/documentation/unreal-engine/fbx-import-options-reference-in-unreal-engine?lang=en-US). Keep imported normals/tangents; all eight current section tangent-recompute flags remain false.
