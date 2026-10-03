# Private accepted-packet commit draft

2026-09-09. Draft only; no active edits, compilation, tests, or UE launch. `PrevalidatedServoCommit.apply-patch.txt` contains eleven uniquely matching hunks across five files. Parent owns promotion and execution, after its separate AVX2 comparison.

## Optimization

The native world's flattened packet is made exclusively from accepted, owned per-rig arrays. `PublishRigVelocityTargets` remains the transactional validation boundary; disjoint rig ownership and whole-rig teardown establish that concatenation cannot introduce duplicate or stale BodyIDs. Full proof is in `FlattenedServoValidationAudit.md`.

Extract the existing commit tail into private `FVelocityServo::CommitValidatedTargets`. Only the global native owner `FProphecyJoltWorldState` has friendship. The world uses it after flattening; every existing `Publish`/`PublishPerTarget` caller retains the original validated route. No public trust-input switch is introduced. The private commit checks GT ownership.

An in-memory source comparison verified that the copy/capacity reuse, denominator normalization, sample reset, and empty/mixed denominator handling are byte-identical to the previous tail. Activation and all remaining listener math are byte-identical. No callback, target cadence, sample, native body validity check, or overflow check is removed. The measured preparation ceiling was about 0.169 ms per 100-agent world; this candidate only removes part of that cost, so no speedup is claimed before measurement.

## Required finite-quaternion correction

During regression construction, source inspection found that the pre-existing normalized-quaternion check is not sufficient to enforce the stated finite-packet contract. UE5.7 `Core/Public/Math/Quat.h:1149–1156` uses `!VectorAnyGreaterThan(abs(1-dot(q,q)), threshold)` in vectorized builds. `UnrealMathSSE.h:2664–2666` implements that with greater-than comparisons; unordered NaN lanes compare false, allowing the negation to return true. Its non-vectorized fallback behaves differently.

The parent approved adding explicit `TargetRotation.ContainsNaN()` before `IsNormalized()` at **both** accepted boundaries: world rig publication and direct native `PublishPerTarget`. Despite its name, `ContainsNaN` checks finiteness of all four components (`Quat.h:1394–1400`), rejecting infinities too. The full pre-existing public validation prefix otherwise remains unchanged. This is a separately identified correctness repair, not a consequence of trusting unvalidated inputs.

## Meaningful tests in the patch

- New `Prophecy.Jolt.Servo.RejectedAndEmptyPacketsPreserveBodyState`: two real dynamic bodies with different accepted denominators. Fourteen rejected packets each contain a changed valid prefix followed by an invalid body, duplicate, nonfinite position/rotation/strength/denominator, nonunit rotation, negative strength/denominator, or zero denominator. After **each** rejection, real Jolt Update must preserve the prior endpoints/denominators and produce analytic unit-strength velocities and integrated positions. An accepted empty packet then clears samples and permits unchanged-velocity coasting.
- Existing `Prophecy.Jolt.MultiRig.IndependentPacketsOneWorldStep` gains NaN and infinity quaternion rows behind a changed valid prefix; the existing real-world analytic output checks establish atomic rejection through the owner route. Its existing empty-A packet section already validates B's retained endpoint/denominator and two collision steps, and A's unchanged coasting velocity. No duplicate empty-rig fixture was added.
- Existing `Prophecy.Jolt.MultiRig.RemovalGenerationAndWorldLifetime` and `Prophecy.Jolt.RigWorld.ServoHandlesAndWholeRigRemoval` retain the teardown/stale-handle coverage needed by the ownership proof.

These tests were reviewed from source only, not executed. Run the full foundation suite after promotion, then a matched actual-NN100 comparison while retaining the same SIMD build, no-lock policy, padding, cameras, P-class affinity, and validation settings.

## Exact checked baselines

| File | SHA256 |
| --- | --- |
| VelocityServo.h | 62DFE32BF436CFB84E8F2BCE3B95C8DCA5A46A56200911CA0B2AC5D2C57691B3 |
| VelocityServo.cpp | 9307C97E7513C2EB68DE2498AFD5E32EF7367654962C9A022A19D293BB7B9B92 |
| WorldSubsystem.cpp | 0EF5A9FB530595EDE339CFFC2CF1F97A30B905347CAA28CBD300F214FE4382C6 |
| VelocityServoTests.cpp | 10D26C726765801023567FB95847D65280318767A7F429CFCD791804FC9B5163 |
| RigWorldTests.cpp | F96716E8556A32F885650D849542FE7C42D60774822CE9F3DA297D1AEEB82375 |
