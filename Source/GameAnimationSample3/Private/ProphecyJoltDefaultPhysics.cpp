#include "ProphecyJoltFightSetup.h"
#include "ProphecyJoltSceneCollisionComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"

namespace ProphecyJolt::DefaultPhysics
{
// One project switch, enabled by default. A level's explicit Fight Setup still wins, including
// bEnableJolt=false for deliberate Chaos comparisons. No saved map or Blueprint is rewritten.
static TAutoConsoleVariable<int32> Enabled(TEXT("Prophecy.Jolt.DefaultPhysics"), 1,
    TEXT("Use Jolt for ordinary gameplay mesh physics by default. Read once at world startup."));
static TSet<TWeakObjectPtr<UWorld>> Started;
static FDelegateHandle Tick, Cleanup;
void Startup()
{
    Tick = FWorldDelegates::OnWorldPreActorTick.AddLambda([](UWorld* World, ELevelTick, float)
    {
        if (!World || !World->IsGameWorld() || !World->HasBegunPlay() || World->bIsTearingDown || Started.Contains(World)) return;
        Started.Add(World);
        if (!Enabled.GetValueOnGameThread() || UProphecyJoltSceneCollisionComponent::FindForWorld(World)) return;
        for (TActorIterator<AProphecyJoltFightSetup> It(World); It; ++It) return;
        FActorSpawnParameters Params;
        Params.ObjectFlags |= RF_Transient;
        Params.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        auto* Setup = World->SpawnActor<AProphecyJoltFightSetup>(AProphecyJoltFightSetup::StaticClass(), FTransform::Identity, Params);
        if (!Setup) UE_LOG(LogTemp, Error, TEXT("Could not create the default Jolt gameplay owner."));
    });
    Cleanup = FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World, bool, bool) { Started.Remove(World); });
}
void Shutdown()
{
    FWorldDelegates::OnWorldPreActorTick.Remove(Tick);
    FWorldDelegates::OnWorldCleanup.Remove(Cleanup);
    Started.Reset();
}
}
