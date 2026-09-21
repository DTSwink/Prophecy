# Pelvis hitch during post-attack backward walking

Diagnosed in the user's current unsaved testNN setup on 2026-09-20. Initial diagnosis made no runtime/Blueprint changes. The later support-source refinement below changes two runtime source files; Blueprint/scene wiring and unsaved assets remain untouched. All scene experiments used temporary PIE instances; owned sessions ended and diagnostic trace settings were restored.

## Reproduction

Baseline `Saved/Diagnostics/PelvisHitch-20260920-193832` records 600 game frames, Blueprint `tick debug`, physical body state, presented/future NN targets, root/cube positions and the existing lower-policy input/output trace. Possessed actor is `BP_ProphecyManualPoseAgent_C_1`.

The attack starts at tick121 and has returned to locomotion by tick149. The post-attack tempering return lasts30 ticks (0.5 authored seconds); it is inactive by179. The recovery source and normal destination are both Walk: pelvis and both leg Walk weights stay1. This reproduction is not a Run-to-Walk mixture switch.

The reported hitch is present in the presented pelvis target itself. Backward displacement (world negative Y) per game frame:

| Tick | Current setup | Reconstruction disabled after tick172 |
|---|---:|---:|
|173|2.534cm|2.534cm|
|175|1.652cm|2.910cm|
|177|2.714cm|3.184cm|
|179|1.575cm|3.280cm|
|181|2.489cm|3.352cm|

The physical pelvis follows the baseline target within approximately0.15–0.31cm over172–182. Root position is smooth and identical between these replays through the diagnostic interval. No missing game samples: dt stays1/60 and interpolation alpha alternates0.5/1 as expected for30Hz NN publication.

## Causal isolation

The strongest experiment is `PelvisHitch-20260920-194230`: disable only the existing leg-chain reconstruction switch after172. Keep tempering values, return clocks, inputs and physical simulation unchanged.

- At173 the NN inputs and outputs, published pelvis and root conditioning match baseline exactly. Reconstruction changes primarily thigh rotations. Foot rotations remain exactly equal; foot position changes are only vertical, approximately0.001cm left and0.1902cm right.
- At175 current and previous pelvis input and root conditioning still match exactly. The current leg input differs, because the previous step's reconstructed leg state is fed back into the NN. The NN now predicts a different pelvis delta (largest coordinate difference2.449cm per policy step), and the slowdown is absent.
- The same tempering values and blend schedule are active in both runs. This isolates the feedback through the reconstructed leg state, rather than a direct pelvis clamp, mover jump or a physics obstacle.
- Across151–195 the baseline published pelvis position equals `lerp(previous published pelvis, current NN input pelvis + raw NN delta, pelvis tempering)` within0.000004cm. No additional pelvis position correction is responsible for the hitch.

Code path: `ApplyOutputBatch` in `ProphecyNNLocomotionManager.cpp` applies tempering and pinning, calls `ResolveTemperedLeg`, copies the corrected full lower pose to the recurrent state, and `BuildInputBatch` supplies that pose/history to the next lower inference. The accepted knee solver in `ProphecyLowerTempering.inl` changes thigh orientation and, where necessary, foot reach/floor placement. The next Walk prediction responds by changing pelvis movement.

Additional valid experiments, all identical to baseline before intervention and with unchanged root trajectory through149–190:

- `193932`: disable all tempering during recovery; two reported slowdowns disappear.
- `194131`: return pelvis tempering to1 after150, keep feet return; a slowdown remains, shifted to177.
- `194147`: return feet tempering to1 after150, keep pelvis return/reconstruction; a slowdown appears earlier at171. Neither group alone is a complete remedy.
- `194158`: disable reconstruction after150, keep the original tempering return;173–181 displacement remains approximately3.16–3.39cm/frame.

Earlier `194009`, `194026`, `194057` selective trials are excluded: hidden Blueprint functions were unavailable through Python's generated method names. The corrected scripts use reflected `call_method`; valid selective trials have `applied.json` with success=true.

## Conclusion and limits

The hitch in this setup is a leg-reconstruction-to-NN feedback interaction during recovery. Physical simulation reproduces an irregular pelvis target. This is not evidence of an invisible Jolt blocker. It is also not a direct pelvis projection or a run/walk switch.

The follow-up below isolates thigh orientation and its history as the dominant trigger. It does not prove every historical pelvis hitch has this cause. Disabling reconstruction is a diagnostic, not an accepted fix: the user has already approved the current knee behavior. Any repair must preserve that behavior and validate the recurrent-pose contract before changing what the NN sees.

Analysis helpers: `Saved/Diagnostics/CapturePelvisHitch.py`, `CapturePelvisHitchAblation.py`, `ComparePelvisHitch.py`, `PelvisHitchCausality.py`. One-step comparisons are saved to baseline `causality.json`.

## Follow-up: checkpoint and solver replay

Offline replay of the installed Walk checkpoint reproduces all 43 recorded output channels over ticks151–195 within a maximum absolute error of 1.55e-6, for both baseline and the after172 reconstruction ablation. These tests leave Unreal and the user's setup untouched.

At tick175, replace selected baseline input fields with the ablation's fields while retaining the identical pelvis/history/root conditioning. Numbers below are the raw NN pelvis delta on the principal backward-motion coordinate, in cm per policy step; they are not the final tempered displacement per game frame:

| Input replacement | Predicted delta |
|---|---:|
| None | -3.2517 |
| All changed leg fields | -5.7008 |
| Left thigh rotation and its difference features | -5.3425 |
| Right thigh rotation and its difference features | -4.5405 |
| Foot positions and their difference features | -3.2505 |

The small foot-position corrections barely affect backward motion. Both thigh pose and frame-to-frame difference features matter. Group effects are nonlinear and must not be added. Input packing and difference scaling match the training implementation; recorded differences equal `(current - previous) / pose_delta_scale_final` within float precision. No stale history or units mismatch was found.

An independent geometric replay of the accepted solver, using the runtime reference offsets and already-resolved ankle endpoints, reproduces the recorded final thigh rotations within approximately0.0001 degrees. It identifies a large contribution from the added knee-forward guidance:

- Tick173 left thigh: NN requests about5.32 degrees from the current input; the final published change is35.11 degrees. Transport before knee guidance changes the previous published thigh by7.73 degrees; guidance adds a23.79-degree turn around the hip-to-ankle axis. These angles use different comparisons and are not additive.
- Tick177 right thigh: guidance adds approximately23.24 degrees; the final rotation differs from the raw NN prediction by35.55 degrees.
- Removing only the tick173 left knee-guidance contribution from the next input, with its difference features recomputed, changes tick175's principal pelvis delta from -3.2517 to -4.9694cm. Removing only tick177 right guidance changes tick179 from -2.6491 to -3.5166cm. These are one-step sensitivity experiments, not validated production fixes; other pelvis coordinates change too.

The implementation interaction is in `ProphecyLowerTempering.inl`: knee-guidance strength depends on geometry, with an exact-zero feet-rotation guard, but does not fade toward the raw NN thigh rotation as tempering approaches1. At177 feet rotation tempering is about0.9885, yet the right thigh still receives the large correction. At179 tempering retires and this reconstruction path is bypassed. Therefore a nearly completed tempering blend does not imply nearly unmodified thigh input. The first slowdown occurs before retirement, so the final bypass alone does not explain it.

The left guidance also approaches a feasibility boundary: its plane-intersection parameter Q is about-0.818 at173 and below-1 at175/177, where the requested knee plane cannot be reached and guidance stops. The 15cm inner forbidden region is not active here: hip-to-ankle distance is approximately76cm at173. Do not change that accepted safeguard as a remedy for this hitch.

Evidence: `Saved/Diagnostics/PelvisHitchInputs/replay.json`, `second_hitch_replay.json`, `thighs.json`, `solve_replay.json`. Helpers: `ReplayPelvisHitchInputs.py`, `PelvisHitchThighAudit.py`, `PelvisHitchSolveReplay.py`. No runtime source or Blueprint fix was applied. A repair must address the correction's transition and recurrent feedback without reintroducing the previously rejected knee snaps, outward drift, jitter or backward bending.

## Support versus descending leg experiments and retained refinement

The captured attack is **kickR**. The large correction at173 is on the LEFT supporting leg; the RIGHT kick foot is descending and receives its late correction after landing. The support foot is not literally world-pinned throughout172–182: it moves roughly4–5cm per policy sample. Its forward knee displacement stalls while its full thigh orientation keeps turning. Much of that orientation change is axial twist, so knee-point measurements alone miss the signal seen by the NN.

Eight editor-only variants were evaluated in temporary PIE, each for four complete recoveries, against an exactly reproduced baseline. Trials are retained under `Saved/Diagnostics/SupportSourceExperiments`; rejected runtime paths were removed from production code.

| Trial | Result |
|---|---|
| Fade knee-forward guidance near the floor | Smaller pelvis hitch, but13–15cm lateral support-knee drift; rejected. |
| Follow raw NN source near floor and fade guidance | Lateral drift up to19cm; rejected. |
| Follow NN source near floor, keep full guidance | Good late recovery, but an initial54.5-degree support-thigh step; rejected abrupt handover. |
| Scale source following by feet-rotation follow or its square | Smaller initial handover, but later support-knee drift up to17cm; rejected. |
| Limit source handover to10/20/30 degrees per policy step |20-degree variant gave the strongest joint pelvis/leg result and was retained. |

A separate twist-only probe improved the next pelvis prediction while preserving knee points, but changed calf rotation by27–30 degrees and degraded hinge alignment. It was not installed as a runtime candidate.

The retained source is captured after raw NN pose cleanup, before tempering and pinning. A support factor based on final sole clearance is1 below2cm and smoothly0 at12cm. It admits the raw source pelvis/ankle/thigh with a20-degree bound on the previous-to-NN source rotation per policy step. The accepted connected-leg and forward-knee solve then runs normally. The same published pose continues into lower recurrence and upper conditioning. This changes actual coherent reconstruction rather than supplying a separate invisible NN pose. All-zero/frozen controls and high-foot solving retain their previous paths; all-one/inactive settings add no copies, timers or inference. Each leg selects its own Run/Walk source, including its source pelvis.

Long comparison: baseline `PelvisHitch-20260920-202427`, candidate `PelvisHitch-20260920-202525`,1440 game frames each,11 completed recoveries. `CompareLongRecovery.py` detects actual tempering windows: candidate attacks finish two ticks earlier from the third recovery, so fixed149+120n windows miss its first return frames.

- Pelvis position second-difference peak in each hitch interval: baseline1.408–2.103cm, candidate0.753–1.084cm; reduced in every cycle.
- Descending right foot remains monotonic above20cm, right knee stays in its forward plane, no measured branch reversal.
- Right-thigh rotation at retirement:7.3–8.4 degrees/game frame versus15.5–16.0; left-thigh maximum12.97–15.67 versus17.56–24.68.
- Left-knee lateral offset generally improves; worst relative regression0.77cm in cycle2, with no accumulating drift across11 recoveries.
- Early right-foot relative-pelvis path changes by up to1.17cm forward,2.61cm lateral,4.45cm vertical. Later descents reach20cm height one NN step later. The airborne algorithm is unchanged, but the recurrent model's trajectory is not bit-identical.
- Initial right-knee positional acceleration peaks increase9–18% in some later cycles, although foot acceleration, retirement and orientation continuity improve. Hinge alignment remains imperfect (roughly19 degrees left/15 right maximum); endpoint agreement alone is not claimed to prove anatomical perfection.

Independent report: candidate `long_recovery_independent_review.json`. Other helpers: `CompareRecoveryLegs.py`, `RecoveryHingeContinuity.py`, `SummarizeRecoveryExperiments.py`. This bounded test supports a refinement in the current setup; it does not establish universal absence of hitches or exact preservation of the old descent. User visual acceptance remains pending.

Runtime source: `ProphecyLowerTempering.inl` and `ProphecyNNLocomotionManager.cpp`. No reflected-layout changes. Editor comparison CVar `Prophecy.Tempering.SupportSource` defaults1;0 restores the old source selection while retaining all other controls. Packaged builds have no comparison CVar. Live Coding loaded the cleaned implementation at18:30:17UTC without restart or asset saves.

Final cleaned-code verification: `PelvisHitch-20260920-203359` captured600 frames and exactly matched the selected mode7 run `202148` in every lower input, lower output, published lower pose and presented pelvis target (maximum difference0). New `SupportSourceContracts` passed, covering frozen/raised-foot bit equality, preserved pelvis/foot/toe state, reachable ankle/segment lengths and decoded calf FK. `TranslationAxes`, `ReturnTimeline`, `SeparateReturns`, `PelvisInertia.LegChain` and `PolicyBlend.RegionalPose` also passed. The older `RootLocalPinAndChain` test reports two failures in its pre-existing oblique-pole/sideways-crossing assertions; those calls supply no NN source and execute the unchanged previous-source path.

Legacy-test isolation: simplified old Mode0 and final null-source function bodies have identical normalized text hashes. The oblique test's pure-forward radial-pole requirement (>0.999) contradicts the accepted vertical knee-plane solution: the knee is forward with zero lateral offset, but its radial pole forward dot is0.7938. The sideways fixture includes an initial endpoint jump and reports2.053 degrees against a1.146-degree bound; settled progressively finer sweeps converge1.246→0.724→0.419→0.241 degrees with no branch reversal. These old expectations were not weakened to make the suite green, and the accepted solver was not changed for them. Evidence: `Saved/Diagnostics/RecoveryCandidateReviewLegacyTests.json`. Thus six focused tests pass and one legacy test retains two unrelated assertion failures.
