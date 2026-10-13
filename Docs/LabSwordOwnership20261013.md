# Lab sword attachment ownership — October13

With **Leeway attachment phase** off, **Sheathing entry → Tip distance
threshold · cm** now controls the tip-to-entrance gate (default2cm), alongside
rotation tolerance. The debug sphere and distance readout use the same value.
This setting does not change the enabled attachment/alignment phase.

User explicitly requested the sword be owned by the holster immediately at
attachment, with the arm following rather than controlling it. The previous lab
only labelled it attached: Align tip still displayed the solved-hand sword and
waited for that hand to deliver the tip. This contradicted the requested behavior.

The shared S continuation in `online.js` now displays the sword from its
holster-local alignment target. Alignment completion uses that same sword;
arm reach error cannot move it or delay sliding. Slide already uses the authored
sword target, including early FK return. Fractional alignment playback always
samples the holster-local path, including unreachable-hand cases. Head aiming
uses the actual displayed sword. Capture and approach are unchanged.

The arm remains limited by its bone lengths; no stretch or exact-grip illusion
was added. Existing hand-error metrics remain visible, and Align tip status
reports hand tracking error instead of falsely saying sword motion is blocked.
The spine/clavicle reach schedule fix remains intact. No settings, assets,
Unreal source/runtime, new controls, or Blueprint edits in this turn.

## Verification

-36 cases: both planner modes × idle/walk/run × linear/custom curves ×
  shrink0/20/65. All attach/align/slide/return complete.14 include unreachable
  hands; maximum reported alignment grip gap13.891cm in stress cases. Actual
  sword tip reaches mouth at the authored alignment endpoint, error<2e-13cm.
  Integer and fractional path, capture continuity, rotation tolerance, scale,
  speed caps, and both sequence orders pass.
-Adversarial test translates solved arm100cm after capture: sword path and
  slide timing remain exactly unchanged in both modes; hand error is exposed.
-12 body-schedule regression cases pass; no attachment spine snap reintroduced.
-Causal input audit and future-input perturbation tests pass. No future gait
  access added. No-cheat-off retains its explicitly labelled old reach planner.
-Six drawing cases (both planners × three motions) match pre-edit frame data
  exactly. Saved `state.json` bytes unchanged.
-Isolated UI test passes both modes, sequence, curves, body worker, playback
  continuity, save/reload and runtime-error checks. User window/state untouched.

Current saved S: attachment84 unchanged; slide93→90; fully seated122→119;
full return193→191. The removed3tick wait was the unreachable-hand gate, not an
alteration to sliding speed. The old No-cheat-off D→S sequence failure reported
during the spine fix now passes the full tip-alignment test as well.

Tests: `test_tipalign.cjs`, `test_sword_owner.cjs`,
`test_attach_body_schedule.cjs`, `test_online.cjs`, `test_online_ui.cjs`.
Backups/receipts: `Saved/Diagnostics/LabSwordOwnership20261013/`.
The old test requiring the sword to stay on the unreachable hand was replaced
with assertions of the explicitly requested ownership and honest tracking gap;
speed/path/continuity checks remain. This establishes this ownership rule, not
full lab/Unreal1:1 pose parity. Refresh the lab. No build, restart or push.
