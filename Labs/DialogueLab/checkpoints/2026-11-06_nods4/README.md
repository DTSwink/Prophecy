# Dialogue Lab

Lightweight three.js lab to iterate on dialogue body/face/head motion with the speech pipeline.
Local only (127.0.0.1:8842), no internet: three.js r170 is vendored in `vendor/`.

- **Face**: the Unreal MetaHuman audio solve + inner-voice listener + script emotions (scene `apples_occitan_A5`),
  baked to Boss vertex deltas, shipped as PCA morph targets (`mu`, `pc0..pcK-1`) in `data/boss.glb`.
- **Wrinkles + skin colour**: MetaHuman animated maps (cm1-3 colour, wm1-3 normal) blended with 37 region masks
  (`assets/maskpack/mask_atlas.png`, 4 per RGBA tile).
- **Head**: Unreal head yaw/pitch/roll (x0.25, smoothed) added on top of the body over neck_01/neck_02/head (0.3/0.3/0.4).
- **Body**: game idle `M_Neutral_Stand_Idle_Loop` (Anim_Idle.fbx) retargeted onto the Boss rest pose, all 87 bones incl. fingers.
- **Motion** section: the user's speech poses (`speech poses.fbx`, UEFN skeleton: frame 1 = idle reference, then
  explanatory/emphasis poses, shrug, plead), baked into boss.glb as clip `Poses` (`lab_build.py --poses <fbx>`).
  A motion = pose + blend in (duration, ease in/out) + hold (negative = start leaving before reaching the pose) +
  blend out (duration, ease in/out) + idle sway kept in the pose + strength. Preview on either character; save several
  profiles per pose to `motions.json`: each parameter has a [min, max] range and one variation value u (0..1) per take
  sets all of them (coherent takes). FBX frame 4 is dropped (`--poses-skip 4`).
- **On the dialogue** (`speech.js`): saved profiles are placed on the speaker's phrases, apex on the stressed word,
  pose chosen from the script emotion (shrug/plead for exasperation...), u drawn per gesture; deterministic.
- **Emotion slider**: the script-emotion overlay baked at gains 0 · 0.3 · 0.6 · 1 · 1.3 · 1.6 · 2 (1.6 = approved);
  the lab blends the two nearest levels. Levels live in `build/dialog_levels_on_A5.npz`, expressed in the A5 PCA basis
  (max error 0.4 mm), made in the cloud face pipeline (`dialog_layer3.py` with `EMO_GAIN`, `bake_levels.py`, `levels_on_a5.py`).
- **Light**: exposure, key (intensity, angle, height, warmth), fill, rim, ambient. Panel sections fold; folds, emotion and
  light values are remembered per browser.
- **Left ankle**: the fitted Boss rig's `foot_l` rest frame is twisted ~24 deg vs the mannequin, so that one bone takes
  the idle's motion relative to rest (see `DELTA` in `lab_build.py`).
- **Audio**: the 8 ElevenLabs line mp3s scheduled on the scene timeline (1x only).
- **Snapshot for Claude** writes `current_view.png` + `current_view.json` here, so Claude can see the exact view.

## Run
`powershell -ExecutionPolicy Bypass -File launch.ps1` (add `-Window` for an app window, `-Stop` to stop the server),
then open http://127.0.0.1:8842/.

## Rebuild data (Blender 5.1, ~1 min)
```
blender -b --factory-startup -P build\lab_build.py -- <SKM_Boss_UEFN_Fitted.fbx> <Anim_Idle.fbx> <dialog_XX.npz> build\scene_meta.json <this folder> [build\dialog_levels_on_A5.npz] [--poses <speech poses.fbx>]
```
`dialog_XX.npz` comes from the face pipeline (`Tools/FaceSpeech`, `bake_dialog.py`). Textures are copied from
`Saved/SpeechMHA/blender/tex`, audio from `Saved/Speech/ab_apples_occ_fv_tag/v4`.
