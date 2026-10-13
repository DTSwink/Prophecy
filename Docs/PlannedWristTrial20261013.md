# Planned-travel wrist trial — October 13

**REJECTED by the user and reverted.** This document records the experiment,
not current behavior or an accepted fix. `armfk.js` and `online.js` were restored
byte-for-byte from `Saved/Diagnostics/PlannedReachTrial20261013/before/`.
The trial source and test remain under `rejected/` there. Saved settings were
preserved. Unreal remains untouched. Do not reapply this trial.

User approved trying a schedule based on planned FK travel after rejecting the
per-tick remaining-distance controller. This is a **lab-only trial awaiting
the user's motion review**, active in No cheat mode. Reference mode is unchanged.
Unreal work remains stopped. Do not apply the rejected staged native port.

At reach admission, sample the existing FK arm/body path 96 times against the
current frozen base pose. Include the selected reach curve and body turn.
Accumulate hand travel, normalize it, and interpolate it with monotone cubics
whose first derivative is continuous. The wrist follows this fixed travel
fraction from its starting orientation to the requested orientation, relative
to the holster. Live hand-distance errors never feed back into this fraction.
The holster-relative orientation destination is constant in this lab's setup;
moving the holster carries the rotation normally.

Retain the existing FK position path, destination refits, body/pole schedule and
entry inertia. Seed wrist inertia against the new outgoing rotation. Include
the planned wrist's analytic maximum derivative in the shared reach duration;
lengthen it only if the angular cap requires it. Current saved profiles retain
all six original reach deadlines. The existing FK planner still owns the linear
speed budget; this does not impose a new cap on total motion from gait,
inertia or destination refits. No new controls or tuning changes.

Hand orientation is stored in the held-arm pose before the draw/slide handoff.
The existing head target partly follows the blade tip, so its motion can respond
to the new sword orientation. Head code/settings were not changed.

## Verification and limits

- Frozen current run/S: planned deadline stays91; direct attachment88→91;
  completion186→190. Last10 reach angular speeds now decrease
  272,243,214,186,161,139,119,103,88,71deg/s. Largest angular velocity-vector
  change in that tail207.62→29.43deg/s per tick; whole-reach peak angular speed
  625.61→443.03deg/s. These are measurements, not human motion approval.
- Across idle/walk/run and D/S, pre-transfer FK positions outside the responding
  neck/head match the old path exactly; other bone rotations differ by at most
  .0000042deg numerical noise. All reference-mode frames compare exactly.
- Causal input/time-budget/sequence tests pass.12 leeway-off combinations
  complete, maximum capture translation discrepancy1.46e-13cm.
- Analytic path tests check arc progress, monotonicity, derivative continuity
  and the derivative bound.12 motion/action/angular-limit cases pass; maximum
  planned angular ratio .999596 of the configured limit.
- Isolated read-only browser loads the current trial, advances playback and
  rebuilds the same plan in the body worker without errors. User page, tuning,
  camera and playback were not operated or saved.

This remains a plan made at admission, not a prediction of future gait. A moving
hand target can still arrive after that deadline (walk/S attaches108 against
deadline107 in this fixture). Existing translation velocity changes from
destination refits are unchanged. No claim of a general moving-target arrival
guarantee or of smoothness accepted by the user.

Source changes: `Labs/SwordHolsterLab/armfk.js`, `online.js`; test
`test_planned_wrist.cjs`. Frozen before-files, comparison trajectories, browser
receipt and preservation checks:
`Saved/Diagnostics/PlannedReachTrial20261013/`.
