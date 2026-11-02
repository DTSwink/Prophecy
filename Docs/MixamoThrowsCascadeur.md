# Mixamo throw exports for Cascadeur — October 24, 2026

Current correction: both user downloads were retargeted with Unreal 5.7's IK
Retargeter and exported again as **animation-only** FBXs for the user's existing
Cascadeur UEFN rig. The initial mesh-inclusive exports displayed severe mesh
distortion in the user's Cascadeur workflow and are superseded.

Output folder: `C:/Users/singerie/Documents/UEFN_Throws_Cascadeur_20261024`

| File | Samples at 30 fps | Duration |
| --- | ---: | ---: |
| UEFN_Throwing_AnimationOnly.fbx | 168 | 5.566667 seconds |
| UEFN_Throw_Object_AnimationOnly.fbx | 147 | 4.866667 seconds |

Both have 88 bones, centimetre units, Z-up coordinates, no meshes and no bind-pose
objects, matching `Documents/cascadeur/Sitting_Idle_Anim1.FBX`. Bone names,
hierarchy, reference translations/rotations/scales and pre/post rotations are
exactly equal to that working export. Every global joint transform at all315
frames is exactly unchanged from the original retarget (maximum difference0).
Import as animation onto the existing UEFN rig. No trimming or speed changes.
Each original download contains an empty `Take 001` lasting 9.08 seconds plus
the real `mixamo.com` take. Preparation removes only the empty take in working
copies; original downloads remain byte-identical, verified by SHA256.

Saved Unreal assets:

- `/Game/_mygame/animations/MixamoThrows20261024/UEFN_Throwing`
- `/Game/_mygame/animations/MixamoThrows20261024/UEFN_Throw_Object`

Source imports and dedicated IK rigs/retargeter are in the same isolated content
folder. The target asset resolves to `/Game/_mygame/SKM_UEFN_Mannequin` with
`/Game/_mygame/SK_UEFN_Mannequin`. Auto-characterized chains, exact anatomical
mapping, target retarget-pose alignment, and target full-body IK were used.
All 19 source body/finger chains map. UEFN-only metacarpals retain their target
pose; the standard root-motion operation handles the additional target root.
Existing skeleton/mesh assets and gameplay Blueprints/maps were not saved.

Tools: `Tools/Animation/PrepareMixamoThrows.py`, `RetargetMixamoThrows.py`,
`ReexportMixamoThrowsAnimationOnly.py`, and `VerifyAnimationOnlyThrows.py`.
Preparation/verification use the existing Stepper
Python 3.10 environment with Autodesk FBX SDK. Run the Unreal script only in an
owned process: it quits that process. Use `UnrealEditor-Cmd` with
`/Engine/Maps/Entry -nullrhi -nocef -unattended -NoSplash -NoSound` and
`-ExecutePythonScript=<absolute script path>`. One below-normal-priority process
was used for the correction and exited afterward. Wait for concurrent normal
project builds before launching. No rendering or C++ build needed for this export.

Receipts: `Saved/Diagnostics/MixamoThrows20261024/` contains source hashes,
Unreal mappings/export results, SDK readback verification, logs, and sampled
pose review. `animation-only-verification.json` records the corrected checks.
Initial verification checked bone motion but missed the user's actual skin/import
failure. Follow-up Autodesk-SDK skin evaluation of both original FBXs produced
coherent meshes at sampled poses; this does not reproduce or disprove the observed
Cascadeur failure. The concrete export-format mismatch (extra mesh and bind pose)
was removed. No Cascadeur application import of the correction was performed:
user stopped Computer Use and explicitly requested no desktop interaction.
Do not claim that the Cascadeur import itself was verified. Superseded mesh FBXs
are preserved under the audit folder's `SupersededMeshExports`, with hashes checked
before moving. `VerifyMixamoThrows.py` is historical initial verification only.
Owned Unreal processes exited. No C++ changes, project build, gameplay wiring,
training changes, or interruption of the user's running labs were required.
