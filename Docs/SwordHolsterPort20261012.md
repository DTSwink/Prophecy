# D/S native parity port — October 12, 2026

Status: native feature port implemented and numerically verified. Full-motion
parity and physical limitations are explicit below; no visual approval is claimed.

## Preserved baseline

- User requested a Git checkpoint first, then the latest lab behavior and values
  in Unreal, except lab holster stabilization.
- Pushed `e0da908c53df3a76e5d06503b9a44868d0a54d7d` to
  `origin/codex/standalone-sim`; remote SHA verified. Includes saved lab tuning,
  lab/scripts and freshly saved PoseAgent Blueprint.
- Frozen live and disk lab settings agree; originals, graph and asset hashes
  are in `Saved/Diagnostics/SwordPort20261012/`. No user Play or dirty assets.
- D reach/rotation/slide: 260 cm/s, 900 deg/s, 250 cm/s. S: 230, 600, 150.
  Compensation .96, entry inertia 1/.5s, shrink 15%, unshrink .5s.
- Holster stabilization .32 is explicitly excluded from native configuration.
  Native geometry continues to read the actual physical holster.

## Implementation decisions

1. Export runtime configuration using `Tools/SwordHolster/SyncLabProfile.cjs`.
   Both action profiles remain independent. Include the lab's neutral body
   reference quaternions, so offsets refer to the same neutral pose in Unreal.
   Exclude lab timeline, animation choice, preview gaze and holster placement.
2. A configured lab profile supplies per-action speeds and shrink settings;
   existing Blueprint nodes/wiring remain intact. Unconfigured calls retain
   their speed pins. No new reflected nodes or per-agent idle update.
3. Replace automatic shoulder-distance fitting with authored spine and both
   clavicle endpoints. Capture spine/right-arm locals at entry, compensate
   pelvis rotation on the whole chain, and retain live left-arm local motion.
   Keep current pelvis translation. Existing early FK return remains active.
4. Carry the elbow preference in the moving spine/arm frame, optionally
   transferring its reference to the sword during sliding. Reach preference
   uses the available reach duration with angular speed as an upper bound.
5. Use the lab palm-in roll about the blade axis at the holster mouth. Rebuild
   from the original captured reference on each action, avoiding repeated roll.
6. Reuse the existing parent-local inertia envelope at entry, including the
   spine and both arms through the hands. Seed incoming velocity from the NN
   snapshot at action admission, avoiding recurring idle history work.
7. Add drawing's hand rotation and positional offset to the existing FK-return
   inertia evaluator. No separate hand-return solver or timer.
8. Preserve the tick clock, crowd admission/refit scheduling, sparse arm guides,
   physical attachment, collision/limit restoration and cancellation paths.
9. Retained profile/controller layouts changed. One normal shutdown/build/reopen
   is required; Live Coding is unsafe for this batch. The first build dispatch
   arrived before shutdown completed and was rejected by UBT. Waited for the
   process to exit before retrying; no force-kill or stale DLL launch.

## Verification plan

- Independent lab numerical oracles for authored body targets, compensation,
  pole transport/rate, and entry inertia, then recorded idle/walk/run lifecycles.
- Existing frozen head, return, bone-order, timing and scheduling regressions.
  Historical optimizer fixtures explicitly retain the old optimizer contract.
- Actual owned PIE: kinematic first, then simulation; idle, correct WalkF
  (run checkpoint/input .4), run, both actions and repeated cycles.
- Preserve graph/assets; verify reflection, completion, finite poses, ownership,
  joint count, physical lag and abrupt bone changes numerically.
- Measure active-controller cost after correctness, distinguishing it from
  whole-game inference/physics and diagnostic overhead.

## Findings during verification

- Body, pole and entry-inertia primitive comparisons agree with the lab within
  0.000005 degrees and 0.000001 cm. These are primitive tests, not a claim of
  whole-motion parity. Recorded idle/walk/run actions all finish; larger moving
  arm differences remain under investigation.
- Preserved the lab's conservative reach deadline: its first planning pass uses
  the partially turned torso. Replanning only from the final torso made entry
  too fast. Idle/walk deadlines now match; recorded run differs by one tick.
- Slide guides must start from the arm before the elbow preference is applied.
  Feeding the corrected arm back into the guide solver accumulated twist.
  Corrected this and the duplicate preference application during early return.
- Real walking/running captures initially stalled even in kinematic mode. The
  actor turned roughly 48 degrees after action entry, but compensation froze the
  torso against that character turn. The lab operates in imported mesh space.
  Native compensation now removes pelvis gait inside the moving character mesh
  frame, preserving character heading. A rigid-transform invariance regression
  covers all compensation values. This required another retained-state build.
- Reach destination updates must likewise solve from the captured entry arm,
  as the lab does, rather than repeatedly using the previous solution. This
  avoids accumulating axial arm rotation as locomotion moves the target.
- Corrected the owned-PIE harness to use the run checkpoint with movement input
  length .4 for walking, disable the Blueprint debug overrides only in that
  owned world, and avoid retaining a deleted equipment object during delayed
  starts. No Blueprint wiring or asset tuning was changed by these tests.
- Normal builds and the earlier 13-test regression passed. Latest fixes still
  require rerunning the numerical and live matrix; simulation verification and
  final performance results are pending. Low drive space dialogs can block the
  interactive editor; the user dismissed the first one. Computer Use failed to
  initialize with kernel-assets OS error 3.

## Live results after character-frame correction

`frame-fixed/` and `frame-sim/` each contain idle/walk/run S→D with three agents:
18 complete sequences total, no missed ticks, fixed 1/60 simulation delta,
finite transforms. The previous locomotion stalls no longer reproduce.
Simulation maximum physical hand lag: idle .42cm, walking 3.01cm, running
6.58cm; this measures physical tracking, not target-path parity.

Completion exposed another issue: one kinematic walking case has a 124.51deg
upper-arm local rotation step at slide entry; running has an 84.62deg wrist
local step at the same transition. Both arms were near straight before entry.
The corresponding simulation cases complete with smaller steps, but this is
still an unresolved target-generation issue, not a smoothness pass. Added
on-demand source/guide/pole fields to the existing pose diagnostic to identify
the cause. No continuous diagnostic overhead or added controller state.

The captured-entry reach seed reduced the recorded run-S maximum discrepancy
from 162.49deg to 37.03deg (walk-S 75.72→16.52deg). Pole scalar and basis stayed
close throughout, so the prior accumulation was arm axial orientation rather
than a pole target speed error. Remaining online-versus-recorded path differences
must be distinguished from the abrupt slide-entry defect.

## Shared solver corrections

The captured walking transition isolated the first flip: pre-pole guide rotation
was only 8.58deg, but projecting the old elbow onto the new target line made the
final swivel 124.59deg. Transporting the whole seed arm plane toward the new
wrist direction before bending reduces the same captured transition to 9.44deg,
preserves segment lengths and the wrist target, and needs no history or knob.
Applied to the lab and authored native solver; legacy optimizer tests retain
their historical solve. Saved values are untouched. Three captured regression
cases pass. Live idle/walk/run confirms the original flip is removed.

An extended transition case then exposed a second issue: the sword-relative
reference projection itself can spin near its undefined direction during early
return (78.67deg local wrist step, actually an arm swivel while the world wrist
rotates only .39deg). The existing pole speed is now a shared budget for scalar
preference pursuit and reference adjustment around the transported arm axis.
This preserves the user's moving-frame interpretation and adds no persistent
state. Both implementations use the same rule; sampling uses the prepared frame
rather than bypassing its bound. Synthetic 60/240Hz and 0/5/180deg/s checks pass.
The final motion matrix below covers this change.

All 11 lifecycle cases passed after the plane-transport correction: completion,
custom limits, hide in reach/slide/return, drop, mode switch, sword destruction,
drawing interruption, pause, and repeated sim/kinematic cycles. Exact saved neck
limits restore and temporary joints clean up. The 13-case extended motion matrix
also completed, including 20FPS, turning, changing gaze and extreme gaze.
These are completion/cleanup results, not a claim that every physical step is
smooth: +.95 gaze releases an already constrained physical head at admission,
with up to29.96deg world rotation versus6.88deg in its commanded pose.

Three older lab tests fail identically against the untouched Git checkpoint:
`test_armfk` assumes no pole overlay, `test_motion_clock` assumes no entry inertia
on the left arm, and `test_slide_rotation_clock` assumes live rather than captured
arm lengths. They are not counted as passes. Current entry/compensation/hand,
pole-arrival, early-return, sequence and head-clock regressions pass; final
pole-budget reruns are underway.

## Final verification and remaining differences

- Final `bounded-final/` matrix: 13 cases × 3 agents = 39 complete S→D sequences,
  including kinematic/sim idle/walk/run, transitions, turns, changing gaze,
  extreme gaze and 20FPS. No missing ticks/nonfinite transforms; world delta
  remains 1/60. Matched run20/run60 captures agree exactly for 267 shared ticks,
  including commanded/physical poses, equipment and phase changes.
- All 11 lifecycle tests pass. Added reset during sliding also passes with exact
  restored limits and no temporary joint. Its first harness assertion was wrong:
  Reset is queued to a manager timer boundary, unlike synchronous Hide. Corrected
  the harness to check after that boundary; no reset runtime change was needed.
- Native authored oracle passes: 54 body cases, six pole tracks, six inertia
  tracks, three captured straight-arm regressions and six complete recorded
  motions. Primitive maxima: 0.000004183deg and 0.000000001cm.
- The reference-speed change exposed a lab-only sampling defect: early-return
  playback reapplied the pre-return reference instead of its prepared grip
  reference, seeding an artificial return spin. Grip guides now retain their
  own reference, interpolated between samples. Running-S release regression
  drops from >100deg/tick to4.294deg/tick. Native already follows its active
  return reference; no extra native state or patch was required for this repair.
- Latest lab early-return48 cases, both-order sequence12 cases, head-clock,
  entry inertia, pole-arrival36 cases, straight-arm and reference-speed tests
  pass. New `test_return_pole_reference.cjs` freezes the running release case.
  The three historical baseline failures listed above remain explicitly excluded.
- Five recorded reach/slide-entry deadlines match the lab exactly: idleD29/S56,
  walkD32/S57, runD23. RunS is45 native versus44 lab. D slide19ticks and S31ticks
  agree. The lab can plan against future clip poses; native refits against live
  holster/NN geometry. Full-pose maximum residuals: idleD9.05deg/3.00cm,
  idleS4.10deg/1.41cm, walkD10.04deg/3.39cm, walkS13.32deg/6.95cm,
  runD6.96deg/2.92cm, runS25.70deg/10.76cm. These are **not** bitwise whole-motion
  parity. The former 169deg return divergence is gone; the receipt checks that
  no opposite-winding (>90deg) mismatch reappears in these fixtures.
- The original live walking slide-entry125deg flip is removed. The extended
  early-return78.67deg spike is16.93deg with the same fixture. Rapid bending and
  inherited NN/entry velocity still contribute to arm speed; no extra smoothing
  layer or arbitrary tuning change was introduced.
- Extreme+.95 gaze retains a physical admission kick (up to29.96deg world head
  step in the tested case) when already-stressed neck limits become Free. The
  commanded head does not contain that kick. User neck/motor settings and the
  authorized restore policy are preserved; this remains a physical limitation.

## Performance

Seven warmed repeats per motion/action, 100 simultaneous controllers, **without
staggering** in the benchmark. Median mean tick0.529–0.605ms; median per-run peak
1.435–1.545ms; worst observed peak3.873ms. Initial planning plus inertia seed
math for all100 is2.132–3.378ms (21.3–33.8µs/agent). Individual recorded active
steps average4.72–6.11µs in the final run. See the CSV/receipt for every case.

Scope: pose copies, planning, body/arm/head/pole, entry inertia and FK return.
Excludes configuration JSON loading, live NN/snapshot reads, cache publication,
equipment, physics and rendering. This is not a whole-game FPS benchmark.
The existing four-slot admission/refit scheduler remains in gameplay. No idle
tracking, pose bank or extra physics scan was added; diagnostics are on demand.

## Final save/build state

Current normal DLL contains the initial authored/frame/reach port. Subsequent
layout-safe Live Coding patches contain plane transport, pole budgeting and
diagnostics/tests; compile and reload succeeded. **Normal DLL is stale: build
before any cold launch.** Editor PID2736 remains open on TestNN with latest code,
Play stopped. Final postflight confirms exact Blueprint graph, unchanged map/BP/
sword hashes, reflection status3 and no dirty packages. Saved lab tuning is
unchanged; Ctrl+R loads the shared solver corrections. The initial checkpoint
is `e0da908`; final source/test/doc commit is recorded in Git. Compact evidence:
`Tools/SwordHolster/Port20261012.json`; full captures remain under the Saved path.
