# Physical neck alignment — October 13, 2026

## Subsequent D/S loops and return spikes — October13 correction

User deferred the missed-grip report (item2) and authorized correcting the other
three. They then explicitly chose **everything at least root-local**: the whole
character turn carries the head, while look-in/out speeds govern motion relative
to that root. Spine/pelvis gait compensation remains independent.

Two source errors were isolated; the PHAT topology/collision settings were not
the cause of these loops/spikes:

1. Head history and stabilized holster orientation remained in a fixed world
   frame. NPC root turn is120°/s versus100°/s look-out speed, so the head could
   never catch up. Near a full world turn, the rotation-vector representation
   moved141.9° for an actual1.75° target change; neck distribution inherited it.
   Holster stabilization also opposed root turning while the authored torso
   followed it, pulling the grip out of reach. `SetRootFrame` now transports the
   complete head history (quaternions AND signed vectors) and stabilized holster
   orientation with the root delta. This is root-local behavior represented in
   existing world-space storage; no re-anchoring, clamp or new retained state.
2. During early FK return, the almost straight arm's elbow correction added a
   large axial turn, then captured it as incoming return inertia. The existing
   tip-alignment roll-transport rule now also applies here: keep the final elbow/
   wrist positions and hand rotation, carry each segment's existing roll through
   its direction change. Shared helper avoids duplicating the same rule. No speed
   clamp, inertia reduction, forced completion or changed grip threshold.

Current unchanged-BP captures:591 consecutive ticks each in sim and kinematic,
three agents, all motion/gaze/profile inputs untouched (kinematic test changes
only simulation mode at tick6). Sim NPC head yaw range now66.83/70.77° versus
970.97/803.21°; maximum base rotation-vector step1.14/3.73° versus269.77/276.19°.
Player gaze is deliberately changing, so its larger208° range is not labelled
an unwanted loop. Sim D release hand command error is at most.071cm/.260° over
six releases, versus5.36cm/22.74° player and7.70cm/31.87° NPC previously. First
return sword rotation is2.03–3.65° instead of20.7–31.6°. Player second-S physical
hand rotation on the first return tick falls61.99→2.67°; the maximum commanded
step over the next15 ticks falls110.58→8.45°.
There is still ordinary running/return movement, not zero world displacement.
No claim of bitwise sim/kinematic timing or universal motion perfection.

Lab code/tuning, Blueprint wiring/defaults, PHAT and scene unchanged this turn.
User BP and TestNN remain dirty. Runtime patch is implementation-only, loaded
through Live Coding without restart. Normal DLLs still need a normal build before
cold launch. Evidence: `Saved/Diagnostics/DSFourIssues20261013/`, notably
`comparison.json`, `coverage.json`, raw captures and the reproducible scripts.

The added work is a few rotation transports per active D/S root change and two
segment swings inside the existing held-arm solve. No new tick, inactive-agent
history capture, solver pass, allocation or retained layout. No new performance
benchmark was run, so no measured runtime-cost claim is made.

Final regression run initially found a stale `LabChannels` fixture: it set slide
progress to1 at tick90 but left sheathing insertion at0. Production correctly
uses insertion for the sheathing look-out threshold, so the test never started
looking out while its recorded lab reference did. Corrected that one test input;
no expected output, threshold, lab file or gameplay behavior was changed. The
`HeadStep` function is byte-identical to the pre-fix source. Final rerun: all3
focused tests pass:
- `HeadRootFrame`:720ticks for each of−2/+2/+7° root turn per tick; root-local
  head/neck path error≤.00000513°, same completion ticks and speed, with holster
  stabilization/return also invariant under root motion.
- `HeldArmRoll`: nearly straight moving-arm segment spike113.85→1.95°, preserving
  exact elbow/wrist positions and hand orientation.
- `LabChannels`:18000 recorded head/neck samples, head≤.00000296°,
  neck≤.00000342°/.000000119cm, zero completion mismatches. Slide geometry passes.

Final test-only Live Coding compile109.91s; successful reload at10:18:43UTC,
no object changes/restart. Gameplay source is unchanged from the final sim and
kinematic captures. Editor remains open on TestNN, outside Play; user BP/map
remain dirty and unsaved. Final changes local; no new push.

### Initial observation, retained for provenance

User subsequently reports head loops/backwards motion, missed drawing grip,
draw-release sword spike, and violent post-sheathing hand rotation. They require
all four to be observed before diagnosis or fixes, stopping if any is missing.
The prior controlled tests below are not acceptance of this current setup.

Captured the current unsaved Blueprint/TestNN unchanged, all591 consecutive ticks
and three agents, with no locomotion/gaze/profile overrides. Confirmed:
- Player head backwards around280; NPC actor-relative head yaw travels565°
  between190–350 (another430°), establishing actual loops.
- D release: sword tip moves23.934cm at229, sword turns21.703°.
- S return: hand command turns110.577° at428, physical hand61.992° then63.902°;
  actual hand displacement peaks15.935cm at444. This establishes that the violent
  rotation is already present in the commanded motion, not solely physical response.
- The large missed D acquisition was **not reproduced**: the three captured
  acquisitions at211/391/571 have grip gap.326/.890/.933cm and1.44/2.00/2.47°.

Stopped before changes as requested; need the affected agent/tick for that missing
case. No runtime, PHAT, Blueprint, lab, or tuning edits. Owned Play ended, editor
open; user Blueprint and TestNN remain dirty. Evidence and repeatable capture/
analysis in `Saved/Diagnostics/DSFourIssues20261013/`. The capture begins at1 and
ends591 with no missing ticks; current Blueprint drives moving/changing-gaze inputs.

## Current result

Saved the corrected original PHAT and loaded the runtime changes through Live
Coding. Unreal remains open on TestNN, outside Play. No restart was performed.
**Normal DLLs are stale: build normally before the next cold launch**, particularly
because the saved asset now has 23 bodies and 22 joints.

Pre-change recovery checkpoint, including lab, saved Blueprint, sword, scripts
and original PHAT: `3c8d11b6c7778dd7815076fa31130e7fa16899d6`, pushed and verified
on `codex/standalone-sim`. Final changes remain local. The user's TestNN edits
and dirty map are preserved. Lab files, Blueprint graph, saved Blueprint and
sword bytes match the checkpoint.

## Decisions and implementation

- Keep the original PHAT; append `neck_02` without renumbering existing bodies
  or joints. Connect neck_01 → neck_02 → head using reference-skeleton anchors.
  The old head-to-neck_01 shortcut had incompatible targets when neck_02 bent.
- Preserve existing constraint tuning and profiles. The new joint inherits the
  original head/neck profile. Existing D/S code discovers it by bone name and
  restores its exact angular modes and values on completion or interruption.
- Automatic fitting was inspected but never applied: dominant weights produced
  a .505 cm radius, any weight a 13.659 cm radius. User approved copying the
  existing capsule size (radius 6.25 cm, cylinder length 2 cm), centering the new
  capsule halfway from neck_02 to head, and splitting the existing 1.194967866 kg
  neck mass equally: .597483933 kg each. Lower-neck geometry stays unchanged.
- Permanently exclude both necks from head and both clavicles, plus the adjacent
  neck pair, as requested. The new neck inherits the old neck's other exclusions.
- **Head versus either clavicle is suppressed only during D/S**, per the user's
  final answer. Two independently owned scoped pairs begin on physical admission
  and end after the full return, or on cancellation/failure. This does not write
  PHAT or overwrite user collision preferences. The sword component owns the
  scope; existing completion, hide, drop, destruction, reset and mode teardown
  paths release it. No per-tick collision update or new retained runtime layout.
- Remove the obsolete production admission check for exactly 22 bodies/21 joints.
  Existing rig validation remains. Name-based targets, completed physical poses,
  and NN feedback already support neck_02; they now read its real body directly.
  No feedback thresholds, alignment semantics, NN ownership or lab motion changed.
- Update real-asset test counts and live/crowd benchmark counts. Sealed-capture
  replay now validates and iterates its actual body count instead of silently
  assuming 22. Synthetic 22-body math fixtures remain synthetic.
- Editor-only `Prophecy.Editor.NeckRig Inspect/Apply` reproduces the asset edit;
  it refuses Play and unexpected/partial topology, does not save automatically,
  and does not halve mass again when rerun. Idempotence was verified before save.

## Numerical evidence

Current stationary second S, player tick 289:

| Measurement | Corrected chain, head/clavicle contacts on | Final D/S exclusion |
|---|---:|---:|
| Head position error | 1.3261 cm | .0551 cm |
| Head rotation error | 1.4395° | .0601° |
| Physical head travel, ticks 283–293 | 2.6932 cm | .6689 cm |
| Commanded head travel, same ticks | .7016 cm | .7016 cm |

Final NPC head errors at 289: .0770/.0825 cm and .0912/.0977°.
No neck/head self contacts in the final 270–300 capture. Rendered versus native
neck/head positions agree within 8.6e-14 cm. Commanded neck joint anchor gaps are
below .000006 cm, versus the original shortcut's 1.34064 cm contradiction.
These are numerical samples, not a claim of perfect physical tracking.

Six live idle/walk/run × kinematic/sim cases completed two S→D cycles on three
agents each: 72 actions, no missing capture ticks or nonfinite bone values.
Maximum active head position error: kinematic <1.1e-13 cm; sim idle .4628 cm,
walk .7463 cm, run 1.6389 cm. Maximum physical head step: 2.8403/2.8676/2.9084°
respectively (authored cap about 2.8333° per tick). The moving tests disable only
the known blocking Cube's collision in owned PIE; saved scene stays unchanged.

Ten neck-limit/contact lifecycle cases pass: ordinary and custom completion,
hide during reach/slide/return, drop, mode switch, sword destruction, draw-side
hide with custom limits, and reset. Completion removes exactly two head/clavicle
pairs; hide/drop/destruction return scoped counts to their prior unrelated base.
Custom neck01/neck02/head limits and a user-disabled head/left-clavicle preference
survive. Mode/reset changes occur at the physics boundary; a later new Blueprint
request is distinguished from the cancelled action. Two additional walking
repeat/pause cases pass in sim and kinematic mode, including switch back to sim
with the original non-simulating holster preference restored.

Final focused automation: **57/58 pass** across physical pose composition, query
publication, native body feedback, target helpers, angular limits, contacts,
mode switching, physical start, sword collision, attack feedback and Get Up.
Normal-gain stress completes 360 steps at both 60 and 30 Hz; deliberately excessive
10× gain exercises the pre-existing contained numerical-failure path.

**Unresolved pre-existing test:** `AuthoredTrajectoryAcrossSubstepChanges`, which
alternates 16.6668 and 17.0364 ms. With matching zero gravity in UE and Jolt, the
stationary pelvis speed exceeds its .5 cm/s bound at step 32: new rig .6074 cm/s,
original checkpoint PHAT .5201 cm/s at the same step. The test is still failing;
no tolerance relaxation or gameplay workaround was added. Temporary original
PHAT copy and probe code were removed after this comparison.

Other test corrections exposed by this audit: compare rigid position/rotation
separately from visual scale; count both existing sword hand/forearm exclusions;
retain user collision preferences across rebind; prevent a second automatic
world initializer in the explicitly initialized backend fixture. Lifecycle
fixtures capture before D/S starts and preserve the actual holster simulation
preference rather than assuming the holster is simulated.

## Cost, build and evidence

Runtime additions are one physical body, one anatomical joint, and two event-owned
contact pairs per active D/S agent. No new always-running pose recorder, solver,
collision polling or feedback conversion. Benchmark source compatibility was
compiled, but **no fresh whole-game/crowd performance measurement was run**;
historical timings are not presented as new-neck measurements.

Final layout-safe Live Coding build/reload passed (40.59 seconds for the final
benchmark compatibility changes); previous runtime and regression changes are
also loaded. Native Blueprint health: status 3, zero stale native properties or
pin types. PHAT saved hash:
`5c3f98c01afb385ba5a64d7b8910f0850dbbfaa3311941891c4bca83bbc9bb9d`.
No unrelated content saved; TestNN remains dirty.

Evidence: `Saved/Diagnostics/NeckRig20261013/`:
- `asset-apply.t3d`, `asset-changes.diff`, `asset-report.json`, `postflight.json`;
- `live-comparison.json`, paired `*-detail.json`, `motion/analysis.json`;
- `lifecycle-final/` plus `lifecycle-mode-final/` for the final mode result;
- `tests-final.log`, `legacy-control.txt`, retained temporary probe source;
- compact tracked receipt: `Tools/SwordHolster/PhysicalNeck20261013.json`;
- original diagnosis: `Saved/Diagnostics/HeadParent29020261013/root-cause.json`.

Preliminary failures remain in the evidence directory. They are not overwritten
or counted as passes. The pre-save BP backup predates the saved Git checkpoint;
final byte comparison uses the pushed checkpoint, and full graph comparison is
also exact.
