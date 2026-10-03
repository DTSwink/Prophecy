# Locked wrist separation: upstream research, 13 September 2026

Research only. No gameplay settings, assets or physics implementation changed.

## What upstream establishes

- [Fixed Constraint Effects on Motion, discussion 1077](https://github.com/jrouwe/JoltPhysics/discussions/1077): Jolt's maintainer explicitly says a fixed constraint is not perfectly rigid because of the solver. A compound is the solution for a genuinely rigid assembly. This explains finite joint error, but does not establish that our large wrist separation is expected. Combining the forearm and hand would remove the wrist articulation we need.
- [Procedural skeletal animation, JoltPhysics.js discussion 122](https://github.com/jrouwe/JoltPhysics.js/discussions/122): a user encountered insufficiently rigid animated ragdoll constraints and discovered they had only two velocity iterations. The maintainer says the default ten velocity and two position iterations should provide a strong connection. The user's revised example still needed tuning. Our integration already uses those defaults, so copying that correction alone is not a fix for our case.
- [Jolt architecture](https://github.com/jrouwe/JoltPhysics/blob/master/Docs/Architecture.md): joints and contacts are solved iteratively in velocity space, followed by integration and positional drift correction. CCD can alter body travel after the main velocity solve, before positional correction. Limited iterations can leave incompatible demands incompletely resolved. This is a mechanism, not a diagnosis of which stage causes our wrist gap.
- [Native ragdoll stabilization source](https://raw.githubusercontent.com/jrouwe/JoltPhysics/master/Jolt/Physics/Ragdoll/Ragdoll.cpp): Stabilize adjusts parent/child masses and inertias to improve ragdoll stability. The pinned local source contains this functionality. It changes physical properties; it is not a free switch preserving authored behavior exactly.

## Match to our integration

The prior read-only capture confirms physical lowerarm-to-hand origin distance growing from 22.550 cm at tick 95 to 43.136 cm at tick 125, despite locked wrist translation. It does not expose current native joint anchor error or per-stage corrections directly.

We import Chaos per-body inertia conditioning, but do not run Jolt's chain stabilization. Adding attached sword inertia changes the hand without applying the equivalent parent-chain adjustment. Magnetization also assigns each body its own target-tracking velocity. These are plausible contributors to poor convergence under sword/thigh contact, not isolated causes yet.

Welding promotes the hand to LinearCast when the sword uses it (ProphecyJoltWorldSubsystem.cpp). The pinned PhysicsSystem.cpp confirms CCD resolves before positional joint correction. Isolating this CCD contribution is worthwhile; no matching maintainer report or proof was found that CCD causes this scene's failure.

The imported UE wrist profile enables linear projection, which our Jolt conversion does not implement. That is a real backend difference, but adding projection without diagnosing the solve could conceal the underlying problem.

## Recommended next step

Capture actual wrist anchor error before/after the solver stages, alongside contact impulses. Then isolate attached inertia, drive contribution and CCD one at a time. Choose stabilization or solver-iteration changes based on the measured cause. Iteration overrides can increase work for the connected island, not just one wrist. Do not treat a rendered-pose correction as a physics fix.

No upstream patch was identified that can presently be called a demonstrated fix for this specific failure.
