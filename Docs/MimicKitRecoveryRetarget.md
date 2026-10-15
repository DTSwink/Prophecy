# Recovery retarget review — October 15, 2026

User requested the same retarget and foot cleanup as the omni locomotion candidates, applied to `C:/Users/singerie/Documents/Cursor/stepper/ue5/slashes/recoveries`. This is an isolated side-conversation deliverable. No training, cloud allocation, Unreal modification, locomotion export change, or parent-task change was performed.

## Current result

- Review: `http://127.0.0.1:8843/`. Two clips, original cyan and reduced orange; overlay, frame scrubbing, speed, and optional hand/head/foot spheres (30 cm default).
- Export directory: `Saved/MimicKitRecoveryRetarget`. Each clip has a MimicKit `.pkl`, numerical source/before/after `.npz`, and foot-correction report. `manifest.json` records source and dependency hashes; `verification.json` records checks.
- Back get-up: 34 frames at 30 Hz, 1.1 seconds; front get-up: 40 frames at 30 Hz, 1.3 seconds. Full original timing retained. Saved motions use CLAMP, not gait wrapping; the viewer repeats only for inspection.
- Originals are unchanged, verified by SHA-256. These are candidate references for review, not approved or wired into training.

## Method and explicit limitations

`Tools/Recoveries/PrepareRecoveryRetarget.py` reads the source FBXs with the installed Autodesk SDK. It uses the existing Stepper FBX-to-UE world/local basis conversion, then the exact anchor offsets, rotation projection and 15-body/28-DOF hierarchy from `PrepareMimicKitOmni.py`. The common `RetargetFootLift.py` helper is imported unchanged. No scaling, smoothing, fitting, joint-limit clipping or mesh edits.

Source arm and thigh-to-knee local offsets agree with the exported UEFN reference within 0.00021 cm; source ankle offsets differ by approximately 0.0533 cm. This independently checks the coordinate conversion. FBX unit scale is centimetres and all sampled global scales are one.

Foot correction raises each foot vertically only enough to remove **additional** penetration caused by retargeting. Pelvis, hip positions, foot XY, foot world orientation, limb lengths and the projected knee pole are preserved. Original foot/collider intersection is deliberately retained, as in the accepted omni cleanup. Across these clips, the original PHAT foot boxes already intersect the floor by up to 4.53 cm; these outputs are not a claim of collision-free reference motion.

Back: 45 foot-frames corrected, maximum lift 0.909 cm. Front: 38 foot-frames corrected, maximum lift 0.1055 cm. Front frame 7 asks for a 0.0511 mm lift of a nearly straight left leg which is outside its exact hinge reach. That entire frame is retained unchanged rather than stretching a leg or moving the pelvis. The isolated wrapper permits an explicitly reported unreachable correction only below 0.1 mm; larger or different failures stop conversion. The shared helper and parent exports are unchanged. All other added floor penetration is below 0.000024 cm (float32 rounding).

The compound torso cannot preserve independently animated spines/clavicles, and the reduced wrists are fixed. Resulting maximum hand-position differences are 18.23 cm for the back clip and 19.55 cm for the front; wrist orientation differences reach 73.59 and 80.60 degrees respectively. These matter for hand support in get-ups and were disclosed to the user alongside the comparison. No additional hand-contact correction was invented or applied.

## Verification and viewer

- Both exports loaded through MimicKit's own motion loader, with finite 34-column frames, correct sampling and duration, and CLAMP semantics.
- Foot-solve targets and knee locations checked against FK; corrected foot world rotations retained within 1e-6 matrix tolerance.
- Upper body/pelvis bit-identical before/after foot cleanup. Uncorrected leg frames bit-identical.
- Per-frame collider clearance checked, with only the frame-7 exception above.
- Both original and retarget layers visually inspected in the browser; clip selection and 30 Hz scrubbing checked.
- Viewer at `Labs/MimicKitRecoveryRetarget` reuses a separate snapshot of the existing omni viewer, with correct 30 Hz timing. Its server serves shared Three.js dependencies read-only and binds localhost only. Parent viewer on 8842 is untouched.

Rebuild: run `Tools/Recoveries/PrepareRecoveryRetarget.py` using `C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe`. Viewer: run `Labs/MimicKitRecoveryRetarget/serve.py` with the same interpreter. Current server PID is recorded in `Saved/MimicKitRecoveryRetarget/viewer.pid`.

## Fixed-camera review mode

Added at the user’s request: **Fixed camera · foot sliding**, enabled by default. Both layers use the first frame’s pelvis XY as a constant display offset instead of subtracting the current pelvis XY every frame. This retains all recorded world displacement against a stationary grid, so foot drift remains visible. Camera orbit/zoom stays available for choosing an inspection angle; playback never moves the camera. Disabling the checkbox restores the previous pelvis-centred view. Animation data and retargeting are unchanged.
