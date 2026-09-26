# Small right-knee snap around tick 202 — September 26, 2026

Implemented and loaded September 26 at 19:21:21 UTC. The recovery thigh length now smoothly converges to the normal published length on the existing recovery clock. Blueprint tuning, checkpoints and the accepted leg/pole solver were preserved; no asset save or restart.

Current possessed agent reports Physical mode. First attack is jabL at tick 120, ends at 140; next starts 240. The reported small snap is measurable at tick **200**, exactly 60 ticks after exit. Target knee translation changes 0.729484 cm, compared with 0.1528 cm on the preceding tick; foot translation is only 0.0434 cm. Target knee bend drops 19.63655 → 17.76616 degrees. The PhysicalMesh follows the same discontinuity (only small mesh/socket differences), so this is a target-presentation event, not an independently generated physics collision. Both effective pin values stay 1 and Walk weight stays 1. Later foot-relative pole steps around 201–204 are also recorded (1.47/1.52/0.65/0.66 degrees); the principal positional discontinuity is 200.

## Cause

`ProphecyKickFootLeewayLibrary.cpp::CaptureLengths` stores upper-segment lengths from the reference skeleton. Its pose-return lifecycle is shared by full specials, including this jab. `PublishLengths` sends those fixed upper lengths to presentation. `FProphecyNNPoseStore::ApplyRigidCalves` samples **calf** length from the previous/current publication using the render alpha, but reconstructs the knee using the stored reference **thigh** length. On expiry, `Tick` removes the presentation recovery entry immediately.

Measured right thigh length:

- Normal published endpoints: approximately **38.865064 cm**.
- Presented while recovery is active: **39.048656 cm**.
- Presented at expiry tick 200: **38.865065 cm**.

The 0.183592 cm discrepancy moves the almost straight knee considerably more than that. This differs from the earlier calf interpolation bug: calf length already uses consistent endpoint interpolation here; upper length does not match the pose it hands back to.

## Frozen-pose check

`ProbeKnee202Lengths.py` re-solves only the recorded knee before expiry, preserving the recorded hip, ankle, pole and interpolated calf length, but using the interpolated published thigh length. No world/NN advances or recurrent feedback changes:

| Tick | Recorded bend | Consistent-upper-length bend |
| --- | ---: | ---: |
| 197 | 20.31639° | 18.81325° |
| 198 | 19.92023° | 18.38422° |
| 199 | 19.63655° | 18.07646° |
| 200 | 17.76616° | 17.76616° |

Knee step at 200 falls **0.729484 → 0.162661 cm**, with unchanged hip/ankle. This initial offline experiment identified the cause; it used the destination length immediately, rather than the gradual runtime convergence below. It does not claim that every later pole movement is removed.

Evidence: `Saved/Diagnostics/Knee202/baseline.json`, `baseline_nn.jsonl`, `baseline_analysis.json`, `length_probe.json`; scripts `CaptureKnee202.py`, `AnalyzeKnee202.py`, `ProbeKnee202Lengths.py`. Capture was owned, completed 280 ticks and ended. Input tracing was reset to 0; pin debug enabled only on the owned temporary actor. No live user Play was stopped.

## Runtime fix and verification

`PublishLengths` forwards the existing pose-return curve's remaining weight (or active joint-return weight where applicable). `ApplyRigidCalves` blends from the original reference thigh length to the published previous/current thigh lengths sampled at the same presentation alpha. It retains the existing calf-length interpolation, pole, roll and endpoint-preserving solver. This is shared recovery, not a jab-specific gate.

The clock is unchanged: the existing cubic curve reaches zero on its configured final tick. There is no extra timer, inference or history capture. A separate small weight map preserves live allocation layouts across Live Coding. Its entry is removed with the recovery record, on cancellation/reset and on pose-store cleanup. The extra lookup/math only occurs while recovery is active. Zero-duration and disabled reconstruction retain their existing bypasses.

Editor-only `Prophecy.Recovery.UpperLengthBlend` defaults 1; 0 is a diagnostic comparison retaining the original fixed thigh length. It is not a gameplay knob. Leave it at 1.

Verification:

- UBT compile succeeded in 91.91 seconds; patch loaded at **19:21:21 UTC**. This was Live Coding, not a fresh normal-DLL build.
- Seven focused native tests passed at **19:23:31 UTC**: `RecoveryUpperHandoff`, `RecoveryCalfLength`, `FrameCadence`, `SharedReadersAndLifecycle`, `CalfReturnLocomotionTarget`, `KickFootLeeway`, `SixtyTickClock`. The new test covers both legs, the entire curve, exact return to the unmodified pose on retirement, and reset/new-return weight cleanup.
- Paired 280-tick capture runs the old setting but reads old/new targets on the **same unadvanced frames** 185–215. The old right-knee targets match the original capture exactly through the measured window. The new knee step at 200 is **0.163145 cm**, after **0.162945 cm** at 199, rather than 0.729484 cm. Thigh length at 199 is 38.865215 cm and converges to 38.865065 cm at 200.
- Pelvis and both hip positions are identical in paired reads; right foot/toe are identical. All tested pelvis/foot/toe rotations are identical. Left physical foot/toe target queries differ by at most **0.001746 cm** because they include downstream physical-target handling; do not describe every final target position as bitwise unchanged. The reconstruction itself leaves the ankle untouched, covered by the native test.
- Full 280-tick replay with the fix enabled from start agrees: right target knee step 199/200 = **0.162946 / 0.163145 cm**; PhysicalMesh = **0.162941 / 0.163132 cm**. All recorded transforms are finite. Maximum raw future position difference versus the original capture is 0.000086 cm; the paired measurement establishes causality independently of this tiny rollout difference.
- Both owned captures finished and ended Play, reset tracing to 0 and restored the comparison switch to 1. No user Play was stopped, BP edited/saved, restart or push performed. User visual acceptance is still pending.

Additional evidence: `paired.json`, `paired_analysis.json`, `final.json`, `final_analysis.json`, their NN traces in `Saved/Diagnostics/Knee202`; `CompareKnee202.py` and `TestKnee202.py`. The small later authored pole changes at 201–204 remain; this fixes the length discontinuity at retirement without retuning their guidance.
