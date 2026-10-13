# Moving D/S diagnosis — October 12

## Follow-up: reach-deadline snap fixed

User authorized only the hand snap fix, explicitly deferring tip aiming.
`ReachArm` now retains its existing four-tick destination smoothing window
instead of shortening it to one at the reach deadline. Refit cadence, solver,
quaternion sign continuity, FK path and length preservation are unchanged.
No new retained state, allocations, solves, tuning controls or wall-clock use.
New targets can take additional ticks to be accepted; the reach timer alone
does not force exact arrival. Sliding still uses the existing arrival checks.

Layout-safe Live Coding build/reload succeeded (UBT171.65s). Editor stayed open;
normal DLL remains stale. This also compiled the previously pending optional
legacy-constraint guard in the editor mount helper. No assets saved.

Extended existing reach regression:16 sign/arc cases pass,832 unchanged-cadence
fits, max step1.3deg, stationary-target final error.0000153deg.48 deadline/refit
slot cases pass: sudden30deg target change is limited to7.5deg first step and
converges to.0002263deg residual. Existing480 bone-order cases also pass.

Live current500cm/s setup,3agents: sim capture to160 completes; player deadline77
step6.3861→2.4665cm, local window peak6.3861→3.0654cm, post100 max step
3.1693→1.8860cm. Both NPC deadline steps also decrease. Kinematic capture was
ended externally after the relevant deadline/post100 window; do not describe
it as a completed full requested capture. Player deadline now79 (previous78),
step1.4287cm versus previous6.6305cm; nearby maximum3.3585cm. Do not claim an
identical-prefix kinematic A/B. No further Play started after that interruption.

All agents still wait in Reach: tip aiming/unreachable approach is deliberately
not fixed here. User clarified that matching holster rotation is not aiming at
the entrance: clamping hand reach while retaining perfect holster rotation moves
the tip off-target. Rotation tolerance is currently an admission gate, not a
means of preserving tip placement within the feasible orientation range.

Lab source/settings/setup, runtime profile and saved Blueprint bytes unchanged
by hash; only lab's live `current_view.json` changed during work. Dirty PoseAgent
and TestNN left unsaved. Evidence: `Saved/Diagnostics/HolsterSnapFix20261012/`.

## Original diagnosis

User requests diagnosis only: hand snap near absolute tick85, jitter and S
never finishing while running. No runtime/lab/Blueprint/tuning changes made.

## Captures and scope

No user Play existed. Ran owned PIE against the current unsaved setup: sim to
absolute360, kinematic control to240, then a sim entry capture to135. Existing
Blueprint starts S at15 (third agent admitted16); no manual action or locomotion
override. Current setup runs forward at500cm/s. Temporary60FPS cap restored and
only owned Play ended. Kinematic control changes PIE agent mode at6.

Player gaze is yaw-.4166667/pitch-.1111111; NPCs zero. Saved lab UI is WalkF,
start50, neutral gaze; native exported profile hash matches current saved lab
parameters. Lab uses settled recordings. These captures are not matched-input
whole-motion lab/native parity tests.

## 1. Reach deadline removes destination smoothing

The player snap reproduced at absolute77 in sim,78 in kinematic (not exactly85).
These are precisely each capture's planned reach deadline: action62/63 ticks.
Pelvis-translation-relative commanded hand steps are6.3861cm/6.6305cm.
Physical sim hand follows the same jump; tracking error at77 is.0472cm.

`ProphecySwordHolsterPose.cpp::ReachArm` refits every tick once ReachDone and
uses `clamp(ReachTicks-LastGuide+1,1,4)` for the destination interpolation window.
At the deadline LastGuide becomes Tick, the window becomes1, and the new
destination is applied immediately, even though the sword has not arrived.
Afterward it directly follows each new gait-dependent endpoint. This explains
the abrupt catch-up and removes smoothing from the unresolved reach.

Offline replay of captured guide/source/destination transforms reconstructs the
actual hand to<8e-14cm. For this single boundary update, using25% of the same new
destination instead of100% changes the hand step to2.1310cm/2.0933cm. This is
causal numerical evidence for the deadline snap, not a tested runtime fix or a
claim that every later visible irregularity is solved.

## 2. Correct orientation, unreachable position

All3agents stay in Reach; insertion stays0. No slide or FK return begins.
After absolute100 the player's frozen arm length is48.9948cm, while the requested
shoulder-to-hand-target distance varies56.5982–64.2828cm. The arm solve clamps
to almost full extension, leaving7.6044–15.2890cm commanded hand error.

The actual sim blade tip stays6.0804–14.6779cm from the entrance, while its
rotation error is.3034–6.2973degrees (inside the15degree allowance). In kinematic
mode rotation error is effectively0, but tip distance remains7.5934–15.2799cm.
NPCs also remain outside the positional gate; min sim tip errors3.6929/2.8730cm.
`SheatheReady` requires both tip distance<=2cm and rotation within allowance,
plus completed body authoring. Thus correct pointing does not admit sliding.
No timeout or alternative unreachable-target path finishes the reach.

Physics is not necessary for either reproduced failure. After100, sim hand
tracking error stays below.014cm; kinematic also stalls. The deleted old holster
constraint is not implicated.

## Why the settled lab succeeds

Unmodified lab planners using current saved values/new holster placement finish
S for WalkF and Run at start15 and50; run slide entries58/93, walk70/107.
Arm lengths are the same~49cm, so this is not a lab scale discrepancy.

Replayed the exact live action-entry base pose and subsequent live base poses
through the unchanged lab `bodyreach.js`, applying actor heading transport as
Unreal does. After100, all3 shoulder positions reproduce Unreal to<6.4e-14cm.
The live captured starting posture is the key input difference: driven torso
locals and the compensated pelvis orientation are retained from action start
during acceleration. Their later relationship to the moving pelvis/holster
leaves the requested hand target beyond the arm's reach. The stable lab clip
starts from a different posture; native body authoring is not numerically
disagreeing with lab body authoring on these same inputs.

An offline counterfactual rebuilding the body context from each later live pose
reduces player target distance from56.80–64.12cm to49.37–51.13cm. This confirms
the captured posture's contribution; it is NOT a proposed per-tick recapture fix
(which would change the intended authoring and could reintroduce gait motion).
Do not change saved targets or the lab to conceal the difference.

## Evidence

`Saved/Diagnostics/HolsterMoving20261012/`: current.json, kinematic.json,
entry.json, geometry.json, *-metrics.json, deadline-replay.json,
lab-recorded-comparison.json, live-input-lab-body.json and the generating
read-only/offline scripts. All implementation decisions remain pending user
discussion; no compile/restart/push.
