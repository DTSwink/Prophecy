# Intermittent backward pelvis movement — diagnosis, 2026-09-10

This records the original investigation before implementation. The completed fix and live verification are in [Validation.md](Validation.md).

Detected on the possessed main `BP_ProphecyManualPoseAgent` in live `testNN` PIE.
The captured backward movements originate in the shared root/pose interpolation
before the target reaches Jolt. No gameplay source, asset, collision setting,
feedback setting, drive gain, frame cap, or engine configuration was changed.

## Evidence

The first 75-second capture contains 4,347 frames. After the first five seconds,
4,093 samples retain the same mover velocity: 180.001920 cm/s along world +X.
Three backward events occur:

| World time | Prior frame time | Interpolation alpha | Capsule movement | Pelvis target movement | Actual pelvis movement |
|---|---:|---:|---:|---:|---:|
| 12.132816 s | 41.883301 ms | 1 → 0.984468 | −0.093269 cm | −0.093496 cm | −0.038676 cm |
| 36.086231 s | 55.998798 ms | 1 → 0.586871 | −2.478790 cm | −2.481630 cm | −1.887569 cm |
| 37.763413 s | 46.852998 ms | 1 → 0.902325 | −0.585938 cm | −0.586114 cm | −0.441498 cm |

The **36.086231 s** event occurred during uninterrupted sampling, before the
first status bridge call. The 37.763413 s event followed that bridge call and
is considered an observer-triggered timing disturbance, not a second independent
natural occurrence. The 12.132816 s event also preceded any status bridge call.

At each backward step, the future pelvis endpoint is unchanged across the two
frames. Those endpoints never move backward across the steady portion of the
capture. The capsule's Y and Z are unchanged. Actual Jolt body position and
displayed pelvis agree to within 2.184e-12 cm across the first capture.

The capsule reversal is predicted by `(new alpha - 1) * mover speed / 30` with
maximum error below 0.000117 cm across all three events. The large event's next
frame is 17.114699 ms; its interpolation returns from 100% to 58.6871% within the
same endpoint pair. The target reverses 2.481630 cm and the simulated body follows
backward by 1.887569 cm.

The second uninterrupted 75-second capture contains 4,314 frames and no backward
event above the 0.01 cm detection threshold. Its initial metadata explicitly
confirms pelvis linear/angular feedback tolerances 0/0, the hand/head self-contact
pair disabled, no held sword, and constant +X movement input. The first capture
began during startup before the user's test settings had all taken effect; its
seal metadata confirms the same final settings, but their exact change times were
not sampled. The diagnosis follows the recorded timing and position relationship,
not an assumption about when the feedback controls changed.

## Responsible code

1. `Source/GameAnimationSample3/Private/ProphecyNNLocomotionManager.cpp:1911`
   selects fractional accumulator interpolation when the current frame is shorter
   than the NN interval; otherwise it forces `VisualPoseAlpha = 1`.
2. The same file at line 3796 uses that alpha to interpolate the capsule's published
   root endpoints, then applies the result through `SetManagedRootLowPoint`.
3. `Source/GameAnimationSample3/Private/ProphecyAgent.cpp:1817` repeats the frame-time
   gate for `ReadNNFutureWorldPoseWithSnapshot`. A slow frame followed by a shorter
   frame can therefore revisit an earlier point inside the same pose pair.
4. `Source/GameAnimationSample3/Private/ProphecyJoltCharacterComponent.cpp:531`
   sends that interpolated pose directly to Jolt's physical-animation servo.

The 30 Hz NN need not predict backward motion for this to happen. A one-frame
switch from exact endpoint display to interpolation can move both the capsule
and the physical-animation target backward. The observed physical response is
consistent with the already-reversed target. No contact or skinning discrepancy
is needed to explain these captured events.

## Repair direction, not implemented

Make presentation time monotonic when switching between exact low-frame-rate
poses and interpolated poses, and use the same timing decision for capsule/root,
skeletal presentation, and physical-animation targets. Preserve the accepted
30 Hz policy cadence and the rule that sustained low frame rates show the newest
completed pose. A simple unconditional removal of the low-frame-rate path would
change that existing contract. Masking this by changing collision or feedback
tolerances would leave the demonstrated interpolation defect in place.

This report establishes the source of the captured backward steps. It does not
claim to explain every possible tracking error, diagnose why Windows/Unreal had
the occasional slow frame, or validate a correction.

## Files and methodology

- `capture-102005.json`: initial live trace and settings at seal.
- `capture-102143.json`: continuation under confirmed edge-case settings.
- `analysis.json`: event measurements and body/display errors.
- `selected-event.json`: detailed frame window around the largest event.
- `pelvis-backward.png`: plot of measured target/body motion plus a straight
  constant-mover-speed guide. The green guide is not an alternative NN rollout.
- `capture_live.py`: read-only Slate post-tick sampler, deduplicated by world time;
  no forced animation evaluation or physics stepping. Records in memory and writes
  after capture. Initial completion serialization was corrected and the first
  in-memory trace was explicitly sealed; its sample data were retained.
- `analyze.py`: reproducible offline measurements/plot.

Both sampler callbacks have completed. PIE was started for this diagnosis and left
running for the user's inspection. Source review also checked UE 5.7's local
`LevelTick.cpp`; general background references are Epic's
[actor ticking documentation](https://dev.epicgames.com/documentation/en-us/unreal-engine/actor-ticking-in-unreal-engine)
and Jolt's pinned
[architecture documentation](https://github.com/jrouwe/JoltPhysics/blob/v5.6.0/Docs/Architecture.md).
The diagnosis itself is based on local source and the live numerical captures.
