# Drawing completion forward snap — October 12

Diagnosis only, preserving the user's20% debug shrink. No implementation,
Blueprint, profile, lab or saved tuning changes; no build/restart.

## Reproduction

No user Play existed. Owned current-setup simulation to absolute350 reproduces
the possessed agent stuck in Reach while both NPCs complete S then D. Left NPC
is BP_ProphecyManualPoseAgent_C_2 (initial X≈-396.5; player X≈16.8).
Captured retained sword scale is.8. Its sequence:

- S slides79–108, full return completes160.
- D begins195, slides221–239; early FK starts238.
- Sword transfers to hand and temporary grip is destroyed239.
- Unshrink/return lifecycle completes284.
- New NN future changes abruptly286; displayed/physical forward burst287–288.

The hand's pelvis-translation-relative commanded step is5.1662cm at287 and
5.0087cm at288, almost entirely forward (+Y). Physical steps5.2073/5.0854cm
follow that command. Final D/S-to-base step284 is only.5842cm; FK error relative
to its current base is.6101cm on283. This specific late burst is not the sword
parent switch or the earlier sliding/early-return discrepancy.

## Isolated cause: right-hand position feedback resumes

During active D/S, `RetainNNUpper` in ProphecyNNLocomotionManager.cpp retains
the NN upper state instead of feeding the authored physical upper pose back
into inference. When D/S finishes, that guard turns off. The feedback code in
ProphecyNNPhysicalFeedbackBatch.inl can replace the recurrent upper state and
history with the sampled physical state.

Controls use the same setup and preserve the recurrent prefix, changing only
temporary owned PIE tolerances at absolute280, before completion:

1. Block feedback for clavicle_r, upperarm_r, hand_r (10000cm/180deg).
2. Block ONLY hand_r POSITION feedback (10000cm), keeping its existing angular
   tolerance35deg. Original hand positional tolerance is5cm.

Both controls have identical target/future/physical poses to baseline through
285 across every captured bone. The first future divergence is286, first
presented/physical divergence287. Both reduce commanded steps287/288 to
1.6146/1.5572cm, and their right-hand trajectories agree at those ticks.
Thus resuming hand POSITION feedback is sufficient to explain the extra forward
burst. No collision, grip, solver, FK timing or angular-feedback intervention was
needed. This is an input handoff issue that produces a new NN command, rather
than physics independently throwing the hand forward.

Separate kinematic capture completes D at284 without that burst: steps287/288
are1.543/1.489cm. Its earlier motion differs, so it is supporting evidence;
the late-intervention matched-prefix controls establish causality.

The exact raw recurrent-vector mismatch/velocity jump at re-admission has NOT
been captured. Do not claim a particular coordinate, projection or history bug
inside that handoff as proven. The implementation guard changes abruptly at
completion; diagnosis identifies the specific feedback channel responsible.
Permanent feedback suppression or increased user tolerance is not a proposed
fix. A future fix should reconcile the return destination and the recurrent
hand-position state/history at handoff, keeping intended feedback afterward.

## Evidence and cleanup

`Saved/Diagnostics/HolsterDrawRelease20261012/`: current.json, kinematic.json,
arm-feedback-control.json, hand-position-control.json, receipt.json, window/
summary/comparison scripts. All four completed captures use a temporary60FPS
cap, restored afterward; only owned PIE was ended. Earlier no-arm-feedback.json
is an aborted harness attempt: it tried to set unsupported lowerarm_r feedback
at280 and stopped. It is not a completed control; corrected probes only use
supported feedback bones. Changes affect PIE instances only.

Earlier draw sliding/return excursions around239–252 also exist in the capture;
this diagnosis does not claim to explain all D/S motion issues. The previous
reach-deadline snap fix and the deferred sword-tip aiming problem are separate.
