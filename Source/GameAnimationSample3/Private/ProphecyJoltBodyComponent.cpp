#include "ProphecyJoltBodyComponent.h"

#include "ProphecyJoltBody.h"
#include "ProphecyJoltCharacterWorldSubsystem.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Chaos/KinematicTargets.h"
#include "Components/PrimitiveComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Misc/ScopeExit.h"
#include "Physics/Experimental/PhysScene_Chaos.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/BodySetup.h"
#include "PhysicsEngine/PhysicsSettings.h"
#include "PhysicsProxy/SingleParticlePhysicsProxy.h"

DEFINE_LOG_CATEGORY_STATIC(LogProphecyJoltBody, Log, All);

struct FProphecyJoltBodyComponentState
{
    FProphecyJoltBodySnapshot Snapshot;
    TWeakObjectPtr<AActor> Actor;
    TWeakObjectPtr<UBodySetup> BodySetup;
    TWeakObjectPtr<UStaticMesh> StaticMesh;
    TWeakObjectPtr<UProphecyJoltWorldSubsystem> WorldOwner;
    TWeakObjectPtr<UProphecyJoltCharacterWorldSubsystem> Coordinator;
    FProphecyJoltBodyHandle Handle;
    FPhysicsActorHandle QueryActor = nullptr;
    FBodyInstance* QueryInstance = nullptr; // Identity only; reacquired before use.
    ECollisionEnabled::Type OriginalCollisionEnabled = ECollisionEnabled::NoCollision;
    ECollisionChannel OriginalObjectType = ECC_WorldDynamic;
    FCollisionResponseContainer OriginalResponses;
    FVector OriginalComponentVelocity = FVector::ZeroVector;
    uint64 ExpectedWorldSteps = 0;
    uint64 Revision = 0;
    bool bActive = false;
    bool bStopped = false;
    bool bReceiverChanged = false;
    bool bRestoreOriginalSimulation = false;
    bool bAttachedCollider = false;
    TWeakObjectPtr<USceneComponent> FollowParent;
    FName FollowSocket;
    FTransform FollowRelative;
};

void FProphecyJoltBodyComponentStateDeleter::operator()(FProphecyJoltBodyComponentState* InState) const { delete InState; }

namespace
{
bool SameBody(const FProphecyJoltBodyHandle& A, const FProphecyJoltBodyHandle& B)
{
    return A.WorldLifetime == B.WorldLifetime && A.Slot == B.Slot && A.Generation == B.Generation;
}

bool SourceIsIntact(const FProphecyJoltBodyComponentState& Binding)
{
    UPrimitiveComponent* Source = Binding.Snapshot.SourceComponent.Get();
    AActor* Actor = Binding.Actor.Get();
    if (!Source || !Actor || Actor->IsActorBeingDestroyed() || !Source->IsRegistered()
        || Source->GetOwner() != Actor || Actor->GetRootComponent() != Source
        || (Source->GetAttachParent() && (!Binding.bAttachedCollider || Source->GetAttachParent() != Binding.FollowParent.Get()))
        || Source->GetWorld() != Binding.Snapshot.SourceWorld.Get() || !Source->IsPhysicsStateCreated()) return false;
    FBodyInstance* Instance = Source->GetBodyInstance(NAME_None, false);
    if (!Instance || Instance->WeldParent || !Instance->IsValidBodyInstance()
        || Instance->GetBodySetup() != Binding.BodySetup.Get()) return false;
    if (const auto* Static = Cast<UStaticMeshComponent>(Source))
        if (Static->GetStaticMesh() != Binding.StaticMesh.Get()) return false;
    return true;
}

bool CanEnableSource(const UProphecyJoltBodyComponent& Component, UPrimitiveComponent& Source, FString& Error)
{
    if (!IsValid(&Component) || !Component.IsRegistered() || !IsValid(Component.GetOwner())
        || Component.GetOwner()->IsActorBeingDestroyed() || !IsValid(&Source) || !Source.IsRegistered()
        || Source.GetOwner() != Component.GetOwner() || Source.GetWorld() != Component.GetWorld()
        || Component.GetOwner()->GetRootComponent() != &Source || Source.GetAttachParent()
        || Source.Mobility != EComponentMobility::Movable)
    {
        Error = TEXT("A standalone Jolt body requires this actor's registered, detached, movable primitive root.");
        return false;
    }
    return true;
}
}

UProphecyJoltBodyComponent::UProphecyJoltBodyComponent()
{
    PrimaryComponentTick.bCanEverTick = false;
    PrimaryComponentTick.bStartWithTickEnabled = false;
}

UProphecyJoltBodyComponent::~UProphecyJoltBodyComponent() = default;

bool UProphecyJoltBodyComponent::Fail(FString& OutError, const FString& Message)
{
    LastError = Message;
    OutError = Message;
    return false;
}

bool UProphecyJoltBodyComponent::EnableBody(UPrimitiveComponent& Source, FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread()) return Fail(OutError, TEXT("Jolt body admission requires the game thread."));
    if (bEnableInProgress || bDisableInProgress || bPublishing || DeferredRestore)
        return Fail(OutError, TEXT("Jolt body admission cannot reenter its handoff or receiver restoration."));
    if (IsSteppingStopped()) { OutError = LastError; return false; }
    if (State) return State->Snapshot.SourceComponent.Get() == &Source
        ? true : Fail(OutError, TEXT("Disable the existing standalone binding before selecting another component."));
    if (IsEnablePending()) return PendingSource.Get() == &Source
        ? true : Fail(OutError, TEXT("A different standalone source already awaits admission."));
    if (!CanEnableSource(*this, Source, OutError)) return Fail(OutError, OutError);
    UProphecyJoltCharacterWorldSubsystem* Coordinator = GetWorld()
        ? GetWorld()->GetSubsystem<UProphecyJoltCharacterWorldSubsystem>() : nullptr;
    if (!Coordinator) return Fail(OutError, TEXT("The shared Jolt coordinator is unavailable."));
    bEnableCancelled = false;
    bool bDeferred = false;
    FGuid AdmissionId;
    if (!Coordinator->RequestClientAdmission(*this,
        FProphecyJoltClientAdmissionCallback::CreateUObject(this, &ThisClass::CompleteDeferredEnable),
        FProphecyJoltClientAdmissionCallback::CreateUObject(this, &ThisClass::CancelDeferredEnable),
        bDeferred, AdmissionId, OutError)) return Fail(OutError, OutError);
    if (bDeferred)
    {
        PendingSource = &Source;
        PendingAdmissionId = AdmissionId;
        AdmissionCoordinator = Coordinator;
        LastError.Reset();
        return true;
    }
    return EnableBodyNow(Source, OutError);
}

void UProphecyJoltBodyComponent::CompleteDeferredEnable(const FGuid& AdmissionId)
{
    if (PendingAdmissionId != AdmissionId || !AdmissionId.IsValid()) return;
    const TWeakObjectPtr<UPrimitiveComponent> Source = PendingSource;
    PendingAdmissionId.Invalidate();
    PendingSource.Reset();
    AdmissionCoordinator.Reset();
    FString Error;
    const bool bSucceeded = Source.IsValid() ? EnableBodyNow(*Source, Error)
        : Fail(Error, TEXT("The queued standalone source was destroyed before admission."));
    if (bEnableCancelled || !IsValid(this) || !IsRegistered() || !IsValid(GetOwner()) || GetOwner()->IsActorBeingDestroyed())
    { OnDeferredEnableCompleted.Clear(); return; }
    FProphecyJoltBodyEnableCompleted Completion = MoveTemp(OnDeferredEnableCompleted);
    OnDeferredEnableCompleted.Clear();
    if (!bSucceeded) UE_LOG(LogProphecyJoltBody, Error, TEXT("Deferred body admission failed: %s"), *Error);
    Completion.Broadcast(bSucceeded, Error);
}

void UProphecyJoltBodyComponent::CancelDeferredEnable(const FGuid& AdmissionId)
{
    if (PendingAdmissionId == AdmissionId && AdmissionId.IsValid()) DisableBody();
}

bool UProphecyJoltBodyComponent::EnableBodyNow(UPrimitiveComponent& Source, FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread() || bEnableInProgress || bDisableInProgress || bPublishing || State || DeferredRestore)
        return Fail(OutError, TEXT("Immediate body admission requires an idle game-thread handoff."));
    TGuardValue<bool> EnableGuard(bEnableInProgress, true);
    ON_SCOPE_EXIT { if (DeferredRestore) RestoreReceiver(MoveTemp(DeferredRestore)); };
    bEnableCancelled = false;
    if (!CanEnableSource(*this, Source, OutError)) return Fail(OutError, OutError);
    UProphecyJoltWorldSubsystem* Owner = GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    UProphecyJoltCharacterWorldSubsystem* Coordinator = GetWorld()->GetSubsystem<UProphecyJoltCharacterWorldSubsystem>();
    FProphecyJoltWorldDiagnostics Diagnostics;
    if (!Owner || !Coordinator || !Coordinator->CanRegisterStepClient(*this, OutError)
        || !Owner->GetDiagnostics(Diagnostics).IsSuccess() || !Diagnostics.bInitialized || Diagnostics.bFaulted)
        return Fail(OutError, OutError.IsEmpty() ? TEXT("Initialize a healthy shared Jolt world before enabling a body.") : OutError);

    FProphecyJoltBodySnapshot Snapshot;
    FProphecyJoltPreparedBody Prepared;
    if (!ProphecyJolt::Body::CaptureLiveBody(Source, Snapshot, OutError) || !Prepared.Build(Snapshot, OutError))
        return Fail(OutError, OutError);
    auto Pending = MakeUnique<FProphecyJoltBodyComponentState>();
    Pending->Snapshot = MoveTemp(Snapshot);
    Pending->Actor = GetOwner();
    Pending->BodySetup = Source.GetBodyInstance(NAME_None, false)->GetBodySetup();
    if (const auto* Static = Cast<UStaticMeshComponent>(&Source)) Pending->StaticMesh = Static->GetStaticMesh();
    Pending->WorldOwner = Owner;
    Pending->Coordinator = Coordinator;
    Pending->ExpectedWorldSteps = Diagnostics.CompletedSteps;
    Pending->OriginalCollisionEnabled = Source.GetCollisionEnabled();
    Pending->OriginalObjectType = Source.GetCollisionObjectType();
    Pending->OriginalResponses = Source.GetCollisionResponseToChannels();
    Pending->OriginalComponentVelocity = Source.ComponentVelocity;
    TArray<FString> Coverage;
    const FProphecyJoltWorldStatus Created = Owner->CreateBody(Pending->Snapshot, Prepared, Pending->Handle, Coverage);
    if (!Created.IsSuccess()) return Fail(OutError, Created.Message);
    Pending->bActive = true;
    State.Reset(Pending.Release());
    FProphecyJoltBodyComponentState* const Committing = State.Get();
    const FProphecyJoltBodyHandle Handle = State->Handle;
    const auto CommitIsValid = [&]()
    {
        return !bEnableCancelled && IsValid(this) && IsRegistered() && State.Get() == Committing
            && SameBody(State->Handle, Handle) && SourceIsIntact(*State) && Owner->OwnsBody(Handle);
    };
    const auto Abort = [&]()
    {
        if (State.Get() == Committing && SameBody(State->Handle, Handle)) DisableBodyInternal(true, false);
        if (OutError.IsEmpty()) OutError = TEXT("The standalone body binding changed during ownership handoff.");
        return Fail(OutError, OutError);
    };
    // No solver can advance during this synchronous commit. The complete Jolt body exists before
    // changing the original receiver, and rollback always destroys it before restoring Chaos.
    State->bReceiverChanged = true;
    Source.SetSimulatePhysics(false);
    if (!CommitIsValid()) return Abort();
    Source.SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    if (!CommitIsValid()) return Abort();
    State->QueryInstance = Source.GetBodyInstance(NAME_None, false);
    State->QueryActor = State->QueryInstance ? State->QueryInstance->GetPhysicsActor() : nullptr;
    if (!PublishCompletedBody(OutError) || !CommitIsValid()
        || !Coordinator->RegisterStepClient(*this, nullptr, StepRegistrationId, OutError)) return Abort();
    LastError.Reset();
    return true;
}

bool UProphecyJoltBodyComponent::ValidateBinding(FString& OutError) const
{
    OutError.Reset();
    if (!IsInGameThread() || !IsValid(this) || !IsRegistered() || !State || !State->bActive || State->bStopped
        || !SourceIsIntact(*State) || !State->WorldOwner.IsValid() || !State->WorldOwner->OwnsBody(State->Handle))
    { OutError = TEXT("The standalone Jolt body no longer has its live, unchanged source binding."); return false; }
    UPrimitiveComponent* Source = State->Snapshot.SourceComponent.Get();
    FBodyInstance* Instance = Source->GetBodyInstance(NAME_None, false);
    FPhysScene* Scene = GetWorld() ? GetWorld()->GetPhysicsScene() : nullptr;
    const FPhysicsActorHandle Actor = Instance ? Instance->GetPhysicsActor() : nullptr;
    if (!Scene || UPhysicsSettings::Get()->bTickPhysicsAsync || Source->IsAnySimulatingPhysics()
        || Source->GetCollisionEnabled() != ECollisionEnabled::QueryOnly
        || !Source->GetComponentScale().Equals(State->Snapshot.ComponentToWorld.GetScale3D(), 1.0e-6)
        || Instance != State->QueryInstance || !Actor || Actor != State->QueryActor
        || Actor->GetMarkedDeleted() || !Actor->GetSyncTimestamp() || !FPhysicsInterface::IsKinematic(Actor)
        || FPhysicsInterface::GetCurrentScene(Actor) != Scene
        || (StepRegistrationId.IsValid() && (!State->Coordinator.IsValid()
            || !State->Coordinator->IsStepClientRegistered(*this, StepRegistrationId))))
    { OutError = TEXT("Standalone query identity, collision policy, scale or shared registration changed externally."); return false; }
    FProphecyJoltWorldDiagnostics Diagnostics;
    if (!State->WorldOwner->GetDiagnostics(Diagnostics).IsSuccess() || Diagnostics.bFaulted
        || Diagnostics.WorldLifetime != State->Handle.WorldLifetime || Diagnostics.CompletedSteps != State->ExpectedWorldSteps)
    { OutError = TEXT("The standalone native world changed or contains an unconsumed step."); return false; }
    return true;
}

bool UProphecyJoltBodyComponent::PublishCompletedBody(FString& OutError)
{
    if (bPublishing) return Fail(OutError, TEXT("Standalone body publication cannot reenter itself."));
    if (!ValidateBinding(OutError)) return false;
    if (State->bAttachedCollider)
    {
        // The hand owns both native collision and socket presentation.
        ++State->Revision;
        return true;
    }
    TGuardValue<bool> PublishGuard(bPublishing, true);
    ON_SCOPE_EXIT { if (!bEnableInProgress && DeferredRestore) RestoreReceiver(MoveTemp(DeferredRestore)); };
    FProphecyJoltBodyComponentState* const Publishing = State.Get();
    const FProphecyJoltBodyHandle Handle = State->Handle;
    const FGuid Registration = StepRegistrationId;
    const uint64 Revision = State->Revision;
    FProphecyJoltBodyState Completed;
    const FProphecyJoltWorldStatus Read = State->WorldOwner->ReadBody(Handle, Completed);
    if (!Read.IsSuccess()) return Fail(OutError, Read.Message);
    FTransform ComponentWorld = State->Snapshot.BodyOriginToComponent.Inverse()
        * FTransform(Completed.Rotation, Completed.PositionCm);
    ComponentWorld.SetScale3D(State->Snapshot.ComponentToWorld.GetScale3D());
    if (ComponentWorld.ContainsNaN() || !ComponentWorld.GetRotation().IsNormalized())
        return Fail(OutError, TEXT("The completed standalone component transform is invalid."));
    UPrimitiveComponent* Source = State->Snapshot.SourceComponent.Get();
    Source->SetWorldTransform(ComponentWorld, false, nullptr, ETeleportType::TeleportPhysics);
    // SetWorldTransform may dispatch transform/overlap callbacks which remove or replace this body.
    // Never keep a State reference or dereference the old native actor across that boundary.
    if (State.Get() != Publishing || !State || !SameBody(State->Handle, Handle)
        || StepRegistrationId != Registration || State->Revision != Revision || !ValidateBinding(OutError))
    { if (OutError.IsEmpty()) OutError = TEXT("The standalone body was removed during transform publication."); return false; }
    Source = State->Snapshot.SourceComponent.Get();
    const FTransform Actual = Source->GetComponentTransform();
    // UE's InternalSetWorldLocationAndRotation intentionally retains per-axis changes
    // below KINDA_SMALL_NUMBER cm/degrees, even for TeleportPhysics. This detached
    // root's relative rotator is the engine's comparison frame. Preserve rejection
    // of callback mutations beyond those supported update tolerances.
    const bool bLocationMatches = Actual.GetLocation().Equals(ComponentWorld.GetLocation(), UE_KINDA_SMALL_NUMBER);
    const bool bRotationMatches = Actual.GetRotation().Equals(ComponentWorld.GetRotation(), 1.0e-6)
        || Source->GetRelativeRotation().Equals(ComponentWorld.GetRotation().GetNormalized().Rotator(), UE_KINDA_SMALL_NUMBER);
    if (!bLocationMatches || !bRotationMatches || !Actual.GetScale3D().Equals(ComponentWorld.GetScale3D(), 1.0e-6))
    {
        return Fail(OutError, FString::Printf(TEXT("The completed standalone component transform differs beyond UE update tolerances. Position delta=%.12g cm, rotation delta=%.12g rad, scale delta=%.12g; source=%s parent=%s."),
            FVector::Distance(Actual.GetLocation(), ComponentWorld.GetLocation()),
            Actual.GetRotation().GetNormalized().AngularDistance(ComponentWorld.GetRotation().GetNormalized()),
            (Actual.GetScale3D() - ComponentWorld.GetScale3D()).GetAbsMax(),
            *Source->GetPathName(), *GetPathNameSafe(Source->GetAttachParent())));
    }
    auto& External = State->QueryActor->GetGameThreadAPI();
    // Match UE's synchronous teleport path and the existing character query bridge. Clear targets
    // so Chaos cannot move the query proxy back later; update both immediate and pending scene trees.
    External.SetKinematicTarget(Chaos::FKinematicTarget());
    External.SetV(Chaos::FVec3(0));
    External.SetW(Chaos::FVec3(0));
    External.SetX(Completed.PositionCm, false);
    External.SetR(Completed.Rotation);
    External.UpdateShapeBounds();
    FPhysicsActorHandle Actors[] = { State->QueryActor };
    GetWorld()->GetPhysicsScene()->UpdateActorsInAccelerationStructure(MakeArrayView(Actors));
    Source->ComponentVelocity = Completed.CenterOfMassVelocityCmPerSecond
        + FVector::CrossProduct(Completed.AngularVelocityRadiansPerSecond,
            ComponentWorld.GetLocation() - Completed.CenterOfMassPositionCm);
    ++State->Revision;
    return true;
}

bool UProphecyJoltBodyComponent::SynchronizeCollision(FString& OutError)
{
    if (!State || !State->bActive || !State->WorldOwner.IsValid())
        return Fail(OutError, TEXT("Collision synchronization requires a live Jolt body binding."));
    auto* Source = State->Snapshot.SourceComponent.Get();
    if (!Source || Source->IsAnySimulatingPhysics())
        return Fail(OutError, TEXT("Collision synchronization lost its source or Chaos simulation was enabled externally."));
    // Presets can re-enable the UE physics filter. Retain Jolt simulation ownership
    // and rebuild only the UE query proxy when that preset recreated its actor.
    if (Source->GetCollisionEnabled() == ECollisionEnabled::QueryAndPhysics)
    {
        const auto* Binding = State.Get();
        Source->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
        if (State.Get() != Binding || !State || !SourceIsIntact(*State)) return false;
        State->QueryInstance = Source->GetBodyInstance(NAME_None, false);
        State->QueryActor = State->QueryInstance->GetPhysicsActor();
    }
    if (!ValidateBinding(OutError)) return false;
    const auto Channel = Source->GetCollisionObjectType();
    const auto Responses = Source->GetCollisionResponseToChannels();
    if (Channel == State->OriginalObjectType && Responses == State->OriginalResponses) return true;
    FProphecyJoltCollisionUpdate Update;
    Update.Handle = State->Handle;
    Update.ObjectChannel = Channel;
    Update.Responses = Responses;
    const auto Result = State->WorldOwner->UpdateBodyCollision({ Update });
    if (!Result.IsSuccess()) return Fail(OutError, Result.Message);
    State->OriginalObjectType = Channel;
    State->OriginalResponses = Responses;
    return true;
}

bool UProphecyJoltBodyComponent::PrepareJoltWorldStep(float DeltaSeconds, bool bPublishMissingTargets, FString& OutError)
{
    if (!FMath::IsFinite(DeltaSeconds) || DeltaSeconds <= 0.0f)
        return Fail(OutError, TEXT("Standalone Jolt step duration must be finite and positive."));
    if (!SynchronizeCollision(OutError)) return false;
    if (State->bAttachedCollider)
    {
        auto* Parent = State->FollowParent.Get();
        if (!Parent || !Parent->IsRegistered() || !Parent->DoesSocketExist(State->FollowSocket))
            return Fail(OutError, TEXT("The attached collider lost its hand socket."));
        if (!State->WorldOwner->IsBodyShapeWelded(State->Handle))
            return Fail(OutError,TEXT("The attached collider lost its simulated hand body."));
    }
    return true;
}

bool UProphecyJoltBodyComponent::ConsumeCompletedJoltWorldStep(FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread() || !State || State->bStopped || !State->WorldOwner.IsValid())
        return Fail(OutError, TEXT("Completed standalone publication requires live owned state."));
    FProphecyJoltWorldDiagnostics Diagnostics;
    if (!State->WorldOwner->GetDiagnostics(Diagnostics).IsSuccess()
        || State->ExpectedWorldSteps == MAX_uint64 || Diagnostics.CompletedSteps != State->ExpectedWorldSteps + 1)
        return Fail(OutError, TEXT("Every shared world step must be consumed exactly once by each standalone body."));
    State->ExpectedWorldSteps = Diagnostics.CompletedSteps;
    if (!PublishCompletedBody(OutError)) return false;
    LastError.Reset();
    return true;
}

void UProphecyJoltBodyComponent::LatchJoltStepError(const FString& Error)
{
    check(IsInGameThread());
    if (!State) return;
    if (!State->bStopped) LastError = Error;
    State->bStopped = true; // Ownership stays native until an explicit disable; no Chaos fallback.
}

void UProphecyJoltBodyComponent::DisableBody() { DisableBodyInternal(false, true); }

void UProphecyJoltBodyComponent::DisableBodyInternal(bool bRestoreOriginalSimulation, bool bCancelEnable)
{
    if (!IsInGameThread()) return;
    if (bCancelEnable)
    {
        bEnableCancelled |= bEnableInProgress || IsEnablePending();
        const FGuid Admission = PendingAdmissionId;
        PendingAdmissionId.Invalidate();
        PendingSource.Reset();
        if (auto* Coordinator = AdmissionCoordinator.Get()) Coordinator->CancelClientAdmission(*this, Admission);
        AdmissionCoordinator.Reset();
        OnDeferredEnableCompleted.Clear();
        LastError.Reset();
    }
    if (bDisableInProgress) return;
    TGuardValue<bool> DisableGuard(bDisableInProgress, true);
    auto Removed = MoveTemp(State);
    const FGuid Registration = StepRegistrationId;
    StepRegistrationId.Invalidate();
    if (!Removed) return;
    if (auto* Coordinator = Removed->Coordinator.Get()) Coordinator->UnregisterStepClient(*this, Registration);
    if (auto* Owner = Removed->WorldOwner.Get(); Owner && Owner->OwnsBody(Removed->Handle))
    {
        const FProphecyJoltWorldStatus Destroyed = Owner->DestroyBody(Removed->Handle);
        if (!Destroyed.IsSuccess())
        {
            // Retain the exact handle for a later explicit retry; never restore a second simulator.
            Removed->bStopped = true;
            State = MoveTemp(Removed);
            LastError = Destroyed.Message;
            UE_LOG(LogProphecyJoltBody, Error, TEXT("Native standalone cleanup failed: %s"), *LastError);
            return;
        }
    }
    Removed->bActive = false;
    Removed->bRestoreOriginalSimulation = bRestoreOriginalSimulation && !bEnableCancelled;
    if (bPublishing || bEnableInProgress)
    {
        check(!DeferredRestore);
        DeferredRestore = MoveTemp(Removed);
        return;
    }
    RestoreReceiver(MoveTemp(Removed));
}

void UProphecyJoltBodyComponent::RestoreReceiver(
    TUniquePtr<FProphecyJoltBodyComponentState, FProphecyJoltBodyComponentStateDeleter> Removed)
{
    TGuardValue<bool> DisableGuard(bDisableInProgress, true);
    if (!Removed->bReceiverChanged || !SourceIsIntact(*Removed)) return;
    const auto CanRestore = [&]() { return SourceIsIntact(*Removed) && !State; };
    UPrimitiveComponent* Source = Removed->Snapshot.SourceComponent.Get();
    Source->SetSimulatePhysics(false);
    if (!CanRestore()) return;
    Source->SetCollisionEnabled(Removed->OriginalCollisionEnabled);
    if (!CanRestore()) return;
    if (!Removed->bRestoreOriginalSimulation) return;
    Source->SetWorldTransform(Removed->Snapshot.ComponentToWorld, false, nullptr, ETeleportType::TeleportPhysics);
    if (!CanRestore() || bEnableCancelled) return;
    Source->SetSimulatePhysics(Removed->Snapshot.Body.bSimulating);
    if (!CanRestore()) return;
    if (bEnableCancelled)
    {
        // An explicit disable from a dynamic-state callback cancels rollback as well.
        Source->SetSimulatePhysics(false);
        return;
    }
    FBodyInstance* Instance = Source->GetBodyInstance(NAME_None, false);
    Instance->SetLinearVelocity(Removed->Snapshot.Body.CenterOfMassVelocityCmPerSecond, false, false);
    Instance->SetAngularVelocityInRadians(Removed->Snapshot.Body.AngularVelocityRadiansPerSecond, false, false);
    if (Removed->Snapshot.Body.bAwake) Instance->WakeInstance();
    else Instance->PutInstanceToSleep();
    if (!CanRestore()) return;
    if (bEnableCancelled) { Source->SetSimulatePhysics(false); return; }
    Source->ComponentVelocity = Removed->OriginalComponentVelocity;
}

bool UProphecyJoltBodyComponent::IsJoltBody() const { return IsInGameThread() && State && State->bActive; }
bool UProphecyJoltBodyComponent::IsAttachedCollider() const { return IsJoltBody() && State->bAttachedCollider; }
bool UProphecyJoltBodyComponent::FollowWelded(const FProphecyJoltBodyHandle& Hand, USceneComponent& Parent, FName Socket,
    const FTransform& Relative, FString& OutError)
{
    if (!ValidateBinding(OutError)) return false;
    if (!Parent.IsRegistered() || Parent.GetWorld() != GetWorld() || !Parent.DoesSocketExist(Socket)
        || Relative.ContainsNaN() || !Relative.GetRotation().IsNormalized())
        return Fail(OutError, TEXT("Invalid attached collider parent, socket or relative transform."));
    FProphecyJoltBodyState HandState;
    const auto Read=State->WorldOwner->ReadBody(Hand,HandState);
    if(!Read.IsSuccess()) return Fail(OutError,Read.Message);
    FTransform ComponentWorld=Relative * Parent.GetSocketTransform(Socket);
    ComponentWorld.SetScale3D(FVector::OneVector);
    const FTransform BodyWorld=State->Snapshot.BodyOriginToComponent * ComponentWorld;
    FTransform Local=BodyWorld.GetRelativeTransform(FTransform(HandState.Rotation,HandState.PositionCm));
    Local.SetScale3D(FVector::OneVector); Local.NormalizeRotation();
    const auto Result = State->WorldOwner->WeldBodyShape(Hand,State->Handle,Local);
    if (!Result.IsSuccess()) return Fail(OutError, Result.Message);
    State->bAttachedCollider = true;
    State->FollowParent = &Parent;
    State->FollowSocket = Socket;
    State->FollowRelative = Relative;
    return true;
}
bool UProphecyJoltBodyComponent::IsSteppingStopped() const { return IsInGameThread() && State && State->bStopped; }
uint64 UProphecyJoltBodyComponent::GetRevision() const { return IsInGameThread() && State ? State->Revision : 0; }
UPrimitiveComponent* UProphecyJoltBodyComponent::GetSourceComponent() const
{ return IsInGameThread() && State ? State->Snapshot.SourceComponent.Get() : nullptr; }

bool UProphecyJoltBodyComponent::GetBodyHandle(FProphecyJoltBodyHandle& OutHandle) const
{
    OutHandle = {};
    if (!IsJoltBody() || !State->WorldOwner.IsValid() || !State->WorldOwner->OwnsBody(State->Handle)) return false;
    OutHandle = State->Handle;
    return true;
}

bool UProphecyJoltBodyComponent::GetBodyState(FProphecyJoltBodyState& OutState) const
{
    OutState = {};
    FProphecyJoltBodyHandle Handle;
    return GetBodyHandle(Handle) && State->WorldOwner->ReadBody(Handle, OutState).IsSuccess();
}

bool UProphecyJoltBodyComponent::GetBodyOriginToComponent(FTransform& OutTransform) const
{
    OutTransform = FTransform::Identity;
    FProphecyJoltBodyHandle Handle;
    if (!GetBodyHandle(Handle)) return false;
    OutTransform = State->Snapshot.BodyOriginToComponent;
    return true;
}

UProphecyJoltWorldSubsystem* UProphecyJoltBodyComponent::GetWorldOwner() const
{
    FProphecyJoltBodyHandle Handle;
    return GetBodyHandle(Handle) ? State->WorldOwner.Get() : nullptr;
}

bool UProphecyJoltBodyComponent::GetPointVelocity(const FVector& WorldPointCm, FVector& OutVelocityCmPerSecond) const
{
    OutVelocityCmPerSecond = FVector::ZeroVector;
    FProphecyJoltBodyState Completed;
    if (WorldPointCm.ContainsNaN() || !GetBodyState(Completed)) return false;
    OutVelocityCmPerSecond = Completed.CenterOfMassVelocityCmPerSecond
        + FVector::CrossProduct(Completed.AngularVelocityRadiansPerSecond, WorldPointCm - Completed.CenterOfMassPositionCm);
    return !OutVelocityCmPerSecond.ContainsNaN();
}

bool UProphecyJoltBodyComponent::SetBodyVelocity(const FVector& CenterOfMassVelocityCmPerSecond,
    const FVector& AngularVelocityRadiansPerSecond, bool bWake, FString& OutError)
{
    if (!ValidateBinding(OutError)) return false;
    const FProphecyJoltWorldStatus Result = State->WorldOwner->SetBodyVelocity(State->Handle,
        CenterOfMassVelocityCmPerSecond, AngularVelocityRadiansPerSecond, bWake);
    return Result.IsSuccess() ? true : Fail(OutError, Result.Message);
}

bool UProphecyJoltBodyComponent::AddPointImpulse(const FVector& ImpulseKgCmPerSecond,
    const FVector& WorldPointCm, FString& OutError)
{
    if (!ValidateBinding(OutError)) return false;
    const FProphecyJoltWorldStatus Result = State->WorldOwner->AddPointImpulse(State->Handle, ImpulseKgCmPerSecond, WorldPointCm);
    return Result.IsSuccess() ? true : Fail(OutError, Result.Message);
}

bool UProphecyJoltBodyComponent::MakeHitResult(const FProphecyJoltRayHit& Hit, FHitResult& OutHit) const
{
    OutHit = FHitResult();
    FProphecyJoltBodyHandle Handle;
    if (!GetBodyHandle(Handle) || !SameBody(Hit.Handle, Handle) || !SourceIsIntact(*State)
        || Hit.PositionCm.ContainsNaN() || Hit.Normal.ContainsNaN() || !FMath::IsFinite(Hit.Fraction)
        || Hit.Fraction < 0.0f || Hit.Fraction > 1.0f) return false;
    OutHit = FHitResult(State->Actor.Get(), State->Snapshot.SourceComponent.Get(), Hit.PositionCm, Hit.Normal);
    OutHit.bBlockingHit = true;
    OutHit.Time = Hit.Fraction;
    OutHit.Location = OutHit.ImpactPoint = Hit.PositionCm;
    OutHit.Normal = OutHit.ImpactNormal = Hit.Normal;
    OutHit.FaceIndex = INDEX_NONE;
    OutHit.Item = INDEX_NONE;
    return true;
}

bool UProphecyJoltBodyComponent::StepAndPublish(float DeltaSeconds, FString& OutError)
{
    if (!ValidateBinding(OutError) || !State->Coordinator.IsValid()) return false;
    return State->Coordinator->StepExplicit(*this, StepRegistrationId, DeltaSeconds, OutError);
}

void UProphecyJoltBodyComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    DisableBody();
    Super::EndPlay(EndPlayReason);
}

void UProphecyJoltBodyComponent::OnUnregister()
{
    DisableBody();
    Super::OnUnregister();
}
