# Right physical foot jiggle, ticks 173–182 — September 29

Fixed September 29, Live Coding loaded17:54:44 UTC. The investigation below records the original behavior.

## Fix and validation

Recovery now passes the snapshot's local calf-to-foot axis into `ProphecyRecoveryLegLength::Resolve`. The calf's shortest swing aligns that anatomical axis with the reconstructed knee-to-foot direction, preserving its transported roll, the accepted foot transform and both requested segment lengths. Straight-leg singularities retain the knee/pole and still correct the calf aim. The shared presentation path supplies both NN rendering and physics targets. No joint limits, foot targets, inference, retained layouts, Blueprint pins, or assets changed. Inactive recovery performs no new work; active recovery reuses its existing snapshot and replaces the old aim calculation.

Three focused tests passed17:55:02 UTC: RecoveryCalfAim, RecoveryCalfLength, RecoveryUpperHandoff. New regression covers a misaligned midpoint at multiple rolls, minimal swing, endpoint/length preservation, repeated evaluation and a straight leg.

Matched205-tick replay completed and owned PIE ended. Pre-recovery NN positions and foot targets throughout173–182 are unchanged. Maximum right-foot tracking error in that window falls1.40576→0.08927 cm (under0.9mm), removing the centimetre-scale alternating displacement:

| Tick | Before error (cm) | After error (cm) |
| --- | ---: | ---: |
| 173 | 1.40576 | 0.08087 |
| 174 | 0.05172 | 0.04036 |
| 175 | 1.23673 | 0.08927 |
| 176 | 0.05152 | 0.04080 |
| 177 | 0.94676 | 0.05996 |
| 178 | 0.04016 | 0.02974 |
| 179 | 0.69688 | 0.02952 |
| 180 | 0.02898 | 0.01954 |
| 181 | 0.39121 | 0.02794 |
| 182 | 0.02633 | 0.02101 |

Evidence: `Saved/Diagnostics/Knee202/foot_jiggle_calf_aim.json`, `Saved/Diagnostics/CompareCalfAim.py`, `Saved/Diagnostics/TestCalfAim.py`. No full suite, editor restart or explicit asset save.

## Original investigation

The current physical rollout reproduces an alternating error against the presented NN foot target. Full slashR begins at 144 and changes to half attack at 167; this window is already using locomotion legs and lower recovery. Neither foot is owned by attack-foot locomotion authoring.

| Tick | Right foot position error (cm) |
| --- | ---: |
| 173 | 1.4058 |
| 174 | 0.0517 |
| 175 | 1.2367 |
| 176 | 0.0515 |
| 177 | 0.9468 |
| 178 | 0.0402 |
| 179 | 0.6969 |
| 180 | 0.0290 |
| 181 | 0.3912 |
| 182 | 0.0263 |

Odd ticks have pose interpolation alpha approximately 0.5; even ticks approximately 1. Physics publication tracing confirms its final foot target equals the presented NN target. The target moves smoothly a little; the physical body adds the visible zigzag. Both foot drives remain linear/angular strength 1 and joint damping 0.

The intermediate target pose is geometrically inconsistent: at 173 the target foot in target calf coordinates is (38.039, 2.418, 1.157) cm; at 174 it is (38.175, -0.097, -0.385). The latter lies along the authored calf/ankle axis. At 173 the physical foot correction in that frame is (-0.073, -0.897, -1.080) cm, toward that axis.

`AProphecyAgent::ReadNNFutureWorldPoseWithSnapshot` blends world positions and rotations independently, then calls `ApplyRigidCalves`. During recovery, `ProphecyRecoveryLegLength::Resolve` repairs lengths by rotating from the interpolated joint-position directions to the new directions. It preserves any existing mismatch between the interpolated calf orientation and its actual knee-to-foot direction. Thus the midpoint pose asks the ankle translation constraint and body drives to satisfy incompatible targets. Endpoints align again, accounting for the alternating error.

`ProphecyJoltFootExtension::Settings` permits calf-axis translation and locks both transverse axes; angular-limit disabling does not remove those linear constraints. Calf allowance is about 19.5 cm here, but that is axial allowance, not lateral freedom.

Owned comparison captures disabling self-collision, joint-limit prediction, or authored angular limits produced identical errors. A further calf-angular-drive setter comparison also produced identical errors; it is inconclusive because current Blueprint tick/profile writes can override that setter before simulation. Do not treat that last comparison as a validated drive isolation.

The recommended anatomical-axis correction is now implemented and validated above.

Evidence: `Saved/Diagnostics/CaptureFootJiggle.py`, `AnalyzeFootJiggle.py`, and `Knee202/foot_jiggle_{baseline,trace,no_prediction,no_self,no_limits,no_calf_angular}.json`. Each owned replay completed 205 ticks and ended its own PIE. Foot target tracing was reset to zero. No full suite, asset save, or editor restart.
