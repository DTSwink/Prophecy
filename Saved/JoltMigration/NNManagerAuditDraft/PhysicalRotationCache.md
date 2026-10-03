# Physical-feedback rotation cache — bounded source draft

2026-09-09. Active manager baseline SHA256 `D983398002471BB0A6AD4605D4340250A942EB00C5F62A593FB3A998E0886B2D`. Candidate: `PhysicalRotationCache.apply-patch.txt`. No active edits, native build, Unreal launch or timing run were performed. The parent's measured physical-resample mean is approximately 0.544 ms; this includes sampling and all feedback processing, not just quaternion conversions. No numerical saving is claimed.

## Smallest candidate

Cache only the result of the existing expression:

```cpp
MirrorYBasis(QuatToMatrix(ActualTransforms[Index].GetRotation()))
```

The cache is created after a successful physical sample and destroyed when that one `ResamplePhysicalAgentState` invocation returns. It has 25 fixed matrix slots and a 32-bit ready mask, with no heap allocation, asset identity or persistent state. A slot is filled on the first existing use of that sampled bone; later uses copy the exact stored float matrix. The unchanged helper still normalizes an `FQuat`, builds an `FTransform`/`FMatrix` in UE's original precision, explicitly narrows its nine matrix components to float, then applies the existing training MirrorY basis. It does not alter the separate Jolt coordinate conversion.

Current run and walk contracts both request **31 conversions from 21 distinct indices** per successful resample. Repeated requests are pelvis twice, spine_01/02/03/04 twice each, spine_05 four times, and neck_01/02 twice each. The fixed cache avoids computing unused lower-arm/calf rotations, though its 25 `FMat3f` slots still incur their ordinary default initialization. Its readiness checks/storage also cost time; removing ten conversions is not proof that the whole phase improves.

Verified against these actual contract files:

| File | SHA256 |
| --- | --- |
| `Content/locomotion/NN/prophecy_lower_body_runtime.json` | `C738FE68038AF646022576F0023C28708C8AAEEE47AC14B4FBF80A6C3E7BF14D` |
| `Content/locomotion/NN/prophecy_lower_body_walk_runtime.json` | `033F75249FA7E7BB9E49D64AEFFDCABA09276DF8188BD235A0053D9BEF65ADF8` |
| `Content/locomotion/NN/prophecy_upper_body_runtime.json` | `CEB386C4F3D891D35FBEDD6AA314C33EAD2D884E81F640970E458B9FBD0802E0` |

Counts were computed from pelvis, the selected policy's actual start/end/toe indices, each actual upper-core body/parent pair, and both actual arm end/start pairs. No constant assumption about an unverified skeleton layout was used.

## Preserved math and state order

Source locations refer to the manager baseline above:

- `311–319`: original quaternion normalization, double transform/matrix construction and explicit float narrowing remain unchanged.
- `2675–2679`: actual physical read/failure return remains once per call, before cache creation. The 25-transform slice is established at `1036–1040`.
- `2680–2707`: lower raw sample still writes the same positions, rotations and toe values, followed by its original cleaning.
- `2709–2788`: lower tolerance math, signs, float intermediates, comparisons, Slerp and copies are untouched.
- `2790–2827`: upper raw sample still uses the same body-parent multiplication order, seed-root multiplication, offsets and cleaning. Only the repeated sampled-body conversion expressions change.
- `2829–2886`: upper tolerance math and second cleaning remain untouched.
- `2888–2951`: exact float `!=` comparisons and all recurrent-state updates remain untouched.

The all-matching path must preserve the exact previous/current recurrent pair and update only previous-physical samples plus `bHasPhysicalSample`. In a mismatch path, each previous state still comes from its own previous-physical sample only when the **old** `bHasPhysicalSample` was true; first samples use the new sample. Lower mismatch still updates upper base and both pelvis-heading buffers before the independent upper-state copy. The flag is set only at the existing return/end sites. Do not move its assignment between lower and upper processing.

The six patch hunks match the active source once each in an in-memory application. The lower tolerance block, the entire upper-clean/tolerance/recurrent tail, and `EncodeComponentPoseToNNStates` compare byte-identically after newline normalization. The active manager hash was unchanged afterward. The draft has not been compiled or numerically tested.

## Precision, zero and nonfinite caveats

Do not simplify repeated `GetNormalized`, replace rotation tolerance zero with a direct sample copy, eliminate cleaning, combine/reassociate matrix products, substitute `FQuat4f`, or share a quaternion between body-relative and seed-root frames. These are separate operations in the current float state pipeline and can change its exact recurrent comparison branch. Negative tolerances retain the current clamp-to-zero route.

UE 5.7 `Core/Public/Math/Quat.h:1106–1145` normalizes a copy and has the existing near-zero identity fallback. The candidate calls this exact helper; it does not introduce a new fallback. `Core/Public/Math/TransformVectorized.h:105–112,1214–1220` shows that `GetRotation()` may repair a nonfinite stored rotation and report a diagnostic when `ENABLE_NAN_DIAGNOSTIC` is enabled. Lazy filling preserves the existing first-use order. Tests must use independent input copies for the cached and uncached paths so the oracle cannot sanitize the candidate's inputs first. Nonfinite handling should match the active build's diagnostics and output classification, rather than adding a new silent finite-value policy. Signed zero requires bitwise float comparison for the valid-output oracle; numerical `==` alone does not distinguish its sign.

## Nearest meaningful oracle

The existing `EncodeComponentPoseToNNStates` at `1238–1315` is an unchanged uncached encoder of the same raw 41-float lower and 90-float upper samples, with their first cleaning passes. The existing `Prophecy.NN.PhysicalFeedbackTolerance` test at `391–443` tests a standalone transform helper, not these sample arrays or recurrent-state ordering; it is insufficient on its own.

The nearest bounded numerical test should be in this translation unit so it can use the private production cache and existing uncached encoder without a public runtime API:

1. Build a small plain `FImpl` fixture with actual body/parent/core/limb/seed-root data; no model inference, actor/editor world or material assets are needed for raw encoding. Compare the cached raw-encoding route against the existing uncached encoder for **every** lower/upper float, not only final bone rotations.
2. Also compare every production-cache `Get` result with the original expression for the real 31-request order, repeated/aliased indices, and reordered valid layouts. Use independent transform copies and a fresh cache after every changed sampled pose. This directly covers the only new memoization behavior.
3. Cover deterministic randomized signed-axis rotations, quaternion sign pairs, finite nonunit/near-zero quaternions, zero, signed-zero components, large finite translations, and changed walk/run limb indices. Compare finite floats bitwise. Add nonfinite cases only with the expected diagnostics for the actual `ENABLE_NAN_DIAGNOSTIC` build; preserve the baseline's behavior rather than asserting that malformed inputs must become finite.

A cached copy of the raw encoder can retain its original arithmetic and replace only the same eight conversion call sites. The existing uncached encoder should remain the independent baseline. This is a stronger test than repeating one matrix helper and checking only approximate quaternion angles. Given equal raw arrays and the byte-identical downstream code, all tolerance and recurrent branches receive identical inputs.

If a larger pure-feedback extraction is later chosen, add a full snapshot oracle covering lower/upper physical/current/previous/previous-physical arrays, current upper-base, both pelvis-heading buffers and the flag. Exercise first/subsequent samples, all-match, lower-only, upper-only and both-mismatch cases with zero, nonzero and oversized tolerances. Do not introduce that larger extraction merely to claim this small cache's speedup.

## Split/parallelization option: hold until its split is measured

`AProphecyAgent::SampleActualComponentPose` at `3185–3214` reads UObjects/mesh state, and its Jolt branch calls `SampleCompletedComponentPose` (`ProphecyJoltCharacterComponent.cpp:918–937`), which resolves the current inherited AgentMesh frame and name mapping. This stage belongs on the game thread. The later matrix/tolerance/recurrent processing is largely plain manager-owned data, but its current phase timer does not isolate read cost from math.

Before any worker staging, measure those two portions. A future split must gather each current 25-transform sample on the GT, retain the exact per-agent before-state and immutable layout/tolerance inputs, run only plain math, join, then commit in the existing order with failure/sample counters preserved. The present approximately 0.544 ms inclusive phase is a small ceiling for that additional machinery. No persistent pose cache, frequency reduction, hidden zero-tolerance bypass or parallel split is included in this draft.
