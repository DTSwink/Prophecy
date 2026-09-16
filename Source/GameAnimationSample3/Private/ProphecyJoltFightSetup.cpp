#include "ProphecyJoltFightSetup.h"

#include "ProphecyAgent.h"
#include "ProphecyJoltBlueprintLibrary.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltSceneCollisionComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/World.h"
#include "Engine/LatentActionManager.h"
#include "EngineUtils.h"

AProphecyJoltFightSetup::AProphecyJoltFightSetup()
{
    PrimaryActorTick.bCanEverTick = false;
    SetRootComponent(CreateDefaultSubobject<USceneComponent>(TEXT("Root")));
    SceneCollision = CreateDefaultSubobject<UProphecyJoltSceneCollisionComponent>(TEXT("SceneCollision"));
    SceneCollision->bAutomaticScenePhysics = true;
}

void AProphecyJoltFightSetup::ReportError(const FString& Error)
{
    LastError = Error;
    UE_LOG(LogTemp, Error, TEXT("Jolt fight setup %s: %s"), *GetName(), *Error);
}

void AProphecyJoltFightSetup::BeginPlay()
{
    Super::BeginPlay();
    if (!bEnableJolt) return;
    for (TActorIterator<AProphecyJoltFightSetup> It(GetWorld()); It; ++It)
    {
        if (*It != this && It->bEnableJolt)
        {
            ReportError(TEXT("Keep only one enabled Jolt Fight Setup actor in the world."));
            return;
        }
    }
    FString Error;
    if (!UProphecyJoltBlueprintLibrary::InitializeJoltWorld(this, Error)
        || !SceneCollision->EnableSceneCollision(Error))
    {
        ReportError(Error);
        return;
    }
    SpawnHandle = GetWorld()->AddOnActorSpawnedHandler(
        FOnActorSpawned::FDelegate::CreateUObject(this, &ThisClass::QueueActor));
    for (TActorIterator<AProphecyAgent> It(GetWorld()); It; ++It) QueueActor(*It);
}

void AProphecyJoltFightSetup::QueueActor(AActor* Actor)
{
    auto* Agent = Cast<AProphecyAgent>(Actor);
    if (!IsValid(Agent) || Agent->GetWorld() != GetWorld()) return;
    PendingAgents.Add(Agent);
    if (!PreActorTickHandle.IsValid())
        PreActorTickHandle = FWorldDelegates::OnWorldPreActorTick.AddUObject(this, &ThisClass::BeforeActorTick);
}

void AProphecyJoltFightSetup::BeforeActorTick(UWorld* World, ELevelTick TickType, float DeltaSeconds)
{
    if (World != GetWorld() || World->bIsTearingDown) return;
    if (SceneCollision->IsEnablePending()) return;
    if (!SceneCollision->IsSceneCollisionEnabled())
    {
        ReportError(SceneCollision->GetLastError());
        PendingAgents.Reset();
    }

    // Drain before tick dependencies are queued, after normal actor/NN BeginPlay initialization.
    // New spawns during callbacks enter a fresh queue; existing explicit mode changes are not polled.
    TSet<TWeakObjectPtr<AProphecyAgent>> Candidates = MoveTemp(PendingAgents);
    PendingAgents.Reset();
    for (const TWeakObjectPtr<AProphecyAgent>& Candidate : Candidates)
    {
        AProphecyAgent* Agent = Candidate.Get();
        if (!IsValid(Agent) || Agent->IsActorBeingDestroyed()) continue;
        if (!Agent->HasActorBegunPlay()) { PendingAgents.Add(Candidate); continue; }
        if (!Agent->bManualNNPoseApplication || Agent->GetSimulationMode() != EProphecyAgentSimulationMode::Physical
            || Agent->IsJoltPhysicalAnimationEnabled()) continue;
        // The existing fighter BeginPlay uses Delay(0) before begin_f2, which finalizes
        // Chaos collision and equipment. HasActorBegunPlay alone precedes that work.
        // Wait for the actual latent initialization to finish, without a timed delay.
        if (World->GetLatentActionManager().GetNumActionsForObject(Agent) != 0)
        {
            PendingAgents.Add(Candidate);
            continue;
        }

        const bool bPreviousMACD = Agent->IsMACDEnabled();
        Agent->SetMACDEnabled(false);
        if (!Agent->EnableJoltPhysicalAnimation())
        {
            if (IsValid(Agent) && !Agent->IsActorBeingDestroyed()) Agent->SetMACDEnabled(bPreviousMACD);
            const auto* Character = IsValid(Agent) ? Agent->GetJoltCharacterComponent() : nullptr;
            ReportError(FString::Printf(TEXT("%s could not enter Jolt: %s"), *GetNameSafe(Agent),
                Character ? *Character->GetLastError() : TEXT("physical mesh initialization/admission failed")));
            continue;
        }
        auto* Character = Agent->GetJoltCharacterComponent();
        if (Character && Character->IsEnablePending())
        {
            Character->OnDeferredEnableCompleted.AddWeakLambda(this,
                [this](bool bSucceeded, const FString& Error)
                {
                    if (bSucceeded) ++StartedAgentCount;
                    else ReportError(Error);
                });
        }
        else ++StartedAgentCount;
    }
    if (PendingAgents.IsEmpty())
    {
        FWorldDelegates::OnWorldPreActorTick.Remove(PreActorTickHandle);
        PreActorTickHandle.Reset();
    }
}

void AProphecyJoltFightSetup::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (GetWorld()) GetWorld()->RemoveOnActorSpawnedHandler(SpawnHandle);
    SpawnHandle.Reset();
    FWorldDelegates::OnWorldPreActorTick.Remove(PreActorTickHandle);
    PreActorTickHandle.Reset();
    PendingAgents.Reset();
    Super::EndPlay(EndPlayReason);
}
