# Repeated feedback reference transform: read-only findings

2026-09-09. No implementation, build, or editor execution. The parent reports that the preceding cache/oracle tests pass, with only about 0.018 ms measured physical-feedback reduction; this audit does not independently rerun those measurements.

## What repeats

`ProphecyJoltCharacterComponent.cpp:918–936` samples the same completed world-pose snapshot into the current inherited AgentMesh reference frame. It performs 25 `GetRelativeTransform(Reference->GetComponentTransform())` calls for the manager's 25-bone sample. There are no callbacks or reference-frame mutations in this loop. The name/layout and completed-index validation preceding it remains necessary.

The getter itself is just an inline reference to `ComponentToWorld` (`Engine/Classes/Components/SceneComponent.h:1097–1100`); hoisting that expression alone is unlikely to matter. `IsJoltPhysical` is a constant state/active check (`CharacterComponent.cpp:914`), not another rig scan.

The meaningful repeat is inside UE5.7's out-of-line `TTransform<double>::GetRelativeTransform` (`Core/Private/Math/TransformVectorized.cpp:205–259`). Each sampled bone repeats reference quaternion normalization checking, negative-scale selection, the same safe scale reciprocal, and the same quaternion inverse. For one 25-transform sample, a prepared reference could eliminate 24 repetitions of those **reference-only** operations. It still must perform every bone's scale product, translation subtraction, inverse quaternion vector rotation, translation scale product, quaternion product, and result diagnostics.

The accurate reciprocal is a vector divide followed by a threshold mask: `TransformVectorized.h:1407–1422`, `UnrealMathVectorCommon.h.inl:391–399`, `UnrealMathSSE.h:2169`. The original tolerance is constructed through `ScalarRegister(UE_SMALL_NUMBER)`; a replacement must not silently choose a differently rounded double literal near that boundary.

## Feasible exact-operation route, if later justified by timing

There is no stock prepared-relative-reference object. A small private helper could prepare the current reference once per sample and use the same public UE vector primitives in the original order for its finite ordinary-scale path:

1. Preserve `Other.IsRotationNormalized()` behavior. The stock runtime returns identity when that check fails; do not normalize the reference on its behalf.
2. Cache the safe reciprocal reference scale, `VectorQuaternionInverse(referenceRotation)`, and reference translation. Reuse the original vector reciprocal/mask operations and retain all signed component values.
3. Per world transform, perform the original sequence: scale product; translation difference with W cleared; `VectorQuaternionRotateVector`; translation scale product; `VectorQuaternionMultiply2`; construct the result without an extra rotation normalization.
4. Fall back directly to the original `GetRelativeTransform` for negative scale in either operand and any unusual/nonfinite input that is not covered by the optimized branch. Keeping stock zero/tiny-scale behavior through fallback is also valid. The current reference and sampled world values must be read afresh on the next sample.

Public register getters are available for rotation and translation (`TransformVectorized.h:973–980`), and the public vector-register transform constructor performs the stock NaN diagnostics (`229–235`). Scale extraction must preserve the XYZ values and use the original vector operations; no raw-layout aliasing or access to protected fields is needed. Any implementation still needs a direct stock-function oracle over rotations/sign pairs, positive nonuniform scales, zero/tiny scales around the threshold, negative scales, invalid reference rotations, and changed reference values.

Do **not** implement this as `World * Reference.Inverse()`. UE's inverse path scales translation before rotation (`TransformVectorized.h:1446–1454`), while the relative path rotates the translation difference before reciprocal scaling; nonuniform scales make the substitution materially different. Do not replace the vector rotation with `FQuat::RotateVector` and assume bit equivalence: that public method is scalar cross-product arithmetic (`Quat.h:1238–1250`), whereas the transform path uses vector multiply-add (`UnrealMathVectorCommon.h.inl:765–772`).

`SetToRelativeTransform` is not a drop-in shortcut for the complete contract either: its current source (`TransformVectorized.cpp:150–187`) has no negative-scale matrix branch and only a `checkSlow` for reference normalization. The stock negative-scale relative path uses matrices plus decomposition with the desired signed scale (`190–201`); retain it by delegation rather than recreating it for this optimization.

Reusing `Completed.ComponentTransforms` is also not an exact replacement. Physical bones receive an extra `NormalizeRotation()` after their relative transform during composition (`ProphecyJoltPose.cpp:116–125`), and helper bones are composed through their parent component frames before world conversion (`130–135`). The current sampler performs a fresh world-to-current-reference conversion, so its arithmetic and possibly its reference differ.

## Other small duplicate work in the current feedback path

- The raw upper encoder resolves 10 core bone names against the 25-body list on every sample (`NNLocomotionManager.cpp:1388–1392`). Production writes to those names are confined to contract loading. A correctly rebuilt index layout could remove these searches, but this is a small name-lookup cost, not a demonstrated large arithmetic saving.
- The seven literal lower-body tolerance names (`2853–2868`) are converted to `FName` at each call. Function-static immutable names would preserve behavior and avoid repeated interning lookups. Upper core/arm names already come from FName arrays. Both upper hand tolerances are looked up once for position and again for rotation in the same arm loop (`2933–2936`); passing one retrieved const reference to both would remove two TMap lookups per sample.
- When the lower state differs, `BuildUpperBaseFromLower(Current, ...)` computes `MatrixFromRot6(Current+3)` and its seed-root product (`1115–1116`), and the subsequent `LowerTransformToHeading(Current,0,3,...)` repeats those same two expressions (`1098–1100`, called at `2982–2984`). Sharing these exact intermediates could save one six-dimensional-rotation reconstruction and one matrix multiply on that branch. Its 90-value upper base is not identical to the nine-value heading buffer, so copying one entire output into the other would be wrong.
- The larger-looking repeated normalization/cleaning work is **not** proven redundant. There are 19 angular tolerance channels, each constructing kinematic and sampled quaternions through the current normalization chain. `MatrixToQuat` normalizes and its callers normalize again; numerical normalization is not generally bit-idempotent. Removing that, skipping zero tolerances, bypassing second cleaning, or reusing a body quaternion in a parent-relative frame can change exact recurrent-state comparisons. No such shortcut is recommended by this source audit.

None of these isolated repetitions is established as the missing millisecond. Before implementing a prepared-reference operation, separate the existing physical-sample read from subsequent encoding/tolerance/state work in the same matched benchmark. A game-module instruction-set experiment would affect inline math in that module; it does not recompile UE Core's exported `GetRelativeTransform` implementation. No performance estimate is assigned to this unimplemented candidate.
