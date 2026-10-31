# Bodyflip secondary motion and lossless hot paths

October 30, 2026. Scoped work for the throws/bodyflip aiming integration.

## Secondary motion

`spinLag` now defaults to 0.6 and the existing Spin lag widget defaults to 60%.
The response already consumed continuous changes in angular commands, not just
instantaneous changes. Smooth acceleration, braking and axis changes therefore
use the same articulated response without adding a second system. Explicit saved
zero remains off. Existing scene settings were not written.

The four arm/leg chains use the existing collider mass/inertia and hinge frames.
Critically damped offsets preserve COM and skeletal lengths; contact/follow solves
retain priority. The prescribed spin command is unchanged. The response remains
an artistic animation model driven by angular impulse, not a full free-body solver.

`verify-secondary-motion.mjs`: 1731 checks across three axes and 0.05/0.4/1 s ramps.
Peak visible displacement 1.26-4.56 cm at 60% response, COM error below 1.1e-15 m;
Jolt limits, exact angular command, inactive bypass and reverse seek pass.
`verify-instant-spin.mjs`: 3164 checks. `verify-spin.mjs`: 161 analytic checks;
the analytic suite explicitly disables secondary motion to isolate rigid spin.

## Lossless changes

- `spin-response.js`: cache each articulated inertia-vector product within its
  body impulse calculation; reuse across the 4x4 matrix. No accumulation reorder.
- `mass.js`: compute each body centre once for an inertia tensor, retaining the
  original COM summation order and tensor arithmetic.
- `target-rig.js`: foot clearance requests only the physical/render foot shapes
  for that side. It no longer builds the torso, head, arms and opposite leg merely
  to discard them in every clearance iteration.
- `body-contact.js`: one geometry list for a stationary resolve's before/after;
  platform AABB extents computed once per move. These are per-call values, not a
  cache that could become stale after platform/pose mutation.

No contact order, iteration counts, tolerance, time sample, solver or arithmetic
precision changed. No approximation, skipped collision, new gate or fixed cache
of mutable user geometry was introduced. Existing APIs remain compatible;
`BodyContact.create(...).footShapes(pose, side)` is the added selective helper.

## Evidence

`verify-spin-performance.mjs` compares against checkpoint 67516390 using the
actual former modules. 878 exact `JSON.stringify` comparisons pass for 24 varied
poses, flat/inclined/empty surfaces, complete target/body corrections, 100 impulses
and damped poses, and 362 smooth/instant full-spin samples. This requires that
checkpoint in local Git history. Run with `--benchmark` for the scoped timings.

`Saved/BodyflipLab/SpinPerformance/parity-performance.json` is the receipt.
The latest alternating four-repeat run (same JS realm) measured 192 full projections
per repeat: old median 163.9 ms, new 148.1 ms (~9.7% reduction). Full 3 s/180-sample spin
median 318.8 ms before and 319.0 ms after: no demonstrated aggregate spin speedup in
that run. Shared-laptop variance overlaps, so these are scoped measurements,
not total FPS or a promised global speedup. Earlier isolated VM timings were
biased by realm boundaries and are not used as evidence.

Live Bodyflip state, desktop, Unreal and persistent processes were untouched.
Native port may use the same formulas; the optimized mass/response math is exact.

## Native simulated drive audit and correction

The existing native `MagnetizationMode=0` was not the lab controller. It changed
the target reference to the physical parent, but still corrected each child's
position and approximated COM carry with `angular velocity cross COM offset`.
The lab only position-tracks the pelvis. Each child receives an angular command
plus its parent's COM velocity adjusted by the finite displacement of both joint
anchors during the step.

The active Bodyflip publication now opts into `bFiniteJointCarry`, with root
world tracking and child local angular tracking, both at full velocity strength.
`ProphecyBodyflipDrive.h` is an effective profile; it never writes saved agent
magnetization settings. Follow weights, target offsets and optional arm velocity
motors are bypassed while this profile is active and remain available afterward.
Foot/forearm positional presentation corrections are likewise bypassed for this
authored Bodyflip packet. Existing body simulation exclusions remain respected.

`PublishRigVelocityTargets` obtains the native constraint's COM-space anchors,
using actual body IDs to handle either PHAT/native ordering. Missing connections
or missing parent commands fail publication instead of guessing a skeleton pivot.
Angular trajectories interpolate each joint's local rotation; the parent's actual
commanded endpoint supplies the child's reference. The pelvis COM command uses
its rotated finite endpoint, and children preserve the prior anchor separation
without another absolute or relative position servo. Native body velocity caps
remain in force. Gravity cancellation is inherited once; differing existing body
gravity flags are accounted for without changing those flags.

Native checks and current verification state:

- `Prophecy.Jolt.Servo.FiniteJointCarry`: three-body chain, large rotations,
  nonzero COM offsets, deliberately wrong child positions, displaced joints,
  trajectory interpolation, reversed packet order, and ignored saved follow /
  offset overlays. Passed in `native-tests-2.log`.
- `Prophecy.Jolt.RigWorld.FiniteJointCarryAnchors`: real prepared native PHAT
  constraints in both body orderings, COM-adjusted anchors, atomic missing-parent
  rejection, and ordinary drive publication after the flag clears. Passed in
  `native-tests-4.log` after a normal rebuild corrected the earlier stale object.

The same native run passes projectile geometry/recorded seeking and fractional
release. Its approved-scene test fails before motion preparation: the first
five-second native NN rollout takes 362.003 seconds, versus a 120-second planner
deadline. Script peak memory is only 68.8 MiB at that point. A process-local
single-thread inference diagnostic and native cancellation instrumentation are
in progress; full-agent physical tracking remains unverified.

The parent ran owned headless native tests after a normal build; no desktop or
live scene was changed. Passing command-level tests will not alone establish full-agent contact
parity: the native floor/platform collision geometry, captured PHAT bodies and
step scheduling must also match the comparison. Authored time remains 60 Hz.

## Native hand-push preparation profile — October 30

The native paired-hand fixture is substantially more expensive to prepare than
the other V8 fixtures: 38.69 native CPU seconds for its 1.2-second motion. This is
planning cost, not measured playback FPS. Its contact at 0.366667 s, push at
0.395833 s and independent hand releases remain unchanged.

One bounded Node CPU profile (384 MiB old-space, 8 MiB semi-space) reproduces all
eight saved complete frames exactly. It attributes 22.6% inclusive sampled CPU to
native wrist aiming, 35.6% to the nested hand contact/reach evaluation, and 15.3%
to garbage collection. Inclusive percentages overlap and must not be summed.
Receipts and original sources are retained under
`Saved/Diagnostics/BodyflipPort20261030/v8-parity/hand-profile/`; the CPU profile is
the adjacent `native-hands.cpuprofile`.

The native wrist search now prepares its fixed twist quaternion, inverse joint
frame and limit radii once per search. Every trial, ternary-search iteration,
ellipse projection, normalization and quaternion multiplication keeps the same
arithmetic order. Its opposite normal and palm axis are also reused. Default
lab wrist aiming is unchanged; ordinary joint-coordinate calls keep their
existing path. No motion parameter, tolerance or iteration count changed.

`Tools/Bodyflip/verify-hand-push-performance.mjs` checks the retained former
sources against the candidate without modifying the packaged runtime:

- 12,288 complete joint/wrist results match exactly, including default and native
  profiles, both hands, locked swing axes, outside-limit inputs and zero weights.
  Maximum wrist limit residual is 1.94e-12 rad, identical to the original.
- All eight saved native paired-hand frames, including event/contact metadata,
  match exactly. The official Runtime.js hash remains unchanged.
- Across 960 native palm solves, quaternion exponentials fall from 58,560 to 960
  and inversions from 61,440 to 3,840. The scoped measured time is 247 to 115 ms.
- The full candidate requires 62.73 CPU seconds / 76.43 wall seconds, with
  181.5 MiB process peak. An aggregate speedup is not established: the earlier
  unprofiled original used different heap settings, while the new original
  profile includes sampling overhead. The isolated timing is not a whole-motion
  performance claim.

The narrow optimization is accepted and packaged as
`0af4a8b4c140838fe4edd1d8cd51e950410d0f416a4b7970c4a09adb19c2d14d`.
The native owner replayed all eight complete frames / 1,740 numbers exactly under
an enforced 384 MiB Windows process-commit cap. Receipt:
`hand-profile/accepted-wrist-v8-receipt.json`. CPU time was 40.42 s, wall time 136.66 s;
peak commit was 380.36 MiB. The earlier V8 probe was not actually capped by its
environment variables, so this is not a matched aggregate-speed comparison.
No additional full-fixture timing is requested while the laptop is paging.
Native build/agent validation remains a separate outstanding requirement.

The next contact-planning candidate prepares the unchanged pose's local joints
once for each contact fit, copying the q/p arrays before every IK trial. Crouch
weight reads only the pelvis translation when there is no prepared pose. In
paired root projection, contact rows are reused until any root correction,
which immediately invalidates them. Both changes retain iteration order,
thresholds, all corrections and final FK arithmetic.

Focused former/candidate comparisons pass 384 complete IK/contact outputs and
25 complete bounce trajectories with 96 existing paired-contact assertions.
Frozen input arrays verify that IK cannot mutate the shared prepared pose.
Measured evaluation counts fall from 2,557 to 689 localizations and from 3,533 to
1,626 paired constraint queries. These are work counts, not timing claims.
Original files and `contact-focused-summary.json` are beside the wrist receipts;
the repeat tool is `Tools/Bodyflip/verify-hand-contact-performance.mjs`.
The complete eight-frame hand-motion replay also matches exactly. The process
was assigned to a Windows Job before its first instruction, enforcing a
384 MiB commit cap with a 190-second timeout. Peak commit was 163.1 MiB; the
motion replay used 60.22 CPU seconds / 147.34 wall seconds, and the whole runner
finished in 171.86 seconds. No aggregate speedup is established under this
paging/heap configuration. Receipts: `contact-full-summary.json` and
`contact-process-cap.json`. `Tools/Bodyflip/run-limited-process.py` retains the
generic cap mechanism rather than relying on environment variables.

The optional prepared-pose argument follows the approach adapter's existing
time/progress arguments; those numeric inputs retain their meaning. The accepted
source is packaged as
`626c70e2219a62ae9fd3f82c6bcee397281e88f2aa7e1c1f1d5e82488d2bb2fc`.
A single native V8 replay then matched all eight complete hand frames / 1,740
numeric values exactly against the preserved original oracle. It enforced a
384 MiB Windows process-commit cap before process execution; peak commitment
was 365.14 MiB and peak working set 369.64 MiB. CPU time was 32.80 seconds and
wall time 109.61 seconds during paging. Receipt: `hand-profile/accepted-v8-receipt.json`.
The earlier wrist-only capped receipt and original 64-frame cohort are retained.
These runs do not establish native gameplay frame time or completion of the
approved longer scene. This optimization changed no user scene or native C++.
