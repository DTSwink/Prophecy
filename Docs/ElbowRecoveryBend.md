# Elbow bend during hand recovery

Implemented and accepted by the user September23,2026.

The current slashR return reproduced a large elbow swivel in the kinematic
target. The torso clearance guard reported zero correction during it. The
previous solver first mixed a shoulder quaternion and hand endpoint, then
derived a bend from that artificial intermediate arm. Slash recovery also
constructed its idle/NN guide this way. These independently mixed quantities
do not preserve a coherent hinge, producing strongly nonlinear swivel and a
late catch-up toward the desired idle bend.

`ProphecyHandChain::Resolve` now transports each complete source hinge to the
same final shoulder–wrist axis before blending bend directions on the exact
two-bone solution circle. Upper-arm and forearm lengths, requested hand rotation
and reachable hand endpoint remain respected. Shoulder twist is blended only
after both frames share the solved upper direction. Wrist roll does not steer
the elbow. Nearly straight or ambiguous guidance loses influence smoothly;
the previous bend supplies continuity. Full following still returns the exact
destination solution. This is not a new anatomical joint-limit system.

The slash return uses that same coherent solve for both its idle/NN guide and
its previous-pose-to-guide transition. The shared solver also covers both hands'
tempering and regional recovery. Special checkpoint outputs, leg reconstruction,
blade route/winding/clearance, captured distance-scaled speed and authored
60-tick durations are unchanged. There are no new actor fields, sidecar maps,
timers or inference calls. Existing inactive/normal bypasses remain.

## Evidence

- Baseline: `Saved/Diagnostics/SlashReturnStages-20260923-184351.json`.
- Revised: `Saved/Diagnostics/SlashReturnStages-20260923-185035.json`.
  Both360-frame runs contain the same three slashR exit frames134/222/312.
  At0.7833 authored seconds in the third return, bend-direction error relative
  to transported idle falls from about34° to1.54°. Maximum displayed right
  shoulder step remains7.31°; its95th percentile falls4.54→3.87°.
  Maximum displayed forearm step is effectively unchanged8.15→8.16°.
  These are bounded comparisons, not a guarantee for every pose or setting.
- `SlashSwordVariants-20260923-185207.json`:900 frames, six full slash directions,
  full pike, half slashL and half pike. Existing blade protection remains;
  slashLU's already-overlapping attack-exit pose has normalized squared sampled
  clearance0.979, improving to≥1.266 after four ticks. Other tested full slash
  returns and half slashL remain outside the measured envelope. Pike retains
  its intentionally excluded behavior.
- A longer completion capture was stopped at1173 frames; do not claim its
  planned1800-frame survey completed. The user subsequently confirmed the
  current result was perfect and requested a push; no further gameplay changes.
- Live gameplay patch22 built successfully in129.55s. Test-only patch23 built
  in74.13s. All eight focused native tests passed16:55:08UTC, including new
  `HandRecovery.BendBlend`: recorded exit geometry, continuous nonreversing
  bend progression, link lengths/target preservation and near-straight noise.
  Existing continuity, root equivariance, wrist-roll independence, end-of-blend,
  lifecycle and core attachment tests also pass.

Editor-only `Prophecy.SlashReturn.Audit` includes detailed hinge stages and
defaults off; shipping builds exclude this probe. No Blueprint wiring or scene
transforms were changed. The pose Blueprint was compiled and explicitly saved
for the user's requested backup after acceptance. Live patches still need the
normal editor build at the next authorized restart.
