# Face journal

Separate handoff for facial expressions: baked face morph targets, wrinkle textures, face material
and curve/runtime hookup. Unreal-wide rules (golden rules, build/restart, preserve user Play/BP) still
come from ProjectJournal.md. Technical reference: [Docs/FaceExpressions.md](Docs/FaceExpressions.md).

**Goal (user, Nov 4):** facial expressions at the lowest possible framerate cost. Everything pre-computed,
no procedural face. Characters are MetaHuman meshes retargeted to the UEFN skeleton with NO face rig,
NO DNA/RigLogic. Chosen approach: baked morph targets driven by curves + optional wrinkle (and later
flush) textures in the face material. Not bones (keeps the shared 78-bone UEFN skeleton untouched,
keeps the cost on the GPU while NN/Jolt load the CPU). UE 5.7.4 now, 5.9 later (morphs/curves are stable API).
Caveat for later: Nanite skinned meshes still don't support morphs (Epic, Aug 2026).

## Current status

**November 4 — wrinkle textures built (cloud), NOT imported.** Source: Epic's public MetaHuman DNA
Calibration repo, Ada's wm1/wm2/wm3 wrinkle normal maps and 37 region masks (shared MetaHuman UVs, so
they fit the Boss head exactly). Per-expression mask weights come from Ada.dna's animated-map logic for
the same control values as the morphs. Detail = wrinkle map minus Ada base normal in slope space, so no
Ada pores/identity are carried. Two layers: stretch (wm1+wm3, merge loses ~3% of detail energy) and
compress (wm2); a single merged layer would lose ~27%, so it was rejected.
- `Exports/FaceWrinkles/T_Face_WrinkleDetail.png` 1024 RGBA (RG stretch XY, BA compress XY, DX green).
- `T_Face_WrinkleMasks_0..3.png` 256 RGBA, 14 (expression, layer) channels; table in `wrinkle_layout.json`.
- `FaceWrinkles.hlsl`: Custom-node code. Neutral face = uniform branch, zero texture reads; expressive =
  5 reads + ~30 ALU. Dead and LookDown reuse the blink channels (no extra textures). Look* have no wrinkles.
- Import: `Tools/FaceExpressions/import_face_wrinkle_textures.py` -> `/Game/_mygame/MetaHumans/FaceWrinkles`,
  sRGB off, Detail BC7, masks TC_Masks, not saved.
- Verified: the snippet math in numpy against shipped textures matches the preview normals within 8-bit
  rounding (mean 0.05 deg, p99 0.3 deg). Offline Cycles preview `wrinkles_preview.png` uses Ada's colour/
  normal maps as stand-ins (Boss textures are only in .uasset): NOT an in-engine look check.
- Not done: wiring into the head material. Boss head uses `MI_Face_Skin_Baked_LOD3_VT` (parent shared
  with other heads, already has Boss-only static switches). Plan: add a default-off static switch
  "Use Face Wrinkles" to that parent, Custom node between the existing tangent normal and the Normal pin.
  Needs user OK before touching the shared material.

**November 4 — Boss expression morphs built (cloud), NOT imported.**
14 morphs: Blink_L, Blink_R, JawOpen, Effort, Pain, Shout, Anger, Fear, Grin, Dead, LookLeft/Right/Up/Down.
- FBX: `Saved/BossUEFNCompatible/20261104_Expressions/SKM_Boss_UEFN_Fitted_Expressions.fbx`, built from
  the 20260908_Stitched keeper FBX with shape keys added only. Round trip: bones max 6.9e-6, vertices
  8.7e-8 m, UV/weights/materials/vertex order identical, normals within 4.3e-4.
- Import: `Tools/MetaHuman/import_boss_expressions.py` (no Play; backup; asserts reference rig + base
  vertices unchanged and 14 morphs; does NOT save).
- Method: numpy RigLogic on Ada.dna (head at LOD0 incl. blendshapes, sampled to LOD3; other parts LOD3
  rig), UV correspondence (Boss head = MetaHuman LOD3 parts 1:1), similarity transfer (scale 1.004).
  Limit: Ada-proportioned motion transferred to his face, not his own DNA.

## Next

1. User/agent in editor: run both import scripts, look at morphs + textures, save.
2. With user OK: material switch + Custom node; same-named curves flagged Morph + Material.
3. Runtime: curve-only expression sequences (or native SetMorphTarget/SetScalarParameter per tick) on
   hit/attack/death/idle blink. Morphs LOD0 only for the Boss (single LOD).
4. Optional flush: same masks drive Ada's cm1-3 colour maps; one extra low-res texture.
5. Other characters: export their MetaHuman-LOD3 face/character FBX; rerun `Tools/FaceExpressions` (~1 min).
   Wrinkle textures are shared as-is (same UVs).

## Lightweight Git backup

The November 4 small-file checkpoint includes these journals, expression scripts,
wrinkle shader/layout and four small mask PNGs. The detail texture, offline preview
images and generated FBX stay local to conserve transfer data. Regeneration needs
the external Epic DNA/maps and Blender environment documented below; this is not
a complete ready-to-import asset backup.

## Reproduce (cloud)

`Tools/FaceExpressions/`: rl.py (RigLogic), match*.py/align.py (correspondence), bake.py (morph deltas),
export_boss.py + verify_rt.py (FBX), wr_build.py (wrinkle textures), wr_render.py/apply_render.py (previews).
Needs Python 3.10 + Epic MetaHuman-DNA-Calibration (Maya2024 linux bindings, Ada.dna, data/maps, data/masks)
and Blender 5.2 `bpy` (pip). All paths in the scripts are cloud paths.
