# Shared character and prop step-client draft

Status: source draft only, not compiled or executed. No active source, native-world initialization, geometry creation, prop component, collision policy, or production backend selection changed. This prepares a dropped prop to keep simulating and presenting after the last character leaves, using the existing single game-world coordinator. Functional behavior and speed are the acceptance criteria; no Chaos trajectory equivalence is required.

## Promotion and baseline

The five files under `Source/GameAnimationSample3` map directly to the corresponding active game-module paths. `Public/ProphecyJoltStepClient.h` is new and needs normal UHT generation in a full Editor build. Existing module dependencies already cover the APIs used.

**Do not replace the active CharacterComponent.cpp with its draft copy.** Root added profiling scopes to that file after this draft's baseline. Merge only these isolated changes, preserving every profiling include/scope:

1. Add `CancelDeferredEnable(const FGuid&)`, which cancels only the matching valid local pending token.
2. Add the three native interface forwarding methods before `PrepareForCoordinatedWorldStep`.
3. In `PublishCompletedPose`, capture `StepRegistrationId` next to the captured revision; require the same ID and, when nonempty, `Coordinator->IsStepClientRegistered(*this, ID)` in the existing publication guard. Empty ID is permitted for initial pose priming before registration.
4. In disable, invalidate the local ID after the coordinator unregister call, including when the weak coordinator has already expired.

The header adds interface inheritance/forward declarations and private `StepRegistrationId`; its existing character-facing methods remain unchanged. Coordinator files can be compared/promoted against their baseline after confirming no newer active semantic edits.

`CharacterComponent.merge.patch` contains only those isolated implementation hunks in apply_patch format for root's review/promotion. It has not been applied to active source. It excludes profiling removals and does not replace the whole implementation file.

| Baseline file | SHA-256 |
|---|---|
| Public/ProphecyJoltCharacterWorldSubsystem.h | CDDB619B4D5789E62E3509BCC6388454A354682A90DC67EA0AD1A984369AB51B |
| Private/ProphecyJoltCharacterWorldSubsystem.cpp | B6688C1E1C7AE4E0D63C187D9D7D02965B767B51F523580C5AFD6DEDC5F71A54 |
| Public/ProphecyJoltCharacterComponent.h | 4BB6918FD052D187A50AEACB0CA8B3B9F3A16C3E89B069A0041EBC899795AD3E |
| Private/ProphecyJoltCharacterComponent.cpp | EAB85599A88D9C40C453C968E268A84EF894041B84C171CE19760C15E6B850CD |

## Interface and ownership

`IProphecyJoltStepClient` is a native-only UE interface implemented by a registered `UActorComponent`. It provides nonmutating active/automatic queries, `PrepareJoltWorldStep(dt, publishMissing, error)`, `ConsumeCompletedJoltWorldStep(error)`, and `LatchJoltStepError(error)`. A stopped binding remains active while it retains native ownership. A future rigid-body presentation component can implement the same interface without skeletal or character dependencies.

The coordinator retains weak component/publisher references, a fresh GUID for every registration, and a GUID-to-weak-component index. Snapshot callbacks resolve that exact current GUID; an old snapshot cannot dispatch to a replacement registration on the same object. The index keeps per-client validation constant-time rather than scanning the entire crowd for each callback. Body/rig handle generation and native-world lifetime validation remain owned by the client/native registry.

Generic methods:

```cpp
bool RequestClientAdmission(UActorComponent& Client,
    const FProphecyJoltClientAdmissionCallback& Complete,
    const FProphecyJoltClientAdmissionCallback& Cancel,
    bool& bOutDeferred, FGuid& OutAdmissionId, FString& OutError);
bool CancelClientAdmission(UActorComponent& Client, const FGuid& AdmissionId);
bool CanRegisterStepClient(const UActorComponent& Client, FString& OutError);
bool RegisterStepClient(UActorComponent& Client, AActor* OptionalPublishingActor,
    FGuid& OutRegistrationId, FString& OutError);
bool UnregisterStepClient(UActorComponent& Client, const FGuid& RegistrationId);
bool IsStepClientRegistered(const UActorComponent& Client, const FGuid& RegistrationId) const;
int32 GetRegisteredStepClientCount() const;
bool StepExplicit(UActorComponent& Requester, const FGuid& RegistrationId,
    float DeltaSeconds, FString& OutError);
```

Existing character callers continue using the typed character wrappers; those wrappers own the character's local registration ID and preserve its revision/stop-state admission checks. A future generic client retains its returned ID itself and invalidates it before callback-capable teardown. It must cancel pending admission and unregister during both relevant EndPlay/OnUnregister paths. It must recheck exact registration, native handles and presentation object identity after callback-capable scene updates.

The optional publishing actor establishes an Actor tick prerequisite. It must be live in the same world. Passive props can pass null and need no enabled actor tick; a prop whose actor authors inputs passes that actor. A prerequisite is removed only after the last registration referencing that actor leaves. The client must not introduce cyclic tick prerequisites.

## Cadence and lifecycle

There remains one nonparallel PrePhysics coordinator tick. A shared step prepares every active client, advances the existing native world once, and presents that completed step to every still-registered client. Automatic stepping requires at least one live client explicitly returning true from `WantsAutomaticJoltStep`. A remaining automatic prop therefore continues after zero characters. Native body count alone never requests a step. All-manual clients remain still under ordinary ticking, and any one exact registered manual client can explicitly step the shared world; an explicit call is rejected while any client requests automatic stepping.

The existing once-per-engine-frame automatic guard, UE physics collision-step cadence, paused-tick behavior and explicit benchmark multiple-step capability remain. Last automatic/explicit frame identity is retained when the last client leaves, preventing same-frame automatic re-admission from causing another step. Native lifetime and completed-step counters are reset only when **all** clients are gone, not when the last character leaves.

Preparation and consumption may remove a client normally. Registrations are revalidated before each callback and before treating a callback failure as a shared fault. If preparation removes every client, the coordinator performs no native step. If native ownership changes or someone directly steps the world during preparation, a second diagnostics check refuses the coordinator step. A real preparation/consumption failure latches the shared error on surviving bindings; no implicit backend fallback occurs.

Admission retains the existing pre-queue boundary: immediate outside world tick or during the open pre-queue window; otherwise the whole native enable/priming operation is deferred to the next `OnWorldPreActorTick`. A weak native delegate must be bound to the requesting UObject (`CreateUObject` or `CreateWeakLambda`); `GetUObject()` is checked for both callbacks. Deferred request repetition returns the same token. Callbacks must recheck that token. Completion removes its queue ownership before dispatch. Cancellation matches component plus token; an old token cannot cancel a new request.

The admission drain snapshots order while retaining not-yet-dispatched entries in the authoritative queue. Nested requests for a later pending client are idempotent; cancellation of a later snapshot entry prevents dispatch; newly queued tokens do not join the current snapshot. World teardown clears queue ownership before weak cancellation callbacks and stops admission. This coordinator never creates a native world/body and never owns a client's presentation object or body teardown.

## Source checks and validation still required

Source review covered exact registration invalidation, optional/shared publisher removal, dead weak clients, prepare/consume self-removal, native lifetime/step counter guards, pending token reuse/cancel/drain ordering, all-manual behavior and the existing character prime/disable guards. `GetUObject()` and weak UObject/weak-lambda delegates are verified in UE5.7 `Core/Public/Delegates/DelegateBase.h` and `DelegateInstancesImpl.h`; the native interface pattern exists in `Engine/Classes/Interfaces/Interface_CollisionDataProvider.h`. Existing UE5.7 `LevelTick.cpp`/`TickTaskManager.cpp` admission ordering remains unchanged from the validated character coordinator.

No fake component UCLASS was added solely for a test: a real non-skeletal UObject implementing a UInterface needs reflected class metadata, and the authorized scope excludes a standalone prop component here. The following are explicit pending runtime fixtures, not claimed passes:

1. Rerun existing single/two-character air/floor, callback removal, second survivor explicit step, and late pending/cancel tests after the full Editor build; compare the optional 100-character timing fixture with profiling retained.
2. Once the first real prop component is introduced, register an automatic falling prop with zero characters. Assert one native step and one presentation revision per ordinary frame, then remove the last character from a mixed scene and prove the exact prop handle/revision continue.
3. Set every prop and character manual. Ordinary frames must leave native completed steps and client revisions unchanged despite live dynamic bodies. One explicit request must advance and present all registered clients once. Turning on any automatic prop must reject explicit stepping.
4. Give two clients the same publishing actor, remove one, and prove the other still prepares after that actor's tick. Remove/re-register a component and assert its stale registration cannot unregister or explicitly step the replacement.
5. Request a prop after queueing, repeat the pending request, cancel/re-request, and drain on the next real frame. Verify no native admission before the boundary, no stale callback, one completion, and clean world teardown while pending. Do not recursively tick a world from its PostActorTick callback.
6. Remove a client from Prepare or Consume; surviving clients must complete without a spurious shared fault. Inject a true client error to verify survivors stop explicitly. Pause a world with automatic clients and verify no native step/presentation revision until resumed.

Existing character benchmark passes were obtained from active code before this draft; they do not prove this interface refactor or a future prop adapter.
