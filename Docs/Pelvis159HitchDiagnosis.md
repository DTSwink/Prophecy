# Pelvis slowdown at ticks 159–161

Initial diagnosis2026-09-24 used the unchanged testNN scene. The subsequent user-authorized trial below changes only the connected recovery solver. Blueprint wiring/values and assets remain untouched; no restart.

## Reproduction

Two captures reproduce the same pelvis positions exactly; the Blueprint tick counter equals the captured 60 Hz frame number. Agent is kinematic throughout the event. PhysicalMesh pelvis equals the interpolated authored target.

| Ticks | World Y advance / tick | World Z change / tick |
| --- | ---: | ---: |
| 157–158 | 3.730 cm | +0.534 cm |
| 159–160 | 2.103 cm | -0.464 cm |
| 161–162 | 3.517 cm | +0.336 cm |

The forward slowdown is about44%, with a short vertical reversal. Pelvis and both leg recovery weights remain100% Walk. Tempering approaches identity smoothly and retires at161; the problematic raw prediction already exists at159, so retiring that blend is not required to produce the hitch.

## Specific mechanism

The connected leg solver finishes with guidance preserving the source knee's lateral stance relative to the foot heading. It attenuates that guidance when the requested plane does not intersect the knee's reachable circle. This is a continuous function of geometry, but it can traverse its complete activation range between adjacent30 Hz predictions.

For the left leg:

| Policy tick | Knee-circle radius | Plane feasibility Q | Guidance strength | Applied plane turn |
| --- | ---: | ---: | ---: | ---: |
| 153 | 7.919 cm | 1.707 | 0 | 0 degrees |
| 155 | 0.286 cm | 32.504 | 0 | 0 degrees |
| 157 | 6.684 cm | 0.563 | .9854 | -45.934 degrees |
| 159 | 11.460 cm | 1.195 | 0 | 0 degrees |

Abs(Q)>1 means that plane is not reachable. As the nearly straight leg bends again, the guidance briefly returns almost fully and rotates the thigh strongly. This is not a claim that thigh aim itself bends46 degrees: the correction rotates the whole thigh about the hip–ankle axis, including its orientation. The resulting pose and its velocity features are fed back to the next Walk prediction.

Independent double-precision geometry replay matches the captured thigh orientation within0.0009 degrees at all these samples, and within roughly0.00001 degrees at the offending157 sample.

## Fixed-input causal checks

Replay of the exact Walk checkpoint over all recorded locomotion inputs matches native output within2.027e-6 in output units. At159, preserve the complete recorded input except the specified left-thigh orientation and its corresponding velocity feature. Rebase alternative orientation into the same recorded input frame. No previous altered rollout is used.

| Single-step159 input | Raw forward advance / policy step | Raw vertical change / policy step |
| --- | ---: | ---: |
| Recorded baseline | 4.181 cm | -0.938 cm |
| Remove only preceding left knee-plane turn | 5.679 cm | -0.003 cm |
| Remove only preceding right knee-plane turn | 4.196 cm | -0.892 cm |
| Use preceding raw left-thigh prediction | 6.249 cm | +0.774 cm |
| Smoothly cap preceding left plane turn at20 degrees | 5.143 cm | +0.209 cm |

The20-degree diagnostic uses cap*tanh(turn/cap);10/30-degree comparisons are also retained. They are offline probes, not installed fixes. The20-degree comparison improves the dip but leaves appreciable slowdown. It has not passed full recurrent rollout or knee-regression validation and must not be described as a solution.

These interventions establish a local causal contribution from the knee-plane correction to this specific pelvis prediction. They do not prove that simply removing reconstruction, disabling pinning, or changing the whole rollout preserves the accepted motion. Other corrected input features also contribute.

## Current pinning observations and boundaries

Effective left pin is1 at153/155,2/3 at157,1 at159. This interacts with the endpoint geometry, but this investigation did not independently isolate the new backward-transfer feature as the cause. It must not be blamed solely because it is recent. Knee-pop smoothing operates on presentation, whereas this event exists in the recurrent authored state.

Next correction should preserve the accepted connected endpoints, knee direction, foot descent and limb lengths while avoiding abrupt reintroduction of strong stance guidance after an infeasible/near-straight interval. Validate frozen-input behavior first, then complete repeated kick and non-kick recoveries; disappearance of the original frame159 event in a different rollout alone is insufficient.

## Evidence

Under Saved/Diagnostics:
- CalfAnkleConnection-pelvis159-baseline.json; CalfAnkleConnection-pelvis159-pins.json
- FootVibration-nn-pelvis159-baseline.jsonl; FootVibration-nn-pelvis159-pins.jsonl
- AnalyzePelvis159.py; AnalyzePelvis159Pins.py
- ReplayPelvis159.py; Pelvis159-replay.json
- ReplayPelvis159Geometry.py; InspectPelvis159Geometry.py; Pelvis159-geometry-details.json
- ReplayPelvis159Candidates.py; Pelvis159-candidate-replay.json


## User-authorized replacement trial

Status: candidate for user acceptance, not a claim of globally perfect animation.

The active replacement carries a normalized bend coordinate in the source foot-heading frame. It describes the knee direction on the connected leg's circle, rather than demanding an absolute lateral knee position. This coordinate is always in[-1,1]; the infeasible-plane gate no longer disappears/reappears. Near straight source legs, vertical toe headings or degenerate side projections, confidence tends continuously toward the already transported hinge. Retain the existing branch, source admission and authored rotation-follow value.

The accepted endpoint projection,15cm inner clearance, floor/pinning order, calf-length recovery, foot rotations, pelvis target and source clocks are untouched. No attack-family gates, additional NN runs, timers or persistent history were introduced. Ordinary unmodified locomotion still skips ResolveTemperedLeg through the existing identity guard; all-one/frozen and regional timing contracts remain tested. The old lateral-plane work is bypassed in the new path.

An initial diagnostic removing all stance guidance (mode2) improved the hitch but worsened subsequent knee behavior, so it was rejected and removed from source. The retained normalized-coordinate trial is mode3. Editor console `Prophecy.Tempering.KneePlane 1` selects the original solver immediately;3 restores the trial.0 retains the older zero-plane diagnostic. Candidate is the source default, including non-editor behavior, pending visual acceptance; normal editor DLL has not yet been rebuilt, so preserve live patch or fold it into the next authorized normal build.

### Paired scene coverage

Fresh same-binary baseline and candidate have identical authored targets through tick130, so the first attack and recovery entry are comparable. The older diagnosis capture differs from the fresh baseline beginning at7; it remains a frozen regression fixture, not the paired rollout baseline. This distinction matters because a changed rollout alone is not causal proof.

In the fresh current scene, six measured return windows show:
- First-return maximum pelvis second difference:2.519→1.168cm/tick squared.
- Largest thigh step over those windows:17.462→11.003degrees per displayed tick.
- Current159 horizontal world-Y advance changes from2.796cm to3.165cm, with the delayed161 slowdown changing2.198→3.292cm. Candidate155/157/159/161 advances3.138/3.158/3.165/3.292cm; vertical values remain positive across that interval.
- During active tempering, maximum knee-direction deviation from foot-forward falls51.6→29.7degrees left and48.4→43.2degrees right. Full post-return motion differs through recurrence; some later ordinary-Walk poses have larger sideways deviations than their baseline counterparts. Do not claim every frame or episode improves.

Eight additionally driven attacks (kickR twice, kickL twice, overL, overR, slashL, slashR) were compared with the same transient input-driving script. Overall maximum thigh step18.127→16.748degrees, pelvis second difference1.567→1.398cm/tick squared. Some individual calf steps, knee directions and later trajectories worsen; this is coverage for the trial, not certification that all tradeoffs are gone. The original directional metric also flags some extreme ordinary-walk poses after the modifier has retired.

Final unchanged-scene replay after cleanup differs from the earlier candidate by at most0.001877 across all captured mesh transform components (2076 agent rows), consistent with small numerical build differences rather than a new algorithm. Never describe this as bit-exact.

### Validation and evidence

Existing23 recovery/native tests passed with the trial selected. A further frozen-input fixture records the original157 previous pose, raw NN output, endpoint geometry and settings; it checks original large turn, candidate small turn, independent double-precision rotation oracle, unchanged pelvis/ankle/foot/toe, connected calf and a1001-point near-straight endpoint sweep. Its executed receipt is recorded in the journal after validation; Live Coding can retain anonymous test implementations, so the fixture is called through the externally linked presentation regression entry.

Additional evidence under Saved/Diagnostics: CalfAnkleConnection-pelvis159-fresh.json, -unified.json(rejected), -coordinate.json, -final.json; -variants-old.json/-variants-coordinate.json; their Unified159-metrics-* analyses; PrototypeBendCoordinate.py and Pelvis159-bend-coordinate.json; Unified159-final-equivalence.json. Source rollback copy: LowerTempering-before-unified159.inl.

### Final executed receipt

Final Live Coding build succeeded in21.13s and loaded14:32:52UTC on2026-09-24. No reflection or retained-layout changes. The newly added fixture was first missed by an anonymous Live Coding test entry, so it was moved to the existing externally linked RecoveryCalfLength test. Its first real run revealed that console priority prevented the test from switching to legacy mode; the harness now uses matching console priority and restores the prior mode. This was a validation-harness failure, not a failed candidate-pose assertion.

At14:33:29UTC the executed frozen-input fixture passes: original thigh step46.256124degrees, new4.866947degrees; the1001-sample horizontal endpoint sweep reaches a near-straight configuration with maximum adjacent step0.372004degrees. Independent rotation oracle, unchanged endpoint/pelvis/foot/toe and calf connection assertions pass. The remaining22 focused recovery tests passed14:31:34UTC; combined with this rerun, all23 focused tests pass. No failing assertion was removed or threshold relaxed.

Fixed-input checkpoint replay using the normalized left bend only changes159 raw forward4.181→5.679cm and vertical-.938→-.008cm; changing both bends yields5.721cm and+.004cm. This proves the targeted feedback effect without relying on the later altered rollout, but does not claim an identical complete trajectory.

Owned captures ended, tracing off and memory released. Trial3 is selected for the user's inspection; no user Blueprint/map edits, saves, restart or push. User acceptance remains pending.
