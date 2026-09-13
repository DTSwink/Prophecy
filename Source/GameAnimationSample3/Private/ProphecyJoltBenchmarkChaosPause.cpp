#include "ProphecyJoltBenchmarkChaosPause.h"

#include "Chaos/ParticleHandle.h"
#include "Chaos/ChaosMarshallingManager.h"
#include "Chaos/ISpatialAcceleration.h"
#include "Chaos/PhysicsObjectInterface.h"
#include "ChaosSolversModule.h"
#include "Components/PrimitiveComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/DefaultPawn.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/PlayerController.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "PhysicsEngine/PhysicsObjectExternalInterface.h"
#include "PhysicsEngine/PhysicsSettings.h"
#include "Physics/Experimental/PhysScene_Chaos.h"
#include "PBDRigidsSolver.h"
#include "UObject/ObjectKey.h"
#include "UObject/UObjectIterator.h"

namespace ProphecyJolt::BenchmarkChaosPause
{
namespace
{
struct FInventory
{
    int32 Components = 0;
    int32 Objects = 0;
    int32 Kinematic = 0;
    int32 Static = 0;
    int32 DynamicOrSleeping = 0;
    int32 SolverParticles = 0;
    int32 SolverDynamicOrSleeping = 0;

    TSharedPtr<FJsonObject> Json() const
    {
        auto Row = MakeShared<FJsonObject>();
        Row->SetNumberField(TEXT("components_with_native_objects"), Components);
        Row->SetNumberField(TEXT("unique_native_objects"), Objects);
        Row->SetNumberField(TEXT("gt_kinematic_objects"), Kinematic);
        Row->SetNumberField(TEXT("gt_static_objects"), Static);
        Row->SetNumberField(TEXT("gt_dynamic_or_sleeping_objects"), DynamicOrSleeping);
        Row->SetNumberField(TEXT("pt_all_particles"), SolverParticles);
        Row->SetNumberField(TEXT("pt_dynamic_or_sleeping_particles"), SolverDynamicOrSleeping);
        return Row;
    }
};

// Also instantiated independently by the controlled test below. No global command-line rewriting.
class FControl
{
public:
    // First positive frame buffers dynamic->kinematic transitions, then clears transient dirty.
    // The second replaces that transition buffer. Moving kinematics may still be returned.
    static constexpr int32 PositiveFramesBeforePause = 2;

    bool Begin(const UObject& Owner, UWorld& World,
        TConstArrayView<TObjectPtr<AActor>> KnownActors, FString& OutError)
    {
        OutError.Reset();
        if (!IsInGameThread()) { OutError = TEXT("Chaos pause control requires the game thread."); return false; }
        if (bOwned)
        {
            if (OwnerKey == FObjectKey(&Owner) && WorldPtr.Get() == &World) return true;
            OutError = TEXT("Chaos pause control already belongs to another benchmark/world lifetime.");
            return false;
        }
        if (bAttempted) { OutError = TEXT("Chaos pause control cannot restart after an attempt in this process."); return false; }
        bAttempted = true;
        OwnerKey = FObjectKey(&Owner);
        WorldPtr = &World;
        Report = MakeShared<FJsonObject>();
        Report->SetBoolField(TEXT("requested"), true);
        Report->SetStringField(TEXT("owner"), Owner.GetPathName());
        Report->SetStringField(TEXT("world"), World.GetPathName());
        Report->SetStringField(TEXT("scope"), TEXT("Opt-in benchmark-only zero-delta maintenance of the default Chaos scene after Jolt admission. Normal world Start/End physics ticks remain enabled. No NN, Jolt step, capsule query, body geometry, collision filter, pose or presentation cadence is removed. This is not a production setting or general mixed-backend world policy."));
        Report->SetStringField(TEXT("required_independent_control"),
            TEXT("Prophecy.Jolt.QueryPose.PausedSceneMaintenanceLifecycle must pass in this binary before this diagnostic is accepted. Its spawned/moved/removed query bodies are outside the timed crowd workload."));
        if ((World.WorldType != EWorldType::Game && World.WorldType != EWorldType::PIE)
            || !World.bShouldSimulatePhysics || World.bIsTearingDown)
            return Fail(OutError, TEXT("Chaos pause diagnostic requires a live Game/PIE world with physics ticks enabled."));
        Scene = World.GetPhysicsScene();
        Solver = Scene ? Scene->GetSolver() : nullptr;
        if (!Solver) return Fail(OutError, TEXT("The default native Chaos scene/solver is missing."));
        if (!CheckConfiguration(OutError)) return false;
        if (KnownActors.IsEmpty()) return Fail(OutError, TEXT("A nonempty explicit fixture actor allowlist is required."));
        for (AActor* Actor : KnownActors)
        {
            if (!IsValid(Actor) || Actor->GetWorld() != &World)
                return Fail(OutError, TEXT("Fixture actor allowlist contains an expired or cross-world actor."));
            AllowedActors.Add(FObjectKey(Actor));
        }
        FInventory Inventory;
        if (!Inspect(Inventory, OutError)) return false;
        Report->SetObjectField(TEXT("before"), StateJson(Inventory));
        // GT has just performed the Jolt handoff. Positive frame 1 must apply it to PT and
        // buffer the resulting transient dirty entries; positive frame 2 replaces that buffer.
        Report->SetStringField(TEXT("admission_pt_state"), TEXT("Pre-admission PT state is recorded, not presumed current. GT must already have zero dynamics. Two ordinary measured positive-delta frames precede pause; every completed frame must have zero GT and PT dynamics and matching whole-world particle/object counts. No sample is dropped and no extra scene/world tick is injected."));
        OriginalPaused = Solver->IsPaused_External();
        if (OriginalPaused) return Fail(OutError, TEXT("The default solver was already paused; this diagnostic requires a known running baseline."));
        LastFrame = Solver->GetCurrentFrame();
        bOwned = true; // Includes armed ownership; early cancellation must release it cleanly.
        Report->SetBoolField(TEXT("armed"), true);
        Report->SetBoolField(TEXT("applied"), false);
        Report->SetBoolField(TEXT("original_paused"), OriginalPaused);
        Report->SetBoolField(TEXT("restored"), false);
        Report->SetNumberField(TEXT("begin_solver_frame"), LastFrame);
        Report->SetNumberField(TEXT("required_positive_delta_frames_before_pause"), PositiveFramesBeforePause);
        Report->SetBoolField(TEXT("positive_frames_remain_in_benchmark_samples"), true);
        Report->SetNumberField(TEXT("validated_positive_delta_frames"), 0);
        Report->SetNumberField(TEXT("validated_zero_delta_frames"), 0);
        Report->SetBoolField(TEXT("applied_paused"), false);
        return true;
    }

    bool ValidateFrame(const UObject& Owner, FJsonObject& FrameRow, FString& OutError)
    {
        OutError.Reset();
        if (!bOwned || OwnerKey != FObjectKey(&Owner))
            return Fail(OutError, TEXT("Completed Chaos maintenance frame has no matching diagnostic owner."));
        if (!CheckConfiguration(OutError)) return false;
        FInventory Inventory;
        if (!Inspect(Inventory, OutError)) return false;
        const int32 CurrentFrame = Solver->GetCurrentFrame();
        auto Row = StateJson(Inventory);
        Row->SetNumberField(TEXT("expected_solver_frame"), LastFrame + 1);
        Row->SetStringField(TEXT("phase"), bPauseApplied ? TEXT("paused_maintenance") : TEXT("measured_positive_delta_buffer_refresh"));
        FrameRow.SetObjectField(TEXT("paused_chaos_maintenance"), Row);
        const double ActualDt = double(Solver->GetLastDt());
        const bool bValidDt = bPauseApplied ? ActualDt == 0.0 : FMath::IsFinite(ActualDt) && ActualDt > 0.0;
        if (Solver->IsPaused_External() != bPauseApplied || !bValidDt || CurrentFrame != LastFrame + 1)
            return Fail(OutError, FString::Printf(TEXT("Chaos maintenance cadence failed: paused=%d expected=%d, dt=%.9f, frame=%d expected=%d."),
                Solver->IsPaused_External(), bPauseApplied, ActualDt, CurrentFrame, LastFrame + 1));
        if (Inventory.SolverDynamicOrSleeping)
            return Fail(OutError, TEXT("A completed diagnostic frame still has native PT dynamic/sleeping particles."));
        LastFrame = CurrentFrame;
        if (bPauseApplied)
        {
            ++ValidatedFrames;
        }
        else
        {
            ++ValidatedPositiveFrames;
            Report->SetNumberField(TEXT("validated_positive_delta_frames"), ValidatedPositiveFrames);
            if (ValidatedPositiveFrames == PositiveFramesBeforePause)
            {
                // Called only after this ordinary frame's full NN/Jolt/query validation. Its
                // timing and completed pose are retained exactly like every other sample.
                Solver->SetIsPaused_External(true);
                bPauseApplied = true;
                Report->SetBoolField(TEXT("armed"), false);
                Report->SetBoolField(TEXT("applied"), true);
                Report->SetBoolField(TEXT("applied_paused"), Solver->IsPaused_External());
                Report->SetNumberField(TEXT("applied_after_solver_frame"), CurrentFrame);
                Report->SetObjectField(TEXT("last_positive_delta_frame_before_pause"), Row);
            }
        }
        Report->SetNumberField(TEXT("validated_zero_delta_frames"), ValidatedFrames);
        Report->SetNumberField(TEXT("validated_total_frames"), ValidatedPositiveFrames + ValidatedFrames);
        Report->SetObjectField(TEXT("last_completed"), Row);
        return true;
    }

    bool Restore(const UObject& Owner, FString& OutError)
    {
        OutError.Reset();
        // Critical: temporary game-world teardown must not release the actual benchmark's solver.
        if (!bOwned || OwnerKey != FObjectKey(&Owner)) return true;
        if (!IsInGameThread()) return Fail(OutError, TEXT("Chaos pause restoration requires the owning game thread."));
        UWorld* World = WorldPtr.Get();
        if (!World || World->GetPhysicsScene() != Scene || Scene->GetSolver() != Solver)
            return Fail(OutError, TEXT("Owned Chaos scene lifetime changed before restoration; no unrelated solver was modified."));
        if (!Scene->IsCompletionEventComplete())
            return Fail(OutError, TEXT("Owned Chaos scene is still executing during restoration."));
        FInventory BeforeRestore;
        FString InventoryError;
        const bool bInventoryValid = Inspect(BeforeRestore, InventoryError);
        Report->SetObjectField(TEXT("before_restore"), StateJson(BeforeRestore));
        const bool bStillOwnedPause = Solver->IsPaused_External() == bPauseApplied;
        // Restore even if an audit or external pause mutation was found. Never strand our flag.
        Solver->SetIsPaused_External(OriginalPaused);
        bOwned = false;
        Report->SetBoolField(TEXT("armed"), false);
        Report->SetBoolField(TEXT("restored"), Solver->IsPaused_External() == OriginalPaused);
        Report->SetBoolField(TEXT("restored_paused"), Solver->IsPaused_External());
        Report->SetObjectField(TEXT("after_restore"), StateJson(BeforeRestore));
        Report->SetStringField(TEXT("restoration_scope"), TEXT("Original pause flag restored at the settled scene boundary. The separate controlled test verifies that the next ordinary frame has positive dt again; no extra frame is injected into benchmark teardown."));
        if (!bStillOwnedPause) return Fail(OutError, TEXT("The owned Chaos pause flag was changed externally before restoration."));
        if (!bInventoryValid) return Fail(OutError, InventoryError);
        return true;
    }

    TSharedPtr<FJsonObject> Json() const
    {
        if (Report) return Report;
        auto Row = MakeShared<FJsonObject>();
        Row->SetBoolField(TEXT("requested"), false);
        Row->SetBoolField(TEXT("applied"), false);
        return Row;
    }

private:
    bool Fail(FString& OutError, const FString& Error)
    {
        OutError = Error;
        if (Report) Report->SetStringField(TEXT("error"), Error);
        return false;
    }

    bool CheckConfiguration(FString& OutError)
    {
        UWorld* World = WorldPtr.Get();
        if (!IsInGameThread() || !World || World->bIsTearingDown || !World->bShouldSimulatePhysics
            || World->GetPhysicsScene() != Scene || !Scene || Scene->GetSolver() != Solver)
            return Fail(OutError, TEXT("Chaos diagnostic world/scene identity or normal physics ticking changed."));
        if (!Scene->IsCompletionEventComplete())
            return Fail(OutError, TEXT("Chaos particle inspection requires a completed physics scene."));
        if (UPhysicsSettings::Get()->bTickPhysicsAsync || UPhysicsSettings::Get()->bSubstepping
            || Solver->IsUsingAsyncResults() || Solver->IsUsingFixedDt() || Solver->IsStandaloneSolver()
            || Solver->GetMaxSubSteps_External() > 1)
            return Fail(OutError, FString::Printf(TEXT("Paused maintenance requires variable-dt, non-async, non-substepped default scenes: settingsAsync=%d settingsSubstep=%d asyncResults=%d fixedDt=%d standalone=%d maxSubsteps=%d. Other modes do not guarantee one zero-dt task per normal frame."),
                UPhysicsSettings::Get()->bTickPhysicsAsync, UPhysicsSettings::Get()->bSubstepping,
                Solver->IsUsingAsyncResults(), Solver->IsUsingFixedDt(), Solver->IsStandaloneSolver(), Solver->GetMaxSubSteps_External()));
        // GetSolvers reads a module-owned map; protect that map without retaining the lock while
        // acquiring the unrelated scene read lock below. The default solver is checked separately.
        TArray<const Chaos::FPhysicsSolverBase*> Solvers;
        {
            FChaosScopeSolverLock Lock;
            FChaosSolversModule::GetModule()->GetSolvers(World, Solvers);
        }
        for (const Chaos::FPhysicsSolverBase* Candidate : Solvers)
            if (Candidate != Solver)
                return Fail(OutError, TEXT("An additional world Chaos solver is present; this default-scene diagnostic refuses it."));
        return true;
    }

    bool Inspect(FInventory& Out, FString& OutError)
    {
        UWorld* World = WorldPtr.Get();
        if (!World || !Scene || !Solver || !Scene->IsCompletionEventComplete())
            return Fail(OutError, TEXT("Whole-world native inventory requires the live settled scene."));
        TSet<Chaos::FConstPhysicsObjectHandle> Objects;
        auto Read = FPhysicsObjectExternalInterface::LockRead(Scene);
        // Component iteration includes native physics receivers not listed in the benchmark's
        // Meshes array (notably APawn root capsules, ISMs and any unexpected world primitives).
        for (TObjectIterator<UPrimitiveComponent> It; It; ++It)
        {
            UPrimitiveComponent* Component = *It;
            if (!IsValid(Component) || Component->GetWorld() != World) continue;
            const TArray<Chaos::FPhysicsObjectHandle> Handles = Component->GetAllPhysicsObjects();
            bool bHasObject = false;
            for (Chaos::FConstPhysicsObjectHandle Handle : Handles)
            {
                if (!Handle) continue;
                bHasObject = true;
                if (!AllowedActors.Contains(FObjectKey(Component->GetOwner())))
                    return Fail(OutError, FString::Printf(TEXT("Unknown nonfixture native physics receiver: %s."), *Component->GetPathName()));
                if (Chaos::FPhysicsObjectInterface::GetSolver(Handle) != Solver)
                    return Fail(OutError, FString::Printf(TEXT("Native receiver uses a different solver: %s."), *Component->GetPathName()));
                if (Objects.Contains(Handle)) continue; // Welded aliases count one actual particle.
                Objects.Add(Handle);
                const auto* Particle = Read->GetParticle(Handle);
                if (!Particle)
                    return Fail(OutError, FString::Printf(TEXT("Native physics object has no accessible particle: %s."), *Component->GetPathName()));
                ++Out.Objects;
                switch (Particle->ObjectState())
                {
                case Chaos::EObjectStateType::Kinematic: ++Out.Kinematic; break;
                case Chaos::EObjectStateType::Static: ++Out.Static; break;
                case Chaos::EObjectStateType::Dynamic:
                case Chaos::EObjectStateType::Sleeping:
                    ++Out.DynamicOrSleeping;
                    return Fail(OutError, FString::Printf(TEXT("Refusing to pause a world with a native dynamic/sleeping receiver: %s."), *Component->GetPathName()));
                default:
                    return Fail(OutError, FString::Printf(TEXT("Unrecognized native object state on %s."), *Component->GetPathName()));
                }
            }
            if (bHasObject) ++Out.Components;
        }
        Read.Release();
        // This is a post-physics read, never a concurrent PT view. It also catches orphan/native
        // particles that no live UPrimitiveComponent exposes, rather than silently allowlisting them.
        for (auto& Particle : Solver->GetParticles().GetAllParticlesView())
        {
            ++Out.SolverParticles;
            const auto State = Particle.ObjectState();
            if (State == Chaos::EObjectStateType::Dynamic || State == Chaos::EObjectStateType::Sleeping)
                ++Out.SolverDynamicOrSleeping;
        }
        if (Out.SolverParticles != Out.Objects)
            return Fail(OutError, FString::Printf(TEXT("Whole-world native object/solver particle count mismatch: GT=%d PT=%d; unknown or unprocessed proxy state is not accepted."),
                Out.Objects, Out.SolverParticles));
        return true;
    }

    TSharedPtr<FJsonObject> StateJson(const FInventory& Inventory) const
    {
        auto Row = Inventory.Json();
        Row->SetBoolField(TEXT("paused"), Solver->IsPaused_External());
        Row->SetNumberField(TEXT("solver_frame"), Solver->GetCurrentFrame());
        Row->SetNumberField(TEXT("external_packet_timestamp"), Solver->GetMarshallingManager().GetExternalTimestamp_External());
        Row->SetNumberField(TEXT("solver_last_dt"), double(Solver->GetLastDt()));
        Row->SetNumberField(TEXT("world_delta_seconds"), WorldPtr->GetDeltaSeconds());
        Row->SetBoolField(TEXT("world_should_simulate_physics"), WorldPtr->bShouldSimulatePhysics);
        Row->SetNumberField(TEXT("solver_max_substeps"), Solver->GetMaxSubSteps_External());
        Row->SetBoolField(TEXT("scene_completion_complete"), Scene->IsCompletionEventComplete());
        return Row;
    }

    bool bAttempted = false;
    bool bOwned = false;
    bool bPauseApplied = false;
    bool OriginalPaused = false;
    FObjectKey OwnerKey;
    TWeakObjectPtr<UWorld> WorldPtr;
    FPhysScene* Scene = nullptr;
    Chaos::FPBDRigidsSolver* Solver = nullptr;
    TSet<FObjectKey> AllowedActors;
    int32 LastFrame = 0;
    int32 ValidatedFrames = 0;
    int32 ValidatedPositiveFrames = 0;
    TSharedPtr<FJsonObject> Report;
};

FControl Control;
}

bool IsRequested()
{
    return FParse::Param(FCommandLine::Get(), TEXT("PhysicsBenchPauseChaos"));
}

bool Begin(const UObject& Owner, UWorld& World,
    TConstArrayView<TObjectPtr<AActor>> KnownActors, FString& OutError)
{
    OutError.Reset();
    if (!IsRequested()) return true;
    if (!FParse::Param(FCommandLine::Get(), TEXT("ProphecyPhysicsBenchmark")))
    { OutError = TEXT("Chaos pause control is restricted to the isolated physics benchmark."); return false; }
    TArray<TObjectPtr<AActor>, TInlineAllocator<128>> AllowedActors;
    AllowedActors.Append(KnownActors.GetData(), KnownActors.Num());
    // Entry's ordinary GameModeBase creates this possessed bootstrap pawn independently of the
    // crowd fixture. Retain it in both A/B workloads; all its native objects still require the
    // same zero-dynamic, solver and lifetime checks. No arbitrary pawn class is admitted here.
    APlayerController* Controller = World.GetFirstPlayerController();
    APawn* Pawn = Controller ? Controller->GetPawn() : nullptr;
    AGameModeBase* Mode = World.GetAuthGameMode();
    const bool bBootstrap = IsValid(Controller) && IsValid(Pawn) && IsValid(Mode)
        && Controller->GetWorld() == &World && Pawn->GetWorld() == &World
        && Pawn->GetController() == Controller && Pawn->GetClass() == ADefaultPawn::StaticClass()
        && Mode->GetClass() == AGameModeBase::StaticClass();
    auto Bootstrap = MakeShared<FJsonObject>();
    Bootstrap->SetBoolField(TEXT("admitted"), bBootstrap);
    Bootstrap->SetStringField(TEXT("controller"), GetPathNameSafe(Controller));
    Bootstrap->SetStringField(TEXT("pawn"), GetPathNameSafe(Pawn));
    Bootstrap->SetStringField(TEXT("pawn_class"), Pawn ? Pawn->GetClass()->GetPathName() : TEXT("None"));
    Bootstrap->SetStringField(TEXT("game_mode_class"), Mode ? Mode->GetClass()->GetPathName() : TEXT("None"));
    if (bBootstrap) AllowedActors.Add(Pawn);
    const bool bResult = Control.Begin(Owner, World, AllowedActors, OutError);
    Control.Json()->SetObjectField(TEXT("entry_bootstrap_pawn"), Bootstrap);
    return bResult;
}

bool ValidateFrame(const UObject& Owner, FJsonObject& FrameRow, FString& OutError)
{
    OutError.Reset();
    return !IsRequested() || Control.ValidateFrame(Owner, FrameRow, OutError);
}

bool Restore(const UObject& Owner, FString& OutError)
{
    return Control.Restore(Owner, OutError);
}

TSharedPtr<FJsonObject> ToJson() { return Control.Json(); }
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Components/CapsuleComponent.h"
#include "Engine/Engine.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"

namespace ProphecyJolt::BenchmarkChaosPause
{
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltPausedSceneMaintenanceTest,
    "Prophecy.Jolt.QueryPose.PausedSceneMaintenanceLifecycle",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltPausedSceneMaintenanceTest::RunTest(const FString&)
{
    // Match the explicit synchronous benchmark workload, then restore project settings after
    // the owned world is destroyed. The project's ordinary default enables substepping.
    TGuardValue<bool> SubstepSetting(UPhysicsSettings::Get()->bSubstepping, false);
    TGuardValue<bool> AsyncSetting(UPhysicsSettings::Get()->bTickPhysicsAsync, false);
    struct FWorldFixture
    {
        UWorld* World = nullptr;
        FWorldFixture()
        {
            const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
                .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
                .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
            World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
            if (World && GEngine) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
        }
        ~FWorldFixture()
        {
            if (!World) return;
            World->DestroyWorld(false);
            if (GEngine) GEngine->DestroyWorldContext(World);
            World->MarkAsGarbage();
        }
    } Fixture;
    UWorld* World = Fixture.World;
    if (!TestNotNull(TEXT("Owned query-only game world"), World)) return false;
    FPhysScene* Scene = World->GetPhysicsScene();
    if (!TestNotNull(TEXT("Owned native scene"), Scene) || !TestNotNull(TEXT("Owned default solver"), Scene->GetSolver())) return false;
    Chaos::FPBDRigidsSolver* Solver = Scene->GetSolver();
    const bool OriginalPause = Solver->IsPaused_External();
    if (!TestFalse(TEXT("Controlled baseline is initially unpaused"), OriginalPause)) return false;
    ON_SCOPE_EXIT { Scene->WaitPhysScenes(); Solver->SetIsPaused_External(OriginalPause); };

    const FVector Gravity = FVector::ZeroVector;
    const auto AdvanceScene = [&]()
    {
        // The same public Start/End scene lifecycle as UWorld's native physics ticks.
        // The nonzero world request is intentionally retained while solver integration is paused.
        Scene->SetUpForFrame(&Gravity, 1.0f / 60.0f, 0.0f, 1.0f / 60.0f, 1.0f / 60.0f, 1, false);
        Scene->StartFrame();
        Scene->WaitPhysScenes();
        Scene->EndFrame();
    };
    const auto NativeParticleCount = [&]() { return Solver->GetParticles().GetAllParticlesView().Num(); };
    const auto AddCapsule = [&](AActor& Actor, FVector Center)
    {
        auto* Capsule = NewObject<UCapsuleComponent>(&Actor);
        Actor.AddInstanceComponent(Capsule);
        Actor.SetRootComponent(Capsule);
        Capsule->SetMobility(EComponentMobility::Movable);
        Capsule->SetCapsuleSize(4.0f, 7.0f);
        Capsule->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        Capsule->SetCollisionObjectType(ECC_WorldDynamic);
        Capsule->SetCollisionResponseToAllChannels(ECR_Block);
        Capsule->SetWorldLocation(Center);
        Capsule->RegisterComponent();
        Capsule->SetSimulatePhysics(false);
        return Capsule;
    };
    AdvanceScene();
    if (!TestTrue(TEXT("Ordinary baseline frame integrates positive dt"), Solver->GetLastDt() > 0.0)) return false;

    AActor* Receiver = World->SpawnActor<AActor>();
    AActor* StimulusActor = World->SpawnActor<AActor>();
    AActor* OtherOwner = World->SpawnActor<AActor>();
    if (!TestNotNull(TEXT("Allowed receiver actor"), Receiver) || !TestNotNull(TEXT("Independent tree stimulus actor"), StimulusActor)
        || !TestNotNull(TEXT("Unrelated owner actor"), OtherOwner)) return false;
    TArray<TObjectPtr<AActor>> Allowed{ Receiver, StimulusActor };
    // Reproduce the real fixture's dynamic warmup before GT hands ownership to Jolt.
    // The first positive refresh must buffer the transient dynamic->kinematic change;
    // another ordinary positive frame replaces those transition results before pause.
    UCapsuleComponent* WarmupCapsule = AddCapsule(*Receiver, FVector(3000.0, 1000.0, 1000.0));
    WarmupCapsule->SetSimulatePhysics(true);
    WarmupCapsule->SetPhysicsLinearVelocity(FVector(60.0, 0.0, 0.0));
    AdvanceScene();
    int32 WarmupDynamicParticles = 0;
    for (auto& Particle : Solver->GetParticles().GetAllParticlesView())
        if (Particle.ObjectState() == Chaos::EObjectStateType::Dynamic || Particle.ObjectState() == Chaos::EObjectStateType::Sleeping)
            ++WarmupDynamicParticles;
    if (!TestTrue(TEXT("Actual dynamic warmup reaches native PT"), WarmupDynamicParticles > 0)) return false;
    WarmupCapsule->SetSimulatePhysics(false);
    const FVector WarmupCenter = WarmupCapsule->GetComponentLocation();
    FString Error;
    // Owning cancellation before any ordinary refresh frame must leave the original flag.
    FControl CancelledControl;
    if (!CancelledControl.Begin(*World, *World, Allowed, Error)) { AddError(Error); return false; }
    if (!TestFalse(TEXT("Armed cancellation control does not immediately pause"), Solver->IsPaused_External())
        || !TestTrue(TEXT("Armed owner can cancel before the first completed frame"), CancelledControl.Restore(*World, Error))
        || !TestFalse(TEXT("Armed cancellation keeps the solver running"), Solver->IsPaused_External())) return false;
    FControl LocalControl;
    if (!LocalControl.Begin(*World, *World, Allowed, Error)) { AddError(Error); return false; }
    ON_SCOPE_EXIT
    {
        FString RestoreError;
        if (!LocalControl.Restore(*World, RestoreError)) AddError(RestoreError);
    };
    // An unrelated subsystem/world identity is never permitted to release another owner's pause.
    if (!TestTrue(TEXT("Unrelated restore is harmless"), LocalControl.Restore(*OtherOwner, Error))
        || !TestFalse(TEXT("Unrelated restore retained armed running state"), Solver->IsPaused_External())) return false;
    const auto TraceAt = [&](FVector Center, UPrimitiveComponent* Expected, bool bExpectedHit)
    {
        FHitResult Hit;
        const bool bHit = World->LineTraceSingleByChannel(Hit, Center - FVector(12.0, 0.0, 0.0),
            Center + FVector(12.0, 0.0, 0.0), ECC_Visibility);
        return TestEqual(TEXT("Native query hit presence"), bHit, bExpectedHit)
            && (!bExpectedHit || (TestTrue(TEXT("Original native query receiver identity"), Hit.GetComponent() == Expected)
                && TestNearlyEqual(TEXT("Actual capsule analytic entry point"), Hit.ImpactPoint, Center - FVector(4.0, 0.0, 0.0), 0.02f)));
    };
    const auto Maintenance = [&]()
    {
        AdvanceScene();
        FJsonObject Row;
        if (!LocalControl.ValidateFrame(*World, Row, Error)) { AddError(Error); return false; }
        return true;
    };
    for (int32 PositiveFrame = 1; PositiveFrame <= FControl::PositiveFramesBeforePause; ++PositiveFrame)
    {
        if (!TestFalse(TEXT("Required refresh frame begins with the solver running"), Solver->IsPaused_External())
            || !Maintenance()
            || !TestTrue(TEXT("Every required refresh frame integrates positive dt"), Solver->GetLastDt() > 0.0)
            || !TraceAt(WarmupCenter, WarmupCapsule, true)) return false;
        if (!TestEqual(TEXT("Pause activates only after the final counted positive frame"), Solver->IsPaused_External(),
            PositiveFrame == FControl::PositiveFramesBeforePause)) return false;
    }
    if (!TestEqual(TEXT("Both positive refresh frames are recorded"),
        LocalControl.Json()->GetNumberField(TEXT("validated_positive_delta_frames")), double(FControl::PositiveFramesBeforePause))
        || !TestEqual(TEXT("No zero-delta maintenance frame has yet occurred"),
            LocalControl.Json()->GetNumberField(TEXT("validated_zero_delta_frames")), 0.0)) return false;
    WarmupCapsule->DestroyComponent();
    // A separate allowed receiver forces newer PT trees while the tested capsule stays still.
    // It cannot refresh the tested capsule's UniqueIdx entry in the pending external queue.
    UCapsuleComponent* Stimulus = AddCapsule(*StimulusActor, FVector(9000.0, 9000.0, 9000.0));
    if (!Maintenance() || !TestEqual(TEXT("First paused maintenance step is actually zero dt"), double(Solver->GetLastDt()), 0.0)
        || !TestNotNull(TEXT("Native external tree"), Scene->GetSpacialAcceleration())) return false;
    const int32 BaselineParticles = NativeParticleCount();
    int32 StimulusStep = 0;
    // Three actual registrations and removals test a bounded proxy lifecycle, not just a static
    // scene that happens to retain its old external tree while all commands remain unprocessed.
    for (int32 Cycle = 0; Cycle < 3; ++Cycle)
    {
        const FVector OldCenter(1000.0 + Cycle * 400.0, 1000.0, 1000.0);
        const FVector NewCenter = OldCenter + FVector(150.0, 0.0, 0.0);
        UCapsuleComponent* Capsule = AddCapsule(*Receiver, OldCenter);
        if (!TestNotNull(TEXT("Registered real native capsule"), Capsule)) return false;
        if (!Maintenance() || !TestEqual(TEXT("Spawned proxy reaches PT during zero-dt maintenance"), NativeParticleCount(), BaselineParticles + 1)
            || !TraceAt(OldCenter, Capsule, true)) return false;
        const int32 MovePacketTimestamp = Solver->GetMarshallingManager().GetExternalTimestamp_External();
        // Match real APawn root movement. A teleport would additionally dirty X/R and would miss
        // the kinematic-target-only maintenance failure this control is intended to detect.
        Capsule->SetWorldLocation(NewCenter, false, nullptr, ETeleportType::None);
        if (!TraceAt(NewCenter, Capsule, true) || !TraceAt(OldCenter, nullptr, false)) return false;
        bool bReturnedNewerStationaryTree = false;
        for (int32 StationaryFrame = 0; StationaryFrame < 8; ++StationaryFrame)
        {
            Stimulus->SetWorldLocation(FVector(9000.0 + ++StimulusStep * 2.0, 9000.0, 9000.0), false, nullptr, ETeleportType::None);
            if (!Maintenance() || !TraceAt(NewCenter, Capsule, true) || !TraceAt(OldCenter, nullptr, false)) return false;
            const int32 ReturnedTimestamp = Scene->GetSpacialAcceleration()->GetSyncTimestamp();
            // Strictly newer: the tested body's older pending external update must now have been
            // consumed/removed. Current rays cannot succeed solely through a refreshed GT entry.
            bReturnedNewerStationaryTree |= ReturnedTimestamp > MovePacketTimestamp;
            AddInfo(FString::Printf(TEXT("Paused stationary capsule cycle=%d frame=%d move packet=%d returned tree=%d; no further tested-body writes."),
                Cycle, StationaryFrame, MovePacketTimestamp, ReturnedTimestamp));
        }
        if (!TestTrue(TEXT("A strictly newer PT tree returned while the tested capsule remained stationary"), bReturnedNewerStationaryTree)) return false;
        Capsule->DestroyComponent();
        if (!TraceAt(NewCenter, nullptr, false) || !Maintenance()
            || !TestEqual(TEXT("Removed proxy/particle is retired by ordinary zero-dt maintenance"), NativeParticleCount(), BaselineParticles)
            || !TraceAt(NewCenter, nullptr, false)) return false;
        AddInfo(FString::Printf(TEXT("Paused lifecycle cycle %d: spawn/move150cm/remove, solver frame=%d, dt=%.9f, particles returned to %d."),
            Cycle, Solver->GetCurrentFrame(), double(Solver->GetLastDt()), BaselineParticles));
    }
    if (!LocalControl.Restore(*World, Error)) { AddError(Error); return false; }
    if (!TestFalse(TEXT("Exact original pause state restored"), Solver->IsPaused_External())) return false;
    AdvanceScene();
    if (!TestTrue(TEXT("Next ordinary scene frame again integrates positive dt"), Solver->GetLastDt() > 0.0)) return false;

    // These use independent ownership instances, never the benchmark's process-global controller.
    UCapsuleComponent* Unknown = AddCapsule(*OtherOwner, FVector(8000.0, 1000.0, 1000.0));
    AdvanceScene();
    FControl UnknownControl;
    TestFalse(TEXT("A nonfixture native receiver refuses admission"), UnknownControl.Begin(*World, *World, Allowed, Error));
    TestTrue(TEXT("Unknown-receiver error is explicit"), Error.Contains(TEXT("Unknown nonfixture")));
    TestFalse(TEXT("Rejected unknown receiver never pauses the scene"), Solver->IsPaused_External());
    Unknown->DestroyComponent();
    AdvanceScene();
    UCapsuleComponent* Dynamic = AddCapsule(*Receiver, FVector(8000.0, 1000.0, 1000.0));
    Dynamic->SetSimulatePhysics(true);
    AdvanceScene();
    FControl DynamicControl;
    TestFalse(TEXT("An allowlisted but actually dynamic Chaos body refuses admission"), DynamicControl.Begin(*World, *World, Allowed, Error));
    TestTrue(TEXT("Dynamic rejection is explicit"), Error.Contains(TEXT("dynamic/sleeping")));
    TestFalse(TEXT("Rejected dynamic receiver never pauses the scene"), Solver->IsPaused_External());
    Dynamic->DestroyComponent();
    AdvanceScene();
    return !HasAnyErrors();
}
}
#endif
