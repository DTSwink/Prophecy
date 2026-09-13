# Forearm target roll from hand orientation

2026-09-12. The user's current `testNN` setup exposed continuous right-forearm rotation with arm physical feedback enabled. The physical body was following an incorrectly reconstructed target, rather than ignoring its magnetisation.

## Cause

The upper-body NN predicts the upper-arm orientation and hand position/orientation. Lowerarm orientation is not a direct NN output or physical-feedback input. Runtime reconstruction previously located the elbow from the upper arm, aimed the forearm at the hand, and chose its roll by projecting an upper-arm pole onto the plane perpendicular to that aim. It did not use the hand orientation to determine forearm roll.

In the captured right-arm pose, that pole is nearly parallel to the forearm (projected length 0.025–0.140 for a unit pole). Small upper-arm changes move the projected direction around the forearm axis; normalization turns this into large target-roll changes. Physical feedback changes the upper-arm input, so the reconstructed forearm target can spin indirectly even though no lowerarm transform is encoded as a feedback input.

## Change

`ForearmRotationFromHand` in `ProphecyNNLocomotionManager.cpp` starts with the NN hand orientation and applies the shortest swing that aligns the forearm's signed local length axis with elbow-to-hand direction. This uses the shared neutral hand/forearm basis of the upper-body runtime contract. The forearm carries hand roll; their relative target rotation contains wrist swing, without an independent axial twist. Both left and right arms use their existing signed local axes.

The upper-arm target still determines the elbow. Hand position, length clamping and hand orientation are unchanged. The zero-distance fallback retains the hand frame; the exactly opposite-direction case uses a deterministic perpendicular axis in the hand frame. No prior-frame or simulated forearm rotation chooses the target. The obsolete upper-arm-pole reconstruction was removed.

This changes the shared locomotion target generation used by Chaos and Jolt. It does not modify the trained NN or its input layout, feedback tolerances, magnetisation, joint angles, prediction switch, simulation timestep, physical constraint response, or authored full-body attack data. It adds no per-agent allocations, persistent history or extra passes.

## Numerical verification

Unmodified current scene, 35-second captures before/after. Statistics below use the final 30 seconds, after five seconds of startup. `capture_before.json` and `capture_after.json` are in `Saved/Diagnostics/ForearmTarget/`; `Analyze.py` produces `comparison.json`. Both captures use Jolt. Prediction preference is true, but the actual wrist and elbow angular modes in this particular setup are Free. No limit/Boolean/feedback/gain setters were invoked by the capture script.

| Right-arm measurement | Before | After |
| --- | ---: | ---: |
| Forearm target maximum orientation difference from start of measured interval | 179.99° | 22.54° |
| Physical forearm maximum orientation difference | 179.97° | 22.70° |
| Maximum forearm tracking error | 0.524° | 0.312° |
| Hand target maximum orientation difference | 37.97° | 37.93° |
| Maximum hand tracking error | 0.922° | 0.094° |
| Maximum absolute hand-to-forearm target twist (interpolated targets) | 179.80° | 0.047° |

The baseline's small forearm tracking error is decisive: magnetisation was following the spinning target. The corrected target and actual forearm no longer make those full rotations in this setup. The earlier wrist-limit activation/cache repair remains a separate valid change; it was not a complete explanation for this target-generation defect.

`Prophecy.NN.PhysicalTargets.ForearmRollFromHand` covers both signed arm axes, hand pronation through a full turn, wrist bend without added forearm twist, aim alignment and finite zero/opposite-direction cases. The existing interpolation/rigid-forearm, source/asset-change and sparse/full target tests also pass. Normal Development Editor build succeeded. This is verification of the reported scene and target policy, not a claim that all possible ragdoll/limit/feedback settings have been validated.

Final normal-build verification repeated the unchanged scene for 35 seconds (`capture_normal.json`): right forearm target excursion 22.5378 degrees, physical excursion 22.7000 degrees, max tracking error 0.3119 degrees; max absolute interpolated wrist target twist 0.0473 degrees. All four PhysicalTargets tests passed again in the normal build, without warnings/errors (`Tests.log`). Unreal remains open on testNN with PIE stopped.
