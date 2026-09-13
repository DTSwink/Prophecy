# Headbutt hands before Armed — implementation plan

Status: **implemented 2026-09-13** after user approval. See
[AttackPinningAndHeadbutt.md](AttackPinningAndHeadbutt.md) for controls and scope.
The user requested to handle gameplay testing themselves; the acceptance checks
below remain the planned validation, not claimed completed results.

## Intended behavior

On a Headbutt, use the original animation to drive both hands during preparation.
The neural policy keeps running and remains responsible for Armed and Hit. On
the first output that latches Armed, release the hands to the NN. Other attack
families and ordinary locomotion keep their existing behavior.

This is a deliberate authored addition to the learned controller. The existing
SlashChain source-parity test must remain unchanged when this option is disabled.

## Source and smallest useful data

Use the original `headbutt.npz` family in Stepper's
`training/slashes2/final_gt_attack_dataset_npz`, together with its original-family
controller-v3 counterpart in `final_target_frame_v3_attack_dataset_npz`.
Use `native_controller_targets.load_controller_target_arrays` and the same
checkpoint/coordinate contract as `Tools/NN/ExportProphecyHalfAttackGT.py`.
Record both source hashes; never edit the source clip or network weights.

The original clip contains 13 frames at 30 Hz: Armed is frame 7, Hit is frame 10.
Export preparation frames 0 through 7 inclusive. Export, for each arm:

- Hand position relative to the GT pelvis.
- Hand rotation relative to the GT pelvis.
- Upper-arm rotation relative to the GT pelvis, needed by the existing arm
  decoder to determine the elbow and forearm consistently.

With quaternions, this is 8 × 2 × (3 + 4 + 4) float32 values: **704 bytes** of
numeric track data, before metadata/container overhead. Load it once and share
it across managers/agents. Do not load/evaluate an AnimSequence for each attacker.

## Runtime insertion

1. Add an explicit Headbutt preparation option on the existing attack path. Keep
   the track and any lookup immutable. Each active Headbutt needs only its track
   time, active flag, and entry-transition state. No idle agent polling or timer.
2. Sample at the existing 30 Hz attack step. Convert the sample through the
   **ghost** pelvis into the attack-root frame. In half mode, use the same fixed
   mounting orientation as the upper attack; real leg/pelvis motion must not
   enter the track or NN history.
3. The current native `Finish` first produces the next upper state, rebases it,
   then runs final upper FK. Move latch evaluation before that FK. For a lane
   whose output is still unarmed, replace only the two 15-value arm state blocks
   before the existing candidate upper FK. Account for the decoder's existing
   frozen-plus-candidate-minus-baseline representation: solve the candidate
   channels for the desired final GT hand transforms using the already computed
   baseline. Copying visible GT coordinates directly into residual channels
   would give the wrong final hands. This
   avoids a second FK pass and keeps the computed forearms coherent.
4. Store those same corrected arm fields in recurrent upper history. A visual
   overlay alone would leave the NN conditioning on its unwanted hand motion
   and could reveal it again on release. The prepared history and the displayed
   authored arm targets must describe the same pose.
5. On the first learned Armed output, use that step's neural arm prediction and
   stop the override. Do not force Armed at GT frame 7, delay Armed for the
   animation, reset Hit, or restart either recurrent history frame. If the GT
   preparation reaches frame 7 before Armed, hold its endpoint while the NN
   continues deciding. `Stop NN Attack` and replacement discard the track state.

Full and half attacks share this modifier. Full-body floor pinning, lower policy,
camera, physical animation, strength and joint limits are unaffected.

## Entry and release continuity

An arbitrary starting hand pose is not necessarily GT frame 0. Snapping to it
would trade one visible defect for another. Use the existing pose-transition
convention at entry, implemented on these few arm channels, and condition both
history frames consistently. The entry blend is an intentional transition to
authored GT, so its frames must not be described as exact GT playback.

Release itself should use the NN prediction conditioned on the authored history,
without a second smoothing layer or a forced phase delay. That makes continuity
testable, but does not guarantee the learned controller will behave correctly:
the model may react to these new conditioning states. Measure that before
enabling the modifier by default. If it still predicts a discontinuity at Armed,
report the measured mismatch; do not silently extend GT beyond Armed.

## Acceptance checks

- Source-coordinate audit: sampled arm channels match the exported original GT
  to float precision, including rotation and elbow-plane interpretation.
- Reproduce the current unwanted pre-Armed hands numerically; then capture hand
  positions, rotations and velocities through entry, pre-Armed and release.
  Outside the documented entry transition, pre-Armed targets must equal GT.
- Check early Armed, delayed Armed, interruption, replacement and consecutive
  Headbutts. Confirm the exact output frame that releases the modifier.
- Idle/walking/running paired half attacks with equal upper initialization and
  equivalent targets must retain equal ghost inputs and upper outputs.
- Verify kinematic and physical followers use the same authored targets. Physics
  tracking error must be reported separately from target/NN error.
- With the option disabled, rerun the immutable SlashChain parity test.
- Benchmark modifier-on versus modifier-off for 1 and 100 active Headbutts.
  Require no additional neural calls, allocations during steady playback,
  skeleton-wide passes, per-agent Timelines or component ticks. Record the
  incremental measured cost rather than claiming zero overhead.

The shortest implementation path is: export the tiny track, add the optional
native per-lane modifier before existing FK, verify entry/release and paired
independence, then expose the option through the existing Blueprint attack API.
