# Repeated left-arm rebound: detection before correction

September30,2026. Supersedes the claim that the earlier forearm-length spring alone fixed the user's visible bounce.

## Detection

Captured760 ticks spanning four SlashR upper exits197,365,543,733. Unlike the earlier single-step comparison, measured elbow/hand lateral distance relative to the left shoulder, in a basis built from both shoulders and pelvis-to-spine. This removes character translation and turning and exposes inward-to-outward reversals. The current Blueprint now explicitly selects Kinematic each tick; the mesh follows the NN through these attacks.

Third attack: the elbow moves inward to11.944cm lateral offset at544, rebounds to13.466cm at550, then moves inward again. Corresponding earlier rebounds are2.701cm and0.638cm. These are actual reversals, not merely a large positional step. Diagnostic cancellation of inertia only after the third upper end preserves the outgoing attack and first interval, but removes the sustained rebound: elbow at550 is11.088cm and moving inward. The raw upper checkpoint contains a smaller reversal, amplified by the final arm solve. Cone audit applies no correction to the left arm in this rollout.

## Concrete bug

Inertia computed a clamped forearm **length** but continued springing the wrist toward the **unclamped position**. These describe different arm geometries. At the third recovery sample targeting550, raw forearm length is17.911cm, clamped goal19.431cm and current inertial length19.374cm. The angular guide elbow is12.654cm outward, but IK pushes it to13.466cm to reach the incompatible wrist target. Earlier springing of length alone did not correct this mismatch.

`ApplyArms` now clamps the wrist along the goal forearm before converting to reference space and advancing the springs. This matches ordinary NN forearm-clamp semantics: retain the authored elbow, move the wrist to the allowed length. Wrist and length now approach the same constrained geometry. Existing Response, Alpha, Hold/Blend, reference-space selection and outgoing momentum remain. No extra inference or disabled-path arm work. Editor-only `Prophecy.UpperInertia.Audit` defaults off and traces goal/guide/solved geometry when explicitly enabled.

## Validation and limits

Live Coding loaded September29 22:56:15UTC (September30 local). Three focused inertia tests passed22:56:35, including a full15-step recovery at Alpha0.25/0.5/1: a checkpoint wrist at16cm with a20cm minimum forearm must never create a lateral swing of a stationary intended elbow. Previous reference-frame, outgoing velocity, retirement and disabled behavior checks remain covered.

Matched760-tick replay retains all four exit ticks and finite captured poses. Measured first15-tick outward retracing falls:

| Upper exit | Before | After |
|---|---:|---:|
|197|2.701cm|0.901cm|
|365|0.638cm|0.326cm|
|543 (reported550)|1.522cm|0cm|

This establishes removal of the reported third-attack reversal and reduction on the earlier two, not removal of all arm movement. The fourth attack differs: the elbow is already moving outward before exit733, and continues after release. Its first15-tick outward excursion increases1.718→2.643cm with the consistent clamp target; the before/after peak and later return are retained in the comparison plot. Do not hide this by treating a smaller first-step displacement as success.

A final790-tick trace separates that fourth case: raw checkpoint elbow offset is20.03cm at733 and19.70cm at735. The current core-carried goal/guide/solved offsets at735 are20.004/19.949/19.991cm. Thus the remaining outward peak follows the checkpoint goal rather than the large artificial IK displacement found around550. Subsequent raw goals move inward. This investigation does not add a new limit or suppress that checkpoint-authored motion.

Evidence under `Saved/Diagnostics/Knee202`: `arm_bounces_current.json`, `arm_bounces_trace.json`, `arm_bounces_trace_nn.jsonl`, `arm_bounces_no_inertia.json`, `arm_bounces_stages_analysis.json`, `arm_bounces_fixed.json`, `arm_bounces_comparison.json`, and `arm_bounces_comparison.png`. Captures preserve the Blueprint; diagnostic disablement only affects owned PIE. No full suite, Blueprint edit/save, restart or push.

Fourth-case evidence: `arm_bounces_tail.json`, `arm_bounces_tail_nn.jsonl`, `arm_bounces_tail_raw_analysis.json`, `arm_bounces_tail_stages.json`. All owned PIE sessions ended; inference, cone and inertia audit switches returned to zero.
