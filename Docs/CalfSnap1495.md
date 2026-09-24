# Calf snap at ticks 1494–1495

Confirmed numerically on 2026-09-24 after the user restored their Blueprint setup.
Initial investigation left gameplay untouched. The shared recovery below was
subsequently authorized and implemented without graph/settings changes.

The possessed `BP_ProphecyManualPoseAgent_C_1` is kinematic. Its full `jabR`
ends at tick1494; the first interpolated locomotion pose appears at1495.
The other two captured agents remain stationary.

| BP tick | Left knee–ankle distance (cm) | Rendered calf-tip gap (cm) | Calf scale X |
| --- | --- | --- | --- |
| 1493 | 45.355 | 2.791 | 1.00000 |
| 1494 | 45.239 | 2.675 | 1.00000 |
| 1495 | 43.871 | <0.00001 | 1.03070 |
| 1496 | 42.564 | <0.00001 | ~1.00000 |

The right tip gap also closes in one tick:2.197cm to approximately zero.
Left calf angular steps at1494–1496 are about0.69,1.90,2.03degrees; this event
is not a large calf roll flip. At1495 the left knee moves1.795cm while the ankle
moves only0.236cm.

Two handoff discontinuities coincide:

1. `ProphecyKickFootLeeway::Begin` only creates an active episode for kicks with
   configured nonzero leeway. `End` cannot capture an outgoing calf-length return
   without that episode. A jab therefore lacks the kick-specific signed length
   recovery. The first locomotion future target is already at reference length
   (42.563cm), reached through the usual two-tick interpolation.
2. `ProphecyNNLocomotionAnimInstance.cpp`'s `ExtendCalfToFoot` resumes outside
   attack presentation. It immediately scales the rendered calf to the ankle
   unless `HasRecoveryCalfLengths` is active. At1495 that changes calf scale X
   from1 to1.03070 and closes the visible gap immediately. Authored target scale
   remains1, so checking target positions alone misses this visible snap.

This is the same presentation discontinuity documented in
[the kick regression](KickExitCalfLengthRegression.md), outside the scope of its
kick-specific recovery. The appropriate remedy is shared outgoing calf-length
and render-scale continuity for special-to-locomotion transitions, retaining the
accepted kick path and no ongoing recovery work once normal.

Evidence: `Saved/Diagnostics/Calf1495-capture.json` (Complete,453 rows,
three agents over151 ticks1380–1530), `Calf1495-analysis.json`, and the matching
`Calf1495-nn.jsonl`. Scripts: `CaptureCalf1495.py`, `AnalyzeCalf1495.py`.
Tip gap uses the reference ankle offset transformed through the evaluated calf
world rotation and scale, including authored transverse scale1.12.
`Calf1495-before-bp-restored.json` is an interrupted earlier setup and is not
evidence for this event. The diagnostic Play session ended and trace was disabled;
Unreal remains open.

## Implemented shared recovery

`ProphecyKickFootLeewayLibrary.cpp` now supplies a pose-only clock when a full
special exits without an active kick allowance. It captures the outgoing signed
calf lengths and uses the existing reconstruction, presentation and render-scale
continuity path. Parry/dodge capture before their pose is removed or root moves.
Half attacks keep locomotion legs. Configured kick return duration is reused when
present; otherwise60 unpaused ticks. Explicit configured zero duration is immediate.
The new path does not modify physical joint allowance; active kicks retain their
existing joint/pose clock. New specials, reset, completion and world teardown
retire the pose-only clock, length state and presentation override. No additional
inference or recovery pose processing remains at normal. The leg-chain diagnostic
disable still bypasses correction through the existing shared check.

Live build succeeded in66.61s, loaded17:41:39UTC. Six focused tests passed:
kick behavior, measured positive/negative jab lengths,60-tick timing at30/60/120FPS,
new-special/reset cancellation and cleanup. Pose BP status3, zero stale types.

The controlled comparison uses editor-only, event-time diagnostic
`Prophecy.Debug.SharedCalfRecovery` (default1). Baseline keeps it0; paired replay
enables it at1493. Every recorded bone position1380–1493 is **identical**.
The first post-exit calf-tip gap change falls:

| Foot | Before (cm) | After (cm) |
| --- | --- | --- |
| Left | 2.675453 | 0.002300 |
| Right | 2.197430 | 0.001812 |

Calves retain authored scale during the return. At1553 gaps are0.00230/0.00181cm;
at1554 they are approximately zero with normal scaling. Capture uses the actual
outgoing displayed pose at1493, holding its length at exit1494, consistent with
the existing kick path.

Fully enabled1565-tick replay covers16 exits: hooks, jabs, headbutt, overL and both
kick sides. Maximum first-return gap change0.004121cm; all transforms finite.
That later rollout is not used as evidence of unchanged input history. Isolated
defense lifecycle replay passes natural/stopped parry and dodge,470 finite samples;
this verifies lifecycle, not quantitative defense tip continuity or dynamic contact.

Evidence in `Saved/Diagnostics`: `SharedCalf-baseline.json`, `SharedCalf-paired.json`,
`SharedCalf-comparison.json`, `SharedCalf-all.json`, `SharedCalf-sequence-check.json`,
`SpecialRecoveryLive-20260924-194841.json`. Automation interrupted the first capture
attempt; those invalid files were replaced by complete captures after tests.
Isolated Python namespaces now prevent callback-state overwrite between runs.
The aborted harness's orphan callback was neutralized; authorized restart clears it.
User authorized saving/restarting; BP saved before closing, prior disk backup
`BP-BeforeSharedCalfRestart.uasset`.

Normal Editor build completed10 actions successfully in45.23s, incorporating
the implementation into the regular DLL before reopening `/Game/testNN`.
Fresh-process verification passed17:52UTC: correct map, shared recovery enabled,
old diagnostic callbacks absent and pose Blueprint native-type inspection clean.
