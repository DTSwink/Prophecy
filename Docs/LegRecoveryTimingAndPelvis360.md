# Independent knee recovery and the pelvis slowdown near 360

Current implementation, 2026-09-25. This extends [foot-frame pole smoothing](KneePoleFootFrameSmoothing.md), preserving the accepted September20 solver and height-based knee guidance. It does not restore the rejected normalized-coordinate/Final Harness knee rules.

Presentation follow-up: [supporting-knee190](SupportingKnee190.md) fixes a mismatch between the live calf-return length and the interpolated pose. The policy destination and independent pole timer below remain unchanged; presentation/physical targets now sample that length with their own pose progress.

Recurrent-input follow-up: [pelvis380](Pelvis380Diagnosis.md) separates procedural ankle/thigh reconstruction and timed pole steering from the NN's next input, including every-tick pinning commits. The displayed/physical-target solve, destination and timer below remain active. Actual physical deviations and pin endpoint displacement still enter recurrence; no extra pose history or inference is introduced.

## Node

`Set Leg Reconstruction Recovery` (Agent):

- **Duration Seconds**, default1: independent smoothing window after returning from attack, parry or dodge. One authored second means60 unpaused game ticks. It does not extend pelvis/foot tempering or hold their positions.
- **Pole Turn Speed Degrees Per Second**, default180: maximum additional steering around hip→ankle, measured relative to the moving foot. “Per second” means per60 game ticks. The former tempering-only cap was equivalent to360 at the normal30Hz policy rate.

The existing reconstruction still chooses its target. Its geometric guidance, foot movement and connected chain remain separate from how quickly the pole approaches that target. The independent window continues limiting the normal target after tempering retires. At duration expiry, any residual finishes at the chosen speed rather than being dropped abruptly; it retires as soon as both knees can follow their targets without limiting. Longer duration means a longer protected recovery window, not a slower speed by itself.

Zero duration retains the previous tempering-only behavior and creates no independent state/clock. Speed must be finite and positive. Retuning an active window changes its settings without restarting elapsed time. A new special, reset, disabled leg reconstruction or actor/world teardown cancels active work. Disabled reconstruction cannot start another window. Settings survive cancellation, but teardown removes them. No actor layout change, new inference, hidden recurrent pose or permanent pose-history buffer.

The shared60-tick clock accumulates budget between NN publications. Duplicate reads get zero budget; each foot receives the same budget. Normal locomotion after retirement performs no extra pose math/copies or timer work (the manager retains the standard empty-state check). Active special motion bypasses this recovery entirely. Both full and half special exits use the common notification path; pending defense does not count as an active special.

## Pelvis diagnosis and fix

The current repeated `overR` scene reproduces the reported slowdown at369–371. Horizontal pelvis travel goes3.21→2.51→4.03cm per displayed tick. This occurs after tempering has finished.

Journal/Git investigation found two historical problems: abruptly reapplied knee-plane guidance affected subsequent NN pelvis predictions; later calf-length recovery also used a modified ankle as if it were the untouched NN hinge. The latter immutable-source correction is restored for calf/regional recovery only. **It did not fix the present slowdown by itself**: switching it on after366 changes369 travel2.510→2.503cm. Do not conflate that earlier fix with the current causal result.

Exact checkpoint replay matches the recorded Walk outputs within1.252e-6. At367 the right thigh is changed13.18degrees by reconstruction, but the pole steering around the final hip/ankle axis is essentially zero. The calf is forced toward rest length while the configured locomotion clamp permits additional length. This straightens the pinned supporting leg and changes the thigh orientation/velocity features passed to the next NN prediction.

Holding the complete369 input fixed except the preceding right thigh and its corresponding velocity feature:

| Intervention | Forward NN displacement per policy step |
| --- | ---: |
| Recorded baseline | 4.906cm |
| Pole-only cap3/6/12degrees | 4.906cm |
| Allow0.5cm more calf length | 6.257cm |
| Allow1cm more | 6.651cm |
| Allow2cm more | 6.972cm |

This is why a longer pole timer alone is not the fix for this particular pelvis event.

Calf recovery now blends the captured outgoing length toward the current locomotion target length **within the user's explicit enabled calf-clamp allowance**, instead of always blending to zero extra length. The requested destination comes from the accepted pelvis/foot and NN thigh before the recovery solve. It is bounded by the same symmetric allowance already used by the physical ankle joint. No new hardcoded stretch range is added. Disabled/unconfigured/zero allowance keeps the old rest-length destination.

The existing finite calf-return clock remains authoritative: `lerp(current bounded locomotion destination, captured outgoing delta, remaining return weight)`. Initial weight1 preserves the outgoing length exactly. New NN samples update the destination without restarting the clock. The shared query and existing presentation publication make reconstruction, render length and physical drive target consume the same value. Completion removes the destination sidecar and all existing length-return state. Physical joint ranges retain their configured behavior; this change does not enlarge them. Locomotion clamp snapshot/blend values are read as they change.

## Controlled result and limits

Same-binary baseline versus enabling only the length destination after366 has **identical authored positions through366**. Subsequent horizontal travel:

| Tick | Before | Length-destination fix |
| --- | ---: | ---: |
| 367 | 3.210cm | 3.210cm |
| 369 | 2.510cm | 3.468cm |
| 371 | 4.034cm | 3.704cm |

Thus the local slow/fast reversal is removed without changing the earlier rollout. The pelvis and foot rotations at367–368 remain identical; the accepted right-foot position differs0.212/0.688cm as the consistent longer calf avoids the prior endpoint correction. Do not claim this complete fix preserves every endpoint: the pole limiter does, while changing the permitted calf recovery length can change reach/presentation corrections.

With all final changes enabled from start,600 ticks complete. Six punch exits show first12-frame foot-relative pole maxima about3.7–4.6degrees. The five fully captured windows run137–197,229–289,319–379,411–471 and497–557, then stop their smoothing work. The sixth starts589 and is cut by capture completion. The360-region pelvis advance remains continuous; the independent same-prefix test above is the causal evidence, not just the changed full rollout.

Alternating kickL/kickR baseline/final600-tick captures cover five complete24-frame exit windows plus the beginning of a sixth. Each window's maximum pelvis second difference decreases; the largest complete-window value1.874→1.459cm/tick². Thigh peaks remain in the same range; some individual steps increase (third kicking-left11.65→13.29degrees), so this is **not** a claim that every kick sample is unchanged or better. Full kicks retain their original checkpoint routing and bypass recovery during the attack. User visual acceptance of the combined recovery remains the final subjective check.

## Validation and operational state

Ten focused native checks passed14:17:20UTC: independent recovery clock, foot-frame pole smoothing, immutable recovery source, height guidance, support-source contracts, pelvis leg chain, recovery calf length, calf destination, kick allowance and shared60-tick clock. They cover30/60/120FPS, duplicate reads, convergence after expiry, zero duration, cancellation, cleanup, signed bounded calf destinations, unchanged initial length and shared timing. Final small cleanup build23.32s; the two affected timer/destination checks reran successfully14:22:45UTC.

The Blueprint function is reflected and callable; pose Blueprint inspection reports status3, zero stale native properties/pin types and preserved wiring. No Blueprint/map edits or saves, engine restart, checkpoint change or push. Live changes must be included in the next authorized normal build. All diagnostic PIE sessions were owned and ended. Trace controls are0; editor comparisons `Prophecy.Recovery.CleanSource`, `Prophecy.Recovery.PoleWindow` and `Prophecy.Recovery.LocomotionLengthTarget` are restored to1.

Evidence under `Saved/Diagnostics`: `Pelvis360*-capture.json`, `Pelvis360*-nn.jsonl`, `Pelvis360-replay.json`, `ProbePelvis360Correction.py`, `Pelvis360V2-length-comparison.json`, `LegRecovery-*-live.json`, corresponding frozen pole records, `LegRecovery-kick-regression.json`, `TestIndependentLegRecovery.py`, `VerifyIndependentLegFinal.py`.
