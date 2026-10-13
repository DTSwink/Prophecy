# Lab sheathing attachment and tip alignment — October 13

User requested both planners capture the sword when the rotation cone turns green, align the tip with translation/rotation using reach speed limits, then slide. This is lab work only. Unreal is unchanged.

## Implementation decisions

- Capture the first eligible tick using the displayed sword's full quaternion error, including roll. No body-ready or tip-distance gate delays ownership. Preserve world transform and blade scale at capture.
- Store the sword and tip alignment in the holster's frame. Holster motion carries the whole target; no reaching refits continue after capture.
- Aim the current grip-to-tip direction toward the entrance, then project the desired quaternion into the rotation-tolerance ball around perfect alignment. Translation closes the remaining gap. Interpolation between the captured and projected rotations stays inside the tolerance.
- The alignment duration bounds both tip/wrist translation and wrist rotation with the existing max reach speeds. The translational bound includes the rotational lever arm. It is deliberately conservative, not an exact maximum-speed trajectory. Alignment runs on normal60Hz time; neither timing curve accelerates this new phase.
- Freeze shrink during alignment. At tip arrival reuse the existing slide position/rotation correction and shrink behavior. Actual tip error must be≤0.0001cm before starting the slide, rather than accepting the old2cm gate.
- The new phase keeps the hand on the sword, with existing arm lengths. If the target is unreachable, the solver's reach clamp keeps the grip together, the actual tip stays outside the entrance, and the UI reports the arm reach limit. This does not promise that every shrink/body combination can finish.
- Continue the authored body toward its clear pose during alignment. If alignment finishes first, slide body interpolation starts from the pose actually reached, rather than snapping to the authored clear pose.
- New alignment guide solves transport existing upper/lower-arm roll through segment-direction changes. Without this, applying the elbow swivel to a nearly straight arm caused160deg axial changes at the first alignment step in an off-mode run case. This change is scoped to the new alignment stage.
- Both modes share the60Hz post-capture sheathing continuation. No-cheat uses the existing causal approach; off uses the existing future-recording approach, sampled with its curves/inertia/pole/head result through capture. Drawing is unchanged. **Off-mode sheathing's post-capture slide/early-return sampling now uses the shared60Hz continuation instead of its previous240Hz return guides.** This is an implementation consequence worth comparing visually; it is not a claim of bitwise preservation after capture. User parameters, head/FK clocks and early-return thresholds are retained.
- Playback/scrubbing uses cached FK poses, not render-time arm solves. Fractional sword alignment is holster-relative. Interpolating the cached FK chain gives a small grip approximation between ticks (maximum0.271cm in the36-case stress suite), while tick grips are exact. No hidden hand teleport corrects that residual.
- `Align tip` appears in the existing phase/status displays. Leeway remains visible during it. No new tuning controls or saved parameters were added.

## Verification

- `test_tipalign.cjs`:36 cases (both modes × idle/walk/run × linear/nonlinear curves ×0/20/65% shrink).24 complete;12 no-shrink cases cannot reach and remain visibly active/blocked without falsely sliding. Rotation stays within tolerance, capture/slide transitions preserve sword transforms, actual slide-entry tip error≤2.5e-13cm, tick grip error≤1.2e-13cm. Requested holster-local wrist speed≤80.1% of the linear cap and≤26.8% of angular cap in this matrix. Both sequence orders complete with the saved shrink/body settings.
- Saved-profile before/after comparison: every bone position identical through capture for idle/walk/run in both modes (floating noise≤4.5e-16cm); drawing unchanged throughout. Quaternion comparison noise≤0.0000042deg.
- `test_online.cjs`: current/past-only input reads, future-input poisoning, duration independence, all motion/actions, curves and sequences pass.
- Existing isolated `test_online_ui.cjs` passes. Additional isolated UI script verifies `Align tip`/green leeway, exact tip at slide entry, both modes, D→S, worker rebuilds, snapshot capture, no browser errors. User state is not written by these tests.
- Two older scripts, `test_sequence.cjs` and `test_sequence_speeds.cjs`, fail on fractional gait precision / cached-array identity when run with the current saved No-cheat state. Both failures were reproduced using the backed-up pre-change code; these are not new regressions and were not weakened or fixed in this change.

Evidence and backups: `Saved/Diagnostics/TipAlign20261013/`. UI images from the reused isolated harness are in `Saved/Diagnostics/NoCheatGrip20261012/tip-align-{causal,reference}.png`. No Unreal build, editor interaction, asset save, or Git push.
