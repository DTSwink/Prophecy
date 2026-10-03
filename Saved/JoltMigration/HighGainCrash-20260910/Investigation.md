# High-magnetization Jolt crash investigation

Follow-up implementation and passing verification are recorded in [Implementation.md](Implementation.md). The investigation below describes the original evidence before that fix.

User report: magnetization multiplied by 10 in simulated Jolt mode caused expected physical instability, then an unwanted editor crash. Scope of this pass is investigation; no implementation, physics/strength settings, assets, builds or reproductions were changed/run.

## Confirmed evidence

- Actual crash: `Saved/Crashes/UECC-Windows-21FF5F7F403B1C07C4FD4FB32508022A_0000/CrashContext.runtime-xml`, `UEMinidump.dmp`, and copied `EditorFixtureReopened.log`. Fatal log timestamp: 2026-09-10 06:02:07 UTC / 08:02:07 local.
- Crash type: Assert. Expression: `!mRotation.IsNaN()` in the pinned Jolt 5.6.0 `Body.inl:96`.
- Symbolized stack: `ProphecyJoltRuntime::AssertFailed` → `Body::AddRotationStep` → `PointConstraintPart::SolvePositionConstraint` → `SixDOFConstraint::SolvePositionConstraint` → `ConstraintManager::sSolvePositionConstraints` → `PhysicsSystem::JobSolvePositionConstraints` → Jolt worker thread.
- `Plugins/ProphecyJolt/Source/ProphecyJolt/Private/ProphecyJoltModule.cpp:56` converts the assertion to `UE_LOG(..., Fatal, ...)`, terminating Unreal.

## Why the existing checks did not contain it

The gain is accepted as a finite nonnegative value. The servo performs its existing velocity rewrite and uses Jolt's clamped velocity setters (`ProphecyJoltVelocityServo.cpp`). Ordinary velocity integration also clamps velocities. These protections are present; this is not evidence that the servo forgot its velocity caps.

The failing phase is separate joint position correction. `PointConstraintPart.h:174–203` calculates a correction from anchor separation, effective mass and Baumgarte stabilization, directly changes positions, and sends an inertia-weighted rotational correction into `Body::AddRotationStep`. That correction is not the body's stored angular velocity and does not pass through its angular-velocity cap. `Body.inl:92–96` calculates its length and a normalized quaternion; this call produced NaN.

`ProphecyJoltWorldSubsystem.cpp:1854` calls `Physics.Update`. Its servo-error and all-body finite-state checks occur after Update returns (1863 onward), so they cannot intercept this internal fatal assertion. Stock `EPhysicsUpdateError` reports contact/cache capacities, not a numerical-solver failure. The step listener runs before a simulation substep and offers no supported cancellation return.

## Certainty and unresolved detail

The fatal location, joint-correction path, and containment gap are established from this user's crash and the matching local source. Runaway gain is consistent with the reported explosion, but the report does not expose the actual correction vector, multiplier, effective mass or first invalid scalar. Overflow versus an ill-conditioned solve is therefore unresolved. No exact velocity-cap value, problematic bone/joint identity, standalone reproduction or tested fix is claimed.

## Fix direction

Reliable containment needs a native numerical guard before invalid position/quaternion mutation, a per-world failure signal, and a safe solver exit/fault path that prevents further stepping or publication of corrupt state. The worker-job/barrier lifetime and both position and rotation updates must be handled; simply returning from an assertion handler or throwing through Jolt worker jobs is not a safe recovery design. This would require a small supported upstream patch or equivalent guarded constraint implementation, followed by an isolated high-gain regression.

An earlier joint-separation/energy cutoff could stop a runaway rig before dangerous arithmetic, but its threshold is a new behavior policy and alone is not proof against within-step overflow. Do not silently clamp the user's gain, retune PHAT, turn off assertions, or describe existing post-update checks as a fix. No fix has been applied in this investigation.

Reference source: pinned local upstream tree `Intermediate/JoltMigration/Upstream/Jolt/Physics/{Body/Body.inl,Constraints/ConstraintPart/PointConstraintPart.h,Constraints/SixDOFConstraint.cpp,PhysicsSystem.cpp,EPhysicsUpdateError.h,PhysicsStepListener.h}`. Public API background: https://jrouwe.github.io/JoltPhysicsDocs/5.5.0/class_body_interface.html (local pinned source is authoritative for this crash).
