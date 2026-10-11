# Sword holster numerical investigation — October 11, 2026

User requested an overnight port, safety checkpoint, broad numerical diagnosis,
systemic fixes and final performance audit. This is the decision/test annex;
the main journal only summarizes the current state. No visual motion claims.

## Plan and acceptance evidence

1. Freeze the live desktop lab state, current native profile, Blueprint graph,
   asset hashes and editor dirty/Play status. Preserve user edits and sessions.
2. Port missing behavior and current tuning. Build normally for retained layout
   changes; verify reflection and actual Play. Commit and push a curated safety
   checkpoint before the investigation changes gameplay behavior.
3. Run all pure lab/native regressions, then collect all failures from owned
   Unreal Play replays: idle/walk/run, kinematic/physical, both actions, repeated
   cycles, different gaze, acceleration/turning, timing/pause and cancellation.
   Keep per-tick phase/ownership, target/future/physical poses, equipment and
   constraint state. Compare parent-local rotations and lengths as well as world
   steps, separating expected locomotion from procedural discontinuities.
4. Classify stalls by authored geometry versus physical lag versus lifecycle.
   Classify snaps by raw NN, authored target, display, physics or ownership edge.
   Fix shared causes with bounded work; do not hide failures through increased
   tolerances, extra shrink, arbitrary delays or changed motor/asset tuning.
5. Rerun the complete matrix after fixes and retain first-failure evidence.
   Measure procedural and admission costs using the existing 100-agent benchmark;
   distinguish diagnostic overhead, whole-game cost and inactive work.

## Decisions and observations

- Initial live state: walking, S, gaze -24°, start25, reach230cm/s,
  rotation600°/s, slide150cm/s, shrink15%, unshrink.5s, head tilt45°.
  D return stored progress.9, S.7. Preserve current live values even when they
  differ from an earlier factory/default discussion. Gaze remains per-agent in UE.
- Native lacked the latest head vertical-axis bound. Port the exact local-X
  head-versus-spine05 swing projection, including the minimum boundary correction
  when spine motion makes the old head illegal. Legacy no-bound tests explicitly
  use90°. This is not a nose-pitch or world-Z limit.
- Locomotion must keep its own tick clock. Native reads current unmodified NN
  every update; test this under real moving agents, not only prerecorded walk.
- Safety checkpoint `822cf42` pushed to origin/codex/standalone-sim. Includes
  current lab, scripts, BP/map/sword, native implementations and their existing
  FK-gaze/checkpoint dependencies. Bulk model files and unrelated PDF excluded.
- Initial real running repro: at501.75cm/s, kinematic player/NPC remain in S
  reach through720 despite authored hand error frequently0cm. Current physical
  holster-to-hand distance remains6–11cm; kinematic hand tracks command to3e-7cm.
  This excludes physics as the primary stall cause. Sim running also stalls;
  moving refits exhibit arm steps up to170°. Idle/walk complete all three agents.
- Systemic correction under test: carry the last completed physical holster's
  pelvis-relative transform onto the current NN pelvis for planning. Keep actual
  physical geometry for tip acceptance and ownership. Do not extrapolate wall
  time or relax the2cm gate. Refit arm destinations from the preceding destination
  to keep the elbow branch continuous, instead of reseeding from the entry arm.
- Baseline player Blueprint continuously sets its own gaze (-.9167,-.1111);
  the initial constant-gaze override affects NPCs but does not override that BP.
  Record actual gaze per tick; do not label player runs as fixed requested gaze.

## Results

- Port normal build: initial compilation failed on a new editor-helper
  `TObjectPtr` range declaration; corrected to explicit `UEdGraphNode*`.
  Incremental retry succeeded69.18s. One clean visible editor restart.
- Native initial suite12/12 passes. LabChannels18,000 samples:
  head2.96e-6°, neck7.25e-6°, position5.38e-7cm, completion mismatches0;
  slide geometry500 samples max1.88e-13cm /2.96e-6°.
- Lab collect-all initial run22/24 passes. Two stale checks fixed without
  changing motion: arm lengths must use continuous locomotion time, and S
  entry now permits the already-authorized tip2cm/angular-tolerance gate.
  Both focused reruns pass; full rerun follows later.
- Remote Python discovers the first editor, including an isolated commandlet.
  An attempted value refresh reached the commandlet and refused saving; no
  disk asset changed. Subsequent remote work is serialized after commandlet
  exit. Visible editor refresh/save succeeded; graph differs only in230/600
  speed literals. No saved map, sword, motors or PHAT changes.

Raw evidence is kept under `Saved/Diagnostics/SwordOvernight20261011/`.
The following chronology preserves failed approaches; final results are below.

## Shared-cause fixes under validation

- All 13 first frame-fix cases have zero missing ticks and fixed1/60 world delta.
  Kinematic running/turning stalls disappear; simulated running/drawing still
  exposes up to20cm real pelvis tracking lag. The first conversion wrongly
  removes that physical lag. Revision carries the completed holster through
  **previous NN pelvis -> current NN pelvis**, keeping the actual physical offset.
- Frozen high-gaze walking inputs prove a second defect: at S exit158/164/165,
  head error is about.02deg but both neck bones retain about120deg. A combined
  continuous quaternion logarithm retains a whole turn. Separate parent
  cancellation from head authoring, expressing authored and current-NN head in
  the same signed world reference and distributing their factors separately.
  At matching coordinates these factors cancel exactly throughout the neck.
- Replaying all three captured high-gaze cases with the new head math preserves
  exit158/164/165, restores the whole neck exactly, max neck step4.9364deg.
  Signed head routes, changing targets across180, q/-q, current gaze, partial
  look-at and sigmoid profiles pass. Updated old tests that asserted the removed
  combined-log implementation; preserved speed, bone-length, world-target and
  whole-neck handoff checks. Added a captured-input regression fixture.
- Sliding guides now return to the common integer guide grid after a fractional
  rotation cutoff. Previously every later guide inherited that fractional phase,
  mixing live gait frames. Solve spacing and crowd staggering remain unchanged.
- An editor-only on-demand pose report captures raw NN and pre-head poses;
  it does no recurring logging or allocations during normal gameplay.
- Required normal restart for two new per-action head vectors: no active Play,
  no dirty assets. Batch frame/head fixes into the same build. No extra controls,
  motor changes, loosened arrival thresholds, hidden shrink or arbitrary delays.

- Full head/frame matrix:12/13 scenarios completed; all kinematic, straight Sim
  runs, acceleration and extreme constant gaze pass. The remaining Sim turning
  player keeps S reach active with a few centimetres of tip error. Actual holster
  velocity predicts its next position/orientation better than rigid NN-pelvis
  motion (recorded90cm lever mean error2.204->.913cm,313 samples). Revision
  integrates the native COM and angular velocity for exactly one authored tick;
  kinematic still uses previous/current NN pelvis. Actual-world acceptance stays.
- The apparent running neck catastrophe at147–150 also occurs without D/S.
  NPC3 runs directly into map obstacle `Cube`, bounds center(-1081.28,-92.54,
  114.50), extent(213.06,179.02,112.02)cm. Physical pelvis abruptly stops near
  x=-856 while NN continues. Preserve the collision case; add a separate owned
  PIE clear-lane fixture by removing only that PIE obstacle, never the saved map.
- A post-D neck kick is reduced when restoration is suppressed diagnostically.
  That control is **not a gameplay fix**: user explicitly requires original
  limits restored. Running without D/S already exposes physical head/neck kicks.
  Keep commanded discontinuities separate from physics/constraint conflicts.
- Baseline measured head changes from factoring neck distribution are small:
  the old +170deg idle regression completes298 vs296 due to a different eye
  position and hence aim path; its reported98–112 interval remains continuous
  (max velocity-vector change.13654deg/tick). Current captured UE exits unchanged.
- Native head/frame build passes12/12 groups;18,000 head samples max3.42e-6deg
  neck and1.19e-7cm, no completion mismatches. Removed obsolete combined-neck
  helper routines rather than keeping duplicate implementations.
- One diagnostic wrapper lookup failed because the Python class alias is absent;
  corrected to the existing reflected CDO call_method path. Failed captures
  remain under controls/, usable repeats under controls-v2/.
- Startup stopped on low-drive warning (~5GB free). Computer-use initialization
  failed (kernel assets, os error3). Dismissed only that verified warning window;
  editor22512 exposes the normal TestNN main window. No user data cleanup.
- Initial velocity-prediction compilation used an incorrect include name;
  corrected it to the existing ProphecyJoltWorldSubsystem.h before retrying.

- Held-sword diagnosis: before D/S the grip matches its authored offset exactly;
  at admission it differs5.78deg, later10–16deg in the stalled turn fixture.
  The replacement joint captured transient body lag, while NN planning and the
  sword drive follower still expected the nominal grip. Preserve the existing
  nominal rest transform for **S reach**; D grip still captures current placement.
  Neither body is teleported; axial shrink updates the same joint.
- Second physics clock mismatch: the temporary sliding sword joint used the
  rendered component from the completed frame, while the hand drive targeted
  the upcoming frame. The Jolt kinematic-body preparation now requests the same
  authored blade target, guarded by exact world/slot/generation identity and
  active Slide state. Render/ownership/acceptance remain post-physics. No second
  motion clock, repeated solving, retained body layout or new public control.
- Removed the previously unused HandTarget hook in favor of that single physics
  target hook. First compile caught absent body-handle equality; changed to the
  explicit three-part handle identity. Also matched the existing ordinary grip's
  remove-scale-before-body-origin conversion. Successful retry31.54s; verifying
  actual reload and Play next. Existing unrelated Niagara deprecation warning
  appeared during dependency compilation; no change to that subsystem.

## Final implementation and decisions

1. Ported the latest live profile and vertical-axis head limit, including its
   moving-boundary behavior. Saved only the existing Blueprint230/600 speed
   literals. The full3310-node graph preserves all other pins, defaults and links.
2. Fixed the planning/physics frame mismatch. Sim prediction uses native COM
   translation and angular velocity over1/60 second, preserving actual physical
   pelvis lag. Kinematic uses previous/current NN pelvis frames. Actual arrival
   still uses the real blade/tip, with the user's original acceptance limits.
3. Matched the sliding sword's next physics target with its gripping hand's next
   target. Exact world/slot/generation identity guards the hook; inactive and
   non-sliding equipment retain their existing path.
4. Preserved the nominal held-sword grip during S reach. Capturing transient
   physics lag had baked a wrong rest orientation into the replacement joint.
   D still captures its current grip. Shrink updates the existing joint and its
   existing drive follower. No teleports, extra joints or physics tuning.
5. Seeded reach refits from the prior destination and returned fractional slide
   cutoffs to the common guide grid. No extra solves or changes to staggering.
6. Replaced the combined head/neck rotation logarithm with separate signed
   head/base factors and independent spine cancellation. Exact factor cancellation
   restores the whole neck, including positions, rather than only the head.
   Native and lab/fractional playback share this law. Look-out selects the current
   base branch initially, then retains continuity; equivalent quaternion signs
   and crossing180 remain covered. Completion checks the signed residual too.
7. Removed obsolete combined-correction state/helpers. Reused quaternion thirds
   and their powers instead of repeatedly exponentiating each neck share; base
   factors are computed once per tick. Existing scratch, sparse FK guides,
   four-slot scheduler and60-game-tick clocks remain. No public knobs added.
8. Added on-demand editor-only numerical pose and geometry-cost reports. No
   automatic per-tick diagnostics, file writes or capture work ships in gameplay.
9. Extended owned-PIE tests with explicit motion/gaze/cycle controls and separate
   command, future-NN, physical, native-body, equipment and parent-local metrics.
   Test runs collect all cases, then fail their process if any cycle fails.
10. Found a fixture flaw: deleting Cube during initial physics admission left
    inconsistent native collision in the cap20/cap60 comparison. Explicitly
    disabling its component/actor collision in owned PIE resolves the comparison.
    Old evidence is retained and is not used to claim full-crowd exact FPS parity.
    The saved map and production scene-collision implementation are unchanged.
11. Preserved user live lab state/camera/snapshots, map/sword asset bytes, Blueprint
    wiring, PHAT/motors and actual prior joint-limit restoration. No wider gates,
    additional shrink, hidden timeouts or permissive success flags hide failures.

## Final numerical results

- Lab:25/25 numerical suites pass, including the new three-agent captured neck
  regression. Frozen exits remain158/164/165, whole-neck endpoint error below.001deg,
  maximum neck step4.9364deg. The previous~120deg residual is gone.
- Clean native build57.53s;12/12 test groups pass.18,000 independent head samples:
  head2.96e-6deg, neck3.42e-6deg, neck position1.19e-7cm, completion mismatches0.
  Slide geometry500 samples max1.88e-13cm/2.96e-6deg. Bone-order480 cases,
  63,420 samples, no timing/nonfinite/length mismatches.
- Final rebuilt Play matrix:13/13 scenarios complete S and D for all three agents
  (78 actions). Idle/walk/run, kinematic/Sim, moving gaze, turning, acceleration,
  both extreme gaze signs and cap20. No missing ticks or nonfinite transforms;
  world delta1/60. Completion is **not** an assertion that every physical motion
  is smooth; the limitations below remain visible in the metrics.
- Lifecycle11/11 pass: full completion with default/custom neck limits; hide
  during S reach/slide/return; drop; mode switch; destroyed sword; D interruption;
  repeated walking Sim and kinematic cycles, pause/duplicate requests, collision
  and exact angular-limit restoration, and switching back to Sim.
- Corrected clear-lane cap60/cap20 tests:3 complete cycles per agent per run,
  872 captured ticks each,36 total actions. All target/future/physical/equipment
  transforms and scale values are **exactly identical**, phase differences0.
  Observed rates39.42/19.99FPS; this verifies pacing independence in the fixed-step
  setup, not sustained60FPS performance.
- Additional Sim turning/current-gaze run completes3 cycles for each agent,
  825 ticks,18 actions, no missing ticks/nonfinite values. In total the final
  matrix and extended repeats cover132 completed actions, plus lifecycle tests.
- Graph export raw comparison initially failed on node iteration order and
  CRLF conversion in a multiline print literal. Canonical node comparison keeps
  every pin/default/link and newline count and passes all3310 nodes. Reflection
  status3, native_properties0, pin_types0. No dirty packages before final rebuild.
- First final-build attempt raced normal editor shutdown and was refused because
  Live Coding was still active. Waited for graceful exit; retry passed. Startup
  low-disk warning was dismissed only after matching the new editor PID19868.
  No force kill, data cleanup or unsaved-asset loss. Existing unrelated Niagara
  deprecation warning remains. Final normal binaries contain the entire patch.
- Final postflight: TestNN visible in editor19868, Play off, dirty packages0,
  healthy reflection and3310 preserved nodes. Saved map/BP/sword/profile hashes
  match the safety checkpoint. Full sources/lab/scripts/compact receipt pushed
  on `codex/standalone-sim`; large raw captures stay local. Refresh the lab to
  load the neck-factor fix; its saved settings and snapshots are untouched.

## Remaining motion limitations — do not call this perfect

1. **Restoring saved neck limits can cause a physical kick.** The whole commanded
   neck returns correctly, but reinstating the prior limited joints opposes some
   extreme-gaze poses. Diagnostic suppression reduces the player's post-D
   physical neck world step17.87->5.23deg. Normal running without D/S also shows
   neck/head kicks. The suppression is not shipped: the user explicitly requested
   restoration. The broader solution is to make base gaze/neck targets compatible
   with the actual joint rest frames/limits, or deliberately change those limits;
   a hidden D/S delay or leaving joints Free would violate the current contract.
2. **Near-fully-folded arm geometry can turn quickly.** The closest-shoulder
   objective plus S clavicle-neutral return puts shoulder/hand~5cm apart and elbow
   angle175–179.6deg in some saved setups. Kinematic arm steps reach~40deg locally;
   a Sim turning wrist reaches64deg locally while blade world direction changes
   only~2deg. The previous-destination seed prevents branch flips, but cannot make
   this geometry slow while retaining the exact path and slide speed. A coherent
   future solution would include an elbow-conditioning/reach margin in the
   shoulder/path objective; no arbitrary extra joint clamp was added overnight.
3. **Crowd equipment contact can delay real arrival.** In the-.95 NPC-gaze walk
   case, the player's held sword gets deflected despite the hand following its
   target, and S slide begins290 instead of56. Removing only NPCs in owned PIE
   gives S56/87/153 and D193/224/291 at the same player/profile settings. Preserve
   actual collision/arrival rules; this does not prove every deflection's exact
   contacting body. A future collision/grip policy decision is separate from
   authoring another hand interpolation.
4. **Environment hits are not motion-parity failures.** The original NPC3 run
   hits Cube at147–150 even with D/S removed. Keep that stress capture, but use a
   controlled unobstructed lane for timing/trajectory comparisons. Source raw NN,
   authored pose and simulated tracking are reported separately.

## Performance

100 agents, seven repeats per scenario, existing staggered benchmark; milliseconds
per tick. Peak is the median of seven run maxima, with worst observed also shown.

| Scenario | Mean | Peak | Admission peak | Worst observed |
| --- | ---: | ---: | ---: | ---: |
| Idle D | .752 | 1.534 | 1.432 | 2.054 |
| Idle S | .762 | 1.423 | 1.412 | 1.428 |
| Walk D | .752 | 1.530 | 1.345 | 1.570 |
| Walk S | .766 | 1.378 | 1.360 | 1.480 |
| Mixed simultaneous | .727 | 1.442 | 1.344 | 1.458 |
| Mixed arrivals | .641 | 1.297 | 1.235 | 1.309 |

Prior published means.638–.772ms and median peaks1.273–1.502ms are comparable;
these are not perfectly paired machine-load measurements. The intermediate head
fix measured.659–.785ms mean before removing redundant exponentials. Final peak
outlier2.054ms is retained, not discarded as a presumed fluke.

This measures procedural admission/math, not NN inference, skeleton discovery,
cache publication, equipment, physics or rendering. The additional live holster
sampler is measured separately across3 actual Sim agents,7 repeats x1000 calls:
median.6955us/call, maximum.7566us/call (~.070ms for100 calls, not a full100-agent
physics measurement). The target hook is a bounded state/identity lookup, not an
extra solver. Diagnostic capture overhead is excluded. No whole-game FPS claim.

Compact reproducible receipt: [Overnight20261011.json](../Tools/SwordHolster/Overnight20261011.json).
Harnesses: RunLabSuite, RunParity, RunMotionMatrix, RunLifecycle,
ProbeHeadFps, BenchLiveGeometry, SummarizeMotionMatrix and SummarizeOvernight.
