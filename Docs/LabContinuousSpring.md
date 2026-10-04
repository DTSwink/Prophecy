# Continuous angular spring return — October 4

## Weight correction after snapshot 10 — reverted by user

The user preferred the prior response and explicitly requested reverting this
correction. The live code again uses inverse-weight stiffness and ordinary
interpolation at zero. The following records the rejected experiment.

The initial spring used the inertia slider as inverse spring mass: at spine .04,
its .05 denominator floor increased stiffness20× while retaining full outgoing
velocity. This caused the reported rapid spine return. The live implementation
now treats weights as momentum multipliers. Spring stiffness, damping and target
timing do not depend on them. Zero retains the same spring with zero own initial
momentum; it does not select ordinary pose interpolation. Hands remain excluded.
Each weighted joint carries only its authored relative angular contribution;
spine01 also carries the lost frozen-pelvis contribution. This prevents repeated
ancestor capture when all five spine joints share one alpha.

Snapshot10 reproduced exactly. At .20s of its .27s return, spine05 was already
within .080deg of idle; corrected it is still4.043deg away. Its .133s world
rotation step drops26.138→1.967deg.224 dedicated cases verify continuous zero,
uniform alpha scaling through the chain, unchanged spring attraction with no
outgoing motion, and exact idle. Prior zero-weight/zero-main descriptions below
are superseded by this correction.

User rejected the segmented follow-through experiment: momentum and a gradually
strengthening idle attraction should coexist throughout the return. Replaced
that checkbox/branch with **Continuous spring return**. Historical source and
tests remain under Saved/Diagnostics/LabSpine20261004; no Unreal changes.

Active joints now retain angular velocity as state and integrate spring torque
toward their parent-local idle orientation. In world mode the target is the
current parent's world rotation times the canonical idle local rotation; damping
uses relative angular velocity. In local mode the integration is parent-local.
Local offset directions have matching angular springs at fixed length. Hands
and zero-weight joints retain ordinary local idle interpolation. FK reconstructs
the connected positions at every step/sample. This is a kinematic articulated
spring approximation: no mass-matrix coupling, gravity, contact or collision
forces, and no guarantee of an exact circular hand path.

Pull frequency grows continuously with normalized return time and remaining
time; Pull ramp shapes its growth. Inertia sets joint response, Spring damping
sets braking/overshoot. Damping approaches critical near completion. No hold,
phase switch or active-joint pose crossfade is used. Return time still imposes
a deadline, so .31s can demand a quick final correction after a large slash.

Backward Euler uses a deterministic grid with480 steps per second of duration,
distributed more densely near completion. Trajectories cache by profile and yaw;
display samples cached parent-local rotations/directions through FK. No elapsed
playback state or wall-clock simulation dependencies. Initial fixed-step tests
caught substantial endpoint error for .1s/high damping. Denser terminal sampling
plus continuously converging damping removed that residual. The final exact-idle
cache endpoint differs from the integrated result by at most .001777degrees /
.01323mm in the broad test; current slashRU16 residual is effectively roundoff.

Verification:1280 spring cases across320 motions, both spaces, .1/.31/.6s,
ramp0/1, damping0/.5/1/4. Finite trajectories, fixed lengths/lower body, tiny
endpoint residue, exact deadline, zero-inertia parity, deterministic seeking,
and exact independence from the obsolete Hold value pass. Maximum measured
profile-build time23.25ms in this run; playback does not reintegrate. Isolated
UI tests cover mode selection, hold hidden, per-attack persistence, refresh,
copy and snapshots with no browser errors. User settings are unchanged.

Live tests: `test_spring_return.cjs`. Receipts: `spring-study.cjs` / JSON and
`spring-ui.cjs` under `Saved/Diagnostics/LabSpine20261004/`.
