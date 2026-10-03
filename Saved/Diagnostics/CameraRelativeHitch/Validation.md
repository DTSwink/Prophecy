# Camera-relative Jolt pelvis hitch — 2026-09-10

**Historical experiment, rejected by the user:** the 10 ms mitigation below did not resolve the visible skeleton jumps. The project and running editor have been restored to 16.667 ms. Position-only thresholds missed the moving-target velocity discontinuity: recorded two-substep frames end near zero pelvis velocity while the root moves at 180 cm/s. This report must not be cited as acceptance of a complete fix. The user clarified that skeleton teleporting, rather than frame-rate stalls, is the active problem.

## Current implementation

The character controller and shared world coordinator now use the same collision-step calculation in `ProphecyJoltStepTiming.h`. The controller denominator is `frame duration / collision steps`, including when the configured step-count cap is reached. Previously it used `min(frame duration, maximum substep duration)`, although Jolt divides the frame evenly. A 17 ms frame therefore used two approximately 8.5 ms integration steps with a 16.667 ms controller denominator.

The project Physics setting `MaxSubstepDeltaTime` is now **0.010000 s**, with substepping enabled and the existing maximum of 64. This is the shared Unreal setting, so it also applies to Chaos when that backend is used. Jolt still takes variable, evenly divided substeps; this is not a fixed-timestep accumulator. The shorter steps reduce the remaining gravity/contact/joint sensitivity to changes in step count. No magnetization strengths, PHAT limits, NN cadence, native gravity semantics or generic servo API changed.

This increases collision-step work. The previous 100-agent performance result has **not** been revalidated with this setting. At approximately 60 FPS, frames that previously needed one or two steps now usually need two; longer frames may need more. No new full performance campaign was run.

## Detection and measurements

Three actual `testNN` PIE recordings each ran for at least **65 seconds**. The sampler reads the controlled Jolt pawn, native pelvis body, authored pelvis target, actor root, cached player-camera POV and numerical screen projection. It runs once per changed world time from Slate post-tick, buffers in memory, and writes after completion. No images, visualizations, injected delays, pose evaluation or gameplay setters were used by the sampler.

Comparisons below use steady movement after the first five seconds. The runtime Blueprint changes startup state: initial feedback tolerance is 10000 cm / 360 degrees, hand/head collision is enabled and the sword is held. At the end, feedback is 0/0, hand/head collision is disabled, the sword is dropped and movement is +X at 180 cm/s, facing -Y. These recordings are not evidence for every fight configuration or held-sword contact. The runs were not identical frame sequences.

| Metric | Before (`capture-114427.json`) | Final (`capture-120539.json`) |
| --- | ---: | ---: |
| Recorded duration | 65.0047 s | 65.0015 s |
| Recorded frames | 3701 | 3769 |
| Steady comparison frames | 3413 | 3488 |
| Maximum frame-to-frame change in body-minus-target error, 3D | 0.9930 cm | 0.06285 cm |
| Maximum forward-axis tracking-error change | 0.96960 cm | 0.001716 cm |
| Maximum horizontal screen tracking-error change | 2.75855 px | 0.004181 px |
| Maximum vertical screen tracking-error change | 0.89512 px | 0.17899 px |

There are **2631 final comparison frames after 20 seconds**; their maximum vertical screen tracking-error change is 0.16825 px. No root, target or native pelvis world reversal occurs in the final steady comparison frames. These are changes in tracking error, not a prohibition on legitimate animated pelvis motion.

Before the fix, at approximately 36.21 s, the root is stationary in the camera reference frame and the target moves only 0.13 px horizontally, while the simulated pelvis moves 2.62 px. The body-target error changes 0.993 cm as the calculated collision-step count changes from two to one. The denominator regression reproduces this mechanism in actual Jolt: the old timing leaves 0.733032 cm maximum lag over 120 moving frames; the corrected timing stays within 0.002 cm.

The intermediate duration-only recording (`capture-115919.json`) substantially reduces forward error but increases vertical jitter, including a 1.2388 cm 3D tracking change. **That intermediate result was not accepted as completion.** The final shorter-step setting reduces both horizontal and vertical maxima below baseline. The largest final changes still coincide with two/three-step transitions, but remain below 0.1 cm and 0.25 px in this recording.

The step counts in the analysis are calculated from captured world delta and reflected physics settings with the same ceil/clamp rule as the coordinator; they are not a directly sampled native counter. Median sampler overhead is about 0.53 ms (final maximum 6.29 ms), so this is not a performance benchmark.

## Verification and remaining limitation

- Live Coding compiled and linked both affected modules successfully; no editor restart or game-asset save was required.
- All **86** Jolt/NN-presentation automation tests pass again with the final project setting (`regressions.json`, `Regressions.log`). Coverage includes the new denominator and real-Jolt changing-substeps regressions, existing joints/collision/servo behavior, character high-gain containment, sword/blood fixtures and shared NN phase tests.
- `validate.py` asserts recording duration, the final setting, positive movement, maximum tracking change below 0.1 cm and screen tracking change below 0.25 px. The baseline exceeds the tracking threshold. `validation.json` and `comparison.json` contain machine-readable results.
- There remains **one 99.4 ms wall-clock gap between samples**, around 50.27 s, followed by a 96.9 ms world delta. Only two post-warmup sample gaps exceed 33.334 ms in the final recording. The sampler itself takes 0.475 ms at that sample. The nearby editor log contains no explanatory non-Blueprint event; **the stall's cause has not been established**. It must not be called resolved or assumed to be physics. Frame-time hitch elimination and the user's perceived smoothness are not established by the tracking fix.

All samplers are unregistered after recording. The current 10 ms setting is persisted in `Config/DefaultEngine.ini` and loaded in the editor. The temporary shorter-step override was finalized; no restoration callback remains active.
