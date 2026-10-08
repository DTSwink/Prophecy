# Upper-body authoring benchmark — September 28, 2026

October 7 maintenance note: Armed blocking was removed from the runtime. These measured results and benchmark evidence are retained for reference; the original checkpoint-hold reproducer depends on the retired node and cannot run unchanged.

Quick result: the current animation-layer upper-body path was approximately **7.1x cheaper** than the half-attack checkpoint path in measured upper-authoring stages.

| Method | Measured cost |
| --- | --- |
| Authored animation, Play NN Animation Layer from spine_01 | 0.54–0.65 ms per 30 Hz update |
| Attack checkpoint, half SlashR | 3.99–4.42 ms per 30 Hz update |
| Manual fixed-pose SLERP, 16 bones plus hierarchy reconstruction | 0.00067–0.00081 ms per pose, native math microbenchmark only |

The animation evaluation/blend stage alone cost0.061–0.069ms. The current layer path still evaluates ordinary upper locomotion input/inference/output, bringing the measured upper path to0.54–0.65ms. Half attacks suppress that ordinary upper inference but still evaluate all three ghost networks: lower1.50–1.67ms, cone0.151–0.174ms, upper1.97–2.15ms per call. Thus the half-attack result includes the dependencies needed to author its upper body, not only its upper network.

Method: one inference-enabled actor, Kinematic, same Run input and lower checkpoint configuration; other scene agents' inference disabled in temporary owned PIE. Clip/attack/attack/clip order,40 warmup ticks then160 measured game ticks per window (80 NN updates), two windows each. Clip is AS_SlashChain30_Reference, looped from spine_01. Half SlashR uses Armed blocking to sustain the policy over the measurement interval. Blueprint actor ticks disabled in both cases. Timed sum is upper input/run/output + layers + attack; shared lower work excluded. No physics/render/FPS claim: world timings and lower GPU timings varied considerably, so use scoped upper-stage costs. This is a short single-character benchmark, not crowd scaling or an identical-motion quality comparison.

The manual result is a separate optimized native C++ /O2 double-precision shortest SLERP + normalization, translation interpolation and16-bone FK loop: seven repeats of200,000 poses, volatile output prevents elimination. It is not an installed Unreal/Blueprint fixed-pose pipeline and excludes bone lookup, Blueprint dispatch, pose submission, recurrent encoding, physics and any retained NN inference. It demonstrates that the interpolation math itself is negligible; it does not establish an end-to-end fixed-pose time. If ordinary upper inference is left running, manual interpolation would still pay that cost.

Evidence: Saved/Diagnostics/AttackPerformance/upper_modes_analysis.json, upper_modes_meta.json and upper_clip_0/3, upper_checkpoint_1/2.json; helpers BenchmarkUpperModes.py and AnalyzeUpperModes.py. Native math source/result: Saved/Diagnostics/UpperPoseSlerpBenchmark.cpp/json. Initial attempt stopped because Armed block cleared on a repeated attack; corrected by explicitly blocking at each entry and reran all windows successfully. Owned PIE ended, profiler stopped, no source/BP/asset configuration changed or saved.
