# Special attacks and grab independence - isolated development

October 20, 2026. Built and tested in isolation; **not installed in the user's editor**.

## October20 release and heading refinement

Current isolated API adds **Release Grab**,0..1,default.8. Zero releases both held
hands immediately. Positive values release after entry blend plus that fraction
of the retained motion;1 releases at completion (including an early cutoff).
Ending/interruption releases any still-held grips. Non-grabbing reach requests
are preserved. This replaces the earlier manual-release-only behavior.

User confirmed the new **Cut Early** convention:0 means full clip; positive values
select the endpoint (.8 means80%,1 means full). This supersedes the old amount-to-
trim convention. With Cut Early.8 and Release Grab1, release occurs at the80%
endpoint. With both.8, release occurs at64% of the original clip, after entry blend.

At start, fit world yaw between the physical pelvis and the animation's frame-zero
pelvis. Rotate the clip about its initial pelvis pivot; preserve subsequent authored
turns. One startup fit and one root transform per sample, no continuous search.
Fresh editor animation compilation must finish before choosing that anchor:
`WaitOnExistingCompression()` is editor-only and called once at start. An initial
validity-only check was insufficient: projectionU returned a temporary reference
pose at startup and its actual authored frame zero later. Trace confirmed the two
quaternions differed. Final pending-compilation wait fixes the cold-load case.
No per-frame waits, no global loading flush, no cooked-runtime compression work.

Final runtime build4 actions/46.55s passed (reflected API build17 actions/457.92s).
Physical D/U/R/L entry-pose heading error relative to actual starting pelvis is
below.000004 degrees, versus roughly98-105 degrees in the original captures.
This measures accepted pose alignment, not physical motor tracking accuracy.
Final12-case suite passed, all three end events once per case. Physical projection
D/U/R/L, release0 immediate, release1 with Cut Early.8, release.8 with Cut Early.8,
four zero-blend heading cases at world yaw0/45/90/-135, and Cut Early1 full-duration.
D cut.8/release1 released and ended together87 ticks after start; both.8 released
at71 and ended87 (includes21-tick entry blend and publication quantization).
Current receipts: refined-results.json/refined-metrics.json. Final fixture has no
manual end-of-clip Release Grab calls; the node owns release timing.

## Location and preservation

Managed checkout: `C:/Users/singerie/.codex/worktrees/grab-special-attacks/Prophecy`.
Independent source/config/dependency copies and required assets, no links to live
asset/output folders. Main editor16632 and production source/assets untouched.
`Saved/SpecialAttacks/baseline.json` records the copied working baseline;
`implementation-manifest.json` and `implementation.patch` identify only this task's
24 changed/new source files. Main files still matched baseline when checked.
Do not merge the entire Git diff: it includes pre-existing user working changes.
Do not merge isolation DefaultEngine.ini (Entry startup map, remote scripting and
Python package auto-install disabled). No Live Coding used.

## Nodes and behavior

- **Grab Object / Grab Bone, Target Mode**: Follow remains the default. Both modes
  track the surface during acquisition. Root Local captures the acquired wrist
  target relative to the grabbing agent's actor/root. After a special attack it
  recaptures the current wrist instead of jumping to the pre-attack target.
- **Joint Independance**,0..1,default0:0 ordinary reciprocal joint,1 no reaction on
  the hand from this grip joint. Intermediate values scale only that constraint's
  hand inverse mass/inertia by1-value during effective-mass calculation, warm start,
  velocity solve and position correction. Actual body masses, contacts and other
  joints are unchanged. Native target motion type is rechecked each setup;
  non-dynamic targets get ordinary reciprocal behavior. Contacts can still push
  the agent normally. No global force or teleport is added.
- **Start Special Attack**: Agent, Animation(UAnimSequence), Blend Duration(default
  .2s), Cut Early(default0), boolean success. Uses the five existing clips in
  `/Game/_mygame/animations/special_attacks`. Smoothly blends from sampled physical
  pose to clip frame0, then plays the authored full-body motion. Timing uses60
  unpaused game ticks, not wall time. Cut Early0 plays all,.5 half,.8 80%,1 all.
  A30Hz publication boundary adds up to a few ticks before end notification.
- The clip owns the body while playing; reach pose output pauses, existing grip
  constraints and fingers remain. New reaching waits until special ownership ends.
  Accepted NN histories are seeded with the clip pose.
- Completion seeds existing FK return and dispatches upper-special-ended,
  lower-special-ended and ordinary attack-ended once. Existing Blueprint recovery
  wiring/tuning determines the return. Stop NN Attack also stops a special attack.
  Grips release automatically at Release Grab (default.8) or at an earlier interruption.

## Verification

Normal isolated build passed; final guard rebuild4 actions/81.40s. Editor-only
native fixture avoids copying/editing the user's Blueprint. Owned headless editor
uses `-nullrhi -nocef -DisablePlugins=Fab`; remote execution disabled.
Native test `Prophecy.Jolt.GenericJoint.GrabIndependence` passed with zero errors/
warnings:0,.25,.5,.75,1 linear/angular reaction; position/angular correction;
unchanged body mass; non-simulated targets; unrelated joint reaction.

Original pre-refinement scene cases (historical timing/release behavior) passed: projectionD/U/R/L with **two physical grips**, both
retained throughout, independence1; projectionU cuts.5 and1; sweepKick full.
Each emitted exactly one upper, lower and ordinary end event. Full physical clips
lasted102/92/106/106 ticks including.35s entry blend; U half57 ticks; U cut1 23 ticks.
Both agents used native Jolt physical rigs; recipient passive simulated.
The fixture releases grips at the end and uses existing lower-body tempering
controls for recovery. This is fixture tuning, not copied user Blueprint tuning.

Follow/Root Local comparison: move kinematic recipient20cm. Follow hands moved
20.49/20.90cm; Root Local drifted only.0117/.0037cm. This isolates target tracking
from physical servo/joint forces. No performance/FPS claim from NullRHI.

Lifecycle checks passed: explicit Stop NN Attack ended at the requested tick and
fired all three end notifications once, with no duplicates during120 recovery
ticks. Invalid Cut Early1.1 was rejected without interrupting playback. A new
reach request during the clip completed playback normally, then resumed reaching.
Final normal build covers the new-state suspension guard.

## Video and reproduction

`Saved/SpecialAttacks/projection-refined.mp4` is the current video: four projections
with automatic release. The earlier projection-demo.mp4 is historical. Both are
1280x720,30fps,about2MB.
Lab-rendered replay of **measured Unreal/Jolt bone transforms**, not a viewport
recording. Orange thrower; blue physical recipient. Acquisition, hold, each
projection, release and recovery. Preview frames visually inspected. No PNG
sequence retained.

Tools in isolated `Tools/SpecialAttacks`:
- `RunScene.py`: creates only `/Game/__SpecialAttackLab/locomotion`, native agents,
  isolated PIE and bounded measurements. Cases: `Saved/SpecialAttacks/cases.json`.
- `RenderVideo.cjs`: streams measured frames through existing lab renderer to
  ffmpeg. Current inputs: refined-D-0.json,refined-U-1.json,refined-R-2.json,refined-L-3.json.
  Repeatable cases: Tools/SpecialAttacks/cases-refined.json.

Evidence in isolated `Saved/SpecialAttacks`: JointTest/index.json,
projection-results.json, tracking-results.json, pose JSONs, manifest/patch and video.
Main `Tools/SpecialAttacks` contains inventory/isolation preparation only.
No production Blueprint wiring or asset modified. Deploy later with a normal
minimal build/restart: reflected APIs and retained state changed.

Disposable-file cleanup was rejected by automatic approval review ("blocked by
policy"). Partial isolated Intermediate/PipInstall, two small crash reports, old
trial captures/logs and preview checks remain. No deletion ran. Approximately9.8GiB
free after testing. All owned test/render processes exited; main editor16632 remains.
