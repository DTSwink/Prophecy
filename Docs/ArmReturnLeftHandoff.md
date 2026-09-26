# Left elbow discontinuity during arm return — September 26, 2026

**Entire bend/twist winding experiment below is now reverted as well.** After the first partial revert, the user still observed the upper arm flipping on itself and requested comparison with the last Git version. `ProphecyHandChainMath.h` is restored byte-for-byte from HEAD `9d10576`; the extra angle histories, extended Resolve arguments, comparison CVar, stage audit and winding test have been removed from the return library. The immediate live comparison flag was set to 0 before compiling. Both two-pass Resolve calls now use the committed stateless solver. The previous limited metrics did not establish preservation of the accepted right-arm return. Do not reinstall either experiment or call the original left-elbow complaint solved. Subsequent reference/rotation controls remain separate from these reverted solver experiments.

## Rejected and reverted: second Pike NN-only hinge experiment

**User rejected this experiment because it broke the accepted right-arm spine-local return, producing weird rotation and sword/body penetration. Reverted the HingeFollow override and NNHinge feature completely; neutral-to-NN hinge guidance is restored.** The metrics below are historical evidence of a locally improved left elbow, not acceptance of the shared change. Do not reinstall it based on those metrics. The earlier continuous bend/twist fix remains. The user's current instruction is simply to revert, not continue experimenting.

Source revert compiled successfully and loaded at **17:29:14 UTC September 26**; no Blueprint save or restart. No additional behavior changes or rollout experiments during the revert.

The user subsequently reported that removing the snap still left the elbow pointing inward, then turning outward late. The earlier continuity fix below remains. On the repeated-Pike scene, attacks start at 90/180/270 and end at 119/207/299. Source/stage probes confirmed that the first solve imposed an additional inward direction: around the second return's middle, final elbow Y was about 3 cm inward of the incoming NN elbow. The following describes the rejected experiment, not current runtime behavior.

The hand still follows the neutral return path and its configured hold/blend, including length recovery and blade/body clearance. Elbow guidance instead fits the incoming NN hinge to that hand target throughout the return, then smoothly approaches it from the accepted previous hinge. The independently mounted idle hinge no longer competes with it. `ProphecyHandChain::Resolve` accepts an optional separate HingeFollow weight; default -1 preserves all other callers. Length interpolation continues to use the original Follow. Both returning arms use this rule, with no attack-specific gate or new timer. The second temporal solve, winding continuity and clearance remain.

Loaded at **16:44:57 UTC**, normal build still pending next authorized restart. Editor comparison `Prophecy.SlashReturn.NNHinge` is 1; 0 restores the previous neutral guidance. `nn_hinge_latefix` enables it at capture frame 206, preserving all captured poses exactly through 206, immediately before the second attack ends. Maximum inward elbow displacement from shoulder in anatomical torso Y, ticks 207–269: **5.641 → 1.970 cm**. Maximum left upper-arm sample rotation: **15.267 → 12.205 degrees**; minimum bend: **23.998 → 37.355 degrees**. Outward recovery begins earlier. This is improvement, not elimination of every inward excursion.

`nn_hinge_final` enables it throughout all three returns: second-return maximum inward displacement 2.432 cm, rotation step 12.385 degrees, minimum bend 35.721 degrees. Its later poses differ recurrently and are not an identical-state comparison. The first return retained a bent arm; sampled blade-clearance metric was essentially unchanged, 0.8761 → 0.8747 (already below the unit clearance threshold). No universal clearance claim. At 16:48:01 UTC the 14 current SlashReturn/HandRecovery/CoreTempering tests passed (plus the stale ClearDirectPath registration); BP compiled, unsaved. No asset save, restart or user Play interruption. Owned captures completed and ended; Audit 0, all normal comparison flags 1.

Tools: `AnalyzeElbowHandoff.py`, `CompareSecondPike.py`; evidence under `Saved/Diagnostics/ArmReach`: `second_pike_inward`, `nn_hinge_latefix`, `nn_hinge_final`. Residual inward geometry and final visual acceptance are not claimed resolved beyond these measurements.

## Result and scope

The current Pike scene exposed a left upper-arm rotation jump inside the return blend, before its retirement. The active return now preserves continuous bend-angle and axial-twist winding across the ±180-degree boundary. It uses the existing recovery clock; no new smoothing duration, endpoint change or inactive solver work was introduced.

Loaded by Live Coding at 16:19:12 UTC. A fresh normal editor build is still needed before the next authorized restart. No Blueprint wiring, asset save or restart was performed for this fix. User visual acceptance remains separate from the numerical checks below.

## Reproduction and cause

Latest captured scene: one Pike starts at BP tick 90 and ends at 121. Both-arm return and Pike pelvis-local position are enabled; the user wired Pelvis Local Rotation Blend = 0.8, Spine Local Rotation Blend = 0. Root/shoulder motion is substantial, so world elbow travel alone is not a snap metric. These are capture conditions, not feature defaults.

At tick 163 the decoded NN shoulder rotation changes only 3.807 degrees. The first procedural arm solve changes it by 83.208 degrees; the second temporal solve leaves a 70.064-degree step. This identifies reconstruction as the immediate discontinuity, rather than an abrupt raw NN target or the final switch to locomotion.

Two source shoulder frames are aligned to the solved upper-arm direction. Their remaining difference is axial twist. Independent shortest quaternion interpolation changes sides when that difference passes ±180 degrees: the signed twist moves from −128.084 degrees at tick 161 to wrapped +172.537 at tick 163 (continuous −187.463). Maintaining twist winding fixes that jump.

Twist continuity alone was insufficient: source bend poles subsequently approach opposition, and the old ambiguity confidence dropped to 0.09468 before reapplying guidance. That intermediate version created a 40.38-degree step at tick 167 and was rejected. The final version also tracks bend winding; an active temporal return already has a direction through the opposite-pole crossing and need not discard it there. Confidence for nearly straight sources and antipodal aim remains.

## Implementation boundary

- `ProphecyHandChainMath.h`: optional histories for aligned-frame twist and bend interpolation; angle winding uses the nearest continuation to the previous sample. Full following retains the exact target orientation.
- `ProphecySlashReturnLibrary.cpp`: independent histories for primary/extra arms and both solve passes. Remove them on finish/cancel/reset/world cleanup. Weak sidecars preserve retained Live Coding allocation layouts.
- Only active arm return supplies the histories. Stateless hand-chain callers retain their previous interpolation and ambiguity fallback. Legs, endpoint lengths, wrist targets, reference selection, blade route and authored hold/blend times are not retuned.
- Editor comparison CVar `Prophecy.SlashReturn.ContinuousTwist` defaults 1. Setting 0 restores the old independent blend behavior while recording histories for an exact-prefix comparison. Despite its short name it now gates both bend and axial-twist continuity. Normal state is 1; Audit is 0.

## Causal and full replay checks

`Saved/Diagnostics/ArmReach/left_stages` is the instrumented original. In `hinge_latefix`, the old algorithm runs through tick 162, then only the continuity switch changes. All captured bone positions and rotations are identical through 162.

| BP tick | Original left upper-arm step | Final same-state step |
| --- | ---: | ---: |
| 163 | 70.064° | 7.363° |
| 165 | 17.378° | 6.787° |
| 167 | 14.424° | 6.165° |
| 181 | 12.760° | 11.718° |
| 183 | 18.048° | 17.311° |

`hinge_final` is the full 360-tick replay with continuity enabled throughout. Its prefix through 162 differs only by floating-point roundoff (0.000020 cm / 0.000069 degrees). It reproduces the causal improvement and completes the return without the rejected later spike. Maximum left upper-arm step over ticks 122–209 falls from 70.064 to 17.311 degrees; right-arm maximum remains 14.763 degrees. Later recurrent motion is not asserted identical.

Through the measured recovery window, the left arm stays bent (minimum 14.38 degrees), and left hand step-change falls from 6.93 to 1.95 cm. The sampled sword-clearance metric is 0.988 versus 1.017 originally: close but slightly below its unit clearance threshold. This is not evidence of guaranteed collision-free motion. No new hard full-extension lock was recorded by the bounded check.

At 16:21:20 UTC all 14 current tests in SlashReturn, HandRecovery and CoreTempering passed, including TwistContinuity. The editor also ran the obsolete ClearDirectPath test retained by an earlier live patch, making 15 log entries. Pose Blueprint compilation after library-default repair succeeded. This is not a full-project or packaged-build validation.

## Resume tooling

- `Saved/Diagnostics/CaptureArmReach.py`: `hinge_latefix` switches at frame 162 and requires owned PIE; ordinary `hinge_final` captures without changing gameplay controls.
- `CompareLeftHandoff.py`, `CompareArmReach.py`, `AnalyzeLeftSolve.py`, `AnalyzeLeftTwist.py` contain the metrics/stage analysis. The last script reconstructs old confidence math for diagnosis, not a final-solver oracle.
- `SlashSolveAudit` identifies the arm and raw / first-solve / final shoulder, elbow and wrist transforms in actual torso space. Existing SlashReturnAudit fields have different coordinate conventions; see the main journal.
- Preserve user Play. Captures may end only sessions they started themselves. Check current scene and flags before resuming; do not assume the user has retained these reproduction settings.

Related: [rotation blend and torso routing](ArmReturn260AndRotationBlend.md), [hand recovery](HandRecovery.md), [project journal](../ProjectJournal.md).
