# Lab spine stop — snapshot 6, October 4

Read the live lab under
`C:/Users/singerie/Documents/Cursor/stepper/training/slashes2/AttackRecoveryLab`,
not the October 3 recovery copy under `Labs/AttackRecoveryLab`.

Latest snapshot `snapshot_0006` is slashR variant 16, time .8577333335 seconds,
just before its authored end at .8666666667. Its actual controls are global
inertia 1, spine 1, duration .26 seconds, easing .12, spine turn 3 degrees and
upper-only anchoring. An independent replay through the live `recovery.js`
reproduces every saved displayed point and axis exactly (maximum error zero).

## Cause

The lab holds all lower bones, including pelvis orientation, at their last
authored pose when recovery starts. `prepare` / `turnedRecovery` compute each
upper joint's momentum only from its parent-local rotations. This preserves
the spine's own local motion but drops the rotation it inherited from the
previously moving pelvis. Hiding the lower body and anchoring spine_01 position
does not remove that inherited rotation during authored playback.

At the boundary, measured infinitesimal angular speeds are:

| Bone / quantity | Before | After |
| --- | ---: | ---: |
| Pelvis world rotation | 168.708 deg/s | 0 |
| spine_01 world rotation | 164.300 deg/s | 36.169 deg/s |
| spine_01 parent-local rotation | 4.741 deg/s | 36.169 deg/s |
| spine_05 world rotation | 363.379 deg/s | 198.770 deg/s |

The .12 easing adds an initial idle-return velocity. With easing 1, which removes
that initial idle-curve contribution, spine_01 starts recovery at only 4.741
deg/s: its retained local velocity, with the entire moving-parent contribution
missing. Thus the inertia slider is applied correctly; its coordinate-space
boundary loses inherited pelvis rotation.

## Calculation-only isolation

Without changing the lab files/settings, a copied recovery model seeds only
spine_01 from its outgoing global angular change expressed in its bone frame.
Because the parent freezes, that is the relative angular velocity needed to
continue the visible motion. Other joints remain parent-local and the pelvis
remains exactly fixed.

- At easing 1, initial spine_01 speed changes from 4.741 to 164.296 deg/s,
  matching incoming 164.300 within the finite numerical sampling error.
- At the snapshot's easing .12, the first 60 Hz spine_01 step changes from .607
  to 2.200 degrees; the preceding authored step was 2.738 degrees.
- The existing short momentum envelope still decays rapidly afterward. Carrying
  the parent contribution fixes the extra boundary loss, not that separate
  decay behavior. Easing below 1 also contributes its own initial return motion.

No live lab/Unreal code or settings were changed. A eventual correction should
carry only the parent's lost angular contribution at the upper/lower boundary;
Unreal's moving pelvis must not receive duplicate inherited momentum. Evidence:
`Saved/Diagnostics/LabSpine20261004/audit.cjs` and `audit.json`.
