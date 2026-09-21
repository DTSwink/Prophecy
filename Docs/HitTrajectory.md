# Get Launch Trajectory

`Get Launch Trajectory` is an execution Blueprint node in `PhysicsHitVelocityLibrary`, category **Prophecy / Physics / Trajectory**. It computes a world launch velocity once per call. It does not launch, move or tick anything. Formerly displayed as Get Hit Trajectory; its internal function name remains `GetHitTrajectory` so existing Blueprint references and connections are preserved.

Main inputs:

- **Start Location:** projectile launch position, world cm.
- **Current Target Location:** current aim point, world cm.
- **Current Target Speed:** target **world velocity vector**, cm/s. Direction is required to lead a moving target; do not connect its scalar speed magnitude.
- **Angle:** standard elevation in degrees, 0 horizontal, 90 straight up, -90 straight down. Clamped to [-90,90]. Horizontal heading is chosen by the solver.

Outputs: **Velocity** (world cm/s), **Exact Hit**, **Flight Time** (seconds until intercept/closest pass), **Miss Distance** (cm between projectile and predicted aim point at that time). Exact Hit uses a numerical tolerance of 0.01 cm. Invalid/nonfinite inputs or nonpositive limits return zero velocity, false, time0 and miss-1.

Advanced inputs:

- **Max Launch Speed:** default10000cm/s. Positive finite bound.
- **Max Flight Time:** default10seconds. Positive finite search horizon, starting at time0.
- **Gravity Scale:** default1. Multiplies world GravityZ;0 disables gravity. Without a world, gravity defaults to -980cm/s².

The bounds make the closest-pass request well-defined. A flat launch toward a stationary point at the same height has no exact finite-speed hit under gravity; its miss approaches zero as speed tends to infinity. The node instead finds the closest pass within the exposed limits. An otherwise possible shot outside those limits is also a fallback. It never changes the elevation to force a hit. Equal-error solutions prefer the earlier pass. If the best pass is at launch time0, the target is already closest at launch within these bounds.

Connect Velocity to the ball's velocity setter with **Add to Current=false**. Set the ball's gravity to match the node. The model assumes constant target velocity, constant vertical gravity and no drag. It solves for points, without ball radius, obstacles, collision deflection or future target acceleration; Exact Hit describes the predicted mathematical path, not a collision-event guarantee. Physical flight time uses seconds, not the project's special 60-tick blend-duration convention.

## Solver

At time t, gravity-compensated required displacement is `Q = Target - Start + TargetVelocity*t - 0.5*Gravity*t²`. With requested elevation a, let `h=length(Q.xy)`, `z=Q.z`, `c=cos(a)`, `s=sin(a)`. Best horizontal heading points along Q.xy, and best speed at that time is `clamp((c*h+s*z)/t, 0, MaxLaunchSpeed)`.

This reduces the search to a single bounded time variable. The implementation enumerates exact-intercept roots, stationary miss roots in the zero/interior/capped-speed regimes, regime boundaries, horizontal-distance cusps and interval endpoints. Polynomial roots (degree at most8) are isolated by recursive derivative roots and bisection on normalized time. Tangent roots are retained. Squaring generates extra candidates, so all candidates are compared using the original unsquared spatial error. There is no fixed time grid or frame-rate dependency in the runtime solve. Numerical precision, rather than symbolic exactness, sets the accuracy.

Focused verification lives in `Prophecy.Physics.HitTrajectory`: known stationary arc, full3D moving target, impossible flat shot closest pass, vertical crossing, zero gravity, speed/time bounds, invalid input, and80 deterministic cases compared against4000 sampled times each. Runtime gameplay testing remains separate from these mathematical checks.

Compiled and loaded via Live Coding2026-09-20 at19:35UTC. The focused suite passed19:35:56UTC. Reflected Blueprint call with stationary target1000cm forward,45degrees and standard gravity returned(700,0,700)cm/s and flight time1.428571seconds. No scene or Blueprint wiring changes.

Display-name-only rename to **Get Launch Trajectory** compiled/loaded19:42:40UTC; runtime DisplayName metadata verified. Internal function identity, pins and trajectory math are unchanged.
