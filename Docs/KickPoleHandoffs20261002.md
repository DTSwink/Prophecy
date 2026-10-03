# Kick knee-pole investigation, October 2



The measurements below describe the pre-fix baseline. The subsequent correction fades each procedural reconstruction with its existing blend clock, then retires it at zero. No Blueprint, checkpoint or tuning edits. One owned 280-tick capture of the current setup completed and ended; input and pole tracing were reset to zero. The capture reports `PHYSICAL` mode; measured PhysicalMesh motion matches the authored targets closely, so the identified discontinuities already exist in target generation.



Current possessed agent performs kickL at tick 120 and ends at 145. Its connected Blueprint uses kick tempering fade 0.4 authored seconds (24 ticks), Run/Walk recovery blend 0.5 seconds (30 ticks), kick joint/calf-length return 1 second (60 ticks), and leg reconstruction pole limit 90 degrees per 60 ticks. Thus tempering ends at 169, checkpoint mixing at 175, and length return at 205. Knee soft zone is 1 cm. The previously diagnosed disabled-reconstruction callback from September 28 is disconnected in this setup; it is not the present explanation.



Measured left/kicking leg at the two boundaries:



| Policy tick | Candidate geometric pole step before limiter | Pole step after limiter | Thigh rotation step after limiter |

| --- | ---: | ---: | ---: |

| 169 | 5.074 degrees | 2.645 degrees | 3.282 degrees |

| 203 | 0.063 degrees | 0.063 degrees | 0.189 degrees |

| 205 | 12.524 degrees | 2.895 degrees | 9.858 degrees |

| 207 | 9.753 degrees | 2.913 degrees | 2.790 degrees |

| 209 | 6.937 degrees | 2.933 degrees | 2.827 degrees |

| 211 | 4.066 degrees | 2.952 degrees | 2.878 degrees |

| 213 | 1.140 degrees | 1.140 degrees | 1.102 degrees |



These pole numbers compare native-root geometric hip/knee/ankle directions, not world Euler angles. The limiter transports the previous pole with the foot and hip/ankle axis; its own signed turn budget is 3 degrees per two-tick policy update. The knee radius is approximately 12.37 cm at 169 and 5.39 cm at 205: this is not an undefined perfectly straight knee.



Presented left thigh rotation at 205/206 is 4.929 degrees each tick, versus about 0.095 degrees each at 203/204. The mesh follows those same changes. Presented knee displacement rises from approximately 0.076 cm at 204 to 0.408 cm at 205. The supporting right pole also changes at 205 (candidate approximately 5 degrees), but converges sooner. No corresponding Walk/Run or effective pinning change occurs at 205: both legs are already fully Walk and pinned. Around 169–175 the checkpoint mix is still finishing and supporting-foot pinning changes as well, so that earlier window has additional moving inputs.



The source explains two discrete reconstruction handoffs:



- `ProphecyLowerTemperingLibrary.cpp::Find` retires the tempering settings when all follow coefficients reach one. `NeedsTemperedLegReconstruction` then becomes false, removing `ResolveTemperedLeg` and its foot-facing/hip-front knee guidance at 169. Its guidance is not faded by the diminishing tempering amount, even though the pose-follow coefficients ease smoothly.

- `ProphecyKickFootLeewayLibrary.cpp::Tick` removes `LengthReturns` at tick 205. In `ApplyOutputBatch`, that makes `bReturnLengths` false and removes the remaining recovery leg solve (`ResolvePelvisLeg`) when no other reconstruction reason remains. The final length values have converged, but the reconstructed thigh/knee orientation is not guaranteed to match the normal decoder at this boundary.



`ProphecyLegRecovery::FinishStep` deliberately keeps the pole limiter alive beyond its nominal duration while it is still limiting. The trace continues through 213, confirming that it did not simply disappear at 205. It limits the geometric pole turn but does not make the full thigh-orientation handoff continuous. At 205 the candidate thigh orientation changes 2.187 degrees before the limiter; correcting its mismatched geometric pole raises the accepted thigh rotation change to 9.858 degrees. This is a procedural target handoff, not evidence of a standalone physics disturbance or a raw NN thigh rotation of 9.858 degrees.



The user requested simple existing-duration fades, with no convergence extension. Implemented: tempering reconstruction uses the remaining feet/pelvis blend weights; length reconstruction and presentation use the remaining length-return weight; the pole limiter fades to zero and retires at its configured deadline even if it was still limiting. Position lerps and shortest-arc rotation interpolation make the zero endpoint exactly the incoming NN pose. No new timer, smoothing state, duration pin or inference pass. The earlier 169 window is smaller and includes the ongoing checkpoint/pinning transition; the strongest isolated discontinuity is at 205.



Evidence: `Saved/Diagnostics/Knee202/kick_current_oct2.json`, `kick_current_oct2_nn.jsonl`, `kick_current_oct2_analysis.json`, `kick_current_pole_trace.json`, and `kick_current_graph.txt`. Scripts: `Saved/Diagnostics/CaptureKickPoleCurrent.py`, `AnalyzeKickPoleCurrent.py`, `ProbeKickPoleTrace.py`.



Validation: Live Coding loaded 18:02:16 UTC; independent pole-clock retirement, reconstruction fade, exact correction endpoints, calf-length and knee-handoff tests all passed. No new gameplay capture. Visual acceptance remains the user’s test.
