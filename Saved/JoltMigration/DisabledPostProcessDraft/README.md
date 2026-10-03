# Callback-time eligibility guards

This draft contains only `EligibilityGuards.merge.patch`, two isolated apply_patch-format hunks for root's review/promotion. No active code, build, editor process or asset was changed by this agent.

Root already applied the admission fix permitting a retained **disabled** postprocess instance. UE5.7 `SkeletalMeshComponent.cpp:4925,4973` requires `!bDisablePostProcessBlueprint` to update/evaluate that graph, while `DoInstancePostEvaluation:2649` still calls its post-evaluation callbacks. Keeping that instance preserves every callback and its relative sequence; queries now commit before those disabled postprocess callbacks. Exact callback-time Chaos equivalence is not required. Finalized-bone socket/query/blood functionality remains required.

The first guard rechecks the exact native pose class, no linked evaluator, and disabled postprocess evaluation inside `CommitPostEvaluateQueries`, immediately before invoking the query callback. The pre-refresh Arm check alone cannot catch a main-instance post-evaluation callback changing these values.

The second guard extends the existing exact binding validation after Refresh: fast ownership requires any retained postprocess graph to remain disabled. A postprocess callback that re-enables it after the query commit therefore stops publication in the same frame, rather than waiting for the next frame's Arm check. Component transform, mesh/anim identity, world step, rig, revision and registration guards remain intact. Normal self-removal still uses the existing removed-binding handling.

The actual mannequin test should retain/check its postprocess UObject instead of asserting null. It already checks native ray/socket agreement inside finalization, after the postprocess callbacks. No callback implementation was injected or asset edited here. Main/postprocess callback mutation can be tested through an existing injectable native test hook if one is introduced later; these two hunks have source review only until root builds/runs them.
