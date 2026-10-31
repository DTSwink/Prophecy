# Predictive aim and legal motion audit

October 30, 2026. Offline tests and actual renderer geometry; no desktop control,
live scene writes, Unreal restart, or persistent process.

## Correction path

The solver predicts the complete future flight pose, including flip, twist,
secondary response and attack articulation. It aims the original contact ray at
Hit; direct kicks, jabs and pike finish preparing that correction at Armed.
Circular attacks finish at Hit. Throws use Release and their world exit velocity.

The initial solver accurately aimed the final pose but interpolated independent
cumulative world rotations along the spine. Some solutions wound past a full turn.
Adjacent spines then selected different shortest quaternion paths, and anatomical
projection abruptly switched sides of a limit. Dense sampling caught 44.7, 45.0,
46.8 and 145.5 degree one-tick jumps in headbutt, hookR, slashRD and sweepKick.

`attack-aim.js` now converts the solved endpoint into additive changes in each
joint's legal coordinates: swing ellipse Y/Z and twist for ball joints; signed
hinge angle for knees/elbows. The current animation keeps advancing underneath
those changes. Continuous projection into the convex swing ellipse keeps the
path legal. Pelvis yaw and any unavoidable residual tilt remain a smooth global
rotation. FK restores the chain, then translation restores the original COM.
There is no attack-specific exception, per-frame speed clamp, or discontinuity
gate in this correction.

`joint-rig.js` also fixes the ellipse projection's bisection bracket: the former
upper bound could remain inside the solution interval for large diagonal bends,
so the supposed projected pose could still violate its own limits. It now grows
the bracket until it contains the solution, matching the existing wrist method.
This is an intentional correctness fix, separate from lossless optimization.

Throws provide the time of adjacent release samples to the aim transform. The
solver uses the actual correction envelope at those times, matching the launch
velocity finite difference rather than applying a constant endpoint rotation to
all neighboring poses. Final throw coverage is in the throw integration report.

## Verification

- `verify-predictive-aim.mjs`: 60 future-hit cases pass.
- `verify-predictive-aim-extended.mjs`: 714 cases: all 17 vanilla attacks,
  three mixed flip/twist configurations, 14 cardinal/diagonal target directions.
  Final rerun after scale-aware LM damping and reuse of the already-projected
  candidate: maximum unit-direction error 3.564e-7; COM drift below 1.777e-15 m.
- The same extended test samples 51 complete attack/return paths at 240 Hz.
  Every corrected path's largest joint step is no larger than that path's
  original largest joint step, within 1.084e-13 degrees. Joint-limit residual is
  below 1.452e-15 radians. The largest corrected step across these paths is
  7.775 degrees per 1/240 s. The four previously observed large jumps are gone.
- `verify-aim-state.mjs`: 695 checks pass, including extreme diagonal ellipse
  projection, idempotence, quaternion sign equivalence, correction amount,
  held correction, transition from the previous held attack, return removal,
  and the standalone default projector. Final maximum projection residual:
  7.836e-16 radians.
- Throw integration's `verify-throw-aim.mjs`: 72 zero-drift cases pass, covering
  both throws, three charges for Small throw, and both directions of mixed
  flip/twist. Maximum applied exit-direction error is 2.19e-8; the solver and
  final finite-difference release velocity agree. This does not cover every
  physically unreachable low-charge throw against a large incoming velocity.
- `verify-spin-performance.mjs`: all 878 exact optimization parity comparisons
  still pass after the projection fix on its existing representative pose set.

The assertions about the largest step describe these fixed regression paths,
not a universal bound on animation speed. The original animations already have
rapid movement in places; this work removes the new aim-induced discontinuities.
The direction contract does not promise radial reach to every target, obstacle
avoidance, or physically realizable exit directions against arbitrary COM drift.

## Saved evidence

`Saved/BodyflipLab/PredictiveAim/` contains before/after extended reports, detailed
raw/aimed/projected joint snapshots at the former snaps, and four contact sheets
rendered from the actual Bodyflip collider geometry: headbutt, slashL, KickR,
sweepKick. Each sheet shows eight points across the motion from two viewpoints.
Those sheets were visually inspected alongside the dense numerical traces.

The final scaled-LM rerun is `extended.json`, with process logs
`extended-scaled-lm.log` and `state-scaled-lm.log`. Both processes exited zero,
running serially after the throw probe. The preceding result is preserved as
`extended-pre-scaled-lm.json`. The solver SHA256 remained
`3b79656eb5dd1b749c439dc44f0f2275f3c94646aa0ac8174d2d0c86d65f926c`
before and after both suites. No assertion thresholds changed. Collider pose
captures were regenerated by the final dense test; the four existing rendered
contact sheets were inspected before this final damping adjustment.

The old `verify-attack-aim.mjs` predates anatomical constraints and full future
flight. Its assumptions that pelvis tilt is always zero, each spine gets an equal
world-space rotation, and correction state exposes `bends` are superseded by this
audit; it should not be treated as a verification of the new legal path.
