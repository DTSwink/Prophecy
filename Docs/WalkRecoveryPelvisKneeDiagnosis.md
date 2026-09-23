# Walk recovery: pelvis stop/drop and supporting-knee pop

Diagnosed and tested 2026-09-23 in the user's updated repeated kickL scene.
The shared final knee-plane guidance now follows FeetRotation tempering. This
substantially reduces the supporting-knee pop, but only partially improves the
pelvis stop/drop. Checkpoint and Blueprint settings are unchanged.

## Current correction and validation

The final stance-plane strength is multiplied by the leg's FeetRotation value,
just as the preceding hinge following respects the held rotation. At zero it
approaches the frozen hinge continuously; at one the original full guidance
returns. This final correction rotates around the hip–ankle axis, preserving
the endpoint and both segment lengths. No new timer, inference, attack-family
gate or normal-path work was added. Existing heading alignment, inward clearance,
floor/pinning and calf-length/scale recovery remain in place.

Five complete returns in the unchanged Walk scene compare as follows:

| Measured maximum | Before | Current |
| --- | ---: | ---: |
| Supporting thigh turn/frame | 13.81° | 4.04° |
| Supporting knee swivel/frame | 13.90° | 4.73° |
| Supporting knee displacement/frame | 4.745 cm | 3.530 cm |
| Pelvis vertical displacement change/frame | 1.864 cm | 1.222 cm |
| Supporting foot vertical displacement change/frame | 0.632 cm | 0.584 cm |
| Kicking foot vertical displacement change/frame | 2.118 cm | 1.946 cm |

Supporting knees remain forward in all 364 measured locomotion samples. Calf
scale remains continuous; first-tick calf-tip gap change is 0.00412 cm and final
gap is below 0.000001 cm. The initial foot descent stays smooth. Pelvis speed
discontinuity falls about 34%, but the initial slowdown persists: this is not a
complete pelvis fix. Recurrent feedback changes later trajectories slightly.

Eight additional kickR/kickL/overL/overR episodes show no renewed full knee spins
(largest transported swivel excursion 79.31°). Previous kick comparison data used
Run, while current kicks use Walk, so those episodes are coverage, not equivalent
Run A/B evidence. The transient `run-plane-follow` attempt was overridden by the
Blueprint's return event and actually remained Walk; do not count it as Run testing.

Gameplay Live Coding loaded at 20:37:06 UTC (67.23 s build); updated test-only
build succeeded in 114.74 s and loaded at 20:42:36 UTC. All 23 focused native
tests passed at 20:49:08 UTC, including connected geometry, zero-follow continuity,
heading/degeneracy, calf recovery, pinning and blend timing. Independent recorded
geometry predicts the updated 3.287029° regression step. Source changes still
need the next authorized normal Editor build before reopening.

Evidence: `CalfAnkleConnection-walk-plane-follow.json`,
`FootVibration-nn-walk-plane-follow.jsonl`, `WalkStanceFollow-verification.json`,
`SupportFollow-geometry.json` and `StanceFollow-variants.json`, all under
`Saved/Diagnostics`. Owned diagnostic Play ended, tracing restored/disabled and
capture memory released. No Blueprint/map edits, asset saves or editor restart.

## Reproduction

`Saved/Diagnostics/CalfAnkleConnection-walk-recovery-pop.json` contains ten game
seconds of evaluated PhysicalMesh bones and authored previous/future/interpolated
targets. The parallel raw trace is `FootVibration-nn-walk-recovery-pop.jsonl`.
Five complete returns reproduce the issue on the non-kicking right leg.

First return, at 60 Hz: pelvis downward displacement per frame changes from
0.773 to0.385 to1.762 cm in successive two-frame policy intervals (46.4→23.1→105.7
cm/authored-second). Later returns reach1.864cm/frame change in this displacement.
Supporting thigh steps reach13.81degrees/render frame; supporting knee positional
steps reach4.745cm. The first supporting swivel reverses from approximately
+7.68degrees/frame to-7.42degrees/frame.

All pelvis/left/right Walk weights are exactly1 throughout the measured return.
The Walk→normal configuration ends at Walk in this scene. No checkpoint-weight
switch coincides with the discontinuity. Tempering eases continuously to1 over
30 game ticks; no wall-time duration failure was observed.

## Direct knee cause

The shared solver first transports/mixes coherent source hinges, then applies a
separate correction to preserve the source knee's lateral stance offset relative
to foot-forward. The latter has full geometric strength whenever its plane is
well-defined, even when FeetRotation following is low. The last fix changed
source-hinge following, not this final plane correction.

Independent double-precision replay in `ReplayWalkKneeGeometry.py` reproduces the
published thigh orientations to a maximum0.000052degrees, including returning
calf length, source heading alignment and the plane correction. It isolates:

| NN time | Right source follow | Right source bend contribution | Final plane turn |
| --- | --- | --- | --- |
| 1.9500 | .0771 | +2.21° | +2.87° |
| 1.9833 | .1115 | +1.34° | **−16.68°** |
| 2.0167 | .1201 | +3.21° | **+8.94°** |

Plane confidence is1 for all three samples. This is not an ill-defined straight
knee: the knee-circle radius is about9.7cm before increasing to15.3cm. The final
plane solve overrides the slow source handover with a rapid opposite correction.
The first kicking-leg plane correction is also large (−20.44degrees), despite the
foot trajectory looking good. Both thighs matter to the next NN prediction.

## Pelvis coupling

Published pelvis Z equals previous Z + raw Walk delta × pelvis-Z tempering within
0.0000048cm across the captured locomotion samples. Thus there is no additional
vertical pelvis snap in the reconstruction/presentation stage.

The actual raw Walk vertical deltas begin−3.093,−1.521,−6.721,−3.569cm. Corrected
thighs and their temporal differences enter the next NN input. Replaying those
recorded152-value inputs through the exact checkpoint reproduces all outputs to
maximum2.87e-6 (native output units).

Single-step counterfactuals preserve every other input and rebase the alternative
thigh into the same input frame, recomputing its matching velocity features:

- At2.0167, removing only the preceding supporting-knee plane turn changes the
  next pelvis delta from−6.721 to−5.076cm.
- Removing both preceding plane turns changes it to−4.518cm.
- At1.9833, replacing only the supporting-thigh group with the no-reconstruction
  comparison changes−1.521 to−6.251cm. Replacing only the kicking thigh instead
  changes it to+1.521cm. Contributions are nonlinear, not additive.

This establishes a material feedback contribution, not proof that removing one
correction would make the entire pelvis trajectory smooth. The Walk policy's
response to the modified recovery pose remains part of the coupled behavior.

## Isolation and boundaries

- `walk-source-off`: disabling grounded NN source guidance retains the stop/drop
  and knee reversal, so the preceding source-follow change alone is not the cause.
- `walk-chain-off`: disabling chain reconstruction reduces the large subsequent
  pelvis drop but produces a23degree initial thigh step and still has an early
  pelvis reversal. Disabling reconstruction is not a solution.
- `walk-no-tempering`: diagnostic cancellation begins after the first return
  prediction; it creates its own transition and worsens the knee. It is not a
  clean vanilla-Walk baseline or a candidate fix.

The initial diagnosis ablations used owned transient Play worlds; SupportSource was restored to its
previous value, tracing disabled, and owned sessions ended. Saved assets and
settings were untouched. That diagnosis phase required no compilation/restart.

The continuity experiment is now implemented and measured above. Further pelvis
work must isolate the remaining recurrent response. Do not
simply disable reconstruction, force Run, clamp a good foot trajectory, or hide
the result with an unvalidated pelvis filter. A proposed fix must retain the
existing forward-knee/inner-reach/floor/pin/length behavior and be checked against
the previously accepted Run recovery and overheads as well as this Walk setup.
