# Compute Catch Up

Pure Blueprint node in **Prophecy | Physics | Trajectory**.

Inputs: **Victim Location**, **Victim Velocity**, **Attacker Location**, and
**Attacker Speed**. Locations are world coordinates in cm; velocity and speed
are cm/s. Uses all three axes. For planar interception, supply locations on the
same Z plane and zero victim Z velocity.

Outputs:

- **Can Catch Up**: whether a finite interception is possible.
- **Duration**: earliest interception time in seconds.
- **Optimal Attacker Velocity**: constant world velocity aimed at the future
  interception position, with magnitude equal to Attacker Speed. If interception
  is impossible, aims directly at the victim's current location at that speed.

Assumes constant victim velocity, instant attacker steering, constant attacker
speed, point targets and no obstacles. This computes a theoretical result; it
does not steer an agent or account for acceleration, turn rate or collision.
Recompute when the victim's motion changes.

Unreachable interception returns false and Duration **10000**, with naive pursuit
velocity toward the current victim position at Attacker Speed. Recompute as the
victim moves. Invalid inputs still return false, **10000**, and zero velocity.
Already coincident locations return true, zero duration and zero velocity.
Negative/nonfinite speed or nonfinite vectors are invalid. Zero attacker speed
can still intercept a victim that passes exactly through the attacker. A faster
victim is not automatically unreachable: direction matters. Valid times are not
capped at 10000; use the boolean to distinguish failure from a long interception.

For relative location R, victim velocity V and attacker speed S, solve
`(V dot V - S*S)*t*t + 2*(R dot V)*t + R dot R = 0`.
The earliest positive root is the first time the future victim lies on the
attacker's expanding reachable sphere. The returned velocity is `V + R/t`.
Equal speeds reduce to a linear equation. Root evaluation avoids subtraction
of nearly equal values; tangency admits only double-precision rounding error.

Constant cost per call, at most one square root, no loop, allocation, actor/world
lookup, cache or tick subscription. Pure-node evaluation follows normal Blueprint
rules; store its outputs if using them in multiple separate execution chains.

Focused test: `Prophecy.Physics.ComputeCatchUp` covers analytic times, 3D lead,
equal/nearly equal speeds, earliest of two roots, tangency/miss, stationary and
invalid cases, long times, 3D naive pursuit on failure, translation invariance and 250 randomized cases with
earlier-time reachability checks. Gameplay testing remains with the user.
