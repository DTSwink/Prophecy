# D/S handoff correction — October 12

## Problem and evidence

The user's debug shrink remains20%. Left NPC C_2 finishes D at absolute284;
its commanded hand jumps forward5.166/5.009cm at287/288. Blocking only hand
position feedback at280 preserves every captured bone through285 and reduces
those steps to1.615/1.557cm. See HolsterDrawReleaseDiagnosis20261012.md.

Raw NN tracing confirms the first changed inference is286. Only upper-input
indices165–167 (current right-hand position) differ: +.00862,+.06264,+.11285m.
The previous90-value frame is identical. The feedback correction is~12.94cm
AFTER the user's5cm deadband: the original mismatch is~17.94cm. Physical tracking
error against the displayed target is only~.1cm at285. This is not a physical
hand throwing the NN off by18cm: the absolute feedback sample and recurrent
state refer to different presentation times/root frames, and the recurrent
hand precedes the fixed-arm-length projection.

Evidence: Saved/Diagnostics/HolsterHandoff20261012/before[-nn].json[l],
position-control[-nn].json[l]. Trace rows are paired to absolute Blueprint ticks
using world time; authoring is still60 unpaused ticks/sec.

## Decisions / implementation

1. Extend the existing Jolt completed-target pairing from lower bones to the
   full25-bone NN skeleton. Keep one stable name set through entry, early return,
   release, interruption and rig re-admission. Reuse existing binding/revision
   checks and target capture; no new timer, solver, inference or frame delay.
2. Encode actual and commanded upper poses in the same current recurrent frame.
   Apply their position/rotation deviation to current NN state, then use the
   unchanged per-bone feedback tolerances/history commit. This fixes the shared
   Jolt upper feedback path, rather than suppressing feedback for a few ticks.
   The underlying issue also exists outside D/S; it must not return afterward.
3. D/S still retains underlying NN upper recurrence while authoring. Skip upper
   deviation encoding in this case, while keeping the paired capture available
   for release. Lower feedback stays active. Kinematic and legacy Chaos paths
   retain their existing behavior.
4. Zero deviation preserves both recurrent frames exactly. No extra quaternion
   cleaning may alter an already identical aligned upper sample. Genuine
   tracking errors still feed back (tested8cm with5cm tolerance =>3cm;
   20deg with5deg tolerance =>15deg).
5. No lab, profile, Blueprint wiring, deadband, timing, shrink or handoff-duration
   change. The existing return continues to its current NN pose; this correction
   prevents unrelated presentation differences becoming NN input on release.
6. Added a development-only A/B switch Prophecy.NNUpperFeedbackAlignment;
   default1 is corrected,0 is legacy. It is absent from Shipping. Live comparison
   switches it just before release to retain an identical causal prefix.
7. Prepared alignment storage grew: one normal build/restart, preserving and
   backing up the dirty PoseAgent Blueprint and TestNN map first. Build succeeded
   in96.45s. Native feedback group6/6 passed, including100-agent mixed ownership,
   serial/prepared/parallel parity and new upper target alignment tests.

## Live verification

Pending. Initial interactive reopen did not expose a main window or remote
Python after startup shaders. User redirected to Recycle Bin storage cleanup.
A subsequent editor20948 appeared during cleanup and now exposes its main window;
it was left untouched. Do not treat native tests as proof of live visual quality.
No push requested/performed.
