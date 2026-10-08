# Fractional magnetization landing

**REVERTED:** user rejected this experiment and the subsequent predictive brakes.
The original momentum blend is restored with no anti-wobble additions. Below is
the historical experiment and its measurements, not the current contract.

User requested strength1 unchanged and strength.5 to close half the remaining
error next tick instead of retaining momentum and overshooting. Applies to both
linear and angular strength; the local/global mode parameter is unchanged.

In the Jolt velocity servo,0<strength<1 now writes
`velocity = strength * pose_error / step_duration` instead of
`velocity += strength * (pose_error / step_duration - velocity)`.
Disabled0 keeps its no-write behavior. Strength1 and values above1 retain their
existing expression. Fractional linear control converts the requested origin
velocity to COM velocity using the FULL resulting angular velocity; multiplying
that conversion by strength again would corrupt the intended origin fraction.
Local parent command prediction, native caps, strength-scaled gravity cancellation
and explicit pelvis-inertia follow weights are unchanged. Physics constraints or
contact can still move the result past a target; this is a drive command contract,
not an unconstrained pose teleport or a guarantee about the collision solve.

The change uses the existing loop/scratch, adds no state, inference or allocation.
Tests cover strong incoming velocities in both directions, repeated25%/50% closure,
no free-space overshoot, nonzero COM offsets, parent ordering, global/local modes,
gravity, disabled channels, and unchanged full-strength behavior.

No Blueprint pins, values or wiring edited. Live Coding needs a normal DLL rebuild
before any future cold launch.


Validation: all15 Prophecy.Jolt.Servo tests pass, including the new25%/50%
repeated landing test with high incoming velocities of either sign. Final build
succeeded and patch loaded03:45:38UTC with no object changes. First compile found
a missing BodyID argument in the new test only; repaired before loading.

The140-tick current-setup replay completed. All recorded poses before the
fractional-strength change (ticks10-78, all3 agents) match the old run exactly.
Head error at92 drops9.396 ->3.099degrees; at100 drops8.108 ->.380degrees. Contacts
still affect subsequent motion (at120,2.101 ->2.238degrees), so do not claim that
all physical wobble is eliminated. Saved values/wiring untouched, owned Play ended,
gravity settings restored/unchanged, user's dirty Blueprint preserved. Receipts:
`Saved/Diagnostics/FractionalMagnetization20261007/` and
`Saved/Diagnostics/LocalMagHead90_20261007/fractional_final.json`.
