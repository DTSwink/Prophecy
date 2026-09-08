# Boss fitted mesh / Unreal bind contract

## Confirmed source and result

Latest keeper update: the collar is now stitched (43 merged pairs, three already-shared positions), with shared normals and skin weights. Current source vertex count is11,331, not the historical pre-stitch11,374 below. Blender source and shared Skeleton remain unchanged. Details and rollback: `Docs/BossSkinTechniques.md`, section6; reports at `Saved/BossUEFNCompatible/20260908_Stitched`. Imported join and geometric normals verified numerically; final normal-map shading awaits user visual check.

- Source: `C:/Users/singerie/Documents/Blender/bossfinalsave.blend`.
- Visible combined mesh: `boss`; actual Armature modifier target: `UEFN_WORKING_CLEAN_RIG.001`.
- Saved fitted rig is already at rest (all pose-basis matrices identity). Hidden/native reference rigs are not interchangeable with its fitted rest matrices.
- Verified source SHA256, unchanged throughout this work: `675AD67F63231704D74C1482AA06479682A2020780110D757DF89B1B98AE3415`.
- Corrected keeper: `/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN_Fitted`.
- Assigned Skeleton: existing `/Game/_mygame/SK_UEFN_Mannequin`, unchanged. The mesh owns its fitted reference joints; assigning the shared Skeleton does not replace those joints.
- Export: `Saved/BossUEFNCompatible/20260907/SKM_Boss_UEFN_Fitted.fbx`.
- The original `SKM_Boss_UEFN` is retained unchanged for recovery/comparison. No agent Blueprint or map was saved or switched to Boss automatically. Choose the corrected keeper explicitly.

## What was wrong

The existing `/Game/_mygame/MetaHumans/BossUEFN/SKM_Boss_UEFN` retains essentially the fitted Boss surface, but its reference joints are the native mannequin rest pose. Against the actual fitted Blender rig, left-wrist offset is10.652cm, left middle distal-finger joint13.970cm, and left-foot5.510cm. This is not just Blender versus Unreal bone-tail display.

The asset was saved July24 at05:56. The FBX currently at its import path was regenerated at13:31. That later exporter intentionally deforms the Boss into native rest before rebinding; it is not a direct preservation of the fitted source. Its saved audit records up to14.959cm source-surface displacement. Its top-level armature also exported as `root.001` (Unreal `root_001`) because the requested `root` name was already occupied. Do not promote this historical FBX without correcting and validating that separate conversion.

## Accepted conversion and verification

The exporter preserves the fitted joint positions, shape and hierarchy while converting bone coordinate axes once in the asset. It uses the saved paired `UEFN_WORKING_CLEAN_RIG` rest matrices and `UEFN_NATIVE_EXPORT_RIG` pose matrices, which describe the same physical pose. For each bone, the rotational correction is `inverse(working rest rotation) * native paired-pose rotation`; the fitted rest matrix is multiplied by this correction. It does not replace the fitted pose with native mannequin rest.

Existing skin weights are normalized without changing their relative influence. No new transfer, inverse solve, source save, NN changes or additional runtime retargeting pass. Converted bone tails are axis markers, not necessarily child-joint endpoints; joint heads remain fitted.

- 87 Blender bones plus armature/root =88 Unreal bones;11,374 vertices and eight existing material regions.
- All11,374 source surface vertices have an imported counterpart within0.000253mm.
- Maximum corresponding joint-position difference:0.00539mm; the axis conversion itself moves no fitted joint heads.
- All88 bone names and parent relationships match native UEFN.
- Idle/walk/run tested with the existing native NN anim instance on an isolated temporary agent in `testNN`. Bone positions match the presented NN targets within6e-14cm; the mover travelled over15m.
- Actual UE CPU-skinned vertices match independently calculated linear-blend skinning within0.00529mm across those three poses. This verifies the deformed surface, not only bone/socket positions.
- Unreal scene captures of those poses were inspected: no obvious inverted limbs or exploding skin. This is a short kinematic NN check, not comprehensive attack/overlay/PHAT certification.
- Keeper and isolated test copy have identical mesh reference transforms, vertices and weights after import onto the shared Skeleton. Original Boss and shared Skeleton file hashes are unchanged.
- Reports and three engine captures: `Saved/BossUEFNCompatible/20260907/{export_audit,verification,runtime,publication}.json`, `{idle,walk,run}.png`; reference extraction: `Saved/BossBindAudit/20260907/unreal_keeper.json`.
- The keeper has no default Physics Asset, as with the original Boss. A mesh-component PHAT override remains a separate setup choice; no PHAT was edited.

## Reproduction and import cautions

- Read-only source probe: `Tools/MetaHuman/audit_boss_bind_20260907.py` (background Blender only; it discards its in-memory scene when importing the historical FBX).
- Keeper export: `Tools/MetaHuman/export_boss_uefn_fitted.py`, run in background Blender opening the source. It refuses to overwrite its FBX and never saves the source blend.
- Publish: `Tools/MetaHuman/publish_boss_uefn_fitted.py`, executed in the live editor. Imports onto the existing Skeleton with `Update Skeleton Reference Pose` off and protects original/shared asset hashes. It refuses to overwrite a finished keeper.
- Runtime validation: `Tools/MetaHuman/test_boss_uefn_fitted.py`; follow its temporary-native-agent setup comment, run in PIE, remove the temporary editor actor afterward. It stops PIE automatically and never saves the map. A dedicated native shell avoids user BP timers/physics/input experiments contaminating the asset test.
- Independent verification: `python Tools/MetaHuman/verify_boss_uefn_fitted.py`.
- UE extraction: `Tools/MetaHuman/audit_boss_unreal_20260907.py`; `capture(path,label)` reads geometry, normalized skin weights and mesh-reference joints, without committing a SkeletonModifier.
- Raw fitted diagnosis helpers: `export_boss_fitted_validation_20260907.py`, `compare_boss_bind_20260907.py`, `import_boss_validation_20260907.py`. Those raw Blender-axis assets under `Validation_20260907/Fitted` are not NN drop-ins. Other validation copies are diagnostic, not keeper replacements.
- Use a fresh destination folder for an independent Skeleton. UE5.7 `InterchangeGenericAssetsPipeline::AdjustSettingsForContext` auto-selects the first Skeleton already in the destination when the option is unset. Reimport also retains an existing mesh's Skeleton association; select the intended Skeleton during a fresh import. Never enable shared-Skeleton reference-pose updates for this workflow.
- Current native source was reloaded successfully with Live Coding and the manual Blueprint recompiled without saving it. `GetLocomotionTarget` resolves through reflection. Python's cached wrapper can remain stale after Live Coding; its missing method is not proof that the reflected Blueprint node is missing.

## 2026-09-08 shading investigation — AO fallback and neck fade published

Consolidated current techniques: `Docs/BossSkinTechniques.md`. BaseColor collar fade is now also saved and enabled on the actual head material (`Boss Neck Color`, width5cm, neutral border0.2cm); it transfers the body's collar colors into head UVs and fades to original face color using the engine's existing BaseColor override function. AO remains enabled. Color visual acceptance is pending the user's check. No mesh/map/Blueprint was saved by color publication.

Latest published state: the Boss-only `(0,0,1)` fallback correction is saved, and `Use Boss Neck AO Fade=True` is now enabled and saved on the ACTUAL existing `MI_Face_Skin_Baked_LOD3_VT`, not just the test copy. The body keeps this switch false. Its corrected material ancestry is under `/Game/_mygame/MetaHumans/BossUEFN/Materials/AORepair`; the shared MetaHuman function/master are unchanged. Existing mesh material assignments did not change; neither the dirty keeper mesh nor any map/Blueprint was saved.

The head-only fade uses `T_Boss_NeckDistance`, a 1024-square linear grayscale mask derived offline from head-surface edge distance to the 46-vertex collar. Weight is `saturate((mask.R * 10 - Neck AO Neutral Border Cm) / max(Neck AO Fade Width Cm, 0.01))`; defaults are 0.2cm neutral border and 5cm fade width. It blends scalar AO and bent-normal Z from1, and the bent-normal vector from `(0,0,1)`, into the unchanged original outputs. Static-disabled body instances do not need the mask branch. Geometry, UVs, rig and source textures are unchanged. Mask audit: all122collar UV samples yield0; all14,564samples beyond5.5cm yield1. The face retains its original AO.

Before/after AO captures `neck_fade_{before,after}_ao.png` and `neck_fade_front_{before,after}_ao.png` in `Saved/BossShading/20260908` show the collar AO edge replaced with a smooth transition. Lit views still show other shading/color differences; do not claim all collar defects are solved. Scripts: `bake_boss_neck_ao_mask.py`, `add_boss_neck_ao_fade.py`, `capture_boss_ao_fix.py` under `Tools/MetaHuman`. Capture requirements: manual postprocess captures need `always_persist_rendering_state=True`; snapshot `PostProcessSettings` using `.copy()` because the getter is a live reference. UE5.7 static-switch setter returns false even after success; verify through its getter. Publication was delayed while the fade was enabled only on the isolated test material; the user's actual material now has the switch enabled and saved.

The historical investigation below records findings before this publication; earlier “pending” wording is superseded by the state above.

### Priority: Lit-only back/shoulder polygon patches

The user identified sharp rear-shoulder patches in the skeletal-mesh editor during `M_Neutral_Stand_Idle_Loop`; those patches were smooth in Unlit and World Normal. A subsequent user capture shows the exact sharp shoulder boundaries in the Material Ambient Occlusion buffer. The earlier conclusion that VSM shadow-terminator faceting explained the user's issue was overconfident and is withdrawn. The collar boundary remains a separate unresolved visual concern; the neck prototype is paused while the material correction is validated.

Reproduced sharp rear-torso lighting patches on a transient actor using the keeper and its unchanged original materials in `testNN`. Captures use a fixed reference pose/camera, not the user's exact animated asset-editor lighting. Camera framing is the back, not hands. Script: `Tools/MetaHuman/capture_boss_back_lighting.py`; outputs `Saved/BossShading/20260908/rear_back_*.png`.

- In those specific captures, disabling only the preview mesh's `cast_shadow` removes the observed polygonal back patches; the collar seam remains. Disabling capture `DynamicShadows` also removes those patches. This different lighting/test setup does NOT establish the cause of the user's Material AO seam or rule out a material contribution.
- Disabling `ContactShadows` alone did not remove the captured patches. Separate Specular and SubsurfaceScattering tests also left them. The capture's MaterialAmbientOcclusion showflag test was NOT a valid exclusion of material AO/bent normals: UE5.7 applies its scalar AO override in game/editor viewport clients, not SceneCapture; even a working scalar AO override does not bypass the separate bent-normal output.
- VSM is enabled (`r.Shadow.Virtual.Enable=1`); ray-traced shadows are off. The keeper has one LOD and this test uses LOD0.
- `capture_boss_shadow_bias.py` tested `r.Shadow.Virtual.NormalBias` temporarily. Original 0.5; 1/2/4/8 did not cleanly solve all facets. Extreme 32/128 values were diagnostic only: large bias removes most back facets but visibly displaces other shadows. These are NOT recommended settings. The script and final live query confirm restoration to 0.5; mesh shadow casting and capture flags restored too.
- These shadow A/B observations remain historical evidence, not an accepted diagnosis or justification for adding geometry. VSM documentation describes shadow-terminator artifacts and the scene-wide bias tradeoff, but that resemblance did not exclude the now-observed Material AO problem.

Current material findings and authorized narrow fix:

- The local `MF_skin_bentNormalsAO` contains `Constant3Vector_0=(0.5,0.5,1)`. Head bent normals are enabled; body bent normals are disabled. Live project settings are `r.AllowStaticLighting=0` and `r.GBufferDiffuseSampleOcclusion=0`.
- This constant is an already-decoded tangent-space direction, NOT a normal-texture RGB sample. UE5.7 `MaterialTemplate.ush::GetWorldBentNormalZero` transforms it directly by the tangent basis; `(0.5,0.5,1)` introduces a 35.26-degree tilt whose world direction changes across UV islands. A flat direction is `(0,0,1)`.
- `BasePassCommon.ush::ApplyBentNormal` still derives occlusion when scalar Material AO is 1, and `BasePassPixelShader.usf` writes that result into `GBufferAO`. Therefore disabling the material's AO scalar or a viewport AO showflag is not equivalent to removing this bent-normal contribution.
- Epic staff recommended the same fallback correction in [MetaHuman UV Seam Skin Tone Inconsistency with Static Lighting Settings](https://forums.unrealengine.com/t/metahuman-uv-seam-skin-tone-inconsistency-with-static-lighting-settings/2652500). The thread also notes head/body bent-normal differences can leave a separate neck mismatch, so this is not a promise to solve every collar issue.
- The user authorized a quick isolated-copy material-function correction from `(0.5,0.5,1)` to `(0,0,1)`. **Actual fix validation and publication are pending.** Do not claim the seams are fixed until the corrected materials are tested in the relevant AO and Lit views. No additional geometry work is part of this fix; preserve original material/function assets, rig, UVs, weights and unrelated dirty assets.

### Separate collar seam: prior partial repair is not solved

Source audit found 46 paired body/head border vertices, with mean separation 1.107mm and max 6.673mm; their source normals differ by up to 28.90 degrees. These are separate border rings, not a single watertight collar. July's smooth-normal preparation is already present in the source and does not fix this.

`boss_collar_normals.py` averages paired border normals and fades the correction over two inner rings. `export_boss_uefn_fitted.py -- --repair-collar-normals` writes a separate candidate to `Saved/BossUEFNCompatible/20260908_Shading`. Raw FBX verification found positions, indices, UVs, skin weights and bind transforms unchanged; paired normal angles fall below 0.007 degrees. This is NOT evidence of a finished visual fix: the user still sees a collar seam in final World Normal and Unlit, especially from behind.

That normals-only FBX was reimported into the fitted keeper in memory with save disabled. Do not mistake the dirty in-memory candidate for an accepted/published repair. Original fitted asset backup: `Saved/BossShading/20260908/Backup/SKM_Boss_UEFN_Fitted.uasset`. Blender source, old Boss, shared skeleton and original material assets were not modified. Unrelated dirty Blueprint/map assets must not be saved as part of this work.

The user approved a separate full-character test copy with only the collar geometry/texture treatment rebuilt; that work is paused for the Lit-only back priority. It must be validated front/back/sides in Lit, Base Color and final World Normal before any keeper replacement. Render-target Base Color/Normal PNGs may have alpha zero: RGB-only preview copies are needed for inline display, otherwise the user sees blank images.
