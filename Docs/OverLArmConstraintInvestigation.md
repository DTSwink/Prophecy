# OverL left-arm separation — 2026-09-19

Confirmed in the user's current `/Game/testNN` setup on possessed
`BP_ProphecyManualPoseAgent_C_1`, performing periodic `overL` attacks in Jolt.
The measurement is the distance between the two **native joint anchors**, obtained
from each constraint's current body COM transform and constraint-to-body matrix.
It is not a bone-origin-distance estimate or a rendered mesh measurement.

## Reproduction and isolated comparisons

Each trial starts fresh PIE from the same editor setup, records 600 frames (ten
attack starts), and ends PIE. Settings change only on runtime instances at frame30;
the table covers frames60–600, 541 samples per joint. The existing attack sequence,
profiles, colliders, sweeps, CCD, targets and Blueprint logic remain in place.
No user assets were saved or edited, and Unreal was not restarted.

Maximum native anchor separation, centimeters:

| Runtime trial | Left shoulder | Left elbow | Left wrist |
|---|---:|---:|---:|
| Baseline: 10 velocity / 2 position, normal stepping | 5.8157 | 6.7086 | 5.8364 |
| 40 velocity / 2 position | 5.6033 | 6.6643 | 5.8627 |
| 10 velocity / 8 position | 2.7369 | 2.7693 | 2.3216 |
| Baseline iterations, minimum 2 collision substeps | 2.4009 | 2.7451 | 2.4058 |
| 10 velocity / 32 position | 0.5987 | 0.5535 | 0.5330 |
| 10 / 32 applied only to possessed attacker | 0.5987 | 0.5535 | 0.5330 |

The attacker's baseline elbow maximum occurs at sample264, learned attack frame13
(Armed and Hit true). The initial separate reproduction measured6.708567cm,
compared with6.708558cm in the baseline. The final attacker-only repeat exactly
reproduced the measured 10/32 results while the other agents retained0/0 overrides.
Elbow mean/p95 dropped from1.3149/5.3850cm to0.0671/0.3086cm. The worst elbow
separation decreased approximately91.75%; this is a mitigation, not zero error.

## Interpretation and upstream evidence

The constraint is present and responds to solver changes. More velocity iterations
alone scarcely help; additional position correction and smaller simulation steps
help substantially. This supports insufficient positional convergence/drift
correction during this fast driven motion. It does not identify a missing constraint
or establish a specific upstream engine bug, nor isolate every contribution from
contacts, independently driven targets and angular integration.

- [Jolt's architecture](https://github.com/jrouwe/JoltPhysics/blob/master/Docs/Architecture.md)
  describes the iterative velocity solve, integration, and subsequent position solve
  that corrects drift/separation. This matches the successful experiment direction.
- [Maintainer discussion1077](https://github.com/jrouwe/JoltPhysics/discussions/1077)
  explains that even fixed constraints are not perfectly rigid. Compounds solve rigid
  attachment, but would remove the arm's articulation and are not appropriate here.
- [Animated-ragdoll discussion122](https://github.com/jrouwe/JoltPhysics.js/discussions/122)
  includes weak constraint behavior and iteration tuning. Its low-iteration setup
  differs from ours: our baseline already uses the default10/2.
- [Constraint iteration documentation](https://jrouwe.github.io/JoltPhysics/class_constraint.html)
  confirms overrides use the maximum requested count across a connected island.
- [Physics settings](https://jrouwe.github.io/JoltPhysics/struct_physics_settings.html)
  documents default10 velocity/2 position iterations and Baumgarte0.2. Baumgarte,
  mass/inertia stabilization and alternate drive models were not modified or tested.

## Usable control and remaining limits

Existing Blueprint node **Set Jolt Solver Iterations**, Target=the attacker,
Velocity Iterations=10, Position Iterations=32 gives the strongest tested improvement.
0/0 restores normal defaults. It can be applied during attacks and restored afterward;
the experiment used a constant runtime override, so the transition itself was not tested.
This requests work for the connected island, potentially including touching agents,
rather than guaranteeing isolated per-agent cost. No performance benchmark was run.

The investigation itself changed no gameplay default. Its native diagnostic edit
extends the explicitly invoked `Prophecy.Jolt.ContactExperiment capture` command
to include left-arm anchors. No continuous diagnostic work is added.

## Accepted special-state policy

The user subsequently requested automatic10/32 during **specials**: attacks,
active parries and active dodges. These now override the configured locomotion
iteration counts on entry, restoring them on exit/cancellation/interruption.
Queued defense waiting for Armed retains the agent's ordinary behavior/settings.
Attack and defense flags compose, so ending one cannot undo another active special.

The configured locomotion values are never overwritten: an explicit solver setter
used during a special updates what will be restored on return, while the effective
counts remain10/32. `Get Jolt Solver Iterations` reports effective counts. Rig
creation/rebinding uses those effective counts, including kinematic-to-sim changes
during a special. At the usual0/0 configuration, exit restores Jolt defaults10/2.
Changes run only on lifecycle events; there is no new Tick, per-frame poll or work
in ordinary locomotion. Transient state is removed when the agent ends play.

Validation: Live Coding build succeeded; `Prophecy.Jolt.SpecialSolver.Lifecycle`
passed (custom restoration, repeated notifications, overlapping states, setter
during a special and default restoration). A180-frame current-setup capture
recorded73 attacking samples at10/32 and107 locomotion samples at0/0, without
effective-policy mismatches. Native elbow diagnostics also confirmed both iteration
states. Evidence: `Saved/Diagnostics/OverLArm/specials_auto.json` and the editor log.
This verifies automatic switching, not that post-attack locomotion retains the
smaller errors measured with a permanently enabled32-position-iteration override.

Evidence: `Saved/Diagnostics/OverLArm/summary.json`, per-trial pose and native-anchor
JSON files; capture script `Saved/Diagnostics/capture_overl_arm.py`; extractor
`Saved/Diagnostics/OverLArm/summarize.py`. Native source log is
`Saved/Logs/GameAnimationSample3.log` (`CONTACT_EXP,<trial>_<agent>_<sample>`).
