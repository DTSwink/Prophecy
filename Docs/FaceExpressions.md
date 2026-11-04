# Face expressions (baked morph targets) — November 4

Cheapest-runtime facial expressions: 14 pre-baked morph targets on the face, driven by curves.
No face bones, no RigLogic, no face AnimBP. Shared UEFN skeleton untouched.

## Current state

- **Boss only, built in the cloud, NOT yet imported.** FBX:
  `Saved/BossUEFNCompatible/20261104_Expressions/SKM_Boss_UEFN_Fitted_Expressions.fbx`
  (source: the 20260908_Stitched keeper FBX, shape keys added only).
- Round trip vs the stitched keeper FBX (`roundtrip_verification.json`): same bones/hierarchy
  (max matrix diff 6.9e-6), vertex positions 8.7e-8 m, UVs/weights/materials/vertex order identical,
  normals within 4.3e-4; shape deltas reproduced within 1.1e-6 m.
- Import: `Tools/MetaHuman/import_boss_expressions.py` (live editor, no Play). Backs up the uasset,
  keeps materials/PHAT/Skeleton, asserts reference rig + base vertices unchanged and 14 morphs present.
  **Does not save** — inspect in the Skeletal Mesh editor, then save.
- Preview: `expressions_preview.png` (offline Cycles renders, flat materials — not an in-engine check).

## Morphs

Blink_L, Blink_R, JawOpen, Effort, Pain, Shout, Anger, Fear, Grin, Dead, LookLeft, LookRight, LookUp, LookDown.
Exact MetaHuman control values per morph: `bake_report.json`. "Look" morphs move eyeballs + lids linearly
(fine up to ~0.7 of MetaHuman look range; not a substitute for eye bones at extreme angles).

## How they were made (reproducible, no Unreal)

Scripts: `Tools/FaceExpressions/`. Python 3.10 + Epic's public MetaHuman-DNA-Calibration repo
(Maya2024 linux bindings) for `rl.py`; Blender 5.2 `bpy` module for import/export/render.

1. `rl.py`: numpy RigLogic (raw controls -> PSD correctives -> joint deltas + blendshapes -> skinning)
   on Epic's reference head **Ada.dna**. Head deltas evaluated at LOD0 (blendshapes included) and sampled
   onto LOD3 vertices; teeth/eyes/eyeshell/eyelashes/eyeEdge evaluated with the LOD3 rig.
2. `match.py`/`match2.py`: Boss head = MetaHuman LOD3 topology (head 2548, teeth 415, eyes 110,
   eyeshell 120, eyeEdge 112, eyelashes 374). Correspondence by UV (exact 1:1 for head/teeth/eyes/eyeEdge;
   eyeshell/eyelashes disambiguated by side).
3. `align.py`: similarity fit Ada -> Boss head (scale 1.004, residual mean 7 mm = face shape difference).
4. `bake.py`: deltas rotated/scaled into Boss space. `export_boss.py`: shape keys + the standard
   `blender_ue_export.export_skeletal_fbx` settings. `verify_rt.py`: round-trip check.

**Limit:** deltas come from Ada's face and are transferred rigidly; the Boss's own DNA is not used, so
expressions are Ada-proportioned on his face. Good for game-distance faces; not a likeness-exact rig.

## Other characters

Any face using the same MetaHuman LOD3 head parts (ally/enemy Optimized MetaHumans use LOD3 materials)
reuses steps 2–4 unchanged: export the face/character FBX, rerun, ~1 minute in the cloud.

## Runtime setup (planned, not done)

Face morphs driven by curve-only sequences or native `SetMorphTarget` per tick; LOD0–1 only; optional
wrinkle/flush material curves. The Boss is a single combined mesh, so curves come from its own AnimBP
(or native code) — no Leader Pose needed for him.

## Wrinkles (November 4, built, not imported)

Cheap expression wrinkles in the face material, driven by the same curve names as the morphs.
- Textures: `Exports/FaceWrinkles/` (1024 RGBA detail, 4x 256 RGBA masks), shared MetaHuman head UVs.
- Material: `Exports/FaceWrinkles/FaceWrinkles.hlsl` Custom node; inputs/outputs documented in the file;
  channel table `wrinkle_layout.json`. Base normal in, wrinkled normal out (slope-space add).
- Cost: neutral face 0 extra reads (uniform branch); expressive 5 reads + ~30 ALU, face pixels only.
- Import: `Tools/FaceExpressions/import_face_wrinkle_textures.py` (sRGB off, BC7 / TC_Masks, not saved).
- Build: `Tools/FaceExpressions/wr_build.py`. Status and next steps: `FaceJournal.md`.
