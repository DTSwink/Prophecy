# Predictive magnetization braking

**REVERTED at the user's request (October7).** None of the braking or tiny-angle
changes below remain active. The original pre-experiment momentum calculation is
restored; the earlier accepted local-parent prediction fix is retained. This
document records rejected experiments only. Do not reapply them automatically.

User rejected direct fractional landing because any positive strength discarded
all previous velocity, causing extreme braking even at0.01 and a discontinuity
at0. Restore the original momentum blend for linear/angular channels, including
the original strength-weighted COM conversion. Retain the accepted current-step
local-parent prediction fix.

For0<strength<1, after the existing inertia follow weights, predict approach over
TWO actual physics steps. With error E, velocity V and actual step h:
if `dot(V,E)*(2*h) > dot(E,E)`, brake to `V=E/(2*h)`.
This removes transverse momentum ONLY when that crossing condition trips; a
plane-only cap allowed pitch to overshoot while error in other axes remained.
Waiting until the last step also left insufficient margin for the connected
neck/spine constraint solve to redistribute momentum.
At exactly E=0, stop the driven velocity because further travel leaves the target.
This is necessarily a hard brake when crossing is imminent, even at low gain;
away and safe lateral velocities otherwise retain the original strength blend.
There is no additional continuous damping.0 retains no native writes;1 and>1
remain unchanged. The authored denominator and actual integration duration can
differ; crossing uses the latter.

Angular E is the shortest quaternion error expressed as an axis-angle vector.
Linear E uses body origin; convert the candidate COM velocity back to origin
velocity before limiting, excluding the existing gravity-compensation increment.
The original origin-to-COM contribution is otherwise restored unchanged.
The guard has no new state, allocations, inference, timers or Blueprint pins.
Only fractional channels run the extra projection check in the existing servo.

This bounds commanded approach along the current error axis. It is not a new
physical constraint: tangential rotation, curved motion around an offset COM,
gravity/external forces, collisions and joint impulses can affect the integrated
pose. No guarantee is made that every constrained limb can never cross a moving
target. Local targets continue to use this-step predicted parent endpoints.

Native tests cover gains0/.0001/.01/.25/.5/1, retained safe/away/tangential
momentum, removal of transverse bypass when braking, repeated collinear settling, actual-step versus
authored-denominator timing, and origin braking with an offset COM. Existing
tests retain full-strength, gravity, local hierarchy and connected-chain checks.

No authored settings/assets edited or saved. Current-scene investigation uses
owned140-tick replays, with settings restored afterward. Live Coding must be
followed by a normal DLL rebuild before any future
cold launch.

Historical one-step validation: runtime patch loaded03:54:58UTC; final test-warning cleanup patch
loaded03:55:38UTC, no object changes. All15 current servo tests passed03:56:32UTC.
An initial broad run also picked up the removed FractionalLanding test, whose
old registration survives Live Coding and still expects the rejected behavior;
that obsolete test failed. The final run explicitly selected all15 tests present
in current source, including PredictiveCrossingBrake. No scene replay ran and no
user Play was interrupted. Receipt: Saved/Diagnostics/PredictiveMagnetization20261007/tests.log.

## Current-scene correction after user reported remaining wobble

The initial one-step brake still produced head pitch overshoot +6.288degrees,
followed by a negative swing. Native trace confirms both pre-solve leakage across
individual axes and post-solve velocity changes. At absolute90 the head's X
rotation error against the resolved local target is -1.209deg before the servo,
+1.445deg under its command and +1.925deg after the solve. At92 command X spin
is -.545rad/s but solved spin is +.126rad/s. Thus the failure is not solely Jolt;
the plane-only guard itself was insufficient.

Owned replay controls, all captured poses through absolute78 exactly unchanged:

| Brake | Maximum positive head pitch90-104 | Head error100 | Head error110 |
|---|---:|---:|---:|
| Original one-step plane cap |6.288deg|4.684deg|1.369deg|
| One-step, remove transverse bypass |4.266deg|3.514deg|1.295deg|
| Two-step braking (selected) |.152deg|.535deg|3.004deg|
| Four-step braking (rejected: sluggish) |No crossing, still bent|12.915deg|3.827deg|

Two-step with victim contacts disabled only after85 gives error100 .680deg and
110 .816deg (versus3.004deg with contact). Later residual movement is contact-
sensitive; do not claim all physical wobble vanished. Selected recovery is slower
than the ringing baseline near90 (7.868deg remaining versus5.051deg), but largely
removes its first rebound. No constant damping was introduced far from crossing.
Temporary trace/experiment switches removed from production source. Receipts:
`Saved/Diagnostics/PredictiveMagnetization20261007/trace-analysis.json`,
`comparison-current.json`, and corresponding `crossing_*.json` captures in
`Saved/Diagnostics/LocalMagHead90_20261007/`.

The stricter settling test also exposed a tiny-angle defect: Unreal's
GetRotationAxis safe normalization can select X when the quaternion imaginary
vector is below its threshold, regardless of the true residual axis. Fractional
channels now use the small-angle logarithm `2*quaternion.xyz` below squared
length UE_SMALL_NUMBER. The full-strength path remains numerically unchanged.
New native regression requests a1e-5-radian Z correction and rejects injected X
spin. Angular test measurements normalize native float quaternions before acos;
the initial unnormalized measurement also included norm rounding error.

Final validation: small-angle correction loaded04:09:43UTC, no object changes;
all15 current native servo tests passed04:10:05UTC, including repeated settling
and the tiny-axis regression. Final140-tick replay completes with the same
reported rebound/error values as the selected two-step candidate; all recorded
pre-change poses through78 remain exact. Eight owned140-tick captures in this
investigation (baseline, trace, three braking comparisons, no-contact control and
two final captures) ended normally. No authored settings/assets saved or changed;
final editor has no Play, gravity override off and no dirty packages. No restart
or push. Final receipts: final-tests.log, final-state.json, comparison-current.json
in Saved/Diagnostics/PredictiveMagnetization20261007/.
