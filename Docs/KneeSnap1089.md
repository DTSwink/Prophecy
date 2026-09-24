# Left knee snap at 1088–1090 — 2026-09-24

Confirmed in unchanged testNN replay; possessed agent Kinematic. User wrote1088–1889; capture covers1060–1910 and finds the sharp pole event at1088–1090. The1888–1889 neighborhood does not show that pole discontinuity.

## Observed

Presented left knee pole turns52.849 degrees at1089 and59.965 at1090; knee moves5.463 and9.611cm. At1088 its underlying future leg is almost straight: knee circle radius0.28602cm, bend0.806degrees. Presentation knee-pop smoothing keeps the visible bend near15.6degrees but does not prevent this direction change.

## Causal isolation

Every-tick Walk pinning is enabled in the current Blueprint. Left effective pin changes1→0 at1089. Its cached future foot moves2.719291cm while future hip stays exactly unchanged. `UpdateWalkTickPinning` writes the new ankle into Changed, then calls `ResolvePelvisLeg` with a null ReferenceState. The solver therefore derives OldAxis/OldPole using the changed ankle with the unchanged old thigh. Near extension this changes the inferred pole drastically, before transporting it. The immutable Lower state is available but not passed as the reference.

Offline geometry using the moved ankle and original upper leg reproduces the resulting future pole within0.000022degrees. Preserving and transporting the original pole differs from the faulty output by87.367degrees. This identifies the geometry error, rather than blaming an unrelated reconstruction mode or physics limits.

Second owned replay matches every captured bone/end-point position exactly through1089. Disable only Every Tick pinning after recording1089, then immediately reread the SAME frame without advancing inference or time: future knee returns6.416989cm to its original cached position; presented knee changes5.832531cm, and its1088→1089 step becomes0.931750cm instead of5.463cm. This same-frame result cannot be explained by a different earlier rollout. Later1090 recurrence differences are not independently isolated.

## Final repair

`MoveTickPinningEndpoint` takes an immutable source pose. When knee-pop smoothing is enabled, the correction obtains its already-cached thigh-local bend reference and applies the same existing soft-IK calculation to a temporary source. Only its bend plane is used; the temporary inward ankle shift is not imposed on the requested endpoint. This avoids switching between the visible stable knee direction and a poorly conditioned raw bend near extension.

`ShiftTickPinningLeg` shares this reference and the existing geometry/reconstruction gates between presentation and recurrence. The next NN input receives the solved thigh together with the corrected ankle, in each buffer's own root frame before physical feedback. General knee reconstruction, calf recovery, clamps, foot rotations, root motion and clocks are unchanged. Disabled skips through the existing empty-map guard; zero offsets skip the reference lookup/solve. No new timer, inference, retained-layout or reflection change.

Editor-only `Prophecy.WalkPinning.PreserveHinge`:0 reproduces the old bug,1 is the intermediate raw-reference-only trial,2(default) uses the shared stable reference. Non-editor always uses the final repair. Captures restore2 on exit.

## Validation

Final Live Coding build116.90s, loaded21:36:07UTC. All10 WalkPinning/Presentation/RecoveryCalfLength tests passed21:37:44UTC, covering source-hinge preservation near extension, connected length, untouched foot rotation, tick cadence, pin bounds/transfer/reach rules, toggle/reset lifecycle and existing pelvis/knee/calflength regressions.

Controlled replay retains old behavior through1088 and switches only immediately before the event. Every captured position and quaternion through1088 is identical to baseline. Presented left knee pole turns:

| Tick | Before | Fixed |
| --- | --- | --- |
|1089|52.849 degrees|1.736 degrees|
|1090|59.965 degrees|7.177 degrees|

Knee displacement falls5.463→2.555cm and9.611→3.612cm; thigh rotations9.603→5.117 and14.150→5.504degrees. On the isolated first corrected frame, pelvis transforms and foot/toe rotations are exact; ankle/toe positions differ by at most0.00000075cm and both segment lengths remain within0.0001cm. No policy step/time is added. Later predictions legitimately differ after corrected legs enter recurrence.

The intermediate raw-reference-only fix removed the erroneous87-degree future-pole turn but left a31-degree presented turn as soft IK changed influence. It was not accepted as the final repair; sharing the existing stable reference addresses this remaining discontinuity without a new knee smoothing rule.

Fixed-from-start replay completes1910 ticks and20 attack exits, including left/right kicks, hooks, jabs, overs and headbutt. All sampled poses finite; maximum locomotion pole step24.33degrees and thigh step12.38degrees. First-return thigh steps remain below9.14degrees across these20 exits. This is bounded regression coverage, not a universal guarantee; defense and slashes were not in this scene sequence. Their active-special bypass remains unchanged in source.

Final same-frame disable at1089 restores every captured previous/future/presented bone position and quaternion exactly to the original cached pose (maximum component error0). Evidence: Knee1089StableOff-capture.json and Knee1089StableOff-verification.json. Final PIE false, trace0, diagnostic mode2; all owned callbacks removed. No Blueprint/settings/assets saved, no editor restart; fold live changes into the next authorized normal build.

## Evidence

Saved/Diagnostics: Knee1089-capture.json and NN trace; Knee1089-metrics.json; Knee1089Off-capture.json and causal-check.json; intermediate Knee1089Fixed-capture.json and Knee1089FullFix-capture.json; final Knee1089Stable-capture.json, Knee1089Stable-comparison.json, Knee1089StableFull-capture.json and summary; matching capture/compare scripts. Native checks: VerifyKnee1089Native.py, VerifyKnee1089Hinge.py. All completed captures disable trace, unregister callbacks and end their own PIE.
