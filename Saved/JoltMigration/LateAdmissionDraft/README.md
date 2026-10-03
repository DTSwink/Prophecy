# Late admission cancellation regression draft

2026-09-09. Draft extension only; no active source writes, builds or Unreal runs were performed for this task.

The only code file is `Source/GameAnimationSample3/Private/ProphecyPhysicsBenchmarkMultiJolt.cpp`, copied from the active crowd benchmark and extended inside `SaveMultiJoltCase`. It preserves the completed measured sample loop, the animation-finalization removal regression and the two unmeasured shared lifecycle steps. No header or frame-state hooks are required.

The new `late_admission_cancellation` result uses the now-kinematic removed agent while survivors still own their native rigs. Save executes from `OnWorldPostActorTick`, so re-enabling that agent must return accepted/pending rather than create a Jolt rig in the already queued frame. The regression verifies:

- Pending status retains the same physical mesh, zero completed Jolt revision and exactly 22 Chaos dynamic bodies for that agent. Native body/joint counts, coordinator registration count, native lifetime, completed steps and creation-failure count stay unchanged.
- Repeated Agent and component enable calls remain pending and do not produce a completion callback or another registered rig.
- `SetSimulationMode(Kinematic)` clears pending status, the one-shot completion delegate and the current error without invoking completion. The ordinary mode transition leaves zero Chaos dynamic bodies.
- Every survivor retains its exact body handles, position, COM, orientation, linear/angular velocity, awake/dynamic state and completed revision. All removed handles remain invalid.

The completion observer captures heap-owned state, avoiding dangling stack references if a failing implementation unexpectedly retains the delegate. Result metadata records the unchanged survivor-body count, pending/cancelled Chaos counts, callback count and coverage limits. Failure is attached to the existing crowd validation result and fails the case.

This is an immediate request/idempotence/cancellation proof. It does **not** advance another engine frame, inspect the coordinator's private pending array, prove successful next-frame admission, exercise a deferred failure callback, or prove the next-frame drain is clean at runtime. JSON explicitly marks both next-frame checks false. A later fixture can use normal frame-state progression for those cases; no recursive `World.Tick` is introduced.

Read-only source checks confirmed the benchmark Save caller is `OnWorldPostActorTick`, the Agent wrapper performs Physical staging before the request, the coordinator defers late admission, and the Kinematic transition cancels pending first. `TSharedRef::Get` returns an object reference in UE 5.7 `Templates/SharedPointer.h:474`; native state comparisons use the UE vector/quaternion equality operators. Whitespace validation passed after removing a copied trailing blank line. The code has not been compiled or executed.

Promotion baseline SHA256 of the active source read for this draft: `85D07D0FFC3AC66D7F7240A37DACE213B47667581872CF38BEE2298EE3B438EB`. Promote only this file after checking that baseline or apply its insertion if the active benchmark changed; do not mirror the draft directory with deletions.
