# Pelvis hitch around380 — procedural recovery feedback isolated

## Current fix, 2026-09-25

The knee reconstruction and its foot-relative turn limiter were copied into the next locomotion NN input as if they were newly authored movement. Their thigh rotations, ankle corrections and derived velocities caused the network to change its subsequent pelvis predictions. Every-tick Walk pinning independently reintroduced the same reconstructed thigh into recurrence, so changing only the main reconstruction pass was insufficient.

The displayed and physical-target legs still use the accepted September20/height-guided reconstruction, length recovery and independent pole limiter. Recurrence now retains the coherent pre-reconstruction ankle/thigh state. Real pin endpoint displacement still enters recurrence; its connected knee solve stays in presentation. Later pelvis-inertia changes survive the separation. This uses the existing recurrent/published buffers, with no new persistent pose, inference, clock or pelvis filter. Physical feedback remains authored-relative: actual deviations from the displayed target still affect policy input according to the existing tolerances; perfect following does not feed the procedural target correction back as an error.

The mechanism is shared, with no attack-family gate. No changes to the accepted knee target construction, kick checkpoint routing, calf allowance/interpolation, foot rotation, pin bounds/smoothing, blend durations, snapshots or reset. Additional copies/math run only while reconstruction is active; normal locomotion retains only guards. The every-tick pin commit now avoids its redundant recurrent IK solve.

Editor comparison `Prophecy.Recovery.PolePresentation` defaults1; 0 restores the old feedback for diagnosis. Non-editor builds always use the corrected separation. The final live build succeeded in22.72s. No Blueprint/map edits, save, editor restart or push; owned diagnostic Play sessions only. Include the live patch in the next authorized normal build.

## Causal experiments

Trials enabled at320, before the third kickL exit323; whole350–386 window measured as below:

| Behavior | Peak horizontal velocity change (cm/tick) | Peak angular velocity change (degrees/tick) | Peak vertical velocity change (cm/tick) |
| --- | ---: | ---: | ---: |
| Original reconstruction |0.679889|3.554192|0.660183|
| Reconstruction disabled at320 |0.414253|1.049761|0.820359|
| Pole feedback separated only |0.580562|1.351779|0.632064|
| Geometry also separated, tick-pinning path still unchanged |0.4333|1.0858|1.3072|
| Complete separation, reconstruction still visible |0.414175|1.049745|0.820353|

The incomplete geometry-only trial worsened vertical motion and was rejected. Input traces isolated the remaining difference to the per-tick pinning commit: the first significant divergence appears at355, after the pin commit at353. Correcting both paths makes pelvis motion almost identical to the reconstruction-disabled comparison while retaining the reconstructed legs. This is causal isolation rather than adding a smoother to conceal the hitch. The sharp opposite yaw turn at374–376 disappears. Vertical variation is not universally lower; no claim that every gait acceleration vanishes.

The complete paired trial differs by at most0.00324cm across captured bone positions through320 versus the older binary's baseline (small physical-run variation), while the original on/off320 comparison below is bitwise identical in position. A full-from-start520-tick trial has horizontal peak0.399706 and angular peak1.145003 in350–386. Eight complete mixed-attack recoveries plus a partial ninth were also captured in old/new900-tick runs: kickL, kickR, overL, overR, slashR, jabL, pike, hookL, then kickL. Poses remain finite. All528 frozen final pole solves obey their actual turn budget, leave pelvis/ankle/foot rotation untouched, and preserve calf length within0.000004cm. Later trajectories differ because recurrent input is corrected; some individual knee steps increase and others decrease, so this is not a claim of universal visual equivalence or zero knee motion.

Evidence under `Saved/Diagnostics`: `PelvisAblation-*`, `PelvisPoleTrial-*`, `PelvisGeometryTrial-*`, `PelvisDisplayTrial-*`, `PelvisConsistentTrial-*`, `RecoveryIsolationMix-*`, their analysis scripts and numerical summaries. Frozen tests cover the same incoming pose rather than relying only on changed downstream trajectories.

Final unchanged-scene capture `PelvisIsolationFinal-capture.json` completes520 ticks on the cleaned implementation:350–386 horizontal peak0.399740, angular peak1.145028, vertical peak0.729185. World-Z angular velocities at372/374/376/378/380 are−2.268/−1.779/−0.831/−0.043/+0.127 degrees/tick, confirming the abrupt reverse turn has gone in this scene.

Native validation15:18:37UTC:26 of30 tests pass, including new `LowerTempering.PolicyIsolation`, foot-frame smoothing, independent recovery timing, physical feedback alignment/tolerances, calf target/allowance,60-tick clock and seven Walk pinning checks. Four older geometry tests (`RootLocalPinAndChain`, `StancePlaneConnectedRegression`, `StancePlaneIdentity`, `SupportHeadingFrame`) fail; repeating all30 with old recurrence restored at15:19:04 produces identical results. These assert older knee-guidance contracts and are not changed here to disguise a failure. Therefore the whole suite is not claimed green. `RecoveryIsolation-native-results.json` records equality; broader visual validation remains appropriate, especially for downstream episodes whose NN history changes. Defense follows the shared recovery path but was not separately recaptured in this task.

The earlier investigations below are retained as evidence and are superseded by this fix.

## Wider reconstruction comparison (subsequent diagnosis)

The initial single-input thigh substitution below was too narrow to assess accumulated reconstruction feedback. Three unchanged-scene520-tick captures now compare: normal reconstruction, reconstruction disabled on the possessed agent at320 (before third kick exit323), and disabled at20. The existing debug node is changed only on transient PIE actors; no saved settings or production source changed. The on/off320 runs have identical authored positions for every captured bone through320 (maximum difference0cm).

Measure the whole350–386 window, with pelvis translation and world-axis angular velocities sampled over two game ticks. Peak changes between successive such velocities:

| Measure | Reconstruction on | Off at320 | Off at20 |
| --- | ---: | ---: | ---: |
| Horizontal velocity change, cm/tick |0.6799|0.4143|0.3967|
| Angular velocity change, degrees/tick |3.5542|1.0498|1.1477|
| RMS angular velocity change |1.4380|0.7854|0.7883|

Thus the same-prefix comparison reduces the peak horizontal discontinuity39% and angular discontinuity70%. Physical-mesh measurements corroborate this: horizontal peak0.6785→0.4160 and angular peak3.4031→1.0447. Over the complete324–386 recovery, angular RMS is1.2753→0.9662 (24% lower); not every metric improves, and the first recovery with reconstruction disabled early has a slightly higher peak horizontal change. This is evidence for the reported local problem, not a claim that disabling reconstruction is globally desirable.

The rotational hitch is particularly clear in pelvis world-Z angular velocity (degrees/game tick):

| Endpoint tick | On | Off at320 |
| --- | ---: | ---: |
|372|-1.878|-2.230|
|374|+1.163|-1.873|
|376|+2.834|-1.078|
|378|+0.235|-0.169|
|380|-0.319|+0.196|
|382|-1.125|+0.177|

Enabled reconstruction produces a brief strong opposite turn and turns back; disabled yields a gradual approach to near-zero. This confirms both rotational and horizontal hitching associated with the reconstruction-enabled recovery over multiple recurrent steps. It does not yet distinguish which reconstruction component or accumulated input causes it: the debug node also bypasses dependent calf/presentation work and cancels the independent pole timer. No fix or permanent disable was installed.

Evidence: `PelvisWide-on-capture.json`, `PelvisWide-off320-capture.json`, `PelvisWide-offearly-capture.json`, their NN traces, `PelvisWide-summary.json`, `AnalyzePelvisWide.py`, `InspectPelvisWidePeaks.py` under `Saved/Diagnostics`. All three owned captures completed and ended; transient overrides were destroyed and NN trace disabled.

## Initial narrow diagnosis

2026-09-25. Current setup repeats kickL; third attack ends323 and next starts388. Recovery uses Walk at weight1; no lower tempering is active365–387. All previously accepted fixes remain enabled. No production source, Blueprint or settings change for this investigation.

Two unchanged440-tick replays confirm a vertical slowdown/resumption immediately around the user's380 report. Authored pelvis positions350–387 match exactly between them (maximum difference0cm):

| Ticks | Authored vertical displacement per game tick | Physical pelvis |
| --- | ---: | ---: |
|377–378|+0.308cm|+0.301 / +0.310cm|
|379–380|+0.156cm|+0.174 / +0.163cm|
|381–382|+0.786cm|+0.789 / +0.787cm|

There is also uneven horizontal travel:3.397cm at373–374,4.076 at375–376,3.657 at377–378,3.710 at379–380,3.426 at381–382. This is not the later attack entry at388 or a physical-only obstruction. The half-rate NN pelvis deltas already contain the vertical dip: +0.616,+0.312,+1.571cm per policy publication377/379/381. Presentation faithfully interpolates those positions.

Exact offline replay of the recorded Walk input matches native outputs within2.504e-6. Substituting only the prior raw thigh orientations and their corresponding velocity features (both legs) changes379 vertical NN delta0.312→0.461cm and3811.571→1.662cm. The pronounced slow/fast contrast remains. This rules out claiming that simply removing the immediately preceding thigh correction solves the event; it does not rule out accumulated effects from earlier reconstruction, pinning or other recurrent inputs.

The previous calf-length/interpolation fixes have not eliminated this distinct NN-prediction slowdown. No speculative smoothing, solver rollback or change to accepted kick behavior was installed. Root cause beyond the observed policy output remains unresolved.

Evidence: `Saved/Diagnostics/Pelvis380-capture.json`, `Pelvis380-nn.jsonl`, `AnalyzePelvis380.py`, `ReplayPelvis380.py`, `Pelvis380-replay.json`. Capture owns its PIE and ends it; NN tracing returns to0. User Play was not interrupted.
