# Current kick pelvis bounce — September 27, 2026

Diagnosis only. No runtime code or Blueprint values/wiring changed.

Read-only in-memory graph audit followed by owned Play captures: 620 ticks across six kicks, then 179 ticks with NN input/output tracing. Both sessions ended; trace budget restored. No compile or automation suite.

Current possessed agent chooses kickL/kickR every 90 ticks. First kickL starts90 and ends113; subsequent exits194,291,381,466,554. The captured locomotion is 100% Walk throughout, including recovery. Current lower-event kick blend selects Walk, hold0, duration0.5; kick lower tempering starts pelvis XY/Z at1 and rotation0, returns over0.6 (36 game ticks). The published root height stays constant in the detailed capture.

The vertical bob is present in the animation target, closely tracked by the physical pelvis:

| Window | Target height range | Maximum physical/target Z difference |
| --- | ---: | ---: |
| Before first kick, ticks30–89 | 9.970 cm | 0.354 cm |
| First lower recovery, ticks113–149 | 5.648 cm | 0.416 cm |
| After tempering ends, ticks150–179 | 8.899 cm | 0.464 cm |

At ticks125/137/151/162/174, the target falls/rises/falls/rises/falls through approximately84.5/90.1/84.3/92.8/83.9 cm. Raw Walk output alternates vertical deltas with the same motion. For every consecutive non-attack NN pair in the detailed capture, published pelvis local Z change equals raw policy delta Z within0.000003 cm. Recovery pelvis Z follow remains1; it does not soften the motion. There is no additional target-stage vertical correction in those samples, nor independent physical spring oscillation. This demonstrates where the visible bob is generated; it does not prove the learned gait or its recurrent inputs are ideal.

The immediate first-exit transient also includes a small raw-policy upward reversal at tick115 (+0.811 cm/NN step), followed by a downward step117 (−1.711 cm). Subsequent larger cycles already exist before attacks. No basis found for changing physics or leg reconstruction to address this height motion. Reducing vertical bob would require deliberate pelvis-height behavior/tuning; leave accepted settings unchanged pending user direction.

Evidence: `Saved/Diagnostics/KickPelvisExit.json`, `KickPelvisSource.json`, `KickPelvisSource-nn.jsonl`; scripts `CaptureKickPelvisExit.py`, `CaptureKickPelvisSource.py`. Current graph audit `Saved/Diagnostics/SwordThigh/BlueprintGraph.txt` is overwritten by later audits.
