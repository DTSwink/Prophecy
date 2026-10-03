# Backend preference draft (not applied)

Production edits are held until the parent confirms its running build is finished.

- Add private `UPROPERTY(Transient) bool bUseJoltForPhysicalMode = false` to `AProphecyAgent`.
- Keep the existing mode transition implementation in private `SetSimulationModeInternal`.
- Public `SetSimulationMode(Physical)` first completes that ordinary transition, then calls `EnableJoltPhysicalAnimation` if the successful prior Jolt selection is retained. Other mode changes keep the current behavior.
- `EnableJoltPhysicalAnimation` uses the internal mode helper to avoid recursion. Successful immediate admission, or successful deferred admission that still owns the active rig, selects Jolt. Repeated explicit enable of an active binding selects Jolt. Failed/cancelled admission does not create a new selection.
- Move existing disable implementation into private `DisableJoltPhysicalAnimationForModeChange`. Switching to Kinematic uses this helper and retains the choice. Explicit `DisableJoltPhysicalAnimation` clears the choice and invokes the helper, including when the actor is already Kinematic.
- Retain the direct Jolt-to-HalfSim refusal; HalfSim remains its existing Chaos implementation.

Regression: actual 22-body/21-joint fixture, Jolt Sim -> Kinematic -> HalfSim -> Sim, native body/velocity handoff checks, one subsequent Jolt step and registry cleanup. Explicit disable while Kinematic must make later Sim stay Chaos. An enable rejected while HalfSim must not change that. For cancellation, use a scoped actual `OnWorldPostActorTick` callback in the transient test world to request deferred enable and immediately request Kinematic; a subsequent world tick must not admit it or select Jolt.

No global map, production asset save, new backend enum, feedback changes or physics tuning. A fresh PIE instance after header reinstancing is necessary because an already-active rig admitted by the old binary has no historical preference field.
