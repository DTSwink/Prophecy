# Calf roll during attacks

## Confirmed cause

The current repeated slashR produced left-calf target rotations of up to139.175 degrees between accepted samples, while the calf's knee-to-foot direction changed only2.522 degrees at the largest event. This was already in the NN presentation target; it was not Jolt inventing a physical wobble. The physical mesh followed that discontinuity with a69.576-degree frame step.

Attack `FSlashNative::SolveLimb` can reconstruct calf orientation by projecting the thigh's pole onto the calf axis and applying a hemisphere correction. The current attack geometry's pole approaches parallel to the calf: its transverse projection falls to0.0279 in the captured sequence. Small pose changes then cause large reconstructed roll changes. The hemisphere branch can add another discontinuity (a94.713-degree correction in a captured sample).

An independent reconstruction using the **attack export's** offsets and poles matches the observed calf rotations within0.000141 degrees at the inspected frames. Do not use locomotion poles to reproduce this decoder: their authored directions differ. Locomotion already uses a signed knee-hinge normal instead of this pole projection and predicts a4.95-degree change at the largest139-degree event.

Baseline: `Saved/Diagnostics/CalfRoll-20260923-143846.json`,600 game frames, six repeated slashR attacks. Metrics and hemisphere-oracle evidence are beside it. The first attempted capture (`143813`) failed because PhysicalMesh is a Blueprint component, not a native reflected property; its owned PIE was stopped and it provides no diagnostic evidence.

## Correction

`SetCalfRollFromThigh` uses the existing locomotion `CalfRotationFromHinge` calculation at the UE attack output boundary. It changes only the calf quaternion, preserving the knee-to-foot aim and carrying the signed thigh hinge. It runs after endpoint clamps and before caching the accepted visible pose, so rendering, physical targets and attacker collider samples consumed by defense share the orientation.

Both legs of every full attack use this rule. Half attacks retain their locomotion-authored lower body, including existing recovery continuity. There is no attack-family-specific tuning, smoothing timer, extra model inference, new node, retained actor layout or recurring locomotion work. Attack weights, raw native decoder/ghost, reduced NN history, thigh and foot rotations, joint positions and clamp controls are not edited. Calf collider orientation deliberately changes; physical contacts can therefore differ. Parry/dodge decoding is outside this attack-specific change.

## Verification

Live Coding patch12 loaded2026-09-23 **12:43:27 UTC**,112.91-second successful build, no object changes. Ten `Prophecy.NN.PhysicalTargets` tests passed at12:44:10UTC. The new signed-hinge test covers both sides through a full folded-knee sweep, five-degree continuity, aim, unchanged location/scale and idempotence. Existing forearm, clamp, interpolation and physical-target tests also pass. Pose Blueprint compiled status3, zero stale native/pin types; existing values/wiring preserved.

Post-fix: `Saved/Diagnostics/CalfRoll-20260923-144427.json`,600 frames/same repeated attacks.

| During attacks | Before | After |
| --- | ---: | ---: |
| Left calf maximum target rotation step |139.175°|8.983°|
| Left calf maximum axial-twist step |139.165°|8.194°|
| Left calf maximum physical-mesh frame step |69.596°|4.491°|

142 matched attack samples show all future joint positions within0.015cm and non-calf rotations within0.015° between runs. Calf roll intentionally differs. The right calf's maximum target step is22.253°, matching the signed-hinge oracle; its thigh itself moves17.861° there. Do not claim that all remaining limb motion is removed or that every physical configuration was tested. Attack-start frames can still contain the incoming locomotion pose before the first authored attack output.

All diagnostic PIE sessions were owned and ended. No Blueprint/scene edits, asset saves or editor restart were performed by this fix. The user's pose Blueprint changed on disk during the turn; preserve that user work. Journal updated; include Live Coding changes in the next authorized normal build.
