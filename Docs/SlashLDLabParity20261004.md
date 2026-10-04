# Current slashLD versus lab snapshot 11

October 4, 2026. Investigation only; no runtime code, Blueprint, map or profile changes.

The current Hold 1 / Trim 0 configuration is applied correctly. The imported FK curve matches the lab when given the same outgoing poses. The current Unreal GT scenario is not a playback of the lab's frozen slashLD variant 2, and Unreal's requested forearm stretch recovery also changes the wrist position during FK return.

## Captured configuration

The published desktop and latest snapshot 11 both select slashLD variant 2, yaw 0, upper-only display (spine position locked), world inertia enabled, continuous spring disabled. The source reproduces the captured desktop trajectory to 3.44e-16 m, excluding a stale desktop calculation.

The current graph calls codex GT slash and Prepare GT Attack From Idle, followed by live NN inference. The custom-attack caller and old profile setters are disconnected. The actor is Kinematic, with AttackViewer interpolation. No physical collision explanation is needed for this capture.

The live FK begin audit confirms slashLD, AlphaHold 1, Trim 0, coefficient 1. NN contribution stays zero during the return. The lab/native profile matches: base time .28 s, main inertia .76, easing .87, inertia hold .05, decay .8, angle addition .29 s per 90 degrees; bone weights spine .31, clavicle 1, upperarm 1, lowerarm .36, neck/head 1. Hands have no own inertia. Resolved duration is .317006 s for the lab variant and .316265 s for Unreal, because their initial spine angles differ slightly.

## Controlled numerical replay

One owned 360-tick Play capture completed three returns and part of the next attack. It ended normally and restored diagnostic CVars. No user Play session was interrupted. The analysis uses the first completed return, with outgoing future endpoints at ticks 100 and 102 and return endpoints 104 through 120.

Replaying those Unreal outgoing poses through the lab JS, with the native moving-pelvis accommodation, matches all upper rotations within .000104 degrees. Non-hand positions agree to sub-.001 cm. This rules out a missing inertia setting or a different rotation-return algorithm in this case.

Even with the pelvis frozen and forearm shortening absent, the lab curve produces an early hand slowdown from the Unreal seed. Right-hand displacement relative to spine per 1/60 s:

| Source passed to the same lab curve | Incoming | Return frame 1 | Frame 2 | Frame 3 |
| --- | ---: | ---: | ---: | ---: |
| Frozen lab slashLD variant 2 | 4.323 cm | 4.472 cm | 4.026 cm | 3.381 cm |
| Actual Unreal outgoing poses | 3.432 cm | 3.275 cm | 2.522 cm | 1.406 cm |

These are samples of the continuous lab curve, not a claim of identical 60 Hz presentation: Unreal interpolates its 30 Hz future endpoints. The capture's actual displayed hand steps also slow down. An exact matched-input curve reproduces the difference without involving a moving pelvis or the wrist length modifier, so the current incoming motion itself is sufficient to cause early braking. This does not identify every upstream reason why the frozen variant and live GT slash differ.

## Additional wrist-position modifier

Set Attack Forearm Stretch Return remains enabled at .3 s / 18 ticks as previously requested. At upper attack release it captures right stretch +2.743 cm (left +1.596 cm) and retracts toward reference. The lab holds outgoing segment lengths fixed instead.

The reconstructed lab right forearm stays 25.397274 cm. Native length falls to 22.653972 cm by tick 120. The wrist error between matched-pose lab and native grows to 2.743187 cm. Replacing only the reconstructed right forearm length with the measured native length reduces wrist residual below .000452 cm across all nine checked endpoints. Thus the residual right-wrist path difference is explained by forearm-length recovery, rather than lost FK angular momentum.

Hold 1 / Trim 0 controls NN takeover; it does not disable that separate length recovery or lower-body motion. Removing or delaying recovery would change the user's previously requested stretch behavior and was not done during this investigation.

## Evidence

`Saved/Diagnostics/SlashLDLabCheck20261004/` contains the current graph, state, desktop capture, 360-tick baseline and native trace, plus `compare.cjs` and `comparison.json`. The live editor audit is in `Saved/Diagnostics/FKPerAttackTiming20261004/editor-final.log`. Latest lab snapshot/source live under `C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/AttackRecoveryLab`.
