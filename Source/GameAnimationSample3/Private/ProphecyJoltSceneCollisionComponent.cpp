#include "ProphecyJoltSceneCollisionComponent.h"

#include "ProphecyJoltCharacterWorldSubsystem.h"
#include "ProphecyJoltStaticBody.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/ModelComponent.h"
#include "Engine/Level.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "InstancedStaticMeshDelegates.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/PhysicsSettings.h"
#include "UObject/UObjectIterator.h"

DEFINE_LOG_CATEGORY_STATIC(LogProphecyJoltSceneCollision, Log, All);

struct FProphecyJoltSceneCollisionSource
{
    ECollisionChannel LastObjectChannel = ECC_MAX;
    FString Path;
    TWeakObjectPtr<ULevel> Level;
    FDelegateHandle TransformChanged;
    TMap<int32, FProphecyJoltBodyHandle> Bodies;
    TArray<FTransform> InstanceTransforms;
    TSet<int32> DirtyInstances;
    bool bFullRefresh = true;
    bool bCollisionDirty = false;
    bool bPhysicsDestroyed = false;
};

struct FProphecyJoltSceneCollisionState
{
    TWeakObjectPtr<UProphecyJoltWorldSubsystem> Owner;
    TWeakObjectPtr<UProphecyJoltCharacterWorldSubsystem> Coordinator;
    FGuid WorldLifetime;
    uint64 ExpectedWorldSteps = 0;
    TMap<TWeakObjectPtr<UPrimitiveComponent>, FProphecyJoltSceneCollisionSource> Sources;
    TSet<TWeakObjectPtr<UPrimitiveComponent>> InstancedSources;
    TSet<TWeakObjectPtr<UPrimitiveComponent>> PendingSources;
    TSet<TWeakObjectPtr<AActor>> PendingActors;
    TSet<TWeakObjectPtr<ULevel>> RemovedLevels;
    FDelegateHandle PhysicsCreated, PhysicsDestroyed, ActorSpawned, LevelAdded, LevelRemoved, InstanceChanged, TreeBuilt;
    int32 BodyCount = 0;
    bool bAllLevelsRemoved = false;
    bool bStopped = false;
};

void FProphecyJoltSceneCollisionStateDeleter::operator()(FProphecyJoltSceneCollisionState* InState) const { delete InState; }

namespace
{
FString SourceError(const FProphecyJoltSceneCollisionSource& Source, int32 InstanceIndex, const FString& Error)
{
    return InstanceIndex == INDEX_NONE ? FString::Printf(TEXT("%s: %s"), *Source.Path, *Error)
        : FString::Printf(TEXT("%s[%d]: %s"), *Source.Path, InstanceIndex, *Error);
}

bool RetireBody(FProphecyJoltSceneCollisionState& State, FProphecyJoltSceneCollisionSource& Source, int32 Index, FString& Error)
{
    const auto* Handle = Source.Bodies.Find(Index);
    if (!Handle) return true;
    if (!State.Owner.IsValid() || !State.Owner->OwnsBody(*Handle))
    { Error = SourceError(Source, Index, TEXT("Owned static body was removed or its native world changed externally.")); return false; }
    const auto Removed = State.Owner->DestroyBody(*Handle);
    if (!Removed.IsSuccess()) { Error = SourceError(Source, Index, Removed.Message); return false; }
    Source.Bodies.Remove(Index); --State.BodyCount;
    return true;
}

bool RetireAll(FProphecyJoltSceneCollisionState& State, FProphecyJoltSceneCollisionSource& Source, FString& Error)
{
    TArray<int32> Indices; Source.Bodies.GetKeys(Indices);
    for (const int32 Index : Indices) if (!RetireBody(State, Source, Index, Error)) return false;
    return true;
}
}

UProphecyJoltSceneCollisionComponent::UProphecyJoltSceneCollisionComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
    PrimaryComponentTick.bStartWithTickEnabled = false;
}
UProphecyJoltSceneCollisionComponent::~UProphecyJoltSceneCollisionComponent() = default;
bool UProphecyJoltSceneCollisionComponent::Fail(FString& OutError, const FString& Error)
{
    LastError = Error; OutError = Error; return false;
}
bool UProphecyJoltSceneCollisionComponent::IsSceneCollisionEnabled() const { return State != nullptr; }
int32 UProphecyJoltSceneCollisionComponent::GetImportedBodyCount() const { return State ? State->BodyCount : 0; }

bool UProphecyJoltSceneCollisionComponent::EnableSceneCollision(FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread() || bEnabling || bReconciling) return Fail(OutError, TEXT("Scene collision admission requires an idle game-thread owner."));
    if (State) return State->bStopped ? Fail(OutError, LastError) : true;
    if (IsEnablePending()) return true;
    if (!IsRegistered() || !GetWorld() || !GetWorld()->IsGameWorld() || !IsValid(GetOwner()) || GetOwner()->IsActorBeingDestroyed())
        return Fail(OutError, TEXT("Scene collision requires a registered component on a live Game/PIE actor."));
    for (TObjectIterator<UProphecyJoltSceneCollisionComponent> It; It; ++It)
        if (*It != this && It->GetWorld() == GetWorld() && (It->IsSceneCollisionEnabled() || It->IsEnablePending()))
            return Fail(OutError, TEXT("This world already has an enabled or pending scene collision owner."));
    auto* Coordinator = GetWorld()->GetSubsystem<UProphecyJoltCharacterWorldSubsystem>();
    if (!Coordinator) return Fail(OutError, TEXT("Shared Jolt coordinator is unavailable."));
    bool bDeferred = false; FGuid Admission;
    if (!Coordinator->RequestClientAdmission(*this,
        FProphecyJoltClientAdmissionCallback::CreateUObject(this, &ThisClass::CompleteDeferredEnable),
        FProphecyJoltClientAdmissionCallback::CreateUObject(this, &ThisClass::CancelDeferredEnable), bDeferred, Admission, OutError))
        return Fail(OutError, OutError);
    if (bDeferred)
    {
        AdmissionCoordinator = Coordinator; PendingAdmissionId = Admission; LastError.Reset(); return true;
    }
    return EnableNow(OutError);
}

void UProphecyJoltSceneCollisionComponent::CompleteDeferredEnable(const FGuid& Admission)
{
    if (!Admission.IsValid() || PendingAdmissionId != Admission) return;
    PendingAdmissionId.Invalidate(); AdmissionCoordinator.Reset();
    FString Error;
    if (!EnableNow(Error)) UE_LOG(LogProphecyJoltSceneCollision, Error, TEXT("Deferred scene collision admission failed: %s"), *Error);
}
void UProphecyJoltSceneCollisionComponent::CancelDeferredEnable(const FGuid& Admission)
{
    if (Admission.IsValid() && PendingAdmissionId == Admission) DisableSceneCollision();
}

bool UProphecyJoltSceneCollisionComponent::EnableNow(FString& OutError)
{
    if (!IsInGameThread() || bEnabling || State || !IsRegistered() || !GetWorld() || !IsValid(GetOwner()) || GetOwner()->IsActorBeingDestroyed())
        return Fail(OutError, TEXT("Scene collision admission lost its live component or idle boundary."));
    TGuardValue<bool> Guard(bEnabling, true);
    auto* Owner = GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    auto* Coordinator = GetWorld()->GetSubsystem<UProphecyJoltCharacterWorldSubsystem>();
    FProphecyJoltWorldDiagnostics Diagnostics;
    if (!Owner || !Coordinator || !Coordinator->CanRegisterStepClient(*this, OutError)
        || !Owner->GetDiagnostics(Diagnostics).IsSuccess() || !Diagnostics.bInitialized || Diagnostics.bFaulted
        || UPhysicsSettings::Get()->bTickPhysicsAsync)
        return Fail(OutError, OutError.IsEmpty() ? TEXT("Initialize a healthy synchronous Jolt world before enabling scene collision.") : OutError);
    State.Reset(new FProphecyJoltSceneCollisionState());
    State->Owner = Owner; State->Coordinator = Coordinator;
    State->WorldLifetime = Diagnostics.WorldLifetime; State->ExpectedWorldSteps = Diagnostics.CompletedSteps;
    State->PhysicsCreated = UActorComponent::GlobalCreatePhysicsDelegate.AddUObject(this, &ThisClass::OnPhysicsCreated);
    State->PhysicsDestroyed = UActorComponent::GlobalDestroyPhysicsDelegate.AddUObject(this, &ThisClass::OnPhysicsDestroyed);
    State->ActorSpawned = GetWorld()->AddOnActorSpawnedHandler(FOnActorSpawned::FDelegate::CreateUObject(this, &ThisClass::QueueActor));
    State->LevelAdded = FWorldDelegates::LevelAddedToWorld.AddUObject(this, &ThisClass::OnLevelAdded);
    State->LevelRemoved = FWorldDelegates::PreLevelRemovedFromWorld.AddUObject(this, &ThisClass::OnLevelRemoved);
    State->InstanceChanged = FInstancedStaticMeshDelegates::OnInstanceIndexUpdated.AddWeakLambda(this,
        [this](UInstancedStaticMeshComponent* Source, TArrayView<const FInstancedStaticMeshDelegates::FInstanceIndexUpdateData>) { QueueSource(Source); });
    State->TreeBuilt = FHierarchicalInstancedStaticMeshDelegates::OnTreeBuilt.AddWeakLambda(this,
        [this](UHierarchicalInstancedStaticMeshComponent* Source, bool) { QueueSource(Source); });
    for (ULevel* Level : GetWorld()->GetLevels()) if (Level && (Level == GetWorld()->PersistentLevel || Level->bIsVisible)) QueueLevel(Level);
    if (!ReconcileSources(OutError) || !Coordinator->RegisterStepClient(*this, nullptr, StepRegistrationId, OutError))
    {
        const FString Failure = OutError;
        DisableSceneCollision(); return Fail(OutError, Failure);
    }
    LastError.Reset(); return true;
}

void UProphecyJoltSceneCollisionComponent::ObserveSource(UPrimitiveComponent& Source)
{
    if (!State || Source.GetWorld() != GetWorld() || Source.GetMobility() != EComponentMobility::Static) return;
    const TWeakObjectPtr<UPrimitiveComponent> Key(&Source);
    if (State->Sources.Contains(Key)) return;
    auto& Entry = State->Sources.Add(Key);
    Entry.LastObjectChannel = Source.GetCollisionObjectType();
    Entry.Path = Source.GetPathName(); Entry.Level = Source.GetTypedOuter<ULevel>();
    Entry.TransformChanged = Source.TransformUpdated.AddWeakLambda(this,
        [this](USceneComponent* Changed, EUpdateTransformFlags, ETeleportType) { QueueSource(Cast<UPrimitiveComponent>(Changed)); });
    Source.OnComponentCollisionSettingsChangedEvent.AddUniqueDynamic(this, &ThisClass::OnSourceCollisionSettings);
    if (Cast<UInstancedStaticMeshComponent>(&Source)) State->InstancedSources.Add(Key);
}

void UProphecyJoltSceneCollisionComponent::QueueSource(UPrimitiveComponent* Source, bool bPhysicsDestroyed)
{
    if (!State || !Source) return;
    check(IsInGameThread());
    const TWeakObjectPtr<UPrimitiveComponent> Key(Source);
    if (!State->Sources.Contains(Key)) ObserveSource(*Source);
    if (auto* Entry = State->Sources.Find(Key))
    {
        Entry->bFullRefresh = true; Entry->bPhysicsDestroyed |= bPhysicsDestroyed;
        State->PendingSources.Add(Key);
    }
}
void UProphecyJoltSceneCollisionComponent::OnPhysicsCreated(UActorComponent* Component)
{
    auto* Source = Cast<UPrimitiveComponent>(Component);
    QueueSource(Source);
    if (State && Source) if (auto* Entry = State->Sources.Find(Source)) Entry->bPhysicsDestroyed = false;
}
void UProphecyJoltSceneCollisionComponent::OnPhysicsDestroyed(UActorComponent* Component) { QueueSource(Cast<UPrimitiveComponent>(Component), true); }
void UProphecyJoltSceneCollisionComponent::OnSourceCollisionSettings(UPrimitiveComponent* Source)
{
    if (!State || !Source) return;
    if (auto* Entry = State->Sources.Find(Source))
    {
        Entry->bCollisionDirty = true;
        State->PendingSources.Add(Source);
    }
}
void UProphecyJoltSceneCollisionComponent::QueueActor(AActor* Actor)
{
    if (State && Actor && Actor->GetWorld() == GetWorld()) State->PendingActors.Add(Actor);
}
void UProphecyJoltSceneCollisionComponent::QueueLevel(ULevel* Level)
{
    if (!State || !Level) return;
    for (AActor* Actor : Level->Actors) QueueActor(Actor);
    // BSP collision components belong directly to the level, not to an actor.
    for (UModelComponent* Model : Level->ModelComponents) QueueSource(Model);
}
void UProphecyJoltSceneCollisionComponent::OnLevelAdded(ULevel* Level, UWorld* World)
{
    if (State && World == GetWorld())
    { State->bAllLevelsRemoved = false; State->RemovedLevels.Remove(Level); QueueLevel(Level); }
}
void UProphecyJoltSceneCollisionComponent::OnLevelRemoved(ULevel* Level, UWorld* World)
{
    if (!State || World != GetWorld()) return;
    if (Level) State->RemovedLevels.Add(Level); else State->bAllLevelsRemoved = true;
    for (auto& Entry : State->Sources)
        if (!Level || Entry.Value.Level.Get() == Level)
        { Entry.Value.bFullRefresh = true; State->PendingSources.Add(Entry.Key); }
}

bool UProphecyJoltSceneCollisionComponent::ReconcileSources(FString& OutError)
{
    if (!State || bReconciling) return Fail(OutError, TEXT("Scene collision reconciliation lost its binding or reentered."));
    TGuardValue<bool> Guard(bReconciling, true);
    // SetCollisionObjectType has no component-settings notification in UE.
    for (auto& Pair : State->Sources)
    {
        if (auto* Source = Pair.Key.Get())
        {
            const auto Channel = Source->GetCollisionObjectType();
            if (Pair.Value.LastObjectChannel != Channel)
            {
                Pair.Value.LastObjectChannel = Channel;
                Pair.Value.bCollisionDirty = true;
                State->PendingSources.Add(Pair.Key);
            }
        }
    }
    // ISM transform edits have no public notification; inspect only retained instance transforms.
    for (const auto& Key : State->InstancedSources)
    {
        auto* Entry = State->Sources.Find(Key);
        auto* ISM = Cast<UInstancedStaticMeshComponent>(Key.Get());
        if (!Entry) continue;
        if (!ISM || !ISM->IsRegistered()) { Entry->bFullRefresh = true; State->PendingSources.Add(Key); continue; }
        if (Entry->bFullRefresh || Entry->bPhysicsDestroyed || ISM->GetCollisionEnabled() == ECollisionEnabled::NoCollision
            || ISM->GetCollisionEnabled() == ECollisionEnabled::QueryOnly) continue;
        if (ISM->GetInstanceCount() != Entry->InstanceTransforms.Num())
        { Entry->bFullRefresh = true; State->PendingSources.Add(Key); continue; }
        for (int32 Index = 0; Index < Entry->InstanceTransforms.Num(); ++Index)
        {
            FTransform Current;
            if (!ISM->GetInstanceTransform(Index, Current, true) || !Current.Equals(Entry->InstanceTransforms[Index], 0.0))
            { Entry->DirtyInstances.Add(Index); State->PendingSources.Add(Key); }
        }
    }
    for (int32 Drain = 0; Drain < 8; ++Drain)
    {
        const auto Actors = State->PendingActors.Array(); State->PendingActors.Reset();
        for (const auto& Actor : Actors)
            if (Actor.IsValid() && !Actor->IsActorBeingDestroyed())
            {
                TInlineComponentArray<UPrimitiveComponent*> Components(Actor.Get());
                for (auto* Source : Components) QueueSource(Source);
            }
        const auto Pending = State->PendingSources.Array(); State->PendingSources.Reset();
        for (const auto& Key : Pending)
        {
            auto* Entry = State->Sources.Find(Key);
            if (!Entry) continue;
            UPrimitiveComponent* Source = Key.Get();
            AActor* SourceActor = Source ? Source->GetOwner() : nullptr;
            const bool bLiveOwner = SourceActor ? IsValid(SourceActor) && !SourceActor->IsActorBeingDestroyed()
                : Source && Source->IsA<UModelComponent>() && Entry->Level.IsValid()
                    && Entry->Level->GetWorld() == GetWorld();
            const bool bGone = !Source || !Source->IsRegistered() || Source->GetWorld() != GetWorld()
                || !bLiveOwner
                || State->bAllLevelsRemoved || State->RemovedLevels.Contains(Entry->Level)
                || Source->GetMobility() != EComponentMobility::Static;
            const bool bNoSimulation = !bGone && (Source->GetCollisionEnabled() == ECollisionEnabled::NoCollision
                || Source->GetCollisionEnabled() == ECollisionEnabled::QueryOnly || Entry->bPhysicsDestroyed);
            if (bGone || bNoSimulation)
            {
                if (!RetireAll(*State, *Entry, OutError)) return Fail(OutError, OutError);
                Entry->InstanceTransforms.Reset(); Entry->DirtyInstances.Reset(); Entry->bFullRefresh = false;
                if (bGone)
                {
                    if (Source)
                    {
                        Source->TransformUpdated.Remove(Entry->TransformChanged);
                        Source->OnComponentCollisionSettingsChangedEvent.RemoveDynamic(this, &ThisClass::OnSourceCollisionSettings);
                    }
                    State->InstancedSources.Remove(Key); State->Sources.Remove(Key);
                }
                continue;
            }
            auto* ISM = Cast<UInstancedStaticMeshComponent>(Source);
            if (Entry->bCollisionDirty && ISM)
            {
                // UE's component setters update the template BodyInstance, which
                // has no actor for ISM/HISM. Propagate its channel policy to each
                // retained instance so UE queries and Jolt use the same settings.
                for (FBodyInstance* Instance : ISM->InstanceBodies)
                {
                    if (!Instance) continue;
                    if (Instance->GetObjectType() != Source->GetCollisionObjectType())
                        Instance->SetObjectType(Source->GetCollisionObjectType());
                    Instance->SetResponseToChannels(Source->GetCollisionResponseToChannels());
                }
            }
            if (Entry->bCollisionDirty && !Entry->bFullRefresh && !Entry->Bodies.IsEmpty())
            {
                TArray<FProphecyJoltCollisionUpdate> Updates;
                for (const auto& Pair : Entry->Bodies)
                {
                    FProphecyJoltStaticBodySnapshot Snapshot;
                    FString Error;
                    if (!ProphecyJolt::StaticBody::CaptureStaticBody(*Source, Pair.Key, Snapshot, Error))
                        return Fail(OutError, SourceError(*Entry, Pair.Key, Error));
                    auto& Update = Updates.AddDefaulted_GetRef();
                    Update.Handle = Pair.Value;
                    Update.ObjectChannel = Snapshot.ObjectType;
                    Update.Responses = Snapshot.CollisionResponses;
                }
                const auto Updated = State->Owner->UpdateBodyCollision(Updates);
                if (!Updated.IsSuccess()) return Fail(OutError, Updated.Message);
            }
            if (Entry->bCollisionDirty && Entry->Bodies.IsEmpty()) Entry->bFullRefresh = true;
            Entry->bCollisionDirty = false;
            TArray<int32> Indices;
            if (Entry->bFullRefresh)
            {
                if (!RetireAll(*State, *Entry, OutError)) return Fail(OutError, OutError);
                const int32 Count = ISM ? ISM->GetInstanceCount() : 1;
                for (int32 Index = 0; Index < Count; ++Index) Indices.Add(ISM ? Index : INDEX_NONE);
                Entry->InstanceTransforms.SetNum(ISM ? Count : 0);
            }
            else Indices = Entry->DirtyInstances.Array();
            for (int32 Index : Indices)
            {
                if (!RetireBody(*State, *Entry, Index, OutError)) return Fail(OutError, OutError);
                if (ISM)
                {
                    FTransform Transform;
                    if (!ISM->GetInstanceTransform(Index, Transform, true) || Transform.ContainsNaN())
                        return Fail(OutError, SourceError(*Entry, Index, TEXT("Instance world transform is unavailable or nonfinite.")));
                    Entry->InstanceTransforms[Index] = Transform;
                    if (Transform.GetScale3D().IsNearlyZero())
                    {
                        const FBodyInstance* Body = ISM->InstanceBodies.IsValidIndex(Index) ? ISM->InstanceBodies[Index] : nullptr;
                        if (Body && Body->IsValidBodyInstance())
                            return Fail(OutError, SourceError(*Entry, Index, TEXT("Zero-scale instance still has native Chaos collision; retirement could hide a live collider.")));
                        continue;
                    }
                }
                else
                {
                    // Static components such as the world's builder brush can advertise collision
                    // without owning a native collider. Keep observing them: physics creation will
                    // queue admission later. A live body still goes through strict shape capture.
                    const FBodyInstance* NativeBody = Source->GetBodyInstance(NAME_None, false);
                    const bool bHasNativeObjects = Source->GetAllPhysicsObjects().ContainsByPredicate(
                        [](const auto& Object) { return Object != nullptr; });
                    if ((!NativeBody || (!NativeBody->IsValidBodyInstance() && !NativeBody->WeldParent))
                        && !bHasNativeObjects) continue;
                }
                FProphecyJoltStaticBodySnapshot Snapshot;
                FProphecyJoltPreparedStaticBody Prepared;
                FString Error;
                if (!ProphecyJolt::StaticBody::CaptureStaticBody(*Source, Index, Snapshot, Error) || !Prepared.Build(Snapshot, Error))
                    return Fail(OutError, SourceError(*Entry, Index, Error));
                FProphecyJoltBodyHandle Handle; TArray<FString> Notes;
                const auto Created = State->Owner->CreateStaticBody(Snapshot, Prepared, Handle, Notes);
                if (!Created.IsSuccess()) return Fail(OutError, SourceError(*Entry, Index, Created.Message));
                Entry->Bodies.Add(Index, Handle); ++State->BodyCount;
            }
            Entry->bFullRefresh = false; Entry->DirtyInstances.Reset();
        }
        if (State->PendingActors.IsEmpty() && State->PendingSources.IsEmpty()) { OutError.Reset(); return true; }
    }
    return Fail(OutError, TEXT("Scene collision kept changing during admission; no native step was issued."));
}

bool UProphecyJoltSceneCollisionComponent::ValidateBinding(FString& OutError) const
{
    if (!IsInGameThread() || !State || State->bStopped || !IsRegistered() || !State->Owner.IsValid() || !State->Coordinator.IsValid()
        || !GetWorld() || GetWorld()->bIsTearingDown)
    { OutError = LastError.IsEmpty() ? TEXT("Scene collision binding is absent, stopped or ending.") : LastError; return false; }
    FProphecyJoltWorldDiagnostics Diagnostics;
    if (!State->Owner->GetDiagnostics(Diagnostics).IsSuccess() || !Diagnostics.bInitialized || Diagnostics.bFaulted
        || Diagnostics.WorldLifetime != State->WorldLifetime || Diagnostics.CompletedSteps != State->ExpectedWorldSteps
        || !State->Coordinator->IsStepClientRegistered(*this, StepRegistrationId))
    { OutError = TEXT("Scene collision native world, step sequence or registration changed externally."); return false; }
    return true;
}
bool UProphecyJoltSceneCollisionComponent::PrepareJoltWorldStep(float, bool, FString& OutError)
{
    return ValidateBinding(OutError) && ReconcileSources(OutError);
}
bool UProphecyJoltSceneCollisionComponent::ConsumeCompletedJoltWorldStep(FString& OutError)
{
    FProphecyJoltWorldDiagnostics Diagnostics;
    if (!State || !State->Owner.IsValid() || !State->Owner->GetDiagnostics(Diagnostics).IsSuccess() || Diagnostics.bFaulted
        || Diagnostics.WorldLifetime != State->WorldLifetime || Diagnostics.CompletedSteps != State->ExpectedWorldSteps + 1)
        return Fail(OutError, TEXT("Scene collision did not observe exactly one completed shared step."));
    State->ExpectedWorldSteps = Diagnostics.CompletedSteps; OutError.Reset(); return true;
}
void UProphecyJoltSceneCollisionComponent::LatchJoltStepError(const FString& Error)
{
    if (State) State->bStopped = true;
    LastError = Error;
}
bool UProphecyJoltSceneCollisionComponent::GetBodyHandle(const UPrimitiveComponent& Source, int32 InstanceIndex, FProphecyJoltBodyHandle& OutHandle) const
{
    OutHandle = {};
    if (!IsInGameThread() || !State || !State->Owner.IsValid()) return false;
    const auto* Entry = State->Sources.Find(const_cast<UPrimitiveComponent*>(&Source));
    const auto* Handle = Entry ? Entry->Bodies.Find(InstanceIndex) : nullptr;
    if (!Handle || !State->Owner->OwnsBody(*Handle)) return false;
    OutHandle = *Handle; return true;
}

void UProphecyJoltSceneCollisionComponent::DisableSceneCollision()
{
    if (!IsInGameThread()) return;
    if (AdmissionCoordinator.IsValid() && PendingAdmissionId.IsValid()) AdmissionCoordinator->CancelClientAdmission(*this, PendingAdmissionId);
    PendingAdmissionId.Invalidate(); AdmissionCoordinator.Reset();
    auto Removed = MoveTemp(State);
    if (!Removed) return;
    if (Removed->Coordinator.IsValid() && StepRegistrationId.IsValid()) Removed->Coordinator->UnregisterStepClient(*this, StepRegistrationId);
    StepRegistrationId.Invalidate();
    UActorComponent::GlobalCreatePhysicsDelegate.Remove(Removed->PhysicsCreated);
    UActorComponent::GlobalDestroyPhysicsDelegate.Remove(Removed->PhysicsDestroyed);
    if (GetWorld()) GetWorld()->RemoveOnActorSpawnedHandler(Removed->ActorSpawned);
    FWorldDelegates::LevelAddedToWorld.Remove(Removed->LevelAdded);
    FWorldDelegates::PreLevelRemovedFromWorld.Remove(Removed->LevelRemoved);
    FInstancedStaticMeshDelegates::OnInstanceIndexUpdated.Remove(Removed->InstanceChanged);
    FHierarchicalInstancedStaticMeshDelegates::OnTreeBuilt.Remove(Removed->TreeBuilt);
    for (auto& Pair : Removed->Sources)
    {
        if (auto* Source = Pair.Key.Get())
        {
            Source->TransformUpdated.Remove(Pair.Value.TransformChanged);
            Source->OnComponentCollisionSettingsChangedEvent.RemoveDynamic(this, &ThisClass::OnSourceCollisionSettings);
        }
        if (Removed->Owner.IsValid()) for (const auto& Body : Pair.Value.Bodies)
            if (Removed->Owner->OwnsBody(Body.Value))
            {
                const auto Result = Removed->Owner->DestroyBody(Body.Value);
                if (!Result.IsSuccess()) UE_LOG(LogProphecyJoltSceneCollision, Error, TEXT("Scene cleanup failed for %s: %s"), *Pair.Value.Path, *Result.Message);
            }
    }
}
void UProphecyJoltSceneCollisionComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    DisableSceneCollision(); Super::EndPlay(EndPlayReason);
}
void UProphecyJoltSceneCollisionComponent::OnUnregister()
{
    DisableSceneCollision(); Super::OnUnregister();
}
