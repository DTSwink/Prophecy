# Supporting-foot height reversal, 2026-09-23

The unchanged repeated kickL scene reproduced a vertical reversal in the right
(supporting) foot after the preceding knee fix. On the first return it rose to
14.35 cm, dropped to 13.40 cm over two rendered ticks, then resumed rising. Five
complete returns reproduced early dips of 0.951, 0.863, 0.621, 0.383 and 0.161 cm.
These are evaluated PhysicalMesh measurements in the user's kinematic setup.

## Cause and correction

The raw locomotion prediction already contains the reversal: at policy times
2.050 and 2.083 seconds it requests vertical deltas of -1.42 and +9.33 cm. Published
foot height matches that delta multiplied by the authored Z tempering. The
reconstruction/floor stage is not independently bouncing the ankle up and down.

Grounded hinge guidance was admitting NN thigh motion much faster than the
displayed foot's 0.1 rotation following. The corrected thigh is fed into the next
policy input, so this inconsistent following perturbs subsequent foot predictions.
In `ResolveTemperedLeg`, the shared source-follow amount now includes FeetRotation
once, before transporting/mixing the source hinges. The stance-offset blend uses
that same amount, removing its previous second multiplication. Thus stance
admission retains its former effective weight while thigh bend/twist no longer
bypasses the authored following amount.

The source-heading alignment and connected-hinge solve from
[Supporting knee recovery](SupportingKneeRecovery.md) remain. No new foot-height
filter, floor lock, attack-family condition, timer or inference was added. No
Blueprint settings changed. Normal modifier-free locomotion still bypasses this
reconstruction. Calf length/scale recovery and the existing 60-tick blend clocks
are unchanged.

## Bounded validation

`CalfAnkleConnection-foot-vibration.json` and `-foot-vibration-fixed.json` in
`Saved/Diagnostics` contain the before/after unchanged-scene captures. Five complete
returns remove the early dip in every case. Supporting knee remains forward in
all 366 measured locomotion samples; maximum supporting thigh step improves
19.76 to 9.85 degrees, maximum swivel step changes 7.83 to 8.61 degrees. Calf scale
stays constant through recovery; first-tick tip-gap changes stay below 0.0035 cm
and final gaps below 0.000001 cm. Kicking-side thigh motion is not claimed reduced.

The whole following second is **not perfectly monotonic**: later returns contain
a small rise up to 0.196 cm over four ticks, compared with 0.086 cm before. This
remains recorded in `FootVibration-final-verification.json`; the regression asserts
removal of the measured early reversal, not universal monotonic NN locomotion.
Do not describe this as eliminating every possible oscillation or as validation
of arbitrary dynamic collisions.

`CheckSupportFollowGeometry.py` independently evaluates the old planted-thigh
fixture in double precision. It reproduces the former expected 6.503658-degree
step, then predicts 3.494478 degrees with shared following. The desired and actual
lateral knee offset remain exactly -0.130313277 m and both segment lengths remain
unchanged. Only the mixed thigh frame/twist changes, so the native fixture's old
exact rotation expectation was updated from this independent calculation.

Gameplay patch compiled in 29.05 seconds and loaded at 19:55:50 UTC. The following
test-only build passed in 244.60 seconds and loaded at 20:09:14 UTC. All 23 focused
native tests passed at 20:09:38 UTC, including planted stance, source heading,
pinning/reach, pelvis inertia, calf recovery and policy blend contracts.
No asset save or editor restart was performed for this correction.
