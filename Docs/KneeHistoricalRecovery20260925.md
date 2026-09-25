# Knee recovery comparison with September 20

Status: **first historical trial (`KneeHistorical20`, archived September20 mode7), plus height-based knee-direction interpolation and independent foot-relative steering recovery.** Raised-leg guidance stays historical; near the floor the bend direction follows the foot heading. The immutable-source correction below has now been restored for post-tempering calf/regional recovery; Final Harness/normalized-coordinate trials remain removed. See [current recovery timing and pelvis360 correction](LegRecoveryTimingAndPelvis360.md). Blueprint settings, checkpoint selection, assets and graph remain unchanged. Historical sections below are evidence, not the current task queue.

## Height-based knee direction — current

The old guidance places the knee itself in the foot-facing vertical plane through the hip. As the ankle moves sideways, the knee-circle bend direction must turn farther inward to keep that placement. In the captured162–166 interval, the constraint is still fully active while the pole gains24.05degrees relative to the foot; it subsequently becomes infeasible. This is a geometric consequence of the placement constraint, not physical wobble.

At the user's request, interpolate the direction on the connected knee circle according to foot clearance: at or below2cm use foot-front bend guidance; at or above12cm preserve the historical hip-front placement; between them use the existing smoothstep height weight and angular interpolation. Clearance uses the orientation-aware minimum ankle height already computed for the foot, not absolute world ankle Z. The old plane's feasibility confidence fades toward full confidence for the feasible ground direction. Both legs use the same geometric rule; no attack-name gate, new timer, history, inference or work outside active reconstruction. Endpoints, foot rotations, segment lengths, pinning and15cm inward exclusion remain unchanged. Zero rotation tempering bypasses the source handover entirely, avoiding a nominal zero-weight quaternion conversion that changed frozen poses by rounding.

Frozen recorded endpoints162–166: ground-direction reconstruction removes24.053789degrees extra inward rotation with unchanged hip, ankle and segment lengths. A201201-case independent height sweep verifies continuous unit directions and both endpoint rules (`KneeHeightDirection-frozen.json`).

Unchanged-scene360-tick replay (`SupportingKneeHeight-live.json`) has identical authored positions through144. Exits remain145/233/323. First supporting-foot turn162–166 is−24.948degrees and knee-pole turn is−24.948degrees; later corresponding intervals likewise have zero extra turn. Supporting-thigh peak per recovery falls16.69/18.15/17.29 to9.96/10.78/10.66degrees. The recurrent rollout changes after the first correction: later kicking-thigh peaks are not uniformly lower (second exit13.80→16.87degrees). This validates the requested direction correction, not a claim that every remaining animation transient is eliminated. No retuning or Blueprint changes were used to obtain these results.

Final Live Coding build succeeded42.71s, loaded2026-09-25 12:47:23UTC. All three focused native tests passed12:48:01UTC: `HeightDirection`, `SupportSourceContracts`, `PelvisInertia.LegChain`. The fixed-endpoint native height sweep changes the knee at most0.166990cm per1mm clearance;141 height samples preserve endpoints/rotations/other leg and connected calf. The independent1001-pose chain check retains sub-micrometre length/FK error. The zero-weight source-handover rounding failure found in the first test run was fixed without weakening the assertion. Older tests asserting the superseded normalized-coordinate trial were not rerun or claimed passing. Owned capture ended; no active diagnostic callbacks remain. Include these Live Coding changes in the next authorized normal build; no restart or asset save was performed.

## Reproduction

Restoration receipt: Live Coding build succeeded48.47s and loaded2026-09-25 12:29:56UTC. Started the current scene in Play without a capture callback or automatic stop, for immediate user inspection. This is the original historical trial, not a new hybrid. Legacy tests for the later normalized-coordinate behavior were not rerun or represented as passing for this intentional restoration.

### Supporting knee turns ahead of foot — detected after restoration

User requested detection only. Play was stopped on arrival, so an owned360-tick capture of the unchanged current setup was started and ended. No code, Blueprint, settings, pin-debug or trace changes. Repeated kickL exits145/233/323; supporting leg is right. Measure the actual bend direction by projecting hip-to-knee perpendicular to hip-to-ankle, then compare its horizontal heading with ankle-to-toe heading. This is distinct from the horizontal hip-to-knee line, which is strongly affected by the tilted chain.

- Authored target ticks162→166: foot turns−27.54degrees, knee bend direction−51.60degrees. Knee gains24.05degrees in the inward direction relative to foot; final relative heading−35.60degrees.
- Physical mesh at the same ticks: foot−28.72degrees, knee−51.89degrees, matching the target behavior.
- Repeats252→256: authored foot−22.34degrees versus knee−53.09degrees;342→346: foot−22.32 versus knee−51.61degrees.
- Knee-circle radii are18–20cm at these measurements: this is a meaningful bend-direction change, not a numerical heading spike on a straight leg.

Evidence: `Saved/Diagnostics/SupportingKneeLead-live.json`, `SupportingKneeLead-analysis.json`; capture/analyzer scripts alongside them. This was the detection-only stage; the cause and subsequent requested change are documented above.

## Historical comparisons — superseded

The current scene already selects the September 20 `good.pt` attack checkpoint. It repeatedly performs kickL in Physical mode. Captures contain both the authored targets and physical mesh; the unwanted direction changes exist in the authored motion.

The baseline has nine exits at ticks145,235,...865. The right supporting knee's largest single-tick transported pole turn near the end of tempering is39.066 degrees. Its knee radius is tiny near full extension. On the raised left leg, frozen-input replay identifies the newer normalized bend-coordinate guidance preserving a lateral attack bend as the foot turns, instead of the older forward-plane guidance. This is distinct from random Jolt wobble.

There is no exact September20 Git commit. The September19 `f314e8d` and September21 `8919c05` history brackets the change; the archived mode7 in `Saved/Diagnostics/SupportSourceExperiments/ProphecyLowerTempering-experiments.inl` and `PelvisRecoveryHitchDiagnosis-20260920.md` provide the contemporaneous accepted solver reference.

### Earlier clean-source correction — removed for requested restoration

At the end of tempering, signed calf-length recovery continues. That path formerly reconstructed from an already pinned/floor-corrected ankle paired with the original NN thigh. Deriving a bend plane from those incompatible endpoints can rotate the pole strongly near extension. Regional pelvis/leg recovery used the same mutable-source pattern.

Keep the cleaned, unmodified policy pose before tempering and pinning while calf-length or regional recovery needs it. Reconstruct the final ankle from that source's hip and hinge, using the source's own Walk/Run mixture. Tempering retains its existing source behavior. This is the same immutable-reference principle already used by the every-tick pinning fix.

No change to pin selection, ankle endpoint goals, foot rotations, pelvis target, returning length curve, reconstruction geometry, attack checkpoint, timers or inference count. The two existing returning-length queries move earlier; they are not duplicated. Source copies occur only during active recovery/tempering. The ordinary unmodified single-policy path retains no additional pose copy, reconstruction, history or clock. Reconstruction-disable still bypasses this path.

Editor comparison: `Prophecy.Recovery.CleanSource 1` is the corrected default;0 temporarily selects the previous mutable-source calculation. `Prophecy.Tempering.KneePlane` remains3, unchanged from task entry.

### Earlier clean-source evidence and limits

`KneeHistoricalBaseline` versus `KneeHistorical11` captures, 931 samples each, ticks20–950:

| Recovery measurement | Before | Untouched source |
| --- | ---: | ---: |
| Supporting pole turn, exit+28 through35 | 39.066° | 14.865° |
| Supporting knee step, same interval | 5.316cm | 5.220cm |
| Supporting maximum thigh step, complete return | 9.670° | 9.697° |
| Kicking maximum thigh step, complete return | 17.422° | 17.713° |

The kicking leg is effectively unchanged, not fixed. Differences before tick175 are at most0.000151cm in authored target positions. The independent frozen tick175 calculation reproduces the old native thigh rotation within0.000005 degrees and the corrected native rotation within0.0017 degrees; the latter comparison has small floating-point differences in recorded input. This is stronger evidence than the original event simply disappearing in a different rollout.

Full restoration of September20 guidance improves the raised-leg direction but worsens support-leg thigh turns and knee displacement. Hybrid raised-plane variants also reduce that leg's lag while producing larger later support-leg movements around pin transitions. A direct projected foot-forward pole introduces severe flips when the leg/heading changes orientation. Isolating gradual raised-foot NN source admission also improves late direction but introduces larger support-leg movements. None of these variants is installed. A presentation-only stable-reference experiment was also removed; the retained correction addresses the earlier malformed source instead.

This change does **not** claim to reproduce the September20 video or eliminate every knee pop. In particular the raised leg's inward/lagging guidance still needs a solution that does not trade it for another artifact. Further work should use the archived same-input fixtures and preserve current source, reach, pinning and zero-tempering contracts.

All diagnostic captures and analyzers are under `Saved/Diagnostics/KneeHistorical*`, `VerifyCleanKneeSource.py` and `KneeCleanSource-frozen.json`. Rejected source variants were archived under `Saved/Diagnostics/SupportSourceExperiments/September25-trials-*` and removed from gameplay source. `ProphecyRecoverySourceTests.inl` contains the frozen post-pin/source mismatch regression.

Final cleanup Live Coding build succeeded37.29s, loaded11:54:27UTC. All33 focused lower tempering, pelvis inertia, policy blend, recovery calf-length, kick allowance, presentation and Walk-pinning tests passed again11:54:53UTC. The new frozen native regression measures33.4189degrees of knee-pole error between compatible and incompatible source calculations at the same endpoints, while retaining foot position/rotation, pelvis, other leg and calf length. No reflected layout changes or editor restart. Include the correction in the next authorized normal build.

The cleaned final source was replayed over the same931 samples (`KneeHistoricalFinal`): supporting end-of-blend pole peak14.854degrees, knee step5.220cm, full-return thigh peak9.696degrees. Kicking-leg behavior remains effectively unchanged. An eight-episode controlled comparison (three kickR, two kickL, two overL, one overR) completes with finite targets. OverL changes improve, but individual later knee-pole maxima are not uniformly lower: one kickL case rises11.13→22.61degrees after the recurrent trajectory changes. Do not characterize this as a universal smoothing fix. The direct frozen-input source-consistency test is the causal evidence for the retained correction; broader pose quality remains open. Results: `KneeCleanVariants-verification.json`.

Owned diagnostic Play sessions ended; tracing and rejected modes are off, CleanSource1/KneePlane3 retained. Capture buffers cleared. Unreal remains open; no asset saves, graph edits or restart during this investigation.

## Final Harness comparison — investigation only

Read the authoritative builders in `C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/` and `FINAL_HARNESS_JOURNAL.md`, including both non-live and newer Live paths. No training, harness, gameplay or Blueprint changes were made for this comparison.

Useful contracts differ from the current UE tempering implementation:

- **Complete foot-local bend direction.** `build_final_harness_standalone.py:6760` keeps both reference poles in their own complete foot frames, interpolates there, then transforms the result through the final ankle axes and projects perpendicular to hip–ankle (`standaloneFootLocalPoleWorld`, line9141). The final solve at line6969 runs after foot orientation corrections. UE `ResolveTemperedLeg` carries a previous source hinge to the new endpoints, then guides a scalar normalized lateral coordinate in the flattened foot-heading frame. Its previous-source solve does not carry foot rotation; the separate guidance is multiplied by FeetRotation and branch/heading confidence. That can under-follow a foot rotation already tempered earlier. This is a concrete architectural difference, not proof that replacing it wholesale will fix recurrent rollouts.
- **Reliable direction near extension.** Non-live `standaloneStableStartLegPoleReference` (line9048) substitutes a meaningful Easy Armed reference if the start bend is below max(2cm, 4% of total leg length). The newer Live `standaloneLiveLegPoleReference` (`build_final_harness_live_standalone.py:5169`) instead uses a separately calibrated left/right neutral-idle thigh-local direction when positional knee radius is below 0.5% of total length. It carries that through the current thigh orientation and uses the same reference for pole and calf fitting. This second approach can work without a known future Armed pose. UE's basic solver only substitutes its geometry pole below a 0.001cm positional radius; tempering confidence fades earlier but is not the same calibrated direction selection. Previously captured future support radius around0.29cm is already below the Live threshold for this skeleton.
- **One reference frame and one transition progression.** The harness blends the knee direction before applying the common foot yaw correction, avoiding an antipodal blend-endpoint flip. The Live path uses the horizontal foot-transform progression for pole interpolation (`poleProgress = transformProgress`, line10578), not independent vertical descent progress. Its journal records the exact support-yaw failure and its correction. This supports keeping UE's knee handover synchronized with the selected foot-rotation/recovery progression rather than adding another independent filter.
- **Preserve an untouched authored chain.** `standaloneApplyTravelFootTransforms` (line9291) skips reconstruction when the source hip and ankle remain unchanged and there is no final yaw correction. This guards identity, not arbitrary changed-rotation cases; it must not be copied as an unconditional endpoint-only bypass into UE.

Executed `Saved/Diagnostics/ProbeFinalHarnessKneeRules.cjs`, which extracts and runs the actual standalone foot-pole conversion/blending functions and the Live near-straight reference function. Synthetic checks: a60degree foot yaw carries the pole60degrees; opposite one-micrometre positional residuals would flip a positional pole180degrees but produce0degree change with a fixed calibrated thigh reference; common yaw179→181degrees produces a2degree pole change. The near-straight test uses an explicit synthetic calibration, not the real idle bank. Results are in `FinalHarnessKneeRules-probe.json`. These validate the local mechanics only, not current UE rollout quality or general singularity handling.

Recommended next experiment: preserve the accepted endpoints/reach and zero-tempering contract; compare full foot-local pole transport with the current second-stage scalar guidance on frozen UE inputs, then verify recurrent left/right kick and non-kick returns. Use a meaningful per-side thigh reference near extension, with a continuous handover if crossing the confidence boundary during recovery. Do not simply replace current code with the harness threshold branch: the harness selects initialization references, whereas UE repeatedly reconstructs a changing recurrent pose. No complete knee fix has been implemented by this inspection.
