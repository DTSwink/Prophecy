# Maintained Jolt patch

`NumericalSafety.patch` applies to Jolt 5.6.0 commit `e77f175595e64cb44218cc9d9d56fc365ad0e36a`. It contains the numerical safeguards and the joint-continuity repair below. Keeping them in one cumulative patch avoids overlapping patches to SixDOFConstraint and ConstraintManager. `BuildJolt.ps1` accepts either that pristine checkout or exactly this patch, and refuses unrelated edits. Both dependency configurations record the patch hash; the Unreal build checks it and the native DLL/import-library hashes before compiling against installed headers.

## Runtime joint continuity (2026-09-12)

SixDOF's free/fixed axis changes invalidate only the affected translation or rotation solver block. Changing angular modes still clears the angular constraint and motor impulses, but preserves the unchanged point/translation attachment and translation-motor impulses. Translation-mode changes similarly leave angular impulses intact. Frames, limits, solver equations, and ordinary stepping are unchanged.

`PhysicsSystem::ReplaceConstraint` replaces a registered constraint at its existing manager index in constant time, holding the usual manager lock and taking a reference before releasing the old entry. Its preconditions are an existing old registration, an unregistered replacement, and no concurrent Update. Keeping the priority preserves exact solve order. Prophecy uses this only outside Update when adding/removing a player's limited-swing wrapper; the same native SixDOF survives. NPCs, Free/Locked joints and twist-only joints retain their existing stock paths. No per-frame work was added.

`Prophecy.Jolt.Joints.RuntimeLimitContinuity` checks nonzero attachment impulses, unchanged off-center loaded motion, stable registration order with another registered constraint, wrapping/unwrapping, and correct angular impulse invalidation. Existing Joints boundary tests and RigWorld live-limit tests cover actual enforcement and player-policy transitions. Causal evidence is in `Docs/JoltWristLimitActivationDiagnosis.md`.

## Numerical safety

The patch contains a high-magnetization crash in rigid-body joint correction. Ordinary finite rotation corrections retain the original arithmetic. Corrections above 10,000 radians use a double norm and scalar trigonometry, avoiding overflow in the float squared norm or SIMD quadrant reduction. This threshold selects arithmetic; it does not clamp a rotation or change magnetization strength.

Invalid position/rotation and solver-velocity writes are rejected before mutation. Point-constraint endpoint increments are checked together before committing either body. Position increments must have a representable native float squared norm, and candidate transforms must keep the full shape inside Jolt's `+/-cLargeFloat` broadphase range. A conservative shape-radius check handles ordinary transforms; near the boundary the exact bounds include rotation and outward float rounding. A sticky failure flag uses an unused Body bit and existing MotionProperties padding, with a compile-time size check. Failed endpoints stop participating in constraints; other assertions retain their original behavior.

The update reports `EPhysicsUpdateError::NumericalFailure` (bit 3). Workers finish existing batches and dependency releases. Before another collision substep begins, active bodies are deactivated and step listeners are skipped so they cannot reactivate the failed simulation. The Unreal owner rejects the entire failed publication and all subsequent steps; the shared coordinator keeps the last published pose. Stop Play and start a new simulation to reset this fault. No automatic gain reduction, PHAT retuning, or backend switch occurs.

Regression tests are `Prophecy.Jolt.NumericalSafety.*` and `Prophecy.Jolt.Character.HighMagnetizationSafety`. The former includes deliberate invalid writes inside actual worker solver jobs, small/large connected islands, and multiple collision substeps; the latter drives the real 22-body PHAT character at normal and tenfold strength. Current run evidence belongs in `Saved/JoltMigration/HighGainCrash-20260910/`.
