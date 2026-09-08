# Active handoff: UEFN-skeleton MetaHuman body via Blender reduction

## Goal

Finish `/Game/_mygame/MetaHumans/BP_test_UEFNDirect`: direct UEFN animation,
no runtime retargeter, and clean wrists/fingers in extreme poses. The user only
wants the MetaHuman mesh rigged to the untouched UEFN skeleton; no RigLogic,
no DNA, no facial animation. Swappable static faces come later from one weight
template stamped per face (all MetaHuman heads share topology).

## Current plan (2026-07-15): Blender static reduction

In-engine weight fitting was abandoned after two failed shapes (see below).
New pipeline:

1. Export from the live editor as FBX: fitted body
   `SKM_test_UEFNFit_BodyMesh` (342 bones, original continuous MetaHuman
   weights), fitted face `SKM_test_UEFNFit_FaceMesh`, `SKM_UEFN_Mannequin`,
   and climb/cliff/sprint UEFN test animations. Then close Unreal.
2. In headless Blender: keep the original MetaHuman skinning, fold each
   MetaHuman-only helper vertex group into its nearest surviving UEFN bone,
   smooth only the affected regions, delete non-UEFN bones, export FBX.
   Most twist bones are shared with UEFN and keep their weights untouched;
   only true helpers (wrist_inner/outer, `*_half`, correctives, toes) fold.
3. Verify visually inside Blender first: pose the reduced armature with the
   imported UEFN animation frames and render Workbench stills of wrists,
   knees, shoulders. Iterate there (fast), not in Unreal.
4. Reimport onto the untouched `/Game/_mygame/SK_UEFN_Mannequin` Skeleton
   asset, rebuild `BP_test_UEFNDirect`, rerun the climb/sprint/slide/cliff
   screenshot audit at LOD0 and Auto.
5. Face path: strip facial joints from the face mesh, fold them all into
   `head` (exact, since they never move without facial animation), keep the
   existing `head/neck_01/neck_02/spine_05/clavicle_*` integration weights.
   That weight set is the reusable template: stamp it by vertex index onto
   any other MetaHuman face (identical topology), no per-face rigging.

## Current status

- Baseline branch: `main`, origin at `8b3e68c` before this investigation.
- The editor is currently running (last PID `12364`) with remote Python working.
- Default generated assets:
  - `/Game/_mygame/MetaHumans/SKM_test_UEFNDirectBody`
  - `/Game/_mygame/MetaHumans/BP_test_UEFNDirect`
- Authoritative rebuild/audit:
  `Tools/MetaHuman/build_uefn_direct_metahuman.py`.
- Exact skeleton data: `Tools/MetaHuman/skeleton_snapshots.json`.
- Source body:
  `/Game/MetaHumans/test_UEFNExactFull/Body/SKM_test_UEFNFit_BodyMesh`.
- UEFN source mesh/skeleton:
  `/Game/_mygame/SKM_UEFN_Mannequin` and
  `/Game/_mygame/SK_UEFN_Mannequin`.

## What is structurally proven

- The direct body has 78 shared bones in the exact UEFN hierarchy/reference
  transforms, uses the actual UEFN Skeleton asset, and has three LODs.
- The full BP Face remains attached to Body and `Face_AnimBP` copies the body
  head exactly.
- On the demanding climb pose below, all 78 shared runtime bone rotations match;
  maximum sampled translation delta is `0.06250490 cm`, rotation delta is `0`,
  and face/head delta is `0` at both LOD0 and automatic LOD.
- Therefore the remaining failure is skin weighting, not animation evaluation,
  skeleton pose, LOD selection, or face attachment.

## Reproducible failing pose

- Animation:
  `/Game/Characters/UEFN_Mannequin/Animations/Traversal/Climb/M_Neutral_Traversal_Climb_Start_2_5_run_F_Lfoot`
- Time: `2.0 s`.
- Pose with `SkeletalMeshComponent.override_animation_data(Animation, false,
  false, 2.0, 0.0)`; this is the reliable editor-preview API.
- Camera: `(220, 0, 108)`, yaw `180`, screenshot `2200x1375`.
- Failing final capture:
  `Saved/CodexLiveShots/MetaHuman_FinalWide_DemandingClimb_LOD0.png`.
- Automatic-LOD failure:
  `Saved/CodexLiveShots/MetaHuman_FinalWide_DemandingClimb_Auto.png`.

## Current implementation and diagnosis

- Uncommitted C++ in
  `Source/ProphecyEditor/Private/ProphecyEditorModule.cpp` uses Epic
  `FSkeletalMeshOperations::CopySkinWeightAttributeFromMesh` to transfer UEFN
  LOD0 weights by closest surface, then prunes MetaHuman-only bones and
  regenerates LODs.
- `Source/ProphecyEditor/ProphecyEditor.Build.cs` adds
  `SkeletalMeshDescription`.
- This replaced the earlier helper-to-ancestor fold, which affected 6,288/7,622
  vertices and produced severe finger/wrist loops.
- The closest-surface result looks clean in sprint, but the climb pose breaks at
  the wrist.
- `Saved/AuditFinalDirectWeights.py` reports 52 used deform bones, no unexpected
  bones, **zero** vertices jointly weighted to `lowerarm_*` and `hand_*`, and 226
  vertices per side rigidly weighted to `lowerarm_*`. The continuous MetaHuman
  surface therefore inherits a hard wrist seam from the segmented UEFN source.

## Failed experiments - do not promote

1. `_HandFixTest`: original MetaHuman helper folding plus 50/50 finger-half
   splitting. Still tore.
2. `_WeightTransferTest`: closest-surface UEFN transfer. Sprint passed, extreme
   climb exposed broken wrists; this was promoted to the current default before
   the extreme failure was found.
3. `_InpaintTest`: Geometry Script normal-aware inpaint, radius `0.025`, normal
   threshold `30 degrees`, smoothing `5 x 0.25`. Hands looked intact only because
   the MetaHuman arms no longer followed the demanded pose; global weights were
   corrupted. Screenshot:
   `Saved/CodexLiveShots/MetaHuman_FinalWide_InpaintDemandingClimb_LOD0.png`.
4. `_WristBlendTest`: added lowerarm/hand blending to 57 rigid lower-arm vertices
   per side over longitudinal range `-10..-2 cm`. The exact climb pose still has
   broken wrists. Screenshot:
   `Saved/CodexLiveShots/MetaHuman_FinalWide_WristBlendDemandingClimb_LOD0.png`.
5. `_PoseFitTest` (2026-07-15): per-vertex NNLS fit of shared-bone weights
   against 52 poses sampled from the driven full rig
   (`Tools/MetaHuman/fit_reduced_skin_weights.py`,
   `Tools/MetaHuman/sample_metahuman_helper_poses.py`). Two important findings:
   - Compatible-skeleton playback of UEFN animations on the MetaHuman skeleton
     diverges from the UEFN mannequin pose by up to ~9 cm on twist pivots and
     ~15 cm / ~37 deg on driven fingers; a fit done purely in the MetaHuman pose
     convention breaks wrists at runtime. Sampling records both conventions
     (`Saved/PoseFit/pose_samples.jsonl` has `bones` + `uefn_bones`).
   - Even with the convention handled through a synthetic rigid skeleton, the
     per-vertex independent solve has no spatial smoothness and produced fins /
     webbing between fingers and along the forearm. Screenshots:
     `Saved/CodexLiveShots/MetaHuman_Iso_Climb_handR.png`,
     `MetaHuman_HandAB_Climb_PoseFitReduced.png`.

Test assets currently exist under `/Game/_mygame/MetaHumans/` with suffixes
`_HandFixTest`, `_WeightTransferTest`, `_InpaintTest`, `_WristBlendTest`, and
`_PoseFitTest`. The old default `SKM_test_UEFNDirectBody` may be in a broken
half-deleted state in the running editor (asset registry entry survives,
loading fails); rebuild it from scratch during promotion. `BP_test_UEFNDirect`
was deleted and must be regenerated.

## Useful local scripts

- `Saved/RunUnrealRemote.py`: execute a Python file in the live editor.
- `Saved/CaptureMetaHumanFinalWideAudit.py`: currently configured for
  `_WristBlendTest` and the one demanding climb pose.
- `Saved/AuditFinalDirectWeights.py`: reliable name-based weight audit via
  `SkinWeightModifier`.
- `Saved/MetaHumanHandWeightAudit.py`: original helper influence audit.
- `Saved/BuildInpaintMetaHumanTest.py`: builds the failed global inpaint test.
- `Saved/BuildWristBlendMetaHumanTest.py`: builds the failed 57-vertex blend.

## Recommended next direction

Do not keep transferring weights from the segmented UEFN render mesh. Preserve
the continuous fitted MetaHuman skinning and build a geometry-/hierarchy-aware
reduction from the 342-bone MetaHuman rig to the 78 shared UEFN bones. Focus first
on the original wrist helpers (`wrist_inner_*`, `wrist_outer_*`) and lower-arm
correctives, deriving a smooth lowerarm/hand blend from the original MetaHuman
weights. Keep the exact climb pose as the acceptance test, then rerun sprint and
two more extreme animations at LOD0 and automatic LOD.

Before promotion, require actual screenshots with intact wrists/fingers and
matching body/face pose. After success: rebuild the default body/BP, remove test
assets, update the finished journal state, compile, then commit/push only the
relevant source/build/journal files while preserving unrelated dirty work.
