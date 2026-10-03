# Sample-local physical-feedback rotation cache

Draft only, 2026-09-09. No active edits, C++ compilation, automation run, or UE launch. This supersedes the earlier untested expression-only candidate in `NNManagerAuditDraft`; apply **only** this complete `PhysicalRotationCache.apply-patch.txt` after review.

## Scope and exact semantics

The cache stores the result of the existing `MirrorYBasis(QuatToMatrix(sampledTransform.GetRotation()))` expression lazily by its current 0–24 index. It exists only inside one successful physical resample. No source pose, asset identity, feedback state, or tolerance persists in it. It preserves the original double-quaternion normalization/UE matrix construction/explicit float narrowing and training basis conversion, including the existing small-quaternion fallback.

The lower and upper raw encoding blocks are moved into two private production helpers, called at their original positions around the unchanged lower tolerance work. The same cache is passed to both. The existing animation encoder `EncodeComponentPoseToNNStates` stays untouched and supplies the independent regression oracle.

`BuildDraft.py` constructs this patch from the current source and checks that the existing encoder, lower tolerance block and upper state-pointer setup, and entire upper tolerance/recurrent-state tail remain byte-identical. It writes only into this draft directory. `SourceVerification.json` records those checks, source SHA256 values, contract hashes, and exact conversion counts. These are source comparisons, not numerical test results.

## Exact possible saving

Both current checked run and walk contracts request 31 sampled rotations from 21 distinct bone indices. The cache eliminates 10 repeated conversions per successful resample: pelvis is requested twice, spine_01 through spine_04 twice each, spine_05 four times, and neck_01/02 twice each. Other matrix, cleaning, tolerance and quaternion operations are unchanged.

All 25 physical transforms still enter the sample. The current raw encoders never request the rotations of lowerarm_l, lowerarm_r, calf_l or calf_r; this is existing encoder behavior, not removal of four sampled or published bones. The cache supports all 25 indices and the test verifies them explicitly. It benefits both policy branches, but it does not optimize unrelated uses of the uncached animation encoder or claim every bone's rotation is part of the 41/90 feedback state.

The cache introduces bit checks, stored matrices and ordinary initialization of 25 matrix slots. Two extracted helper calls may have a cost if not inlined. The roughly 0.544 ms physical-resample phase includes substantially more than these 31 conversions; no saving is claimed until a matched real-NN100 measurement.

## Meaningful oracle and retained behavior

New test: `Prophecy.NN.PhysicalFeedback.RotationCacheRawEncoder`. Its private `.inl` is included only under `WITH_DEV_AUTOMATION_TESTS`, after the production helpers in the same translation unit. It reads the real lower run/walk and upper JSON contracts, validates shared 25-body layouts and referenced indices, and does not create actors, load models, or run inference.

For each of 128 deterministic pose variants and both policy choices, it compares **every one of the 41 lower and 90 upper floats bitwise**, including signed zero, against the unchanged encoder. Independent input copies prevent one route from affecting the other. Differently seeded output arrays expose missed writes. Cases include signed axis rotations, quaternion sign pairs, pi and very small rotations, finite nonunit and zero/near-zero quaternions, changed seed-root frames, large finite translations, nonuniform transform scales, and complete pose-value replacement in the same source allocation. After encoding, every one of the 25 cache entries is compared against the original matrix expression.

The numeric oracle covers the entire raw encoded input to tolerance processing. The existing `Prophecy.NN.PhysicalFeedbackTolerance` covers zero, partial and large tolerances. Combined with byte-identical downstream code, exact raw inputs preserve its comparisons and recurrent update order; this draft does **not** claim a new end-to-end retained-buffer runtime test. In particular, the all-matching path still retains the exact current/previous recurrent pair, and first-versus-subsequent sample behavior still uses the old `bHasPhysicalSample` at the original locations.

Malformed nonfinite transforms are deliberately outside this new finite-output oracle. The production conversion is unchanged and lazy filling retains first-use order, but UE's optional NaN diagnostics may repair stored rotations during `GetRotation`; this patch does not introduce a new nonfinite policy or claim that route was executed.

## Execution after parent promotion

The patch also narrowly expands the foundation runner's accepted filter names, with its candidate PowerShell syntax checked. Run:

```powershell
Tools/Jolt/RunFoundationTests.ps1 -Filter Prophecy.NN.PhysicalFeedback
```

That prefix selects the new raw oracle and existing tolerance test. Follow with the existing full foundation and actual NN functional validation as appropriate. Compare whole-world and physical-resample distributions in matched runs keeping the chosen SIMD build, worker count, no-lock policy, query padding, cameras, P-class placement and all validators the same. Do not infer a speedup from the operation count alone.

Checked manager SHA256: `d983398002471bb0a6ad4605d4340250a942eb00c5f62a593fb3a998e0886b2d`. Checked runner SHA256: `0ba6d2f56e8552c7095930dd607251789215d4356e35e92d5fcd7a0082218e49`.
