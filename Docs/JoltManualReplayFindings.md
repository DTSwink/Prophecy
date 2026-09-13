# Manual Chaos capture/replay findings — 0902 diagnostic

**Historical diagnostic, 9 September 2026: the 0902 recording failed its then-current replay gate.** The measurements below preserve that result. They do not define today's migration acceptance: the user now requires working physical animation, bodies/joints, blood staining and speed, explicitly without 1:1 Chaos behavior. Small Chaos-against-Chaos trajectory differences are diagnostic, not a blocker on a functional Jolt character. Sealed input integrity remains required.

The original analysis read the existing recordings without changing controller code, tolerances, assets or results and without launching a build or UE process. This documentation update likewise changes only this note. Its raw quaternion comparison had a measurement artifact; correcting that artifact did not remove the measured real replay differences.

Current source now normalizes orientation comparisons and records the old tolerance result with `acceptance_role` set to trajectory diagnostic only: [manual capture/replay implementation](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmarkManual.cpp>). Jolt's servo uses pre-Update activation in native units and native clamped velocity setters, not an exact Chaos wake-threshold contract; see [current fixture design](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Docs/JoltManualServoFixtureDesign.md>). Nothing in this note converts an old failed report to a pass.

At this update **28 foundation tests have passed** ([report](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/JoltMigration/Foundation-20260909-092623-577/index.json>)), but **no actual 22-body Jolt air/floor replay has completed successfully**. The [0928 functional attempt](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/jolt_manual_functional_20260909_0928.json>) failed before Jolt rig creation at the pelvis channel 1 fixture-filter check. The effective-native-filter correction, ray query, completed-pose output, live character binding and live benchmark are awaiting the current build and runtime validation. These historical Chaos-only measurements do not validate those newer paths.

## Evidence and scope

- Capture: [jolt_manual_chaos_20260909_0902-manual-air.json](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/jolt_manual_chaos_20260909_0902-manual-air.json>).
- Replay: [jolt_manual_chaos_20260909_0902-replay-manual-air.json](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Saved/Benchmarks/jolt_manual_chaos_20260909_0902-replay-manual-air.json>).
- The replay's source SHA1, `525E67EC7D5DAE6E070C8E1BDD447232C40B429E`, matches the actual capture file bytes.

Both files record UE **5.7.4-51494982**, one native manual follower with **22 bodies and 21 anatomical constraints**, 30 stationary warmup frames, then **60 target publications and 60 consumed callbacks** at fixed 1/60 s. This is the air/no-gravity case with the original Chaos profiles, a separate `PhysicalMesh`, no NN manager, and an explicit contact/discrete fixture configuration. Both files identify this run as **Chaos-only**; no Jolt rig import or execution occurred. These measurements do not establish placed Blueprint, rendered, floor-contact or production performance parity.

The serialized callback denominator and context delta are both `0.01666666753590107` s. Callback context time starts at `0.483333358541131` s for capture and `1.9833334367722273` s for replay. Game-frame provenance starts at 30 and 120 respectively. Absolute time/frame provenance differs as expected for consecutive cases; corresponding sequence, packet sequence, delta and denominator values agree throughout.

## Input and initial-state equality

All **60 packets are exactly equal as decoded JSON values** after excluding only `game_frame` and `source_sequence`. This includes body order/names, actual-bone transforms, `BodyFromBone`, final body targets, both strengths and timing. Every replay source sequence equals its corresponding capture packet sequence.

All **22 first-step body records are exactly equal**: raw X/R, pre-servo V/W and post-servo V/W. The decoded numerical values also have identical IEEE-754 binary64 representations. This checks the recorded numbers; it does not claim that JSON preserves arbitrary native object memory or hidden solver state. Initial-audit body records, constraint frames/live profiles and Chaos console scales also compare equal.

The first real difference appears at **step 2**, after the first physics advance. No complete body record remains equal at that step. For the first listed body, pelvis, the differences are already measurable: position `0.0000825911` cm, pre-V `0.00292609` cm/s, pre-W `0.0000796205` rad/s, post-V `0.00495546` cm/s and post-W `0.000307240` rad/s.

The replay restores raw X/R/V/W through the existing body APIs before its first publication. See [RestoreManualReplayState](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmarkManual.cpp:197>). Its recorded initialization text explicitly excludes solver-cache restoration. Equality of the visible initial state does not prove equality of cached constraint state, teleport bookkeeping or execution ordering.

## Quaternion measurement artifact

At the time of this diagnostic, the comparison calls `Source.Rotation.AngularDistance(Replay.Rotation)` directly on quantized raw quaternions: [comparison](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmarkManual.cpp:349>). UE's implementation evaluates `acos(2 * dot(q1,q2)^2 - 1)` without normalizing its inputs: [Quat.h](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Core/Public/Math/Quat.h:1230>).

Observed raw quaternion norms range from `0.9999999584498416` to `1.00000004088856`. Identical first-step `hand_r` quaternions consequently produce a false **0.0400162°** distance. Across the capture, the raw self-distance reaches **0.0467164°**. These are metric artifacts, not physical orientation changes.

For this analysis, normalize both quaternions, account for the equivalent signs, then measure their geodesic distance. A numerically stable expression used here was:

```text
u = q1 / length(q1)
v = q2 / length(q2)
chord = min(length(u - v), length(u + v))
angle = 4 * asin(clamp(chord / 2, 0, 1))
```

This gives exactly zero for every equal first-step orientation. The reported raw maximum **0.0417354°** occurs at step 56, `spine_03`; its corrected distance is only **0.00400477°**. The actual maximum normalized distance instead occurs at step 41, `neck_01`: **0.0181111°**. It still exceeds the recorded 0.01° gate.

## Measured real differences

Step numbers below are one-based. RMS values aggregate all 60 × 22 = **1,320 body-step samples**.

| Quantity | Maximum | Step / body | RMS |
|---|---:|---|---:|
| Raw body-origin position difference | 0.00326523666 cm | 18 / `neck_01` | 0.000621890648 cm |
| Normalized orientation difference | 0.0181111168° | 41 / `neck_01` | 0.00428557959° |
| Pre-servo linear velocity difference | 0.253770615 cm/s | 24 / `neck_01` | 0.0384274074 cm/s |
| Pre-servo angular velocity difference | 0.0293998588 rad/s | 19 / `clavicle_r` | 0.00667869467 rad/s |
| Post-servo linear velocity difference | 0.195914159 cm/s | 18 / `neck_01` | 0.0373134359 cm/s |
| Post-servo angular velocity difference | 0.0380866774 rad/s | 17 / `spine_05` | 0.00637013381 rad/s |

At the thresholds recorded for the 0902 diagnostic, zero samples exceed 0.01 cm position error, **74** exceed 0.01° normalized orientation error, **27** exceed 0.1 cm/s post-V error, and **98** exceed 0.01 rad/s post-W error. Thus a corrected angle metric still leaves three failed historical criteria. These counts remain evidence about that recording, not current functionality acceptance thresholds.

The divergence is not monotonically increasing. At the last recorded step, per-step maxima are approximately `0.000871076` cm, `0.00702047°`, `0.0522645` cm/s post-V and `0.00735184` rad/s post-W. A final-state-only check would hide larger intermediate errors.

With the identical final targets and unit linear strengths, the current rule implies `delta(postV) = -delta(X) / h`. Across all samples this relation agrees within **9.22e-7 cm/s**, consistent with final float velocity storage. The linear velocity difference follows the changed body state; it is not evidence of a different target stream or controller formula.

## Existing small-angle branch explains the largest W difference

The unchanged manual controller normalizes its quaternion delta, chooses its positive-W representation, then calls `ToAxisAndAngle`: [ProphecyAgent.cpp](<C:/Users/singerie/Documents/Unreal Projects/Prophecy/Source/GameAnimationSample3/Private/ProphecyAgent.cpp:297>). UE's [GetRotationAxis](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Core/Public/Math/Quat.h:1210>) uses [VectorNormalizeSafe](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Core/Public/Math/UnrealMathVectorCommon.h.inl:434>), which substitutes **+X** when delta.xyz length squared is below [1e-8](<C:/Program Files/Epic Games/UE_5.7/Engine/Source/Runtime/Core/Public/Math/UnrealMathVectorConstants.h.inl:64>). For a normalized small rotation, that boundary is approximately **0.0114591559°**.

At step 17, `spine_05`:

| Measurement | Capture | Replay |
|---|---:|---:|
| Rotation error to the same target | 0.0251206317° | 0.0112512464° |
| Delta.xyz length squared | 4.80569107e-8 | 9.64042141e-9 |
| Axis path | Normalized actual axis | +X fallback |
| Axis | (-0.9997713, 0.0212682, 0.0022365) | (1, 0, 0) |
| Recorded post-W, rad/s | (-0.02630025, 0.000559487, 0.0000588343) | (0.01178228, 0, 0) |

This reproduces the maximum **0.0380866774 rad/s** difference using the existing controller rule, with approximately `1e-9 rad/s` reconstruction error. At step 18 the two runs exchange branch sides. There are **52 samples** where capture and replay choose different sides of this fallback threshold. The largest same-branch post-W difference is `0.0160982 rad/s` at step 18, `neck_01`; branch flips do not account for every velocity discrepancy.

This is a retained small-angle discontinuity that amplifies small state differences. It is neither a newly changed controller nor evidence that the replay packet was converted differently. Changing this behavior would be a separate controller decision and would require a fresh reference recording; this analysis does not authorize such a change.

## Historical validation result and current use

The recorded gate is **0.01 cm / 0.01° / 0.1 cm/s post-V / 0.01 rad/s post-W**, with `passed=false`, in the linked 0902 replay file. No historical tolerance or result was rewritten, and no pass is inferred from the small physical scale of the differences. Current source preserves the diagnostic result separately from input-integrity acceptance.

Normalizing quaternions in the orientation metric was the justified diagnostic correction and is now present in source. Further repeated replay could investigate unrecorded solver/teleport state or execution ordering when that information is useful; it is not a prerequisite for the live functionality work. This single capture/replay pair cannot prove nondeterminism or identify the first solver-side cause. It does establish matching recorded input, first consumed visible state and first controller outputs, followed by small state differences amplified by the existing controller threshold.

The current functional proof must show Jolt driving the real retained PhysicalMesh, complete physical feedback, correct body/joint ownership and safe teardown, then blood staining and representative speed. The live fixture compares completed Jolt feedback against its own finalized skeletal sockets; that is a consistency check across the implemented pose path, not a new Chaos parity gate. The new live source has not yet earned a build or runtime pass at this documentation boundary.
