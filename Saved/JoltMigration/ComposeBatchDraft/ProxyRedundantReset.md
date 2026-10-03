# Remove one redundant full compact-pose reset

Draft only, no active changes or build. `ProxyRedundantReset.apply-patch.txt` removes one line from the private native proxy's `Evaluate`. Rotation normalization remains unchanged.

Pinned local UE 5.7 evidence:

- `Engine/Source/Runtime/Engine/Private/Animation/AnimInstance.cpp:889–913`: `UAnimInstance::ParallelEvaluateAnimation` constructs `FPoseContext EvaluationContext(&Proxy)`, calls `EvaluationContext.ResetToRefPose()` at line 904, then dispatches `Proxy.EvaluateAnimation(EvaluationContext)` at line 907. It copies the resulting compact pose at line 911. The forced-reference-pose branch does not call the proxy.
- `Engine/Source/Runtime/Engine/Private/Animation/AnimInstanceProxy.cpp:1397–1423`: `EvaluateAnimation` dispatches through `EvaluateAnimation_WithRoot`, caching bones then calling the native `Evaluate_WithRoot` override. It does not modify the initialized pose before native evaluation.
- `Engine/Source/Runtime/Engine/Public/Animation/AnimInstanceProxy.h:660`: the default `Evaluate_WithRoot` calls our `Evaluate(Output)`.
- `Source/GameAnimationSample3/Private/ProphecyJoltPoseAnimInstance.cpp:48–67`: the private proxy currently resets that same pose a second time, then replaces each available compact entry from the completed snapshot. Empty snapshot and unmapped compact entries correctly retain the reference pose already established by the engine.

All bone-index/range checks, snapshot copying, per-compact-bone assignment and normalization stay identical. Full 88-bone publication and standard Update/PreEvaluate/PostEvaluate/finalization/notification callbacks remain unchanged. No direct proxy caller is introduced. If a future caller invokes native `Evaluate` outside the regular UE initialized-context contract, that caller must initialize its pose before evaluation.

No measured saving claimed. The entire native proxy evaluate phase in the Normal/P-core baseline was ~0.0976 ms/100 characters; removing just its repeated reset can save only a fraction of that. Existing full-pose, empty/clear/republication, callback, blood and runtime validations are the appropriate regression coverage; no new broad tests are needed for this one-line change.
