// Draft only. Insert before RuntimeSelfCollisionControls in ProphecyJoltSwordFixture.cpp
// after the running build has finished and the production edit gate is cleared.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltBackendPreferenceTest,
    "Prophecy.Jolt.Character.BackendPreferenceAcrossModes",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltBackendPreferenceTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::SwordFixture;
    FWorldFixture Fixture;
    const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
        .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
    Fixture.World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
    if (!TestNotNull(TEXT("Backend preference world"), Fixture.World) || !TestNotNull(TEXT("Engine"), GEngine)) return false;
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(Fixture.World);
    Fixture.World->InitializeActorsForPlay(FURL());
    Fixture.World->GetWorldSettings()->NotifyBeginPlay();
    auto* World = Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    auto* Coordinator = Fixture.World->GetSubsystem<UProphecyJoltCharacterWorldSubsystem>();
    if (!TestNotNull(TEXT("Native backend world"), World) || !TestNotNull(TEXT("Native coordinator"), Coordinator)) return false;
    FProphecyJoltWorldSettings Settings;
    Settings.GravityCmPerSecondSquared = FVector::ZeroVector;
    Settings.WorkerThreads = 0;
    if (!TestTrue(TEXT("Initialize native backend world"), World->InitializeSimulation(Settings).IsSuccess())) return false;
    FString Error;
    AProphecyAgent* Agent = nullptr;
    FProphecyJoltRigSnapshot Captured;
    if (!PrepareAgent(Fixture, Agent, Error, PoseId, FTransform(FVector(0, 0, 400)), &Captured))
    { AddError(Error); return false; }
    auto* Character = Agent->GetJoltCharacterComponent();
    auto* Mesh = Agent->GetPoseReferenceMesh();
    const auto CheckOwnership = [&](EProphecyAgentSimulationMode Mode, bool bJolt)
    {
        FProphecyJoltWorldDiagnostics Diagnostics;
        int32 CurrentPoseId = INDEX_NONE;
        float Interval = 0.0f;
        bool bInterpolate = false;
        return Agent->GetSimulationMode() == Mode && Agent->IsJoltPhysicalAnimationEnabled() == bJolt
            && Agent->GetJoltCharacterComponent() == Character && Agent->GetPoseReferenceMesh() == Mesh
            && Agent->GetNNPoseDataSource(CurrentPoseId, Interval, bInterpolate) && CurrentPoseId == PoseId
            && Character->IsJoltPhysical() == bJolt && !Character->IsEnablePending()
            && World->GetDiagnostics(Diagnostics).IsSuccess() && !Diagnostics.bFaulted
            && Diagnostics.BodyCount == (bJolt ? 22 : 0) && Diagnostics.ConstraintCount == (bJolt ? 21 : 0)
            && Coordinator->GetRegisteredCharacterCount() == (bJolt ? 1 : 0)
            && Mesh->IsAnySimulatingPhysics() == (!bJolt && Mode != EProphecyAgentSimulationMode::Kinematic);
    };
    if (!TestTrue(TEXT("Fresh Sim owns exactly one Jolt rig"), CheckOwnership(EProphecyAgentSimulationMode::Physical, true))) return false;
    for (int32 Cycle = 0; Cycle < 2; ++Cycle)
    {
        if (!TestTrue(TEXT("Kinematic releases Jolt bodies and registration"),
            Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic)
            && CheckOwnership(EProphecyAgentSimulationMode::Kinematic, false))
            || !TestTrue(TEXT("HalfSim uses its existing Chaos controller"), Agent->SetSimulationMode(EProphecyAgentSimulationMode::HalfSim)
            && CheckOwnership(EProphecyAgentSimulationMode::HalfSim, false))) return false;
        TArray<FTransform> BeforePose;
        TArray<FVector> BeforeLinear, BeforeAngular;
        for (const auto& Source : Captured.Bodies)
        {
            const FBodyInstance* Body = Mesh->GetBodyInstance(Source.BodyName);
            if (!TestTrue(TEXT("HalfSim owns every actual dynamic body"), Body && Body->IsInstanceSimulatingPhysics())) return false;
            BeforePose.Add(Body->GetUnrealWorldTransform());
            BeforeLinear.Add(Body->GetUnrealWorldVelocity());
            BeforeAngular.Add(Body->GetUnrealWorldAngularVelocityInRadians());
        }
        if (!TestTrue(TEXT("Return to Sim restores selected Jolt backend"), Agent->SetSimulationMode(EProphecyAgentSimulationMode::Physical)
            && CheckOwnership(EProphecyAgentSimulationMode::Physical, true))) return false;
        for (int32 Index = 0; Index < Captured.Bodies.Num(); ++Index)
        {
            FTransform After;
            FVector Linear, Angular;
            bool bSimulating = false;
            if (!TestTrue(TEXT("HalfSim-to-Jolt handoff preserves physical body pose and velocities"),
                Character->GetBodyState(Captured.Bodies[Index].BodyName, After, Linear, Angular, bSimulating) && bSimulating
                && After.GetLocation().Equals(BeforePose[Index].GetLocation(), 0.02)
                && After.GetRotation().Equals(BeforePose[Index].GetRotation(), 1.0e-5)
                && Linear.Equals(BeforeLinear[Index], 1.0e-4) && Angular.Equals(BeforeAngular[Index], 1.0e-4))) return false;
        }
        if (!Character->PublishAuthoredTargets(StepSeconds, Error) || !Character->StepAndPublish(StepSeconds, Error))
        { AddError(Error); return false; }
    }
    Agent->DisableJoltPhysicalAnimation();
    if (!TestTrue(TEXT("Explicit active disable selects Chaos for later Sim"),
        CheckOwnership(EProphecyAgentSimulationMode::Kinematic, false)
        && Agent->SetSimulationMode(EProphecyAgentSimulationMode::Physical)
        && CheckOwnership(EProphecyAgentSimulationMode::Physical, false))) return false;
    if (!TestTrue(TEXT("Explicit enable can select Jolt again"), Agent->EnableJoltPhysicalAnimation()
        && CheckOwnership(EProphecyAgentSimulationMode::Physical, true))
        || !Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic)) return false;
    Agent->DisableJoltPhysicalAnimation(); // Already Kinematic: clear the retained choice too.
    if (!TestTrue(TEXT("A rejected HalfSim admission does not select Jolt"),
        Agent->SetSimulationMode(EProphecyAgentSimulationMode::HalfSim) && !Agent->EnableJoltPhysicalAnimation()
        && Agent->SetSimulationMode(EProphecyAgentSimulationMode::Physical)
        && CheckOwnership(EProphecyAgentSimulationMode::Physical, false))) return false;
    if (!Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic)) return false;

    // Exercise real late-world-tick admission/cancellation, without editing coordinator flags.
    bool bRequested = false, bPending = false, bCancelled = false;
    const FDelegateHandle LateRequest = FWorldDelegates::OnWorldPostActorTick.AddLambda(
        [&](UWorld* TickingWorld, ELevelTick, float)
        {
            if (TickingWorld != Fixture.World || bRequested) return;
            bRequested = true;
            const bool bAccepted = Agent->EnableJoltPhysicalAnimation();
            bPending = bAccepted && Character->IsEnablePending() && !Character->IsJoltPhysical();
            bCancelled = Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic)
                && !Character->IsEnablePending() && !Character->OnDeferredEnableCompleted.IsBound();
        });
    Fixture.World->Tick(LEVELTICK_All, StepSeconds);
    FWorldDelegates::OnWorldPostActorTick.Remove(LateRequest);
    Fixture.World->Tick(LEVELTICK_All, StepSeconds);
    if (!TestTrue(TEXT("Cancelled deferred admission cannot latch a new Jolt preference"), bRequested && bPending && bCancelled
        && CheckOwnership(EProphecyAgentSimulationMode::Kinematic, false)
        && Agent->SetSimulationMode(EProphecyAgentSimulationMode::Physical)
        && CheckOwnership(EProphecyAgentSimulationMode::Physical, false))) return false;
    TestTrue(TEXT("Backend preference fixture leaves no orphan rig"),
        Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic)
        && CheckOwnership(EProphecyAgentSimulationMode::Kinematic, false));
    TestTrue(TEXT("Backend preference native world shuts down cleanly"), World->ShutdownSimulation().IsSuccess());
    return !HasAnyErrors();
}
