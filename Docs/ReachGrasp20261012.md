# Reach and grasp work — October 12


## Explicit elbow posture and PHAT twist — October16 current

**Explicit elbow posture / wrist twist — October16 current:** user reproduced a
full circle by setting Elbow down blend to0, then accepted the corrected lab and
explicitly requested its Unreal port. The earlier version7 case-specific fix was
insufficient: it inferred the bend from an admissible straight forearm (undefined
pole), ignored the blend in grab planning, then froze the inward result on grip.
Exact current-fixture replay reproduces224/363deg left/right total swivel and the
left inward pose. The replacement keeps three responsibilities separate: cached
forearm reach extent for body assistance; explicit outward/down elbow pole at the
actual wrist goal; axial wrist twist within PHAT. Blend updates approach AND held
posture. It never derives a bend from a straight forearm or changes it because
the hand happens to acquire grip. Transport and existing8deg swivel/4deg twist
caps remain. PHAT, contacts, fingers, speed settings and8/6deg gates unchanged.

Wrist twist solves feasible scalar intervals using polynomial boundary roots
(degree<=4), choosing the closest previous twist; already-feasible twists use a
fast path. No repeated elbow candidate search or stall/recovery strategy. The old
straight extent planner remains ONLY for body demand; using the bent posture for
that demand produced positive-feedback lean and was rejected. Cache version8;
Refresh migrates old poses/grips without resetting them. A formerly inward held
elbow can need a bounded near-half-turn to recover its outward posture.

Lab evidence `Saved/Diagnostics/ReachElbowDesign20261016/`: five blend values0..1,
live changes during approach/holding, current held resume,20/50cm dragging and
three prior recordings. Current blend0 grabs58/62, swivel44.49/69.97deg; final
left/right elbow outward, wrist error<.001deg and distance<.001cm. Increasing blend
lowers both elbows monotonically. Exact old circling recording now grabs142/145,
swivel8.01/25.89deg. Bone/PHAT errors at floating-point precision; max swivel8deg.
`Labs/ReachLab/test_elbow.cjs` and `test_wrist_twist.cjs` (720 known-feasible twist
cases including reversed frames, limited/free/locked axes) are current checks.
Do not overclaim all historical snapshots: frozen Stalled_250 retains its existing
left attachment but its requested left rotation remains27.28deg away; extreme
50cm sweeps still exceed reach and retain body-assistance residue. TestNN recorded
now acquires119/89 with final0/.64deg. These are separate from the accepted current
fixture. No user Refresh, reset, settings overwrite or lab service restart.

**Unreal port/build state — user-requested grab behavior restoration:** user rejected
the previous hold change because the balls stopped moving freely and appeared
fixed to the hands; explicitly requested "restore whatever was happening before".
Restore the exact pre-feedback behavior: GrabTarget reads the object's moving
surface/orientation on every tick, including after acquisition; coupled palm
anchor follows that surface; fixed joint captures the actual physical wrist.
The accepted explicit elbow/wrist solver remains unchanged. PHAT, gates, fingers,
body assistance, speeds, Blueprint wiring and ball settings remain unchanged.

Native implementation matches `ReachGripFeedback20261016/ProphecyReachLibrary-before.cpp`
exactly except one unused HoldTarget member retained to preserve loaded private
layout and permit Live Coding without an editor restart. Do not remove it through
Live Coding. Ordinary lab grips again capture the achieved wrist; the alternative
requested-frame attachment is retained only inside the historical feedback test.
No user lab Refresh, reset, persisted-state overwrite or service restart.

Live Coding rollback loaded successfully:269.17s,one C++ compile,patch0,
no object changes. Owned physical TestNN check through220 acquired grips
left120/right89 and retained both. Full commanded-pose trajectory matches
the pre-feedback recording exactly (0cm maximum difference); held targets
move11.88/51.88cm, confirming ball-following motion is restored.
Editor11912 remains TestNN/outside Play,
dirty[], full graph byte-identical and map/BP/PHAT hashes unchanged. No saves.
**Normal DLLs are stale: incremental normal build before the next cold launch.**

This intentionally restores the earlier feedback behavior too; physical elbow
circling is NOT considered fixed by the rejected hold change. Do not reintroduce
the agent-relative held target without a new user request. The previous lab
snapshots `UE_Grip_Feedback_Before`/`UE_Grip_Feedback` and physical receipts remain
historical comparison evidence: holding the authored command removed drift but
changed the requested behavior. Earlier native-final through720 and blend480
results describe that rejected version, not the current one. Evidence for the
rollback: `Saved/Diagnostics/ReachGripRestore20261016/`.

## Historical approach and held-elbow Unreal port — superseded

User explicitly requested loading the accepted lab behavior in UE. Native
`ProphecyReachArm.h` now follows the cached approach hint immediately, transports
the old elbow plane to the new shoulder/wrist axis, and stops approach swivelling
once the actual grip is acquired. The bounded twist/flexion and PHAT projection
remain active. `ArmFirstTarget` reuses static plans despite shoulder movement;
target changes transport/reverse-project the route instead of searching again.
Changed PHAT frames/limits invalidate the plan. No speed, gate, contact, finger,
body-assistance or Blueprint changes. Retained state layout is unchanged; hint
and held inputs exist only on the solve stack, so Live Coding is safe.

One C++ unit compiled in146.06s; patch3 loaded with no object changes. Editor16368
stayed open in TestNN. Normal DLLs are stale: incremental build before any cold
launch. Numerical probe expanded to600 cases across approach, held, target
tracking, free and locked limits. Arm position error7.1e-14cm, output quaternion
error3.4e-16; evaluation counts match, at most two wrist projections/hand/tick.
Equivalent initial planner axial-roll ties can differ by11.25deg; direction
endpoint error<4e-6cm. This is reported separately, not exact planner quaternion
parity. Moving-target transport is included in the comparison.

Actual unmodified TestNN acquires physical grips left112/right87 (lab111/86),
both retained through360, final wrist target distance0.360/0.325cm. Owned physical
right-ball20cm vertical sweep through720 retains both joints; max held-plane
swivel8.7e-12deg over361 samples, wrist violation4.5e-16, length error3.6e-14cm.
Final wrist distance0.235/0.225cm. The new physical ball feedback differs from the
old lab recording: left-elbow max movement200-300 is1.219cm, not the lab's0.0259cm.
Do not conflate that position movement with bend-plane reversals.

Remaining edge cases were kept visible: switching the original scene to Kinematic
before its tick30 fixture did not acquire grips despite terminal commanded arrival;
the controlled legacy auto-contact Kinematic fixture (sync=.82) acquires left but
right remains1.949cm short at690. Exact one-step terminal replay through current
lab code matches the latter position within5.2e-14cm, demonstrating the same
remaining arm-solver limitation in the lab. No acceptance tolerances were changed
to hide either result. This port verifies the current physical TestNN scenario
and held-plane continuity, not successful acquisition for every target.

Final editor16368 remains TestNN/outside Play/no dirty packages. Full Blueprint
graph byte-identical; TestNN, PoseAgent and PHAT SHA256 unchanged. Owned sessions
ended; user lab/window/service untouched. Evidence and rerunnable scripts in
`Saved/Diagnostics/ReachHeldPort20261016/` (`testnn.json`, `held.json`,
`verification.json`, `native-parity.json`, `held-kin-initial.json`,
`held-smoke.json`, `kin-lab-replay.json`, `final-editor.json`).

## Held-target elbow continuity - October16 current

The captured live setup at8960 has both grips, Auto palm contact,250cm/s reach,
1000deg/s rotation,7.5cm balls and recorded PHAT. TestNN input playback ended at360;
there is no live Unreal connection. This regression was in the shared lab solver.

Projecting the previous elbow against the new shoulder/wrist axis can reverse its
bend direction near extension. The solver now derives the bend using the old axis
and carries it to the new axis with the minimal direction rotation. Once gripped,
it preserves that achieved plane instead of swivelling toward the old approach
hint. Elbow flexion, forearm twist, wrist PHAT projection and palm-position coupling
remain active. Explicit rotation/contact edits still use the existing refit/restart
lifecycle. No new state, search, delay or knob, and no TestNN-only arm branch.

`test_held.cjs` uses an owned stdin native kernel (`test_kernel.py`), with no browser,
renderer or requests to the user's service. Six fast50cm screen-vertical cycles
from the exact captured setup: old max one-tick plane swivel120.0649deg with8
reversals; new max1.2e-11deg, zero reversals. Both grips remain, PHAT error<4.5e-16,
length error<4e-14cm. Such large sweeps still have extension acceleration and
hand-orientation residuals (new peak50.38deg, old55.32deg); this proves bend-plane
continuity, not perfect tracking of every extreme/unreachable target. Moderate20cm
sweeps retain both grips with0 hand-angle error. Recorded acquisition remains
left111/right86; left elbow max step over200-300 improves to0.025901cm.
Receipts: `Saved/Diagnostics/ReachHeld20261016/held-50-60.json`,
`held-20-120.json`, `recorded.json`, and full traces alongside. Maximum per-frame
wrist projection count remains two. No new persistent state to migrate.

The initial correction was static JS only; user Refresh preserves current grips.
The subsequent explicit native port is documented above.

## Planned approach and live-save performance — October16 current

The user rejected delayed stall recovery for combat grabs. `coupled.js` now follows
the selected terminal forearm from the first frame, with the existing bounded
elbow/roll movement and wrist projection. No per-frame pose search, stall timer or
fallback strategy. The same two fixed-point passes handle palm offsets, at most
two wrist projections per hand. The existing bounded forearm planning search runs
once at grab start. Static targets reuse it despite shoulder/body motion. Moving
input transports the chosen forearm and reverse-projects it into the desired
hand's PHAT domain (one projection), without new roll selection. A rejected
intermediate version replanned on every target change and caused a left hitch.
Version5 planning state stores wrist/rotation/joint signature for deterministic
snapshot continuation; old snapshots preserve body reserve during migration.
Contacts, fingers, body solver, speed caps and8/6-degree gates are unchanged.

Current numeric results: TestNN recorded right grip86 (previous delayed recovery150),
left111; max left-elbow step absolute200–300=0.0549318cm. Final right0.361cm/4.902deg,
both held. Frozen initial31 grips left112/right85. Stalled250 grips right296 with
maximum right wrist step0.3021cm; it transitions from the existing pose, including
the already-held left arm's old route. One initial plan per hand in all three cases;
snapshot continuation deterministic; max PHAT projection error4.45e-16, no invalid
admissions. Root-only error0; common translation error7.15e-14cm. The837-frame usual
grab/retarget/release regression passes. Paired isolated arithmetic on identical
inputs: mean0.19455→0.04153ms/hand, p950.30198→0.05293ms; not whole-frame/game FPS.
Current regression `test_plan.cjs`, evidence `Saved/Diagnostics/ReachPlan20261016/`.
Earlier `test_escape.cjs` and its exact-left-pose assertion are historical.

The user also reported severe playback lag. The live packet repeated the entire
330-frame recording at top level and inside state; the server pretty-serialized
that5.2MB packet plus a2.5MB session every1.2s. Measured formatting cost was
~1176ms+447ms. API3 stores each content-addressed motion once in
`motions/<sha256>.json`. Recurring states use `motionRef:{id,startTick}`; current
live file~65KB, session~19KB, cached session saves5–9ms. Live reads stay compact;
fetch `/motions/<id>.json` for frames. `/session` expands the reference for exact
resume; explicit snapshots/exports retain inline motion and remain portable.
Old open clients may send full motion; server interning avoids reformatting it.
New clients upload each motion object once and send compact packets thereafter.
Recorded catch-up still solves each authored tick but draws once per batch.
Live publishing no longer redraws the visible canvas. Snapshot camera remains
paired with the captured pose during initial asynchronous motion upload.

`test_live_storage.py` verifies exact restore, compact storage, one recording file,
and old-client compatibility on its own service. Only REACH background service
was restarted to load API3 (18084); user window preserved, last readback paused
at8201. User Refresh loads final JS. No Unreal port, build or editor access.

## Contact-marker occlusion — October16

`reach-renderer.js` draws the gold surface point/normal arrow and cyan palm
reference with depth testing and depth writes enabled against the existing scene
depth buffer. Body and balls now occlude these markers; the visible canvas and
snapshot worker share this renderer. Static change, loaded by the user's Refresh
lab; no automatic refresh, service restart or Unreal changes.

## Historical: superseded blocked elbow/forearm recovery — October16

User asked to fix the arm failure and any independent root dependency. No separate
root-point dependency was found: moving/rotating only the root bone with body and
targets fixed changes no non-root output. Common coordinate translation preserves
the solution within1.24e-10cm. The actual character/root translation in native
TestNN moves its shoulder relative to the stationary ball; that exposed the search
weakness. Removing that legitimate body/target relationship would be incorrect.

`coupled.js` previously rejected coarse elbow-only and roll-only changes, even
when a coordinated move or another approach could improve alignment. Finer local
quadratic search alone still stalled around10deg; guidance used only intermittently
oscillated back toward the old posture. The accepted change reuses `armPlan.forearm`
as a feasible destination when local refinement is blocked. It projects that hint
onto the current elbow circle, extracts the matching forearm twist, and approaches
with the existing bounded elbow/roll steps. Every output wrist remains PHAT-clamped.
It never snaps to a new starting pose or resets the solver/body.

The app counts six authored ticks with angular change below0.05deg while above
`min(Closure angle, Grip angle)`. Only then can the blocked local search enter
guidance. A retained `grabs[].coupled.guiding` flag keeps it on the selected route
until the existing gates are satisfied; `stalled` is capped at6. These fields are
optional/validated in saved snapshots and preserved during exact resume. Ordinary
local solving is unchanged before activation; new grabs discard the old state.
The angle comes from the existing grab update, with no extra angular calculation.
Guide/path probes replace fine probes: at most9 evaluations/pass,18/hand total.
The already-cached body planner supplies the hint; no added global search or native
body solver work. No clamp, tolerance, contact/fitting, target or speed changes.

`test_escape.cjs` compares old/new sources against the same unchanged native cases:

- Recorded31–360 inputs: left grips at110 in both; right changes from never held to
  grip at150, then stays held. Left arm transforms are identical at every frame;
  maximum left-elbow step over200–300 stays0.05366198cm.
- Frozen stalled250: right changes from indefinitely blocked to grip at303
  (53 authored ticks); both grips persist. Maximum right wrist step0.3023cm,
  elbow step1.8478cm; no pose reset or teleport.
- Final right rotation~3.6–3.7deg and wrist error~0.33–0.35cm meet unchanged8/6deg
  gates. This is successful admission within tolerance, not an exact-zero claim.
- PHAT maximum domain-projection error4.45e-16;18 evaluations maximum. Resume
  during active guidance is deterministic. Batched four-tick playback also recovers.
- Root-only output difference0; common-coordinate translation error1.24e-10cm;
  both hands acquire in all three cases.
- Existing837-frame surface/manual, retarget, release, unreachable and retirement
  regression passes. Arm length error<3.2e-14cm; no foot override.

Paired isolated JS benchmark on mixed blocked/approach inputs: mean0.38584→0.39428ms
per hand (+2.2%), p950.51846→0.49864ms. These are diagnostic JS numbers, not native
or many-agent throughput. Evidence: `Saved/Diagnostics/ReachEscape20261016/`.

**Lab only; no Unreal port/build or service restart.** User refreshes the existing
window. Native code and the earlier native parity receipts remain the pre-fix
baseline; historical import/delivery tests expecting non-grab must not be mistaken
for tests of this new solver. `test_escape.cjs` is the current failure regression.
The saved named cases themselves are unchanged and now exercise recovery with the
new lab code. The native normal-DLL stale-build warning from earlier work remains.

## Current right-hand failure reproduced in REACH — October16

User requested the exact TestNN case in the lab and an explanation if it succeeds
there. The on-demand `Prophecy.Reach.Inspect Checkpoint` diagnostic exports actual
native base/command poses, solver state, both fitted grips/targets, planning cache,
tolerances/tuning and current PHAT. `Tools/ReachGrasp/CaptureLabScenario.py` owns a
Play only when none exists, captures absolute31–360, then ends only that session.
No Blueprint, scene-ball, PHAT, simulation-mode or speed overrides are used.
The exporter was loaded with one-action Live Coding (120.52s, no object changes).
Normal DLLs still require an incremental build before any cold launch.

`Labs/ReachLab/import_testnn.cjs` converts native component-space checkpoints and
verifies them in an isolated service/browser. It creates three named JSON+PNG
snapshots listed in the normal lab restore selector after the user's Refresh:

- `TestNN_Right_Recorded`: captured initial state at31, then original neural base
  and relative target inputs through360. The body and reach/grab solve run live;
  this is not playback of solved poses. Root motion is represented by moving
  targets in the root-attached lab coordinates. Inputs freeze after360. Ball paths
  after native acquisition are recorded inputs; the lab still has no Jolt physics.
- `TestNN_Right_Stalled_250`: native stalled state and frozen neural base at250,
  editable targets/tuning, both hands active. Right remains blocked after480 ticks.
- `TestNN_Right_Frozen_Start_31`: identical initial checkpoint with its initial
  base and targets frozen, for comparison. Right acquires at85.

The recorded-input lab run matches all26 native commanded bone positions within
9.26e-7cm over329 continuation ticks. Right at360:1.19230850cm target error,
10.20486083deg rotation error, close0/no grip. The frozen stalled continuation ends
at1.19466430cm/10.21196031deg/no grip. One-step replay also matches within4.1e-9cm.
These results isolate the solver/input behavior; they do not claim full physics
parity or remove Unreal's additional actual-wrist admission checks.

Controlled changes from the same native initial state:

| Inputs advanced | Right result |
| --- | --- |
| Neither base nor goals (frozen control) | Grips at85 |
| Neural base only | Grips at85 |
| Native goals only | No grip,10.25deg at360 |
| Root translation applied to both goals only | No grip,10.61deg |
| Right goal translation only | No grip,10.87deg |
| Native base + goals | Native failure reproduced,10.20deg |

Native mesh/root moves(+6.19018,-6.52061,0)cm from31 to360, with unchanged rotation;
right ball remains world-fixed. Its root-relative coordinates therefore change
from(-28.3934,34.4463,117.0964) to(-34.5836,40.9669,117.0964)cm. Missing this motion
explains the differing input trajectories, but is a trigger rather than a complete
failure explanation. User challenged this interpretation; a controlled final250
geometry comparison now establishes a history-dependent convergence problem.
With exactly the same final targets, contact normals, palm offsets, fitted curls,
PHAT and neural base held fixed for480ticks: continued stalled state stays at
1.194664cm/10.211960deg/no grip; deleting only both arm planning caches still fails
at1.135905cm/10.095898deg; resetting pose/solver history to that same neural base
grips the right hand after67ticks and converges to zero position/rotation error.
Targets/fitting/limits are checked unchanged in every case. Thus the final target
is feasible. The incremental elbow/forearm search uses the previous arm as its
seed and only bounded local corrections; it can remain on a failing approach
despite another successful posture existing. Exact escape mechanism/fix remains
unimplemented. Why the native root translates was not investigated. Do not claim
movement inherently prevents grabbing. Evidence: `check-final-geometry.cjs` and
`final-geometry.json` in the same diagnostic directory. User lab/window/settings
were untouched; the comparison used an isolated headless inspection view.

Optional `basePose` and `motion` snapshot fields preserve capture state across
restore/export/Refresh. The server accepts a validated per-request base pose only
for these cases; ordinary lab operation retains its original base and payload.
Recorded cases advance once per authored tick even when display steps are batched.
Restart replays from31 preserving checkbox/tuning values and edited target offsets;
Reset pose exits the recorded sequence without changing checkbox settings. Restoring
an ordinary snapshot restores the original idle base. Delivery verifies exact
batch/resume, editable offsets, restart tuning and ordinary-snapshot compatibility.
The absent REACH service was started hidden; user's lab window/session was not
refreshed or replaced. TestNN outside Play/no dirty packages after capture.
Evidence: `Saved/Diagnostics/ReachScenario20261016/native.json`, `lab-comparison.json`,
`delivery.json`; cases also installed in `Labs/ReachLab/snapshots/`.

## Settled left-elbow hitch — October16 follow-up

User identified hitching around absolute200–300 in the current TestNN map.
Captured the actual tick30 Blueprint fixture without replacing targets, speeds,
point selection, PHAT or other agent logic. It is different from the port's
separately spawned symmetric two-ball test. The commanded left elbow jumped
0.9cm at193/218/256/275/307; the physical elbow tracked those jumps, while the
shoulder and wrist remained smooth. The left ball stayed physically held.
The right ball never acquired in this original fixture capture or after the fix;
previous claims about both port-test grips do not establish this fixture's success.

The bounded coupled search still tried fixed8deg elbow /4deg roll steps and their
halves for tiny wrist errors. It intermittently selected a large half-step near
a limit. Both `coupled.js` and `ProphecyReachArm.h` now multiply their step bounds
by `min(1,sqrt(initial quaternion chord error)/sin(4deg))`. Above8deg rotation
error the original search is unchanged; near alignment the same candidate budget
uses smaller corrections. No added state, iterations, constraint relaxation,
position smoothing, closure/grip tolerance changes or physical joint changes.

Reconstructed one-step lab replay of captured poses/contact transforms reproduces
the reported jumps within0.0004cm (not a bit-exact pre-physics internal capture).
Those corrected replay steps fall to0.027–0.036cm. Full native same-fixture360-tick
capture confirms max step in200–300 falls0.90093→0.05366cm commanded and
0.90080→0.05329cm physical; max commanded angle2.252→0.131deg. Left grip acquires
at111 versus112 and holds through360.34 wrist samples stay within PHAT (8.89e-16
maximum domain violation). Independent837-frame lab regression passes both contact
modes, retargeting, deterministic resume, release, unreachable rejection and
inactive retirement; maximum18 evaluations remains unchanged.

Evidence: `Saved/Diagnostics/ReachElbowHitch20261016/`, including original/full rich
captures, reconstructed replay, before/after code, `verification.json` and
`lab-verification.json`. A single-action layout-safe Live Coding compile succeeded
in119.36s and reload reported no object changes. **Normal DLLs need an incremental
build before the next cold editor launch.** Editor remains TestNN/outside Play,
no dirty packages; no asset saves or tuning/wiring changes. Lab JS updated but the
user's lab window was not refreshed. The separate right-hand non-grab is unresolved.

## REACH lab port — October 16 (installed and verified)

User explicitly authorized the Unreal port and reopening after the editor stopped.
The normal incremental build succeeded in135.19s with8 actions. New private
`FHand::ArmPlan` storage and a per-agent tuning map were cold-loaded safely.
Unreal reopened on the previous robotics map, with no dirty packages; native
reflection reports status3/native_properties0/pin_types0. The cause of the earlier
exit was not established; the last log contains no fatal entry. Saved PHAT changes
were confirmed in that log and their bytes backed up before this port.

- `ProphecyDoubleReachAnimInstance.cpp` numerical kernel exactly matches the lab
  `solver.inl`, including the lower-elbow preference and its0..1 blend.
- `ProphecyReachArm.h` ports the bounded two-pass elbow/forearm correction from
  `coupled.js`: at most18 wrist projections per hand/tick. The actual palm anchor
  is recomputed with the achievable hand rotation, so clamping does not leave
  the positional solve aimed at a wrist destination for an impossible rotation.
- Arm-first body compensation uses the lab's14-projection look-ahead, cached until
  shoulder movement reaches0.01cm or target/orientation/PHAT/local arm geometry
  changes. Only extra upper-arm shortfall beyond ordinary reach adds reserve;
  ordinary pursuit catches up first and feedback is limited to0.5cm/tick.
- Automatic Grab Object surface selection now queries toward the same-side
  upper-arm origin. **Use Surface Point=true and Grab Bone keep the explicitly
  supplied point.** Existing tick30 Blueprint wiring is preserved, including
  its explicit points; the port does not silently rewrite that experiment.
- **Set Reach Motion Tuning / Get Reach Motion Tuning**, Prophecy → Reach, expose
  shared **Sync Rotation** and **Elbow Down Blend**, both0..1, defaults0 and1.
  Sync recomputes angular pursuit from current wrist distance and reach speed,
  retaining rotation speed as a cap. Elbow0 restores the original outward
  preference;1 keeps the accepted lower preference. The coupled grab solve still
  prioritizes wrist feasibility. Invalid/non-finite settings leave values intact.
  Settings apply to ongoing requests and persist across release within that world.
  The user's current lab Sync0.82 can be supplied explicitly; Blueprint speeds,
  targets and defaults have not been overwritten with lab settings.
- Previous arm poses remain component-local when the actor turns. Public world
  target semantics remain unchanged. Fingers, clearance/fitting,8/6-degree gates,
  actual physical-hand admission, Jolt attachment and return/release stay intact.
  Automatic contact debug marks the gold surface point and its outward normal.

The PHAT is still read from the loaded Unreal asset each active update. No lab
angle table is copied, and D/S's separate wrist lifetime is unchanged. The lab's
kinematic visual ball attachment is not substituted for Unreal physical joints.
No recurring arm solve or plan work runs after reach state retires.

Backups, source parity and120 lab input/expected fixtures:
`Saved/Diagnostics/ReachPort20261016/`. Explicit numeric inspector:
`Prophecy.Reach.Inspect LabPort`; owned runtime test: `Tools/ReachGrasp/VerifyLabPort.py`.
Verification complete: the120 lab/native cases match final arm positions to
2.02e-14cm and quaternion dot error3.34e-16, with identical evaluation counts.
Equivalent look-ahead roll choices differ by up to11.25deg, but the forearm endpoint
used for body compensation differs only3.92e-6cm and projection cosine3.13e-8.
The first diagnostic incorrectly treated the unused axial-roll difference as a
failure; the refined diagnostic checks the endpoint and reports roll separately.
A one-action diagnostic-only Live Coding patch loaded successfully with no object
changes; runtime behavior is in the normal DLL. The normal DLL's diagnostic still
predates this refinement; include it in the next normal build before cold launch.

Three owned Play checks passed: Kin automatic, Sim automatic and Sim explicit
surface points. Both hands held by absolute150/150/180 after request90, four
contact fingers each, held through390, then released/returned/retired by411.
186 sampled wrist poses (including return) obey PHAT; maximum violation8.89e-16.
Motion settings accept boundaries/intermediate values, reject out-of-range inputs,
and persist after release. Physical tests create real Jolt grips; Kin reports
logical grips as before. These are targeted sphere fixtures, not universal grab or
many-agent performance claims. No thresholds/PHAT limits were relaxed to pass.

Final editor16368 is outside Play on the previous robotics map, no dirty packages.
Full Blueprint graph is byte-identical before/after checks, reflection healthy;
saved BP/TestNN/PHAT hashes equal pre-port backups. No asset saves, lab refresh,
D/S/robotics edits or second editor closure. `verification.json` is the receipt.

## Blueprint grab angle tolerances — October 15

User requested a node to tune the closure/grip acceptance angles (not PHAT bounds).
**Set Grab Angle Tolerances**, category Prophecy → Grab, takes Agent,
Closure Angle Degrees (default8) and Grip Angle Degrees (default6).
Call during BeginPlay or before Grab Object/Grab Bone. Settings apply to both
hands and to an ongoing grab on its next update, persist across release/retarget
and D/S interruption, and are discarded with the game world. Other agents retain
their settings/defaults. **Get Grab Angle Tolerances** exposes the current pair.

Both inputs accept finite0–180 degrees inclusive; invalid input returns false
without changing either value. The grip threshold controls both commanded and
actual wrist orientation tests. Position thresholds, closure duration, PHAT
constraints and finger fitting remain unchanged. Raising a threshold accepts
more orientation error; it does not solve a different palm pose or refit fingers.
An existing grip is not released when the thresholds change. Zero requires exact
orientation agreement;180 removes the orientation restriction while preserving
the position and completed-closure checks.

Implementation adds a separate weak-agent settings map, with no recurring work
for inactive reach. This retained storage requires a normal build/restart.
Normal incremental editor build succeeded in492.43s (21 actions), including earlier
Live Coding changes. Editor19216 closed gracefully after backing up disk assets
and saving dirty PoseAgent/TestNN; PHAT was already clean. Editor25832 reopened
TestNN with current normal DLLs. No Live Coding patch is needed for this node.

Owned230-tick Sim test passed: defaults8/6, valid0/180 boundaries, invalid negative,
over180, NaN and infinity rejected without changing either setting; other agents
retain8/6. With closure/grip0/0, no grip at129; closure180/grip0 still no grip at159;
after changing both to180, both physical grips acquired by209. Settings persisted
after Stop Reaching. All268 wrist samples remained inside PHAT limits (maximum
domain violation1.34e-15). This verifies acceptance control, not finger-contact
quality at such permissive angles. No default tuning was changed.

Final editor TestNN/outside Play, no dirty packages, saved PHAT/BP/map hashes
unchanged since preservation. Reflection status3/native_properties0/pin_types0.
Full graph matches after normalizing only input-key nodes' unused Key output
default (None versus empty on reload) and line endings; no wiring edits.
Evidence: `Saved/Diagnostics/GrabAngleTolerances20261015/`, especially `final.json`.

## PHAT wrist constraints — October 15

User requested that reach/grab hand control obey the edited PHAT, with automatic
propagation of later edits; explicitly excluded D/S. The native reach overlay
(not a Control Rig asset) now reads the pose mesh's loaded Physics Asset wrist
constraints on each active update. It projects only the controlled hand rotation
in the authored joint frames, respecting endpoint order, Free/Limited/Locked
motions and the native Jolt swing-quaternion cone (Swing2=Y, Swing1=Z, Twist=X).
No copied angle table or runtime physical Free override is used. Rotated PHAT
frames are already baked into GetRefFrame; the angular offset is not applied twice.
Later changes to the loaded PHAT are used by the next reach update; saved edits
therefore need no manual Blueprint port for subsequent Play sessions.

The hand position/arm solver and D/S remain unchanged. Both hands are supported,
including the reach release return while it owns that hand. Rotation pursuit is
seeded from the constrained result. Finger closure and grip admission use the
remaining constrained orientation error; an unreachable orientation cannot be
marked as an acquired grip. Existing physical grip acceptance tolerances remain.
The physical rig's own live limit import/recreation behavior is unchanged.

Implementation is layout-safe: `ProphecyReachWristLimits.h` and narrow changes in
`ProphecyReachLibrary.cpp`; no retained-state or reflected-field additions. Existing
inspector accepts `Prophecy.Reach.Inspect WristMath` and `Wrists` for explicit
numerical checks. `Tools/ReachGrasp/VerifyWristPHAT.py` owns its PIE sessions; the
Kinematic test edits an isolated `/Engine/Transient` duplicate PHAT, then restores
the original runtime reference; no package writes or force deletion/undo-buffer
clearing. The explicit editor-only `WristClone` inspector action creates that copy
only for the possessed Kinematic agent with an active reach.

**Verified:** 4,860 pure projection cases cover all27 Free/Limited/Locked mode
combinations, rotated joint frames, reversed endpoint order, exact locked-frame
alignment, normalization, unchanged Free rotations and idempotence. Constraint
domain error is below4e-15; quaternion angle comparison noise is below1e-7rad.
Three owned230-tick live checks (Kinematic reach, Sim reach, Sim two-ball grab)
each recorded268 wrist samples including release return; every owned hand stayed
inside the authored limits. The Kinematic test switches to locked wrists at140,
edits that same loaded PHAT to Limited7/9/11 at160 without restarting the reach,
then restores the original asset reference at180. Both changes propagate on the
next update.

**Grab limitation observed:** the two radius3cm ball targets reach zero position
error but neither grip acquires by210 with the current wrist bounds. These are
limit-enforcement checks, not successful-grasp claims. No target, acceptance
tolerance, finger pose, shoulder/forearm solution or PHAT bounds were changed to
force acquisition. Out-of-range orientation remains blocked; target placement
or a future separately requested arm/orientation solver change may be needed.

Evidence `Saved/Diagnostics/ReachWristPHAT20261015/`. Final user PHAT wrist values:
left Swing1/2/Twist50/46.310001/40.860001; right50/23.709999/30 degrees, all Limited.
Source asset SHA256 remains `f948ed9de335c5d55b467ccd667702817c48458fc2e2e3d72773efc74193a4d5`.
Full BP graph unchanged; preexisting dirty PoseAgent and TestNN preserved, no asset
saves/restart. Latest Live Coding patch20 succeeded in209.17s; reload reports no
object changes. Earlier pointer-type compile error and diagnostic-copy/Python
return-value setup errors were corrected before accepting results. The rejected
Content Browser `/Temp` duplication did not create an asset; the final test uses
native transient duplication. Reflection status3/native_properties0/pin_types0;
editor outside Play. Normal DLLs remain stale: build before any cold launch.

## Current user review fixture — October 15

User removed continuous D/S testing and requested the two solid small balls from
the screenshot on their existing one-shot tick30 branch. PoseAgent and TestNN
are saved locally with the user's existing edits preserved. No commit/push.
The historical October12 probes below were temporary; this review fixture is
now deliberately present in the saved Blueprint and map.

- Player `BP_ProphecyManualPoseAgent_C_0` has instance-editable **Left Grab Ball**
  and **Right Grab Ball** references under **Reach Grab Experiment**. Other agents
  have no references and skip the fixture. Level actors are **Reach Grab Ball Left**
  (`StaticMeshActor_5`) and **Reach Grab Ball Right** (`StaticMeshActor_6`).
- Each movable `/Engine/BasicShapes/Sphere` has radius3cm, PhysicsActor collision,
  gravity off and initial simulation off. Positions use the player's initial
  pelvis + forward40cm + right(-22/+22)cm + up28cm. They remain editable in the level.
- **Finger visibility correction, October15:** user saw debug closure but no visible
  physical/kinematic finger motion. Enable Attack Fists was already true; reach fingers
  also bypass that optional attack-fist switch. Current global `r.SkeletalMeshLODBias=1`
  selected LOD1. `Character_LodSettings` LOD1/2 keep hand bones and ancestors, excluding
  finger descendants. The original probe forced LOD0; the initial restored fixture
  omitted that component override. Saved only this player's Mesh and PhysicalMesh
  **Forced LOD Model=1** (render LOD0) in TestNN. Global bias, other agents, mesh assets,
  Blueprint graph and native code unchanged. No build/restart needed.
- Owned finger checks: Kinematic actual finger/model discrepancy at LOD0 below
  3e-7cm; LOD1 lacked usable finger transforms. Physical completed native finger poses
  were identical across the LOD experiment, confirming the solver was already active;
  pre-Play component override selects rendered LOD0 in Sim and both physical grips
  remain active. Changing LOD after starting manual Sim did not refresh its predicted
  LOD immediately, so use the saved override on the next Play. The first fixture's
  grip-status checks did not validate rendered fingers. Evidence
  `Saved/Diagnostics/ReachGrabFingers20261015/`; latest finish outside Play, TestNN
  saved, PoseAgent remains dirty and was not saved by this finger correction.
- `tick debugging`: existing `K2Node_CallFunction_31` **is tick**, i30/modulo-1,
  and Branch `K2Node_IfThenElse_5` are retained. Its True/reroute executes HideSword
  then left/right **Grab Object**,120cm/s,180deg/s, explicit nearest wrist-facing
  collider surface points, then reach visualization. Existing disconnected Reach
  Target and Double Reach nodes remain intact. No automated release at350: hold
  for the user's motion review.
- The branch's formerly unused Else now checks tick29 and enables sphere simulation
  and Jolt ownership. Admission inside Blueprint tick is deferred until the safe
  boundary; same-tick activation/grab initially rejected both grabs. Preparing at29
  fixes the fixture without changing Grab Object admission or the tick30 trigger.
- The existing `is tick` function uses `ttick debug`; the user's condition was not
  rewritten. In fresh Play verification this equals `absolute tick debug`.
- Final owned220tick check: both reaches activate at absolute30; physical left/right
  grips at90/93 and both remain active/gripped through220, four fitted contact fingers
  each. This verifies wiring/acquisition, not human approval of motion or arbitrary
  reach targets. Test ended; editor left outside Play with no dirty packages.
- Full graph comparison: only two existing pins gained connections (tick30 Else and
  terminal `K2Node_Knot_58.OutputPin`);28 added nodes, no removed existing nodes.
  PoseAgent compile status3; reflection status3/native_properties0/pin_types0.
  Existing user tuning, wiring and scene retained; A_Sword asset untouched.
- Editor helper `ProphecyReachGrabFixture.inl` is explicitly dispatched through
  `Prophecy.Editor.LiveAgentTypes WireReachGrabFixture`; no startup registration or
  recurring runtime helper. Latest successful Live Coding build133.58s plus reload;
  no native retained layout changes/restart. Normal DLLs remain stale before a cold launch.

Evidence and recoverable pre-edit live Blueprint:
`Saved/Diagnostics/ReachGrabWiring20261015/` (`verification.json`, `smoke.json`,
`graph-before-install.txt`, `graph-final.txt`, `PoseAgent-live-before.uasset`,
`tick-before-export.txt`, original disk copies). Earlier failed admission captures
are retained separately. No reach/grasp solver, D/S tuning, lab or unrelated asset edits.

## Repeated D/S diagnosis — no D/S changes

Owned current-Blueprint captures, 1,200 absolute ticks each in Sim and Kinematic.
Four S/D cycles on left NPC `BP_ProphecyManualPoseAgent_C_2`; all three agents
recorded, including the possessed agent that remains stuck in reach. User
shrink20%, wiring, locomotion and settings preserved. Ended only owned PIE and
restored FPS. Evidence: `Saved/Diagnostics/ReachGrasp20261012/repeated-{sim,kin}.json`
and `*-boundaries.json`. `Tools/ReachGrasp/AnalyzeBoundaries.py` reproduces measures.

1. **Late S reach reverses in the commanded pose, not a physical tracking failure.**
   Second S, ticks363–366 moves +3.35,+3.18,+2.91,+2.73cm in pelvis-translation-relative
   X, then367–370 reverses -1.11,-1.23,-1.25,-1.37cm. Physical wrist rotation tracks
   command to .33→.11deg. Online ReachArm refits its destination every four slots,
   and every tick after its planned deadline; each destination is filtered across
   four ticks while the holster moves with gait. The lab plans against a known
   future recording. Refit/gait pursuit is implicated, but an exact matched-input
   replay has not yet separated each contribution. No damping fix justified.
2. **Additional S entry jump**, separate from the pre-slide complaint: first
   post-entry command steps4.41cm on first cycle,8.51/8.05/8.15cm later. Example380:
   (-6.09,-4.39,+4.01)cm versus previous(-.56,-.57,+.54)cm. Physical follows. Native
   switches from filtered reach destination to a new sliding guide/pole application.
   Kinematic later S entry peaks~3cm; physical arrival is later in Sim. This boundary
   needs exact captured-entry replay; it was not repaired.
3. **D release has a distinct physical kick.** At539 release, command1.41deg,
   physical8.29deg; at540 command4.11deg, physical28.88deg. Physical wrist already
   has ~11–14deg tracking error during sliding, grows18.05deg at539, then snaps
   toward command (6.74deg error540). Repeats25.63/28.88/31.07deg peaks on first
   three releases. Kinematic has no such excess; its command return still has
   ~6–9deg steps. The fixed grip's captured rest pose opposes authored wrist tracking
   during D sliding; removal exposes the error. Code captures D joint frames at
   grip and retains them while driving the sword. Strong timing/error evidence,
   not a joint-only A/B proof yet.
4. **Command-side D early return also differs from the restored lab.** Previously
   documented native60Hz versus lab240Hz held-arm return integration and release
   velocity sampling remain. This is distinct from the larger physical release
   kick and the later post-completion NN feedback fix.

No D/S solver, lab, profile, Blueprint or physics tuning edits in this diagnosis.
Do not describe either complaint as repaired. Existing evidence preserved.

## Research and chosen method

Primary references read:

- Meta [Hand Grab Interactions](https://developers.meta.com/vr/documentation/unity/unity-isdk-hand-grab-interaction/): palm grip offset and per-finger pose ownership.
- Meta [Custom Hand Grab Poses](https://developers.meta.com/vr/documentation/unreal/unreal-isdk-hand-grab-poses/): authored finger poses and pose debugging.
- Ultraleap [Physical Hands](https://docs.ultraleap.com/xr-and-tabletop/xr/unity/plugin/features/physical-hands.html): collider-based hand contact and multiple-joint considerations.
- Unity [dynamic attachment](https://docs.unity.cn/Packages/com.unity.xr.interaction.toolkit%403.0/api/UnityEngine.XR.Interaction.Toolkit.XRGrabInteractable.useDynamicAttach.html): preserve the actual acquisition pose.

Chosen prototype: original native DoubleReach body/arm math, contact-limited
open-to-closed finger rotation, and one fixed grip per hand. No Control Rig or
15-body finger simulation. Our engineering choice is informed by those systems;
it does not claim to reproduce their proprietary implementations.

## Implemented Blueprint nodes

`UProphecyReachLibrary`, categories **Prophecy → Reach / Grab**:

- **Reach Target:** Agent, Left/Right, world target transform, Max Reach Speed
  (cm/s); advanced Max Rotation Speed (deg/s). Persistent until changed/released.
  Calling the other hand enables both; repeated updates do not restart reaching.
- **Double Reach:** Off/Left/Right/Both, two world transforms and speed. Calls the
  original native body/arm solver directly, without a copied solver or Control Rig.
- **Grab Object:** primitive component, hand and speed; advanced optional world
  surface point and rotation speed. Without a point, chooses the closest simple
  collider point to the approaching palm.
- **Grab Bone:** skeletal mesh, bone name, world collider-surface point, hand and
  speeds. Stores point, normal and grip orientation in that bone's frame.
- **Release Grab:** one hand; **Stop Reaching:** both. Advanced Return Seconds=.25.
- **Get Grab Status:** active, gripped, physical grip, live surface point, commanded
  wrist distance and fitted contact-finger count. Distance is commanded wrist to
  target, not physical tracking error.
- **Set Reach Visualization:** toggles markers for an existing active reach;
  does not create or restart an action.

One update consumes 1/60 authored second, independent of wall-clock FPS. The
original solver supplies shared pelvis/spine/arm geometry and elbow filtering.
Each hand has speed-limited target pursuit. This is not a strict speed cap on
every physical joint after gait, body adjustment and contact response.

## Implementation decisions and corrections

1. Direct NN world/component pose consumers receive the native reach overlay.
   Upper feedback is retained while reach owns the pose. Inactive state exits
   before pose copies/solves; completion removes state. D/S has priority: admission
   during D/S fails and starting D/S cancels reach. No D/S behavior edits.
2. Fingers reuse the existing closed-fist retargeting convention, reference open
   pose and15 phalanges/hand. Simple collider probes stop each joint's curl, using
   12 bracket samples and6 refinements. This fits a pose rather than simulating
   individual fingers. Finger trials recompute only that finger and test only
   segments affected by the changing joint.
3. Fit once per grab, then close over .2 authored seconds once the wrist is close.
   Holding reuses fitted local rotations without recurring collision fitting.
4. Numerical checks caught the open thumb intersecting the sphere before curling.
   Admission now finds minimum outward clearance (bounded4cm,8 refinements)
   before fitting. Requested surface point stays unchanged. Failure to clear the
   open hand rejects admission rather than pretending it has a clean grasp.
5. Physical acquisition requires actual wrist within2cm/6deg of target, commanded
   wrist within1.25cm and finished closure. One fixed native joint captures the
   actual acquisition frames. Repeated requests reuse state and joint. Kinematic
   mode previews pose/grip state without a physical joint or parenting the object.
6. Coarse hand/forearm colliders initially knocked the balls away. Scoped contact
   rules now ignore only the selected target body against that hand and forearm.
   Other collisions remain. Release, invalid target, reset, mode changes, D/S
   interruption and EndPlay remove the owned joint and filter; no overwrite of
   existing collision preferences.
7. Releasing one hand gives that arm/fingers a parent-local FK return while the
   other holds. Full release returns the shared body too. Re-enabling seeds target,
   elbow and rotation from current physical pose, including mid-return. Retained
   body parameters follow full return progress. No restart on duplicate calls.
8. Reject invalid hand values, non-finite inputs, unsupported simple collision,
   missing bones and unavailable physical target bodies. Physical grabs require
   Jolt; Kinematic previews supported. Double Reach validates before mode changes.
9. Ordinary skeletal socket reads for non-physical finger bones were stale in this
   Jolt setup. Numerical inspector uses `SampleActualComponentPose`, reading the
   completed full skeleton used by the renderer. Python `fingers` socket arrays
   are not valid contact evidence; native CSVs are. Wrist/body queries agree.
10. All fixtures are temporary owned PIE actors and instance overrides. Swords and
    extra NN renderer hidden only during experiments. No fixture/wiring saved into
    TestNN. Editor remains open outside Play.

## Verification

Two native automation tests pass: `Prophecy.Reach.NativeKernel` and
`Prophecy.Reach.GrabGeometry`. Cover left/right/both, finite normalized output,
target pursuit speed, arm lengths, real reference/fist conversion, bounded curl,
component-local point transport and invalid admission. Receipt predates the later
implementation-only clearance/fitting patches; final live checks cover those.

Final evidence in `Saved/Diagnostics/ReachGrasp20261012/`:

| Capture | Result |
| --- | --- |
| `small-balls`, radius3cm Sim | Physical grips148/158, held to release350. Steady wrist error max .0184cm/.064deg. |
| `small-balls-kin` | Same148/158 grip ticks; wrist error <3e-7cm; no physical joints. |
| `balls-clearance60` / `balls-clearance20`, radius6cm | All331 captured ticks90–420 have identical commanded/physical hands and grip/release flags. |
| `head-clearance` | Another walking agent approaches; forehead surface grip186, holds to350. Steady wrist error max .0603cm/.056deg. |
| `lifecycle-final` | Duplicates, release-left/retain-right, reacquisition, full-return interruption, target destruction, mode change and reset clean up. |

Head point stayed bone-local across227 samples: max drift3.86e-14cm. Completed
finger poses track the fitted model: small balls max .016cm; head sample .092cm
during settling. Small-ball phalanx centres clear the collider by at least .717cm
at checked hold sample, versus .65cm probe radius. End segments also use intermediate
contact samples; this is not a proof of skin-mesh nonintersection for every asset.

World baseline8 generic joints/8 suppressed pairs; both grips10/12; left release9/10;
reacquisition never exceeds10 joints; target destruction clears its grip; mode/reset/
completion restore8/8. Counts include pre-existing world joints. Receipts:
`latest-validation.json`, `fps-parity.json`, `bone-local-point.json`, each `*-native/`.
`Tools/ReachGrasp/AnalyzeGrasp.py` reproduces summaries. Visuals: `small-balls.png`,
`balls-clearance60.png`, `head-clearance.png`.

An earlier surface below the chin **did not acquire**: actual wrist remained
~2.7cm/11deg from the authored target. The gate correctly refused a joint. Forehead
point succeeds without loosening acceptance or disabling other body collisions.
Failed captures remain, including bad test fixtures with changing facing and a
root-window move that did not durably relocate the target; not counted as passes.

## Performance and limits

Explicit live benchmark,1000 repetitions on the active fixture, warm assets:

- Pose read + native solve + publication: **.0135–.0185ms/agent** for two ball grips;
  .0111ms for the single head reach.
- One-hand reference conversion: **.065–.077ms**.
- One-time fitting: **.093–.119ms/sphere hand**, **.353ms/head collider**.
- Separate100-agent native solver-only test: initial .427–.438ms mean; later run
  during editor startup .855–.859ms. Easy reachable fixture, not whole-game cost.

Live benchmark excludes NN inference, physics, rendering, admission clearance,
first asset load and some controller bookkeeping. Not a measured100-agent live
grasp crowd; simultaneous admissions can accumulate a setup spike. No recurring
contact fit, Control Rig or individual finger rigidbodies were introduced.

Prototype limits:

- Sphere/capsule/box/convex simple collision. Triangle-mesh-only objects rejected.
  No force-closure analysis, grasp taxonomy or obstacle avoidance claimed.
- Reach-and-hold surface grasp; no separate carry/throw trajectory or Kinematic
  parenting. It follows the component/bone; Release destroys the physical grip.
- An obstructed/unreachable admitted target stays active until released/retargeted;
  Gripped remains false. No timeout teleports the hand into place.
- Requires the tested humanoid/fist references. Different skeletons, scaling held
  objects and arbitrary compound shapes require further fit checks.
- Concurrent attack/get-up/defense authoring has not been accepted. Only D/S
  priority and reset/mode/destruction cleanup explicitly handled. This is not a
  complete gameplay ownership system.
- No human motion-quality approval or universally natural grasping claim. Numerical
  traces and screenshots support these ball/head fixtures.

## Build/save state and replay

New-API normal build212s; test-enabled incremental37s. Later retained-return-state
normal build37s/final correction31s, within one additional restart. **Two necessary
editor restarts total.** Subsequent safe implementation patches use Live Coding,
successful reload/no object changes. **Editor25964 has latest code; normal DLLs
are stale and require a normal build before cold reopen.** Log `editor2.log` here.

Final postflight: PoseAgent, TestNN, A_Sword, SwordHolsterProfile and lab state
byte-identical to task preservation checkpoint; full BP graph identical, no dirty
packages. User pre-existing edits remain. No Git commit/push this task.

With normal editor open and no existing Play, run sequentially from project root:

```powershell
& 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe' Tools/RunUnrealRemote.py Tools/ReachGrasp/Probe.py --name review-balls --kind balls --radius 3
& 'C:/Users/singerie/Documents/Cursor/stepper/.tools/python310/python.exe' Tools/RunUnrealRemote.py Tools/ReachGrasp/Probe.py --name review-head --kind head
```

Wait for each owned capture to finish before the next. Probe restores FPS, ends
only its own Play and never saves assets. Inspector/benchmark commands are explicit
development diagnostics, with no polling in normal gameplay.
