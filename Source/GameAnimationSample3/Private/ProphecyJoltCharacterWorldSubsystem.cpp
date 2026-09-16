#include "ProphecyJoltCharacterWorldSubsystem.h"
#include "ProphecyJoltConstraintRuntime.h"

#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltSceneCollisionComponent.h"
#include "ProphecyJoltCharacterProfiling.h"
#include "ProphecyJoltStepClient.h"
#include "ProphecyJoltStepTiming.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Components/ActorComponent.h"
#include "Engine/Level.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "PhysicsEngine/PhysicsSettings.h"
#include "Subsystems/SubsystemCollection.h"

DEFINE_LOG_CATEGORY_STATIC(LogProphecyJoltCharacterWorld, Log, All);

void FProphecyJoltCharacterWorldTickFunction::ExecuteTick(float DeltaTime, ELevelTick TickType,
    ENamedThreads::Type CurrentThread, const FGraphEventRef& MyCompletionGraphEvent)
{
    if (UProphecyJoltCharacterWorldSubsystem* Coordinator = Target.Get()) Coordinator->TickAutomatic(DeltaTime);
}

FString FProphecyJoltCharacterWorldTickFunction::DiagnosticMessage()
{
    return TEXT("ProphecyJoltWorldClients: prepare, shared Step, completed presentation");
}

FName FProphecyJoltCharacterWorldTickFunction::DiagnosticContext(bool bDetailed)
{
    return FName(TEXT("ProphecyJoltWorldClients"));
}

void UProphecyJoltCharacterWorldSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    Collection.InitializeDependency<UProphecyJoltWorldSubsystem>(); // No native initialization.
    StepTick.Target = this;
    StepTick.bCanEverTick = true;
    StepTick.bStartWithTickEnabled = false;
    StepTick.bRunOnAnyThread = false;
    StepTick.bAllowTickBatching = false;
    StepTick.bTickEvenWhenPaused = false;
    const ETickingGroup AutomaticGroup = FParse::Param(FCommandLine::Get(), TEXT("ProphecyJoltDuringPhysics"))
        ? TG_DuringPhysics : TG_PrePhysics;
    StepTick.TickGroup = AutomaticGroup;
    StepTick.EndTickGroup = AutomaticGroup;
    TickStartHandle = FWorldDelegates::OnWorldTickStart.AddUObject(this, &ThisClass::OnWorldTickStart);
    PreActorTickHandle = FWorldDelegates::OnWorldPreActorTick.AddUObject(this, &ThisClass::OnWorldPreActorTick);
    TickEndHandle = FWorldDelegates::OnWorldTickEnd.AddUObject(this, &ThisClass::OnWorldTickEnd);
}

bool UProphecyJoltCharacterWorldSubsystem::DoesSupportWorldType(EWorldType::Type WorldType) const
{
    return WorldType == EWorldType::Game || WorldType == EWorldType::PIE;
}

bool UProphecyJoltCharacterWorldSubsystem::CanRequestAdmission(const UActorComponent& Client, FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread()) { OutError = TEXT("Jolt client coordination requires the game thread."); return false; }
    if (bEnding || !GetWorld() || GetWorld()->bIsTearingDown || !GetWorld()->PersistentLevel)
    { OutError = TEXT("The coordinator world is ending or has no persistent level."); return false; }
    PruneRegistrations();
    if (bStopped)
    { OutError = FString::Printf(TEXT("Disable all stopped client bindings before starting a new session: %s"), *LastError); return false; }
    if (!IsValid(&Client) || !Client.IsRegistered() || Client.GetWorld() != GetWorld()
        || !IsValid(Client.GetOwner()) || Client.GetOwner()->IsActorBeingDestroyed()
        || !Cast<IProphecyJoltStepClient>(&Client))
    { OutError = TEXT("A client must be a registered native Jolt step-interface component in this world."); return false; }
    for (const auto& Registration : RegisteredClients)
        if (Registration.Client.Get() == &Client)
        { OutError = TEXT("This component already has a registered shared-step binding."); return false; }
    UProphecyJoltWorldSubsystem* PhysicsOwner = GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltWorldDiagnostics Diagnostics;
    if (!PhysicsOwner || !PhysicsOwner->GetDiagnostics(Diagnostics).IsSuccess()
        || !Diagnostics.bInitialized || Diagnostics.bFaulted)
    { OutError = TEXT("Explicitly initialize a healthy native Jolt owner before registering clients."); return false; }
    if (!RegisteredClients.IsEmpty() && (StepWorldLifetime != Diagnostics.WorldLifetime
        || ExpectedWorldSteps != Diagnostics.CompletedSteps))
    { OutError = TEXT("Existing clients have an external step or native lifetime change; close them before admission."); return false; }
    return true;
}

bool UProphecyJoltCharacterWorldSubsystem::CanAdmitImmediately() const
{
    if (bEnding || bExecutingStep || !GetWorld()) return false;
    if (!bWorldTickInProgress) return !GetWorld()->bInTick;
    // Enabled at world-tick start even with no clients. The queued task closes admission before
    // ExecuteTick; the tick then closes the flag. PreActorTick benchmark initialization stays immediate.
    return bAdmissionWindowOpen && StepTick.IsTickFunctionRegistered() && !StepTick.IsCompletionHandleValid();
}

bool UProphecyJoltCharacterWorldSubsystem::CanRegisterStepClient(const UActorComponent& Client, FString& OutError)
{
    if (!CanRequestAdmission(Client, OutError)) return false;
    if (!CanAdmitImmediately())
    { OutError = TEXT("Client admission must finish before the world queues this frame's tick dependencies."); return false; }
    return true;
}

bool UProphecyJoltCharacterWorldSubsystem::RequestClientAdmission(UActorComponent& Client,
    const FProphecyJoltClientAdmissionCallback& Complete, const FProphecyJoltClientAdmissionCallback& Cancel,
    bool& bOutDeferred, FGuid& OutAdmissionId, FString& OutError)
{
    bOutDeferred = false;
    OutAdmissionId.Invalidate();
    OutError.Reset();
    if (!IsInGameThread()) { OutError = TEXT("Client admission requires the game thread."); return false; }
    if (bEnding || !GetWorld() || GetWorld()->bIsTearingDown)
    { OutError = TEXT("Cannot admit a client in an ending world."); return false; }
    if (!Complete.IsBound() || !Cancel.IsBound() || Complete.GetUObject() != &Client || Cancel.GetUObject() != &Client)
    { OutError = TEXT("Admission completion and cancellation must be weak native delegates bound to the requesting component."); return false; }
    // An existing accepted request is idempotent, including a later entry in the current drain.
    for (const auto& Pending : PendingAdmissions)
        if (Pending.Client.Get() == &Client)
        {
            bOutDeferred = true;
            OutAdmissionId = Pending.AdmissionId;
            return true;
        }
    if (!CanRequestAdmission(Client, OutError)) return false;
    if (CanAdmitImmediately()) return true;
    FProphecyJoltClientPendingAdmission& Pending = PendingAdmissions.AddDefaulted_GetRef();
    Pending.Client = &Client;
    Pending.AdmissionId = FGuid::NewGuid();
    Pending.Complete = Complete;
    Pending.Cancel = Cancel;
    bOutDeferred = true;
    OutAdmissionId = Pending.AdmissionId;
    return true;
}

bool UProphecyJoltCharacterWorldSubsystem::CancelClientAdmission(UActorComponent& Client, const FGuid& AdmissionId)
{
    if (!IsInGameThread() || !AdmissionId.IsValid()) return false;
    const int32 Index = PendingAdmissions.IndexOfByPredicate([&](const auto& Pending)
        { return Pending.Client.Get() == &Client && Pending.AdmissionId == AdmissionId; });
    if (Index == INDEX_NONE) return false;
    PendingAdmissions.RemoveAt(Index);
    return true;
}

void UProphecyJoltCharacterWorldSubsystem::OnWorldTickStart(UWorld* World, ELevelTick TickType, float DeltaSeconds)
{
    if (World != GetWorld() || bEnding) return;
    bWorldTickInProgress = true;
    bAdmissionWindowOpen = true;
    if (World->PersistentLevel && !StepTick.IsTickFunctionRegistered()) StepTick.RegisterTickFunction(World->PersistentLevel);
    RefreshTickEnabled();
}

void UProphecyJoltCharacterWorldSubsystem::OnWorldPreActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds)
{
    if (World != GetWorld() || bEnding || !CanAdmitImmediately()) return;
    // Keep not-yet-dispatched records in the registry so nested requests remain idempotent and
    // cancellation can remove a later entry. New entries are not part of this frame's snapshot.
    const TArray<FProphecyJoltClientPendingAdmission> Admissions = PendingAdmissions;
    for (const auto& Admission : Admissions)
    {
        if (bEnding) break; // Teardown already cancelled/cleared every still-pending record.
        const int32 Index = PendingAdmissions.IndexOfByPredicate([&](const auto& Pending)
            { return Pending.Client == Admission.Client && Pending.AdmissionId == Admission.AdmissionId; });
        if (Index == INDEX_NONE) continue;
        PendingAdmissions.RemoveAt(Index); // Clear registry ownership before any client callback.
        if (Admission.Client.IsValid()) Admission.Complete.ExecuteIfBound(Admission.AdmissionId);
    }
}

void UProphecyJoltCharacterWorldSubsystem::OnWorldTickEnd(UWorld* World, ELevelTick TickType, float DeltaSeconds)
{
    if (World != GetWorld()) return;
    bWorldTickInProgress = false;
    bAdmissionWindowOpen = false;
    RefreshTickEnabled();
}

bool UProphecyJoltCharacterWorldSubsystem::RegisterStepClient(UActorComponent& Client, AActor* PublishingActor,
    FGuid& OutRegistrationId, FString& OutError)
{
    OutRegistrationId.Invalidate();
    if (!CanRegisterStepClient(Client, OutError)) return false;
    IProphecyJoltStepClient* StepClient = Cast<IProphecyJoltStepClient>(&Client);
    if (!StepClient || !StepClient->IsJoltStepClientActive())
    { OutError = TEXT("Prime an active native client binding before registration."); return false; }
    if (PublishingActor && (!IsValid(PublishingActor) || PublishingActor->GetWorld() != GetWorld()
        || PublishingActor->IsActorBeingDestroyed()))
    { OutError = TEXT("A publishing actor must be a live actor in the client's world."); return false; }
    if (RegisteredClients.IsEmpty())
    {
        UProphecyJoltWorldSubsystem* PhysicsOwner = GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
        FProphecyJoltWorldDiagnostics Diagnostics;
        if (!PhysicsOwner->GetDiagnostics(Diagnostics).IsSuccess())
        { OutError = TEXT("Could not read the first client's native world identity."); return false; }
        StepWorldLifetime = Diagnostics.WorldLifetime;
        ExpectedWorldSteps = Diagnostics.CompletedSteps;
    }
    if (!StepTick.IsTickFunctionRegistered()) StepTick.RegisterTickFunction(GetWorld()->PersistentLevel);
    if (!StepTick.IsTickFunctionRegistered())
    { OutError = TEXT("The shared client tick could not register with the persistent level."); return false; }
    auto& Registration = RegisteredClients.AddDefaulted_GetRef();
    Registration.Client = &Client;
    Registration.PublishingActor = PublishingActor;
    Registration.RegistrationId = FGuid::NewGuid();
    RegistrationOwners.Add(Registration.RegistrationId, &Client);
    if (PublishingActor) StepTick.AddPrerequisite(PublishingActor, PublishingActor->PrimaryActorTick);
    OutRegistrationId = Registration.RegistrationId;
    RefreshTickEnabled();
    OutError.Reset();
    return true;
}

void UProphecyJoltCharacterWorldSubsystem::RemoveRegistrationPrerequisite(const FProphecyJoltStepClientRegistration& Registration)
{
    if (AActor* PublishingActor = Registration.PublishingActor.Get())
    {
        const bool bStillRequired = RegisteredClients.ContainsByPredicate([&](const auto& Other)
            { return Other.PublishingActor.Get() == PublishingActor && Other.RegistrationId != Registration.RegistrationId; });
        if (!bStillRequired) StepTick.RemovePrerequisite(PublishingActor, PublishingActor->PrimaryActorTick);
    }
}

IProphecyJoltStepClient* UProphecyJoltCharacterWorldSubsystem::ResolveClient(const FProphecyJoltStepClientRegistration& Registration) const
{
    UActorComponent* Component = Registration.Client.Get();
    if (!Component || !Component->IsRegistered() || Component->GetWorld() != GetWorld() || !Registration.RegistrationId.IsValid()
        || !IsValid(Component->GetOwner()) || Component->GetOwner()->IsActorBeingDestroyed())
        return nullptr;
    const auto* Current = RegistrationOwners.Find(Registration.RegistrationId);
    if (!Current || *Current != Registration.Client) return nullptr;
    IProphecyJoltStepClient* Client = Cast<IProphecyJoltStepClient>(Component);
    return Client && Client->IsJoltStepClientActive() ? Client : nullptr;
}

void UProphecyJoltCharacterWorldSubsystem::PruneRegistrations()
{
    for (int32 Index = RegisteredClients.Num() - 1; Index >= 0; --Index)
    {
        const auto& Registration = RegisteredClients[Index];
        UActorComponent* Component = Registration.Client.Get();
        IProphecyJoltStepClient* Client = Component ? Cast<IProphecyJoltStepClient>(Component) : nullptr;
        if (!Component || !Component->IsRegistered() || Component->GetWorld() != GetWorld()
            || !IsValid(Component->GetOwner()) || Component->GetOwner()->IsActorBeingDestroyed()
            || !Client || !Client->IsJoltStepClientActive())
        {
            RemoveRegistrationPrerequisite(Registration);
            RegistrationOwners.Remove(Registration.RegistrationId);
            RegisteredClients.RemoveAt(Index);
        }
    }
    PendingAdmissions.RemoveAll([](const auto& Pending) { return !Pending.Client.IsValid(); });
    if (RegisteredClients.IsEmpty())
    {
        // A remaining prop is a live client even when the last character has gone.
        StepWorldLifetime.Invalidate();
        ExpectedWorldSteps = 0;
        bStopped = false;
        LastError.Reset();
    }
    // Retain LastStepEngineFrame so same-frame removal/re-admission never causes two automatic steps.
    RefreshTickEnabled();
}

bool UProphecyJoltCharacterWorldSubsystem::UnregisterStepClient(UActorComponent& Client, const FGuid& RegistrationId)
{
    if (!IsInGameThread() || !RegistrationId.IsValid()) return false;
    const int32 Index = RegisteredClients.IndexOfByPredicate([&](const auto& Registration)
        { return Registration.Client.Get() == &Client && Registration.RegistrationId == RegistrationId; });
    if (Index == INDEX_NONE) return false;
    RemoveRegistrationPrerequisite(RegisteredClients[Index]);
    RegistrationOwners.Remove(RegistrationId);
    RegisteredClients.RemoveAt(Index);
    PruneRegistrations();
    return true;
}

bool UProphecyJoltCharacterWorldSubsystem::IsStepClientRegistered(const UActorComponent& Client, const FGuid& RegistrationId) const
{
    if (!IsInGameThread() || !RegistrationId.IsValid()) return false;
    const auto* Current = RegistrationOwners.Find(RegistrationId);
    if (!Current || Current->Get() != &Client) return false;
    FProphecyJoltStepClientRegistration Registration;
    Registration.Client = *Current;
    Registration.RegistrationId = RegistrationId;
    return ResolveClient(Registration) != nullptr;
}

int32 UProphecyJoltCharacterWorldSubsystem::GetRegisteredStepClientCount() const
{
    if (!IsInGameThread()) return 0;
    int32 Count = 0;
    for (const auto& Registration : RegisteredClients) if (ResolveClient(Registration)) ++Count;
    return Count;
}

int32 UProphecyJoltCharacterWorldSubsystem::GetRegisteredCharacterCount() const
{
    if (!IsInGameThread()) return 0;
    int32 Count = 0;
    for (const auto& Registration : RegisteredClients)
        if (Cast<UProphecyJoltCharacterComponent>(Registration.Client.Get()) && ResolveClient(Registration)) ++Count;
    return Count;
}

bool UProphecyJoltCharacterWorldSubsystem::HasAutomaticStepOwners() const
{
    if (!IsInGameThread()) return false;
    for (const auto& Registration : RegisteredClients)
        if (IProphecyJoltStepClient* Client = ResolveClient(Registration); Client && Client->WantsAutomaticJoltStep()) return true;
    return false;
}

void UProphecyJoltCharacterWorldSubsystem::RefreshTickEnabled()
{
    StepTick.SetTickFunctionEnable(!bEnding && ((bWorldTickInProgress && bAdmissionWindowOpen)
        || (!bStopped && !RegisteredClients.IsEmpty())));
}

bool UProphecyJoltCharacterWorldSubsystem::StopWithError(FString& OutError, const FString& Error)
{
    if (!bStopped) LastError = Error;
    bStopped = true;
    // A callback may unregister the last client, which clears LastError. Keep the dispatched failure
    // stable for the caller and every remaining callback even in that normal removal path.
    const FString Failure = LastError;
    OutError = Failure;
    const auto Clients = RegisteredClients;
    for (const auto& Registration : Clients)
        if (IProphecyJoltStepClient* Client = ResolveClient(Registration)) Client->LatchJoltStepError(Failure);
    OutError = Failure;
    RefreshTickEnabled();
    return false;
}

bool UProphecyJoltCharacterWorldSubsystem::StepRegisteredClients(float DeltaSeconds, bool bPublishMissingTargets, FString& OutError)
{
    namespace Profile = ProphecyJolt::CharacterProfiling;
    Profile::FScope Timing(Profile::EPhase::WorldCoordinator);
    OutError.Reset();
    if (!IsInGameThread()) { OutError = TEXT("Shared Jolt stepping requires the game thread."); return false; }
    if (bStopped) { OutError = LastError; return false; }
    if (bExecutingStep) { OutError = TEXT("Reentrant shared Jolt stepping is unsupported."); return false; }
    if (bEnding || !GetWorld() || GetWorld()->bIsTearingDown)
    { OutError = TEXT("The shared Jolt client world is ending."); return false; }
    if (!FMath::IsFinite(DeltaSeconds) || DeltaSeconds <= 0.0f)
    { OutError = TEXT("Shared Jolt step duration must be finite and positive."); return false; }
    PruneRegistrations();
    if (RegisteredClients.IsEmpty()) { OutError = TEXT("No active Jolt client is registered."); return false; }
    TGuardValue<bool> StepGuard(bExecutingStep, true);
    UProphecyJoltWorldSubsystem* PhysicsOwner = GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltWorldDiagnostics Diagnostics;
    if (!PhysicsOwner || !PhysicsOwner->GetDiagnostics(Diagnostics).IsSuccess() || !Diagnostics.bInitialized
        || Diagnostics.bFaulted || Diagnostics.WorldLifetime != StepWorldLifetime
        || Diagnostics.CompletedSteps != ExpectedWorldSteps)
        return StopWithError(OutError, TEXT("Native owner changed, faulted or was stepped outside the shared client coordinator."));

    const TArray<FProphecyJoltStepClientRegistration> Clients = RegisteredClients;
    FString Error;
    // Reconcile static sources after callback-capable client preparation, immediately before Step.
    for (int32 PreparePass = 0; PreparePass < 2; ++PreparePass)
    {
        for (const auto& Registration : Clients)
        {
            IProphecyJoltStepClient* Client = ResolveClient(Registration);
            if (!Client || (Cast<UProphecyJoltSceneCollisionComponent>(Registration.Client.Get()) != nullptr) != (PreparePass == 1)) continue;
            Profile::FScope ClientTiming(Profile::EPhase::ClientPrepare);
            if (!Client->PrepareJoltWorldStep(DeltaSeconds, bPublishMissingTargets, Error) && ResolveClient(Registration))
                return StopWithError(OutError, FString::Printf(TEXT("Shared-step client preparation failed: %s"), *Error));
        }
    }
    PruneRegistrations();
    if (RegisteredClients.IsEmpty()) return true; // All clients deliberately removed themselves; no native step is requested now.
    if (bEnding) return true; // Teardown during a client callback also cancels the pending shared step.
    // Preparation is callback-capable. Do not issue a second step or use a replaced native world if
    // a client violated its no-stepping/no-reinitialization contract during that callback.
    if (!IsValid(PhysicsOwner) || !PhysicsOwner->GetDiagnostics(Diagnostics).IsSuccess()
        || !Diagnostics.bInitialized || Diagnostics.bFaulted || Diagnostics.WorldLifetime != StepWorldLifetime
        || Diagnostics.CompletedSteps != ExpectedWorldSteps)
        return StopWithError(OutError, TEXT("A client changed or stepped the native owner during shared-step preparation."));
    const UPhysicsSettings* PhysicsSettings = UPhysicsSettings::Get();
    ProphecyJolt::Constraints::Prepare(GetWorld());
    const int32 CollisionSteps = ProphecyJolt::StepTiming::Count(DeltaSeconds, PhysicsSettings);
    {
        Profile::FScope StepTiming(Profile::EPhase::NativeStep);
        const FProphecyJoltWorldStatus Stepped = PhysicsOwner->Step(DeltaSeconds, CollisionSteps);
        if (!Stepped.IsSuccess()) return StopWithError(OutError, Stepped.Message);
    }
    ++ExpectedWorldSteps;
    LastStepEngineFrame = GFrameCounter;
    TArray<UProphecyJoltCharacterComponent*, TInlineAllocator<128>> PoseCharacters;
    for (const auto& Registration : Clients)
    {
        auto* Character = Cast<UProphecyJoltCharacterComponent>(Registration.Client.Get());
        if (Character && Character->GetClass() == UProphecyJoltCharacterComponent::StaticClass()
            && IsStepClientRegistered(*Character, Registration.RegistrationId)) PoseCharacters.Add(Character);
    }
    UProphecyJoltCharacterComponent::PrepareCompletedPoseBatch(PoseCharacters, DeltaSeconds);
    for (const auto& Registration : Clients)
    {
        IProphecyJoltStepClient* Client = ResolveClient(Registration);
        if (!Client) continue;
        Profile::FScope ClientTiming(Profile::EPhase::ClientConsume);
        if (!Client->ConsumeCompletedJoltWorldStep(Error) && ResolveClient(Registration))
            return StopWithError(OutError, FString::Printf(TEXT("Shared-step completed presentation failed: %s"), *Error));
    }
    LastError.Reset();
    ProphecyJolt::Constraints::Finish(GetWorld());
    if (IsValid(PhysicsOwner) && !bEnding) PhysicsOwner->DispatchPendingHitEvents();
    return true;
}

void UProphecyJoltCharacterWorldSubsystem::TickAutomatic(float DeltaSeconds)
{
    check(IsInGameThread());
    bAdmissionWindowOpen = false;
    RefreshTickEnabled();
    if (bEnding || bStopped || DeltaSeconds <= 0.0f || LastStepEngineFrame == GFrameCounter) return;
    PruneRegistrations();
    if (!HasAutomaticStepOwners()) return;
    // Query the executing tick's resolved groups, including prerequisite-driven promotion.
    // UWorld's current group separately records when the GT task actually ran.
    LastAutomaticTickGroup = StepTick.GetActualTickGroup();
    LastAutomaticEndTickGroup = StepTick.GetActualEndTickGroup();
    LastAutomaticWorldTickGroup = GetWorld() ? static_cast<ETickingGroup>(GetWorld()->TickGroup) : TG_MAX;
    const uint64 BeforeSteps = ExpectedWorldSteps;
    FString Error;
    if (!StepRegisteredClients(DeltaSeconds, true, Error))
    {
        if (!bStopped) StopWithError(Error, Error);
        UE_LOG(LogProphecyJoltCharacterWorld, Error, TEXT("Shared Jolt client stepping stopped: %s"), *Error);
    }
    else if (ExpectedWorldSteps != BeforeSteps)
    {
        // A prepare callback can remove the last client without actually stepping the native world.
        ++AutomaticStepCount;
        LastAutomaticStepEngineFrame = GFrameCounter;
    }
}

bool UProphecyJoltCharacterWorldSubsystem::StepExplicit(UActorComponent& Requester, const FGuid& RegistrationId,
    float DeltaSeconds, FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread()) { OutError = TEXT("Explicit Jolt stepping requires the game thread."); return false; }
    PruneRegistrations();
    if (!IsStepClientRegistered(Requester, RegistrationId))
    { OutError = TEXT("The explicit requester does not own this exact client registration."); return false; }
    if (HasAutomaticStepOwners())
    { OutError = TEXT("Explicit stepping is refused while any registered client requests automatic world stepping."); return false; }
    return StepRegisteredClients(DeltaSeconds, false, OutError);
}

bool UProphecyJoltCharacterWorldSubsystem::RequestEnable(UProphecyJoltCharacterComponent& Character,
    bool& bOutDeferred, FString& OutError)
{
    bOutDeferred = false;
    if (!IsInGameThread()) { OutError = TEXT("Character admission requires the game thread."); return false; }
    if (Character.IsEnablePending())
    {
        if (Character.AdmissionCoordinator.Get() != this)
        { OutError = TEXT("This character has a pending admission in another coordinator."); return false; }
        bOutDeferred = true;
        OutError.Reset();
        return true;
    }
    FGuid AdmissionId;
    if (!RequestClientAdmission(Character,
        FProphecyJoltClientAdmissionCallback::CreateUObject(&Character, &UProphecyJoltCharacterComponent::CompleteDeferredEnable),
        FProphecyJoltClientAdmissionCallback::CreateUObject(&Character, &UProphecyJoltCharacterComponent::CancelDeferredEnable),
        bOutDeferred, AdmissionId, OutError)) return false;
    if (bOutDeferred)
    {
        Character.PendingAdmissionId = AdmissionId;
        Character.AdmissionCoordinator = this;
    }
    return true;
}

void UProphecyJoltCharacterWorldSubsystem::CancelPendingEnable(UProphecyJoltCharacterComponent& Character)
{
    check(IsInGameThread());
    // The existing component invalidates its local token before calling this compatibility wrapper.
    PendingAdmissions.RemoveAll([&](const auto& Pending) { return !Pending.Client.IsValid() || Pending.Client.Get() == &Character; });
}

bool UProphecyJoltCharacterWorldSubsystem::CanRegisterCharacter(const UProphecyJoltCharacterComponent& Character, FString& OutError)
{
    return CanRegisterStepClient(Character, OutError);
}

bool UProphecyJoltCharacterWorldSubsystem::RegisterCharacter(UProphecyJoltCharacterComponent& Character, FString& OutError)
{
    if (!IsInGameThread()) { OutError = TEXT("Character registration requires the game thread."); return false; }
    if (Character.StepRegistrationId.IsValid())
    { OutError = TEXT("This character already has a registration identity."); return false; }
    if (!Character.IsJoltPhysical() || Character.IsSteppingStopped() || Character.GetRevision() == 0)
    { OutError = TEXT("Prime the active character's first completed pose before registration."); return false; }
    return RegisterStepClient(Character, Character.GetOwner(), Character.StepRegistrationId, OutError);
}

void UProphecyJoltCharacterWorldSubsystem::UnregisterCharacter(UProphecyJoltCharacterComponent& Character)
{
    if (!IsInGameThread()) return;
    const FGuid RegistrationId = Character.StepRegistrationId;
    Character.StepRegistrationId.Invalidate();
    UnregisterStepClient(Character, RegistrationId);
}

bool UProphecyJoltCharacterWorldSubsystem::StepExplicit(UProphecyJoltCharacterComponent& Requester,
    float DeltaSeconds, FString& OutError)
{
    return StepExplicit(Requester, Requester.StepRegistrationId, DeltaSeconds, OutError);
}

void UProphecyJoltCharacterWorldSubsystem::StopForWorldTeardown()
{
    bEnding = true;
    bAdmissionWindowOpen = false;
    bWorldTickInProgress = false;
    FWorldDelegates::OnWorldTickStart.Remove(TickStartHandle);
    FWorldDelegates::OnWorldPreActorTick.Remove(PreActorTickHandle);
    FWorldDelegates::OnWorldTickEnd.Remove(TickEndHandle);
    TickStartHandle.Reset();
    PreActorTickHandle.Reset();
    TickEndHandle.Reset();
    const auto Admissions = MoveTemp(PendingAdmissions);
    PendingAdmissions.Reset();
    for (const auto& Admission : Admissions)
        if (Admission.Client.IsValid()) Admission.Cancel.ExecuteIfBound(Admission.AdmissionId);
    StepTick.SetTickFunctionEnable(false);
    if (StepTick.IsTickFunctionRegistered()) StepTick.UnRegisterTickFunction();
    StepTick.Target.Reset();
    for (const auto& Registration : RegisteredClients)
        if (AActor* Actor = Registration.PublishingActor.Get()) StepTick.RemovePrerequisite(Actor, Actor->PrimaryActorTick);
    RegisteredClients.Reset();
    RegistrationOwners.Reset();
    // Each component remains responsible for its own body/rig teardown; the native owner is final owner.
}

void UProphecyJoltCharacterWorldSubsystem::OnWorldEndPlay(UWorld& InWorld)
{
    StopForWorldTeardown();
    Super::OnWorldEndPlay(InWorld);
}

void UProphecyJoltCharacterWorldSubsystem::PreDeinitialize()
{
    StopForWorldTeardown();
    Super::PreDeinitialize();
}

void UProphecyJoltCharacterWorldSubsystem::Deinitialize()
{
    StopForWorldTeardown();
    Super::Deinitialize();
}
