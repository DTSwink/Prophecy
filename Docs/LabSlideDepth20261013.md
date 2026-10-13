# Slide from the reached depth — October13

The user requested that sheathing stop pulling the sword back to 0% before
sliding. Alignment now preserves the captured grip position along the holster
axis. It still turns inside the rotation tolerance and corrects the sideways
offset under the existing independent hand speed limits. The resulting tip
depth becomes the starting insertion fraction.

Sliding interpolates from that fraction to 100%, with its duration based on the
remaining distance. The sword stays holster-owned. Its transform at alignment
completion equals its transform at slide start; it is not reset to the entrance.
The captured body pose still anchors the body transition. Sheathing FK-return
and head-look-out thresholds use actual insertion. Rotation correction uses
elapsed slide time, independently of the slide curve. The body endpoint preview
converts requested insertion to progress over the remaining slide.

A negative starting fraction means the aligned tip remains outside the mouth;
the slide then covers that extra distance. No clamp or concealed position jump
forces it to 0%. No new controls. Approach, drawing and saved tuning unchanged.
This is lab-only; Unreal is untouched and does not yet have this behavior.

## Verification

- Frozen user run/S,25% shrink,.5s shrink duration: attach84, slide85.
  Old84→85 axial hand movement was1.287357cm outward. New movement is below
  1e-12cm. Starting insertion is1.919769%;86 moves inward.644721cm.
- Pre-capture frames exactly unchanged. Six drawing trajectories, both planners
  across idle/walk/run, exactly unchanged against pre-edit source.
-36 motion/planner/curve/shrink cases pass capture continuity, tolerance,
  independent hand target speed caps, preserved axial position, correct tip
  depth, continuous slide entry, full seating, and both sequence orders.
-12 focused depth cases pass remaining-distance timing and actual-insertion
  FK/head thresholds; starting insertion range−1.311% to1.920%.
- Displacing the arm solver100cm after capture still cannot change sword motion.
-36 shrink-duration cases,12 body-schedule cases(51 interior samples), causal
  input audit and isolated UI playback/sequence/worker/save/reload checks pass.
- Bone reach limits remain real. Broad suite integer alignment grip error is
  below2e-13cm; fractional FK sampling has up to.708cm tracking error in stress
  cases. No claim of exact physical or full Unreal parity.

Backups and before/after receipt: `Saved/Diagnostics/SlideDepth20261013/`.
Tests: `test_tipalign.cjs`, `test_slide_depth.cjs`, `test_sword_owner.cjs`,
`test_shrink_speed.cjs`, `test_attach_body_schedule.cjs`, `test_online.cjs`,
`test_online_ui.cjs`. The old zero-depth test contract was replaced with the
requested preservation and endpoint assertions; speed/continuity checks remain.
No asset save, native build, editor restart or push. Refresh the lab.
