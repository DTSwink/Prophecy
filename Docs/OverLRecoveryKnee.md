# OverL recovery knee diagnosis — 2026-09-21

The current scene reproduces an inward right-knee snap when the first overL ends
at game tick127. It is already present in the kinematic NN target. The displayed
target, physical-body readback and visible mesh agree; this is not contact wobble.

The right thigh direction changes22.075 degrees over the two displayed exit
frames (10.983 and11.092 degrees). Raw NN direction changes5.537 degrees. All
three regional gait weights remain Walk=1, so no Run/Walk transition occurs.

The exact reconstruction replay separates the cause:

| First right-leg recovery stage | Full thigh orientation change |
| --- | --- |
| Raw NN relative to previous | 5.81 degrees |
| Connected-chain reconstruction relative to previous | 4.62 degrees |
| Additional knee guidance around hip-to-ankle axis | 47.37 degrees |
| Final published relative to previous | 49.73 degrees |

Full orientation includes twist and is different from knee-point direction.
The guidance alone moves the knee14.89cm. It forces the knee into the vertical
foot-forward plane through the hip, instantly removing13.485cm of lateral knee
offset from this wide stance. The constraint is an additional kick-recovery
heuristic, not a requirement for a connected leg or an anatomical knee hinge.
The first source bend is well defined (16.8cm radius), guidance strength is1,
and its angle is far from180 degrees: no singularity or branch flip is involved.

Six overL recoveries reproduce the geometry-dependent behavior: odd exits127,
307 and487 receive roughly46–47 degrees of additional guidance; the other exits
have an infeasible plane and skip it. Replay error across all six recoveries is
below0.000135 degrees.

Two temporary Play comparisons isolate the cause. Disabling support-source
handover preserves the same initial knee snap (positions agree within0.000011cm).
Disabling reconstruction reduces the first right-knee steps to2.616/2.768 degrees,
but also removes required connected-chain corrections and is not the chosen fix.
No Blueprint/map changes or saves were made.

Baseline evidence: `Saved/Diagnostics/PelvisHitch-20260921-172254`.
Support-source comparison: `PelvisHitch-20260921-172452`.
No-reconstruction comparison: `PelvisHitch-20260921-172528`.
Analysis: `Saved/Diagnostics/OverL/CompareCaptures.py`, `CaptureComparison.json`,
`ReplayOverLSolver.py`, `all-overl-stage-replay.json`, `kick-stage-replay.json`.

## Discarded family-specific trial

An experimental tempered return after a non-kick attack used connected hinge
reconstruction without forcing the additional kick knee plane. Endpoint reach,
the15cm inner safeguard, floor handling, foot rotation and near-floor source
handover remain. Kick returns keep their previous guidance expression unchanged.

The trial scope was established after On Attack Ended configured tempering. It was
removed when tempering finishes/is disabled, a new special begins, reset occurs,
or the world/agent is removed. An all-one return creates no entry. Gait blending
can finish earlier without prematurely ending this scope. No new duration,
timer, inference or normal-locomotion pose work is added. Existing live struct
layouts and Blueprint signatures are unchanged.

The first experimental patch loaded15:36:08UTC. A1080-game-frame capture with11
overL returns retained connected calves (active published length error below
0.000017cm) and reduced the initial right-knee steps from10.983/11.092 degrees
to1.523/1.636. Maximum right knee-direction step across the recovery intervals
was5.820 degrees/frame versus11.092 in baseline; full thigh orientation maximum
fell24.866 to10.053. Retirement also improved; repeated cycles settled into
alternating motion without accumulating drift. These measurements apply to the
captured setup, not all possible poses/checkpoints.

A separate experiment multiplied the extra guidance by Feet Rotation. It also
softened the initial snap but retained the unwanted stance-plane correction and
had a larger late full-thigh step than the connected-only candidate. It was not
retained. A negative knee pole relative to foot heading alone is not sufficient
to diagnose anatomical backward bending; the final hinge audit is recorded below.

Candidate evidence: `PelvisHitch-20260921-173625` (360 frames),
`PelvisHitch-20260921-173819` (1080 frames),
`OverL/AnalyzeRecovery.py`, `FullRecoveryComparison.json`.
Discarded weighted-guidance comparison: `PelvisHitch-20260921-173739`.

Runtime kick regression used two disposable360-frame sessions, replacing each
automatic overL trigger with kickR without editing/saving the Blueprint. With
the old/new non-kick switch, all179 lower/upper input/output and published-pose
samples matched exactly. Evidence: `PelvisHitch-20260921-173856`,
`PelvisHitch-20260921-173928`, `OverL/kick-runtime-comparison.json`.
This verifies that the new recovery scope does not leak into kick execution.

The user explicitly rejected attack-family gating. All of that runtime context,
event integration and family selection have been removed from source; the loaded
trial was disabled immediately through its comparison switch. The measurements
above establish the diagnosis and record an experiment, not the final solution.

The signed authored-hinge audit did not find a new anatomical bend reversal in
that trial. Negative foot-relative pole headings occurred while toes were nearly
vertical and also appeared in the NN source. They were not equivalent to a
backward knee. Evidence: `OverL/SignedHinge-*.json`.

## Current geometry-only correction

The new candidate carries the coherent source knee's lateral offset in its own
foot-forward frame, rather than forcing that offset to zero. It uses the same
source policy for every pose: previous coherent source for raised feet; existing
near-floor source handover toward the NN, with its residual following the Feet
Rotation control. The knee-circle equation becomes
`Q = (source lateral offset - Along * SideAlong) / (Radius * NLength)`.
The existing reach, floor and feasibility handling remain. Both valid circle
solutions are considered: use the branch nearest the transported coherent hinge,
with vanishing guidance at a branch tie. When a source toe approaches vertical,
blend its unobservable horizontal heading back toward the transported hinge.
There is no attack-name check, recovery flag, new timer or added actor state.

The first global version reduced the first overL right-knee direction steps from
10.983/11.092 to1.369/1.515 degrees. Six kick returns kept monotonic raised-foot
descent; knee-side offset stayed small rather than growing. The user subsequently
confirmed kicks good and overL much better. This is not bit-identical to the old
kick path: recurrence can change subsequent grounded walking by several centimetres.
Four new geometry checks passed: identity on both coherent branches, captured
wide-stance regression, raised-source isolation and near-vertical degeneracy.
Six other focused timing/pose/extension checks passed. RootLocalPinAndChain still
reports the two previously documented legacy expectations; they were not suppressed.

## Remaining calf snap — confirmed separately

Capture `PelvisHitch-20260921-181133` separates the calf snap from the knee fix.
At the first overL exit127, displayed left/right calf orientation changes
30.767/31.408 degrees in one frame, but calf-axis swing is only2.264/2.963 degrees.
The actual outgoing calf-to-foot length excess is0.200/0.789cm. Later exits have
up to54.31-degree calf orientation steps. The dominant discontinuity is twist.

Attack decoding uses the checkpoint's projected-pole calf frame; normal locomotion
uses the signed-hinge calf frame. The reduced lower state stores thigh and foot
rotation, but no calf twist. Re-decoding the outgoing attack state as the previous
locomotion sample discards that twist immediately, before interpolation. Kick
extension smoothing only controls axial ankle leeway and cannot fix this.

A targeted continuity correction is now loaded: retain the actual preceding
published calf rotation, swing it onto the new calf axis, then follow the decoded
twist with the existing Feet Rotation tempering value. Knee/foot positions, foot
rotation, lower recurrence and kick extension remain unchanged. Same-source-time
republishing uses the preceding sample again rather than advancing smoothing.
No attack-family selection, extra duration, timer or persistent state is added.

Final Live Coding patch13 loaded16:19:12UTC. Six-overL600-frame capture
`PelvisHitch-20260921-182134` reduces the initial left/right calf steps to
2.80/3.31degrees; all six initial returns stay between2.42 and3.79degrees.
Lower/upper NN inputs and outputs, published lower states, pelvis positions and
knee paths are exactly equal to baseline. Foot future targets and rotations are
unchanged; interpolated calf clamping changes visible feet by at most0.046cm.
The small axial gap still closes under existing reconstruction/clamp rules;
this change addresses the independently measured large twist discontinuity.

Kick A/B uses the same final global knee implementation, toggling only the
editor calf-continuity switch. Captures `PelvisHitch-20260921-182013` (off) and
`PelvisHitch-20260921-182050` (on),600frames/six returns each, have exactly equal
NN inputs/outputs, published lower states, pelvis/knee paths and foot future
targets. Interpolated-foot change peaks at0.225cm. Existing kick-extension values
still decay on their previous schedule. Calf twist is deliberately different;
do not describe the entire displayed kick as bit-identical.

CalfTwistContinuity passed (exact calf aim, continuous twist following,
identity/normal endpoints and monotonic repeated convergence). Eleven of twelve
focused tests passed; RootLocalPinAndChain retains its same two documented legacy
failures. No assertions were removed. No Blueprint/map edits, asset saves,
editor restart or training changes. Comparison CVar, editor only:
`Prophecy.Tempering.CalfContinuity 0` disables this correction;1 is the default.
Normal/inactive tempering performs no new calf quaternion or pose-blend work.
