#include "CoreMinimal.h"
#include "ProphecyAgent.h"
#include "ProphecySwordAttackCollision.h"
#include "ProphecySwordComponent.h"
#include "ProphecySwordPhysicsLibrary.h"
#include "ProphecyAngularLimits.h"
#include "ProphecyJoltBodyComponent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyPhysicsSkeletalMeshComponent.h"
#include "ProphecyJointDampingLibrary.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "PhysicsProxy/SingleParticlePhysicsProxy.h"
#include "ProphecyJoltCharacterWorldSubsystem.h"
#include "ProphecyJoltSceneCollisionComponent.h"
#include "ProphecyJoltRig.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltPhysicsCommand.h"
#include "ProphecyNNLocomotionAnimInstance.h"
#include "ProphecyNNPoseTypes.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/EngineBaseTypes.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/WorldSettings.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "PhysicsEngine/PhysicsConstraintTemplate.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

// Reuse the existing actual-asset capture/preparation, including its strict final hull limit.
namespace ProphecyJolt::StandaloneFixture { bool CaptureTrainingSword(FJsonObject& Report, FString& Error); }

namespace ProphecyJolt::SwordFixture
{
constexpr int32 PoseId = 997731;
constexpr float StepSeconds = 1.0f / 60.0f;
constexpr const TCHAR* TrainingPath = TEXT("/Game/_mygame/sword/geometry/Sword_GL01_Training.Sword_GL01_Training");

struct FWorldFixture
{
    UWorld* World = nullptr;
    bool bOwnPose = false;
    TArray<int32> AdditionalPoseIds;
    ~FWorldFixture()
    {
        if (World)
        {
            if (World->HasBegunPlay()) World->EndPlay(EEndPlayReason::Quit);
            World->DestroyWorld(false);
            if (GEngine) GEngine->DestroyWorldContext(World);
            World->MarkAsGarbage();
        }
        // Character EndPlay may restore the source animation; keep its pose alive until teardown ends.
        if (bOwnPose) FProphecyNNPoseStore::ClearAgentPose(PoseId);
        for (int32 Id : AdditionalPoseIds) FProphecyNNPoseStore::ClearAgentPose(Id);
    }
};

bool PrepareAgent(FWorldFixture& Fixture, AProphecyAgent*& Agent, FString& Error,
    int32 AgentPoseId = PoseId, const FTransform& Carrier = FTransform(FVector(0.0, 0.0, 400.0)),
    FProphecyJoltRigSnapshot* CapturedRig = nullptr)
{
    // Same manual PhysicalMesh construction and native pose source as PrepareManualAgent().
    USkeletalMesh* Asset = LoadObject<USkeletalMesh>(nullptr, TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
    UPhysicsAsset* PHAT = LoadObject<UPhysicsAsset>(nullptr,
        TEXT("/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin.PA_UEFN_Mannequin"));
    FProphecyNNPoseSnapshot Existing;
    if (!Asset || !PHAT || FProphecyNNPoseStore::GetAgentLocalPose(AgentPoseId, Existing))
    { Error = TEXT("Manual fixture assets are missing or its reserved pose ID is already in use."); return false; }
    const FVector Offset(3.935413, 0.0, -90.022712);
    const FTransform ActorWorld(Carrier.GetLocation() - Offset);
    Agent = Fixture.World->SpawnActorDeferred<AProphecyAgent>(AProphecyAgent::StaticClass(), ActorWorld,
        nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if (!Agent) { Error = TEXT("Could not spawn the native manual agent."); return false; }
    Agent->bManualNNPoseApplication = true;
    Agent->bAutoEnsureStandaloneNNManager = false;
    Agent->AutoPossessAI = EAutoPossessAI::Disabled;
    Agent->AutoPossessPlayer = EAutoReceiveInput::Disabled;
    Agent->bAutoPublishManualFollowerSubstepTargets = true;
    Agent->bEnableAttackFists = false;
    auto* Physical = NewObject<UProphecyPhysicsSkeletalMeshComponent>(Agent, TEXT("PhysicalMesh"));
    Agent->AddInstanceComponent(Physical);
    Physical->SetupAttachment(Agent->GetAgentCapsule());
    Physical->SetRelativeLocation(Offset);
    Physical->SetSkeletalMesh(Asset);
    Physical->SetPhysicsAsset(PHAT);
    Physical->SetCollisionProfileName(TEXT("PhysicsActor"));
    Physical->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    Physical->bEnableUpdateRateOptimizations = false;
    Physical->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    Physical->KinematicBonesUpdateType = EKinematicBonesUpdateToPhysics::SkipSimulatingBones;
    Physical->PhysicsTransformUpdateMode = EPhysicsTransformUpdateMode::SimulationUpatesComponentTransform;
    Physical->bUpdateJointsFromAnimation = false;
    Physical->bEnablePerPolyCollision = false;
    Physical->BodyInstance.bAutoWeld = false;
    Physical->SetSimulatePhysics(false);
    Physical->SetGenerateOverlapEvents(false);
    Physical->SetNotifyRigidBodyCollision(false);
    Physical->RegisterComponent();
    Physical->SetAllBodiesSimulatePhysics(false);
    Agent->GetAgentMesh()->SetSkeletalMesh(nullptr);
    Agent->GetAgentMesh()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Agent->FinishSpawning(ActorWorld);
    if (!Agent->IsActorInitialized() || !Agent->HasActorBegunPlay())
    { Error = TEXT("Manual agent did not complete normal actor initialization/BeginPlay."); return false; }
    Agent->GetAgentMesh()->SetComponentTickEnabled(false);
    Agent->ConfigureNNPoseDataSource(AgentPoseId, 1.0f / 30.0f, true);
    const FReferenceSkeleton& Ref = Asset->GetRefSkeleton();
    TArray<FName> Names;
    TArray<FTransform> Component;
    Component.SetNum(Ref.GetNum());
    const TArray<FTransform>& Local = Ref.GetRefBonePose();
    for (int32 Bone = 0; Bone < Ref.GetNum(); ++Bone)
    {
        Names.Add(Ref.GetBoneName(Bone));
        const int32 Parent = Ref.GetParentIndex(Bone);
        Component[Bone] = Parent == INDEX_NONE ? Local[Bone] : Local[Bone] * Component[Parent];
    }
    if (AgentPoseId == PoseId) Fixture.bOwnPose = true;
    else Fixture.AdditionalPoseIds.Add(AgentPoseId);
    FProphecyNNPoseStore::SetAgentLocalPose(AgentPoseId, Names, Local, Component, Component, Carrier, Carrier, 0.0, false);
    Physical->SetAnimInstanceClass(UProphecyNNLocomotionAnimInstance::StaticClass());
    auto* Anim = Cast<UProphecyNNLocomotionAnimInstance>(Physical->GetAnimInstance());
    if (!Anim) { Error = TEXT("Manual source animation initialization failed."); return false; }
    Anim->AgentId = AgentPoseId;
    Anim->NNPoseIntervalSeconds = 1.0f / 30.0f;
    Anim->bInterpolateNNPose = true;
    Physical->TickAnimation(0.0f, false);
    Physical->RefreshBoneTransforms();
    if (!Agent->SetSimulationMode(EProphecyAgentSimulationMode::Physical)
        || Agent->GetPoseReferenceMesh() != Physical || Physical->Bodies.Num() != 22 || Physical->Constraints.Num() != 21)
    { Error = TEXT("Manual PhysicalMesh did not produce its actual 22 bodies and 21 PHAT joints."); return false; }
    Agent->GetAgentCapsule()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    // Match the existing manual Jolt fixture's discrete character-body contract.
    Agent->SetMACDEnabled(false);
    for (FBodyInstance* BodyInstance : Physical->Bodies)
        if (BodyInstance) BodyInstance->SetUseCCD(false);
    if (CapturedRig && !Rig::CaptureLiveRig(*Physical, *CapturedRig, Error)) return false;
    if (!Agent->EnableJoltPhysicalAnimation())
    {
        const auto* Character = Agent->GetJoltCharacterComponent();
        Error = Character ? Character->GetLastError() : TEXT("Native Jolt character activation failed.");
        return false;
    }
    Agent->GetJoltCharacterComponent()->bAutomaticStep = false;
    return true;
}

bool Run(FJsonObject& Report, FString& Error)
{
    Report.SetStringField(TEXT("scope"), TEXT("One actual A_Sword/Training item and native manual PhysicalMesh; explicit functional steps, no rendering, inference, world ticks, cutting/blood validation or performance measurement."));
    Report.SetBoolField(TEXT("assets_saved"), false);
    Report.SetStringField(TEXT("stage"), TEXT("asset_preflight"));
    auto Preflight = MakeShared<FJsonObject>();
    const bool bPreflight = StandaloneFixture::CaptureTrainingSword(*Preflight, Error);
    Report.SetBoolField(TEXT("asset_preflight_passed"), bPreflight);
    Report.SetStringField(TEXT("training_mesh"), TrainingPath);
    if (!bPreflight)
    {
        if (Error.IsEmpty()) Error = TEXT("Actual Training collision failed native capture/preparation.");
        return false; // Invalid actual geometry is a failure, never a passing skip.
    }
    Report.SetStringField(TEXT("stage"), TEXT("manual_agent_setup"));
    FWorldFixture Fixture;
    const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
        .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
    Fixture.World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
    if (!Fixture.World || !GEngine) { Error = TEXT("Transient game world creation failed."); return false; }
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(Fixture.World);
    Fixture.World->InitializeActorsForPlay(FURL());
    Fixture.World->GetWorldSettings()->NotifyBeginPlay();
    auto* World = Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    auto* Coordinator = Fixture.World->GetSubsystem<UProphecyJoltCharacterWorldSubsystem>();
    FProphecyJoltWorldSettings Settings;
    Settings.GravityCmPerSecondSquared = FVector::ZeroVector;
    if (!World || !Coordinator) { Error = TEXT("Jolt world/coordinator missing."); return false; }
    const auto Initialized = World->InitializeSimulation(Settings);
    if (!Initialized.IsSuccess()) { Error = Initialized.Message; return false; }
    AProphecyAgent* Agent = nullptr;
    if (!PrepareAgent(Fixture, Agent, Error)) return false;
    auto* Character = Agent->GetJoltCharacterComponent();
    auto* Physical = Agent->GetPoseReferenceMesh();
    TArray<TSharedPtr<FJsonValue>> Checks;
    const auto Check = [&](bool bOkay, const TCHAR* Name)
    {
        auto Row = MakeShared<FJsonObject>();
        Row->SetStringField(TEXT("name"), Name); Row->SetBoolField(TEXT("passed"), bOkay);
        Checks.Add(MakeShared<FJsonValueObject>(Row)); Report.SetArrayField(TEXT("checks"), Checks);
        if (!bOkay && Error.IsEmpty()) Error = Name;
        return bOkay;
    };
    const auto Counts = [&](const TCHAR* Name, uint32 Bodies, uint32 Constraints, uint32 Joints, uint32 Pairs, int32 Clients)
    {
        FProphecyJoltWorldDiagnostics D;
        return Check(World->GetDiagnostics(D).IsSuccess() && !D.bFaulted && D.BodyCount == Bodies
            && D.ConstraintCount == Constraints && D.GenericJointCount == Joints && D.SuppressedBodyPairCount == Pairs
            && Coordinator->GetRegisteredStepClientCount() == Clients, Name);
    };
    if (!Counts(TEXT("character_only_22_bodies_21_joints"), 22, 21, 0, 0, 1)) return false;
    Report.SetStringField(TEXT("stage"), TEXT("equip_physical"));
    if (!Check(Agent->EquipSword(true), TEXT("actual_sword_physical_equip"))) return false;
    AActor* Sword = Agent->GetHeldSword();
    auto* Blade = Sword ? Cast<UStaticMeshComponent>(Sword->GetRootComponent()) : nullptr;
    auto* Body = Sword ? Sword->FindComponentByClass<UProphecyJoltBodyComponent>() : nullptr;
    if (!Check(Sword && Sword->HasActorBegunPlay() && Sword->GetClass()->GetPathName() == TEXT("/Game/_mygame/sword/A_Sword.A_Sword_C")
        && Blade && Blade->GetStaticMesh() && Blade->GetStaticMesh()->GetPathName() == TrainingPath
        && Body && Body->IsJoltBody() && !Body->IsEnablePending() && !Blade->IsAnySimulatingPhysics()
        && Blade->GetCollisionEnabled() == ECollisionEnabled::QueryOnly, TEXT("actual_blueprint_training_mesh_and_query_receiver"))) return false;
    Body->bAutomaticStep = false;
    if (!Check(Blade->BodyInstance.bUseCCD && !Blade->BodyInstance.GetUseMACD(),
        TEXT("physical_equip_retains_CCD_and_disables_MACD"))) return false;
    if (!Counts(TEXT("locomotion_excludes_only_gripping_hand"), 23, 22, 1, 1, 2)) return false;
    Agent->NotifySwordAttackState(true);
    if (!Counts(TEXT("attack_excludes_all_owner_bodies"), 23, 22, 1, 22, 2)) return false;
    Agent->NotifySwordAttackState(false);
    if (!Counts(TEXT("attack_end_restores_owner_collision"), 23, 22, 1, 1, 2)) return false;
    Agent->NotifySwordAttackState(true);
    // Both kinds of impulse prove the live native mass/inertia, without stepping or changing the grip.
    const auto ImpulseResponse = [&](FVector& Linear, FVector& Angular)
    {
        FProphecyJoltBodyHandle H;
        if (!Body->GetBodyHandle(H) || !Body->SetBodyVelocity({}, {}, false, Error)) return false;
        FProphecyJoltPhysicsCommand C;
        C.Operation = EProphecyJoltPhysicsCommand::Impulse; C.Value = FVector(1, 0, 0);
        if (!World->ExecutePhysicsCommand(H, C).IsSuccess()) return false;
        C.Operation = EProphecyJoltPhysicsCommand::AngularImpulse; C.Value = FVector(0, 0, 1);
        FProphecyJoltBodyState State;
        if (!World->ExecutePhysicsCommand(H, C).IsSuccess() || !Body->GetBodyState(State)) return false;
        Linear = State.CenterOfMassVelocityCmPerSecond; Angular = State.AngularVelocityRadiansPerSecond;
        return Body->SetBodyVelocity({}, {}, false, Error);
    };
    FVector BaseLinear, BaseAngular, ScaledLinear, ScaledAngular;
    if (!ImpulseResponse(BaseLinear, BaseAngular)
        || !Check(Agent->SetSwordInertiaScale(0.25f), TEXT("runtime_quarter_inertia_scale"))
        || !ImpulseResponse(ScaledLinear, ScaledAngular)
        || !Check(ScaledLinear.Equals(BaseLinear * 4, 1.e-5) && ScaledAngular.Equals(BaseAngular * 4, 1.e-5),
            TEXT("same_impulses_confirm_native_mass_and_inertia_quartered"))
        || !Check(!Agent->SetSwordInertiaScale(0) && Agent->GetSwordInertiaScale() == 0.25f,
            TEXT("zero_rejected_without_changing_scale"))) return false;
    const auto Step = [&]() { return Character->PublishAuthoredTargets(StepSeconds, Error) && Character->StepAndPublish(StepSeconds, Error); };
    if (!Step()) return false;
    const FTransform ExpectedGrip = Agent->SwordGripTransform * Physical->GetSocketTransform(Agent->SwordHandSocket);
    if (!Check(Blade->GetComponentTransform().Equals(ExpectedGrip, 0.02), TEXT("fixed_grip_keeps_authored_relative_frame_after_shared_step"))) return false;
    const auto Query = [&](AActor* Receiver, UStaticMeshComponent* Mesh, UProphecyJoltBodyComponent* Native)
    {
        FProphecyJoltBodyState State;
        if (!Native->GetBodyState(State)) return false;
        FVector Min, Max; Mesh->GetLocalBounds(Min, Max);
        const FVector Extent = Max - Min;
        const FVector Axis = Extent.X <= Extent.Y && Extent.X <= Extent.Z ? FVector::ForwardVector
            : Extent.Y <= Extent.Z ? FVector::RightVector : FVector::UpVector;
        const FVector Ray = Mesh->GetComponentQuat().RotateVector(Axis) * (Mesh->Bounds.SphereRadius + 50.0);
        FCollisionQueryParams Params(SCENE_QUERY_STAT(ProphecyJoltSwordFixture), false);
        if (IsValid(Agent)) Params.AddIgnoredActor(Agent);
        TArray<FHitResult> Hits;
        Fixture.World->LineTraceMultiByObjectType(Hits, State.CenterOfMassPositionCm + Ray, State.CenterOfMassPositionCm - Ray,
            FCollisionObjectQueryParams(ECC_PhysicsBody), Params);
        return Hits.ContainsByPredicate([&](const FHitResult& Hit) { return Hit.GetActor() == Receiver && Hit.GetComponent() == Mesh; });
    };
    if (!Check(Query(Sword, Blade, Body), TEXT("held_sword_immediate_UE_query_identity"))) return false;
    Report.SetStringField(TEXT("stage"), TEXT("attached_physical_roundtrip"));
    if (!Check(Agent->SetSwordSimulated(false) && Agent->GetHeldSword() == Sword && Body->IsJoltBody() && Body->IsAttachedCollider()
        && !Blade->IsAnySimulatingPhysics() && Blade->GetAttachParent() == Physical
        && Blade->GetCollisionEnabled() == ECollisionEnabled::QueryOnly, TEXT("attached_mode_welds_collider_without_grip_joint"))
        || !Counts(TEXT("attached_mode_native_body_and_owner_pairs"), 23, 21, 0, 22, 2)) return false;
    Agent->NotifySwordAttackState(false);
    if (!Counts(TEXT("attached_locomotion_allows_body_contacts"),23,21,0,1,2) || !Step()) return false;
    if (!Check(Agent->GetSwordAttachedInertiaScale()==1.0f && Agent->SetSwordAttachedInertiaScale(5.0f)
        && Agent->GetSwordAttachedInertiaScale()==5.0f && !Agent->SetSwordAttachedInertiaScale(-1)
        && Agent->GetSwordAttachedInertiaScale()==5.0f,TEXT("attached_inertia_runtime_set_get_and_reject_invalid")) || !Step()) return false;
    Agent->NotifySwordAttackState(true);
    if (!Counts(TEXT("attached_attack_disables_owner_contacts"),23,21,0,22,2) || !Step()) return false;
    if (!Check(Agent->SetSwordSimulated(true) && Body->IsJoltBody() && !Body->IsEnablePending()
        && !Blade->GetAttachParent() && Agent->GetHeldSword() == Sword, TEXT("same_item_returns_to_native_physical_grip"))
        || !Counts(TEXT("physical_roundtrip_restores_counts"), 23, 22, 1, 22, 2)) return false;
    if (!Step()) return false;
    Report.SetStringField(TEXT("stage"), TEXT("drop"));
    if (!ImpulseResponse(ScaledLinear, ScaledAngular)
        || !Check(ScaledLinear.Equals(BaseLinear * 4, 1.e-5), TEXT("scale_survives_attached_physical_roundtrip"))) return false;
    const FVector ExpectedDroppedAngular = ScaledAngular * 0.25;
    if (!Body->SetBodyVelocity(FVector(90.0, -40.0, 20.0), FVector(0.1, 0.2, -0.3), true, Error)) return false;
    FProphecyJoltBodyState BeforeDrop, AfterDrop;
    FProphecyJoltBodyHandle Handle, DroppedHandle;
    if (!Body->GetBodyState(BeforeDrop) || !Body->GetBodyHandle(Handle)) return false;
    AActor* Dropped = Agent->DropSword();
    if (!Check(Dropped == Sword && !Agent->GetHeldSword() && !Dropped->GetOwner() && Body->GetBodyHandle(DroppedHandle)
        && Handle.WorldLifetime == DroppedHandle.WorldLifetime && Handle.Slot == DroppedHandle.Slot && Handle.Generation == DroppedHandle.Generation
        && Body->GetBodyState(AfterDrop) && AfterDrop.CenterOfMassVelocityCmPerSecond.Equals(BeforeDrop.CenterOfMassVelocityCmPerSecond, 1.0e-6)
        && AfterDrop.AngularVelocityRadiansPerSecond.Equals(BeforeDrop.AngularVelocityRadiansPerSecond, 1.0e-6), TEXT("drop_preserves_native_body_identity_and_linear_angular_velocity"))
        || !Counts(TEXT("drop_removes_only_grip_and_pair_exclusions"), 23, 21, 0, 0, 2)) return false;
    if (!ImpulseResponse(ScaledLinear, ScaledAngular)
        || !Check(ScaledLinear.Equals(BaseLinear, 1.e-5) && ScaledAngular.Equals(ExpectedDroppedAngular, 1.e-5),
            TEXT("drop_restores_ordinary_mass_and_inertia"))
        || !Body->SetBodyVelocity(BeforeDrop.CenterOfMassVelocityCmPerSecond, BeforeDrop.AngularVelocityRadiansPerSecond, true, Error)) return false;
    if (!Step() || !Body->GetBodyState(AfterDrop)) return false;
    if (!Check(!AfterDrop.PositionCm.Equals(BeforeDrop.PositionCm, 0.01) && Query(Dropped, Blade, Body), TEXT("dropped_body_moves_and_keeps_UE_query_identity"))) return false;
    Report.SetStringField(TEXT("stage"), TEXT("drop_directly_from_attached"));
    if (!Check(Agent->EquipSword(false), TEXT("equip_attached_item_for_direct_drop"))) return false;
    if (!Check(Agent->GetSwordAttachedInertiaScale()==5.0f,TEXT("attached_inertia_preference_survives_modes_drop_and_equip"))) return false;
    AActor* Attached = Agent->GetHeldSword();
    AActor* AttachedDrop = Agent->DropSword();
    auto* AttachedBody = AttachedDrop ? AttachedDrop->FindComponentByClass<UProphecyJoltBodyComponent>() : nullptr;
    auto* AttachedBlade = AttachedDrop ? Cast<UStaticMeshComponent>(AttachedDrop->GetRootComponent()) : nullptr;
    if (!Check(AttachedDrop && AttachedDrop == Attached && !Agent->GetHeldSword()
        && AttachedBody && AttachedBody->IsJoltBody() && AttachedBlade
        && AttachedBlade->BodyInstance.bUseCCD && !AttachedBlade->BodyInstance.GetUseMACD(),
        TEXT("attached_direct_drop_admits_CCD_body_without_MACD"))
        || !Counts(TEXT("two_independent_drops_and_character"), 24, 21, 0, 0, 3)) return false;
    if (!Check(AttachedDrop->Destroy(), TEXT("attached_drop_cleanup"))
        || !Counts(TEXT("first_drop_and_character_remain"), 23, 21, 0, 0, 2)) return false;
    Report.SetStringField(TEXT("stage"), TEXT("owner_cleanup"));
    if (!Check(Agent->EquipSword(true), TEXT("equip_second_held_item_for_owner_cleanup"))) return false;
    AActor* Held = Agent->GetHeldSword();
    auto* HeldBody = Held ? Held->FindComponentByClass<UProphecyJoltBodyComponent>() : nullptr;
    FProphecyJoltBodyHandle HeldHandle;
    if (!Check(Held && Held != Dropped && HeldBody && HeldBody->GetBodyHandle(HeldHandle), TEXT("second_held_native_body_exists"))) return false;
    if (!Counts(TEXT("dropped_plus_held_and_character_counts"), 24, 22, 1, 22, 3)) return false;
    if (!Check(Agent->Destroy(), TEXT("normal_owner_destruction"))) return false;
    if (!Check(!World->OwnsBody(HeldHandle) && (!IsValid(Held) || Held->IsActorBeingDestroyed())
        && IsValid(Dropped) && !Dropped->IsActorBeingDestroyed() && World->OwnsBody(Handle), TEXT("owner_cleanup_removes_held_item_but_keeps_dropped_body"))
        || !Counts(TEXT("only_independent_dropped_body_remains"), 1, 0, 0, 0, 1)) return false;
    if (!Body->StepAndPublish(StepSeconds, Error) || !Check(Query(Dropped, Blade, Body), TEXT("dropped_body_steps_and_queries_after_owner_cleanup"))) return false;
    if (!Check(Dropped->Destroy(), TEXT("dropped_item_normal_destruction"))
        || !Counts(TEXT("all_native_bodies_joints_pairs_and_clients_retired"), 0, 0, 0, 0, 0)) return false;
    Report.SetStringField(TEXT("stage"), TEXT("complete"));
    return true;
}

void Command(const TArray<FString>& Args)
{
    if (Args.Num() != 1 || FPaths::IsRelative(Args[0]) || FPaths::FileExists(Args[0]))
    { UE_LOG(LogTemp, Error, TEXT("Prophecy.Jolt.SwordFixture requires one new absolute JSON path.")); return; }
    auto Report = MakeShared<FJsonObject>();
    FString Error;
    const bool bSucceeded = Run(*Report, Error);
    if (!bSucceeded && Error.IsEmpty()) Error = TEXT("Sword fixture failed at the reported stage without a native diagnostic.");
    Report->SetBoolField(TEXT("success"), bSucceeded);
    Report->SetStringField(TEXT("error"), Error);
    FString Text;
    const bool bSerialized = FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Text));
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Args[0]), true);
    const bool bSaved = bSerialized && FFileHelper::SaveStringToFile(Text, *Args[0], FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
        &IFileManager::Get(), FILEWRITE_NoReplaceExisting);
    if (!bSaved || !bSucceeded)
    { UE_LOG(LogTemp, Error, TEXT("Sword fixture failed: %s; report=%s; saved=%d"), *Error, *Args[0], bSaved); }
    else
    { UE_LOG(LogTemp, Display, TEXT("Sword fixture passed: %s"), *Args[0]); }
}
FAutoConsoleCommand ConsoleCommand(TEXT("Prophecy.Jolt.SwordFixture"),
    TEXT("Actual Training preflight, Jolt equip/modes/drop/cleanup in one transient world; one new absolute JSON path."),
    FConsoleCommandWithArgsDelegate::CreateStatic(&Command));

bool RunContact(FJsonObject& Report, FString& Error)
{
    Report.SetStringField(TEXT("scope"), TEXT("Actual dropped A_Sword/Training versus an imported UE static Cube floor in one shared Jolt world. Contact response is established by motion and native-floor removal control, not a contact callback count. No second-character, cutting, blood, rendering or performance coverage."));
    Report.SetBoolField(TEXT("assets_saved"), false);
    Report.SetStringField(TEXT("training_mesh"), TrainingPath);
    Report.SetStringField(TEXT("stage"), TEXT("asset_preflight"));
    auto Preflight = MakeShared<FJsonObject>();
    const bool bPreflight = StandaloneFixture::CaptureTrainingSword(*Preflight, Error);
    Report.SetBoolField(TEXT("asset_preflight_passed"), bPreflight);
    if (!bPreflight) return false;
    FWorldFixture Fixture;
    const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
        .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
    Fixture.World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
    if (!Fixture.World || !GEngine) { Error = TEXT("Transient contact world creation failed."); return false; }
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(Fixture.World);
    Fixture.World->InitializeActorsForPlay(FURL());
    Fixture.World->GetWorldSettings()->NotifyBeginPlay();
    auto* World = Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    auto* Coordinator = Fixture.World->GetSubsystem<UProphecyJoltCharacterWorldSubsystem>();
    FProphecyJoltWorldSettings Settings;
    Settings.GravityCmPerSecondSquared = FVector(0, 0, -981);
    if (!World || !Coordinator) { Error = TEXT("Shared Jolt world/coordinator missing."); return false; }
    const auto Initialized = World->InitializeSimulation(Settings);
    if (!Initialized.IsSuccess()) { Error = Initialized.Message; return false; }
    TArray<TSharedPtr<FJsonValue>> Checks;
    const auto Check = [&](bool bOkay, const TCHAR* Name)
    {
        auto Row = MakeShared<FJsonObject>();
        Row->SetStringField(TEXT("name"), Name); Row->SetBoolField(TEXT("passed"), bOkay);
        Checks.Add(MakeShared<FJsonValueObject>(Row)); Report.SetArrayField(TEXT("checks"), Checks);
        if (!bOkay && Error.IsEmpty()) Error = Name;
        return bOkay;
    };
    const auto Counts = [&](uint32 Bodies, int32 Clients)
    {
        FProphecyJoltWorldDiagnostics D;
        return World->GetDiagnostics(D).IsSuccess() && !D.bFaulted && D.BodyCount == Bodies
            && D.ConstraintCount == 0 && D.GenericJointCount == 0 && D.SuppressedBodyPairCount == 0
            && Coordinator->GetRegisteredStepClientCount() == Clients;
    };
    Report.SetStringField(TEXT("stage"), TEXT("actual_equip_drop"));
    AProphecyAgent* Agent = nullptr;
    if (!PrepareAgent(Fixture, Agent, Error) || !Check(Agent->EquipSword(true), TEXT("actual_native_sword_equip"))) return false;
    AActor* Sword = Agent->GetHeldSword();
    auto* Blade = Sword ? Cast<UStaticMeshComponent>(Sword->GetRootComponent()) : nullptr;
    auto* Body = Sword ? Sword->FindComponentByClass<UProphecyJoltBodyComponent>() : nullptr;
    if (!Check(Sword && Sword->GetClass()->GetPathName() == TEXT("/Game/_mygame/sword/A_Sword.A_Sword_C")
        && Blade && Blade->GetStaticMesh() && Blade->GetStaticMesh()->GetPathName() == TrainingPath
        && Body && Body->IsJoltBody() && !Body->IsEnablePending() && Blade->BodyInstance.bUseCCD
        && !Blade->BodyInstance.GetUseMACD() && !Blade->IsAnySimulatingPhysics()
        && Blade->GetCollisionEnabled() == ECollisionEnabled::QueryOnly, TEXT("actual_training_CCD_body_and_original_UE_receiver"))) return false;
    Body->bAutomaticStep = false;
    FProphecyJoltBodyHandle SwordHandle;
    if (!Body->GetBodyHandle(SwordHandle)) { Error = TEXT("Sword native handle missing."); return false; }
    // Remove the holder before measuring motion so released owner contacts cannot arrest the fall.
    if (!Check(Agent->DropSword() == Sword && !Sword->GetOwner() && Agent->Destroy()
        && World->OwnsBody(SwordHandle) && Counts(1, 1), TEXT("actual_drop_then_holder_cleanup_leaves_one_independent_body"))) return false;
    FProphecyJoltBodyState State;
    if (!Body->GetBodyState(State)) { Error = TEXT("Dropped sword state missing."); return false; }
    const double InitialZ = State.CenterOfMassPositionCm.Z;
    const double FloorTop = Blade->Bounds.Origin.Z - Blade->Bounds.BoxExtent.Z - 100.0;
    const double FloorBottom = FloorTop - 50.0;
    const FTransform FloorTransform(FRotator::ZeroRotator,
        FVector(State.CenterOfMassPositionCm.X, State.CenterOfMassPositionCm.Y, FloorTop - 25.0), FVector(10, 10, 0.5));
    auto* Cube = LoadObject<UStaticMesh>(nullptr, TEXT("/Engine/BasicShapes/Cube.Cube"));
    FActorSpawnParameters Spawn;
    Spawn.ObjectFlags |= RF_Transient;
    Spawn.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    AActor* FloorActor = Fixture.World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, Spawn);
    if (!Cube || !FloorActor) { Error = TEXT("Actual static Cube floor creation failed."); return false; }
    auto* Floor = NewObject<UStaticMeshComponent>(FloorActor, NAME_None, RF_Transient);
    FloorActor->AddInstanceComponent(Floor); FloorActor->SetRootComponent(Floor);
    Floor->SetStaticMesh(Cube); Floor->SetMobility(EComponentMobility::Static); Floor->SetWorldTransform(FloorTransform);
    Floor->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics); Floor->SetCollisionObjectType(ECC_WorldStatic);
    Floor->SetCollisionResponseToAllChannels(ECR_Block); Floor->SetGenerateOverlapEvents(false); Floor->RegisterComponent();
    auto* Scene = NewObject<UProphecyJoltSceneCollisionComponent>(FloorActor, NAME_None, RF_Transient);
    FloorActor->AddInstanceComponent(Scene); Scene->RegisterComponent();
    Report.SetStringField(TEXT("stage"), TEXT("import_static_floor"));
    if (!Scene->EnableSceneCollision(Error)) return false;
    FProphecyJoltBodyHandle FloorHandle;
    UObject* AssociatedFloor = nullptr;
    if (!Check(Scene->IsSceneCollisionEnabled() && !Scene->IsEnablePending() && Scene->GetImportedBodyCount() == 1
        && Scene->GetBodyHandle(*Floor, INDEX_NONE, FloorHandle) && World->OwnsBody(FloorHandle)
        && World->ResolveAssociatedObject(FloorHandle, AssociatedFloor).IsSuccess() && AssociatedFloor == Floor
        && Counts(2, 2), TEXT("real_static_floor_imported_with_exact_component_provenance_into_shared_world"))) return false;
    Report.SetStringField(TEXT("sword_class"), Sword->GetClass()->GetPathName());
    Report.SetStringField(TEXT("sword_component"), Blade->GetPathName());
    Report.SetStringField(TEXT("floor_mesh"), Cube->GetPathName());
    Report.SetStringField(TEXT("floor_component"), Floor->GetPathName());
    Report.SetStringField(TEXT("floor_transform"), FloorTransform.ToString());
    Report.SetNumberField(TEXT("gravity_z_cm_s2"), Settings.GravityCmPerSecondSquared.Z);
    Report.SetNumberField(TEXT("step_seconds"), StepSeconds);
    Report.SetNumberField(TEXT("floor_top_z_cm"), FloorTop); Report.SetNumberField(TEXT("floor_bottom_z_cm"), FloorBottom);
    Report.SetNumberField(TEXT("initial_sword_com_z_cm"), InitialZ);
    const auto FloorQuery = [&]()
    {
        const FVector Center = FloorTransform.GetLocation() + FVector(350, 0, 0);
        FHitResult Hit;
        return Fixture.World->LineTraceSingleByObjectType(Hit, Center + FVector(0, 0, 100), Center - FVector(0, 0, 100),
            FCollisionObjectQueryParams(ECC_WorldStatic)) && Hit.GetActor() == FloorActor && Hit.GetComponent() == Floor;
    };
    const auto SwordQuery = [&]()
    {
        FVector Min, Max; Blade->GetLocalBounds(Min, Max);
        const FVector Extent = Max - Min;
        const FVector Axis = Extent.X <= Extent.Y && Extent.X <= Extent.Z ? FVector::ForwardVector
            : Extent.Y <= Extent.Z ? FVector::RightVector : FVector::UpVector;
        const FVector Ray = Blade->GetComponentQuat().RotateVector(Axis) * (Blade->Bounds.SphereRadius + 50.0);
        TArray<FHitResult> Hits;
        Fixture.World->LineTraceMultiByObjectType(Hits, State.CenterOfMassPositionCm + Ray, State.CenterOfMassPositionCm - Ray,
            FCollisionObjectQueryParams(ECC_PhysicsBody));
        return Hits.ContainsByPredicate([&](const FHitResult& Hit) { return Hit.GetActor() == Sword && Hit.GetComponent() == Blade; });
    };
    TArray<TSharedPtr<FJsonValue>> Samples;
    const auto Sample = [&](const TCHAR* Phase, int32 Frame)
    {
        auto Row = MakeShared<FJsonObject>();
        Row->SetStringField(TEXT("phase"), Phase); Row->SetNumberField(TEXT("frame"), Frame);
        Row->SetNumberField(TEXT("com_z_cm"), State.CenterOfMassPositionCm.Z);
        Row->SetNumberField(TEXT("velocity_z_cm_s"), State.CenterOfMassVelocityCmPerSecond.Z);
        Samples.Add(MakeShared<FJsonValueObject>(Row)); Report.SetArrayField(TEXT("motion_samples"), Samples);
    };
    const auto Step = [&]()
    {
        if (!Body->StepAndPublish(StepSeconds, Error)) return false;
        if (!Body->GetBodyState(State) || State.PositionCm.ContainsNaN() || State.CenterOfMassPositionCm.ContainsNaN()
            || State.Rotation.ContainsNaN() || State.CenterOfMassVelocityCmPerSecond.ContainsNaN()
            || State.AngularVelocityRadiansPerSecond.ContainsNaN())
        { Error = TEXT("Contact step produced missing or nonfinite native sword state."); return false; }
        return true;
    };
    Report.SetStringField(TEXT("stage"), TEXT("floor_contact"));
    if (!Body->SetBodyVelocity(FVector(0, 0, -300), FVector::ZeroVector, true, Error)) return false;
    double MinimumZ = InitialZ;
    for (int32 Frame = 1; Frame <= 120; ++Frame)
    {
        if (!Step()) return false;
        MinimumZ = FMath::Min(MinimumZ, State.CenterOfMassPositionCm.Z);
        if (Frame % 15 == 0) Sample(TEXT("native_floor_present"), Frame);
    }
    Report.SetNumberField(TEXT("floor_phase_min_com_z_cm"), MinimumZ);
    Report.SetNumberField(TEXT("floor_phase_final_com_z_cm"), State.CenterOfMassPositionCm.Z);
    Report.SetNumberField(TEXT("floor_phase_final_velocity_z_cm_s"), State.CenterOfMassVelocityCmPerSecond.Z);
    if (!Check(InitialZ - State.CenterOfMassPositionCm.Z > 25.0 && MinimumZ > FloorBottom + 1.0
        && State.CenterOfMassPositionCm.Z < FloorTop + Blade->Bounds.SphereRadius + 5.0
        && FMath::Abs(State.CenterOfMassVelocityCmPerSecond.Z) < 100.0,
        TEXT("sword_falls_to_floor_and_contact_arrests_downward_motion_without_crossing_slab"))
        || !Check(Counts(2, 2) && FloorQuery() && SwordQuery() && !Blade->IsAnySimulatingPhysics()
            && Blade->GetCollisionEnabled() == ECollisionEnabled::QueryOnly,
            TEXT("post_contact_native_ownership_and_original_UE_query_identities"))) return false;
    Report.SetStringField(TEXT("stage"), TEXT("native_floor_removal_control"));
    Scene->DisableSceneCollision();
    if (!Check(!World->OwnsBody(FloorHandle) && World->OwnsBody(SwordHandle) && Counts(1, 1)
        && Floor->IsPhysicsStateCreated() && Floor->GetCollisionEnabled() == ECollisionEnabled::QueryAndPhysics
        && Floor->GetComponentTransform().Equals(FloorTransform) && FloorQuery(),
        TEXT("remove_only_native_floor_while_preserving_UE_floor_and_dropped_body"))) return false;
    if (!Body->SetBodyVelocity(FVector(0, 0, -300), FVector::ZeroVector, true, Error)) return false;
    for (int32 Frame = 1; Frame <= 60; ++Frame)
    {
        if (!Step()) return false;
        if (Frame % 15 == 0) Sample(TEXT("native_floor_removed_UE_floor_retained"), Frame);
    }
    Report.SetNumberField(TEXT("control_final_com_z_cm"), State.CenterOfMassPositionCm.Z);
    if (!Check(State.CenterOfMassPositionCm.Z < FloorBottom - 50.0 && FloorQuery() && SwordQuery()
        && !Blade->IsAnySimulatingPhysics() && Counts(1, 1),
        TEXT("same_sword_crosses_former_floor_only_after_native_collision_is_removed"))) return false;
    FProphecyJoltWorldDiagnostics Final;
    if (!Check(World->GetDiagnostics(Final).IsSuccess() && Final.CompletedSteps == 180,
        TEXT("exactly_180_explicit_shared_native_steps_without_world_tick"))) return false;
    Report.SetNumberField(TEXT("completed_steps"), static_cast<double>(Final.CompletedSteps));
    if (!Check(Sword->Destroy() && FloorActor->Destroy() && Counts(0, 0), TEXT("all_contact_fixture_native_bodies_and_clients_retired"))) return false;
    Report.SetStringField(TEXT("stage"), TEXT("complete"));
    return true;
}

void ContactCommand(const TArray<FString>& Args)
{
    if (Args.Num() != 1 || FPaths::IsRelative(Args[0]) || FPaths::FileExists(Args[0]))
    { UE_LOG(LogTemp, Error, TEXT("Prophecy.Jolt.SwordContactFixture requires one new absolute JSON path.")); return; }
    auto Report = MakeShared<FJsonObject>();
    FString Error;
    const bool bSucceeded = RunContact(*Report, Error);
    if (!bSucceeded && Error.IsEmpty()) Error = TEXT("Sword contact fixture failed at the reported stage without a native diagnostic.");
    Report->SetBoolField(TEXT("success"), bSucceeded); Report->SetStringField(TEXT("error"), Error);
    FString Text;
    const bool bSerialized = FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Text));
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Args[0]), true);
    const bool bSaved = bSerialized && FFileHelper::SaveStringToFile(Text, *Args[0], FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
        &IFileManager::Get(), FILEWRITE_NoReplaceExisting);
    if (!bSaved || !bSucceeded)
    { UE_LOG(LogTemp, Error, TEXT("Sword contact fixture failed: %s; report=%s; saved=%d"), *Error, *Args[0], bSaved); }
    else
    { UE_LOG(LogTemp, Display, TEXT("Sword contact fixture passed: %s"), *Args[0]); }
}
FAutoConsoleCommand ContactConsoleCommand(TEXT("Prophecy.Jolt.SwordContactFixture"),
    TEXT("Actual dropped Training sword/static scene contact and native-floor removal control; one new absolute JSON path."),
    FConsoleCommandWithArgsDelegate::CreateStatic(&ContactCommand));

struct FFighterContactTrial
{
    TArray<FProphecyJoltBodyState> InitialStates;
    TArray<FProphecyJoltBodyState> HeadStates;
    TArray<FString> RigSignatures;
    FString SwordResponses;
    ECollisionChannel VictimChannel = ECC_MAX;
};

FString ResponseSignature(const FCollisionResponseContainer& Responses)
{
    FString Result;
    for (int32 Channel = 0; Channel < 32; ++Channel)
        Result += FString::FromInt(static_cast<int32>(Responses.GetResponse(static_cast<ECollisionChannel>(Channel))));
    return Result;
}

bool FighterContactTrial(bool bContact, FJsonObject& Report, FFighterContactTrial& Output, FString& Error)
{
    Report.SetBoolField(TEXT("sword_victim_contact_enabled"), bContact);
    Report.SetStringField(TEXT("stage"), TEXT("two_manual_fighters"));
    FWorldFixture Fixture;
    const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
        .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
    Fixture.World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
    if (!Fixture.World || !GEngine) { Error = TEXT("Fighter contact world creation failed."); return false; }
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(Fixture.World);
    Fixture.World->InitializeActorsForPlay(FURL());
    Fixture.World->GetWorldSettings()->NotifyBeginPlay();
    auto* World = Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    auto* Coordinator = Fixture.World->GetSubsystem<UProphecyJoltCharacterWorldSubsystem>();
    FProphecyJoltWorldSettings Settings;
    Settings.GravityCmPerSecondSquared = FVector::ZeroVector;
    Settings.WorkerThreads = 0;
    if (!World || !Coordinator) { Error = TEXT("Shared contact world subsystems missing."); return false; }
    const auto Initialized = World->InitializeSimulation(Settings);
    if (!Initialized.IsSuccess()) { Error = Initialized.Message; return false; }
    AProphecyAgent* Holder = nullptr;
    AProphecyAgent* Victim = nullptr;
    FProphecyJoltRigSnapshot HolderSource, VictimSource;
    const FTransform HolderCarrier(FVector(0, 0, 400));
    if (!PrepareAgent(Fixture, Holder, Error, PoseId, HolderCarrier, &HolderSource)) return false;
    if (!Holder->EquipSword(false)) { Error = TEXT("Actual attached sword equip failed."); return false; }
    AActor* Sword = Holder->GetHeldSword();
    auto* Blade = Sword ? Cast<UStaticMeshComponent>(Sword->GetRootComponent()) : nullptr;
    if (!Blade || !Blade->GetStaticMesh() || Blade->GetStaticMesh()->GetPathName() != TrainingPath
        || Sword->GetClass()->GetPathName() != TEXT("/Game/_mygame/sword/A_Sword.A_Sword_C"))
    { Error = TEXT("Fighter contact fixture requires the actual A_Sword/Training receiver."); return false; }
    FVector Min, Max; Blade->GetLocalBounds(Min, Max);
    const FVector Extent = (Max - Min) * 0.5;
    const FVector Axis = Extent.X >= Extent.Y && Extent.X >= Extent.Z ? FVector::ForwardVector
        : Extent.Y >= Extent.Z ? FVector::RightVector : FVector::UpVector;
    const FVector Center = (Min + Max) * 0.5;
    const FVector TipA = Blade->GetComponentTransform().TransformPosition(Center + Axis * Extent.GetMax() * 0.9);
    const FVector TipB = Blade->GetComponentTransform().TransformPosition(Center - Axis * Extent.GetMax() * 0.9);
    const FVector Hand = Holder->GetPoseReferenceMesh()->GetSocketLocation(Holder->SwordHandSocket);
    const FVector Encounter = FVector::DistSquared(TipA, Hand) > FVector::DistSquared(TipB, Hand) ? TipA : TipB;
    FProphecyJoltBodyHandle HolderHead;
    FProphecyJoltBodyState ReferenceHead;
    if (!Holder->GetJoltCharacterComponent()->GetBodyHandle(TEXT("head"), HolderHead)
        || !World->ReadBody(HolderHead, ReferenceHead).IsSuccess())
    { Error = TEXT("Actual PHAT head body is missing."); return false; }
    // Deliberate initial blade/head intersection: no invented attack animation or drive retuning.
    const FTransform VictimCarrier(HolderCarrier.GetLocation() + Encounter - ReferenceHead.CenterOfMassPositionCm);
    if (!PrepareAgent(Fixture, Victim, Error, PoseId + 1, VictimCarrier, &VictimSource)) return false;
    const FProphecyJoltRigBody* HeadSource = VictimSource.Bodies.FindByPredicate(
        [](const FProphecyJoltRigBody& Body) { return Body.BodyName == FName(TEXT("head")); });
    if (!HeadSource) { Error = TEXT("Captured PHAT head is absent."); return false; }
    Output.VictimChannel = HeadSource->ObjectType;
    const ECollisionChannel SwordChannel = Blade->GetCollisionObjectType();
    const FString AuthoredSwordResponses = ResponseSignature(Blade->GetCollisionResponseToChannels());
    if (Blade->GetCollisionResponseToChannel(Output.VictimChannel) != ECR_Block
        || HeadSource->CollisionResponses.GetResponse(SwordChannel) != ECR_Block)
    { Error = TEXT("Authored sword/head profiles do not bilaterally Block; contact acceptance requires a gameplay policy decision."); return false; }
    for (const FProphecyJoltRigBody& Body : VictimSource.Bodies)
        if (Body.ObjectType != Output.VictimChannel)
        { Error = TEXT("Victim has mixed native body channels; this single-channel isolation control is unsupported."); return false; }
    // Owner pairs are already excluded by the actual grip. With only these two rigs present,
    // this one transient response change removes sword/victim contacts and nothing else.
    if (!bContact) Blade->SetCollisionResponseToChannel(Output.VictimChannel, ECR_Ignore);
    Output.SwordResponses = ResponseSignature(Blade->GetCollisionResponseToChannels());
    if (!Holder->SetSwordSimulated(true)) { Error = TEXT("Actual native held-sword admission failed."); return false; }
    auto* SwordBody = Sword->FindComponentByClass<UProphecyJoltBodyComponent>();
    if (!SwordBody || !SwordBody->IsJoltBody() || SwordBody->IsEnablePending()
        || ResponseSignature(Blade->GetCollisionResponseToChannels()) != Output.SwordResponses
        || !Blade->BodyInstance.bUseCCD || Blade->BodyInstance.GetUseMACD())
    { Error = TEXT("Actual held sword has no immediate native ownership."); return false; }
    SwordBody->bAutomaticStep = false;
    auto* HolderCharacter = Holder->GetJoltCharacterComponent();
    auto* VictimCharacter = Victim->GetJoltCharacterComponent();
    FProphecyJoltBodyHandle VictimHead, SwordHandle;
    if (!VictimCharacter->GetBodyHandle(TEXT("head"), VictimHead) || !SwordBody->GetBodyHandle(SwordHandle))
    { Error = TEXT("Contact endpoint native identities missing."); return false; }
    TArray<TSharedPtr<FJsonValue>> Signatures;
    TArray<FBox> HolderBounds, VictimBounds;
    for (int32 RigIndex = 0; RigIndex < 2; ++RigIndex)
    {
        const FProphecyJoltRigSnapshot& Source = RigIndex == 0 ? HolderSource : VictimSource;
        auto* Character = RigIndex == 0 ? HolderCharacter : VictimCharacter;
        FProphecyJoltPreparedRig Geometry;
        if (!Geometry.Build(Source, Error)) return false;
        for (int32 Index = 0; Index < Source.Bodies.Num(); ++Index)
        {
            const auto& Body = Source.Bodies[Index];
            FProphecyJoltBodyHandle Handle; FProphecyJoltBodyState State;
            FVector COM; FBox Bounds;
            if (!Character->GetBodyHandle(Body.BodyName, Handle) || !World->ReadBody(Handle, State).IsSuccess()
                || !Geometry.GetBodyGeometrySummary(Index, COM, Bounds, Error)) return false;
            Output.InitialStates.Add(State);
            (RigIndex == 0 ? HolderBounds : VictimBounds).Add(Bounds.TransformBy(Body.BodyOriginToWorld));
            const FString Signature = FString::Printf(TEXT("%d:%s:%d:%s"), RigIndex, *Body.BodyName.ToString(),
                static_cast<int32>(Body.ObjectType), *ResponseSignature(Body.CollisionResponses));
            Output.RigSignatures.Add(Signature); Signatures.Add(MakeShared<FJsonValueString>(Signature));
        }
        for (const auto& Joint : Source.Joints)
        {
            FString Profile;
            FConstraintProfileProperties::StaticStruct()->ExportText(Profile, &Joint.CurrentProfile, nullptr, nullptr, PPF_None, nullptr);
            const FString Signature = FString::Printf(TEXT("%d:%s:%s"), RigIndex, *Joint.JointName.ToString(), *Profile);
            Output.RigSignatures.Add(Signature); Signatures.Add(MakeShared<FJsonValueString>(Signature));
        }
    }
    FProphecyJoltBodyState SwordInitial;
    if (!World->ReadBody(SwordHandle, SwordInitial).IsSuccess()) return false;
    Output.InitialStates.Add(SwordInitial);
    int32 RigBoundsIntersections = 0;
    for (const FBox& A : HolderBounds) for (const FBox& B : VictimBounds) if (A.Intersect(B)) ++RigBoundsIntersections;
    Report.SetNumberField(TEXT("rig_body_aabb_intersections"), RigBoundsIntersections);
    Report.SetArrayField(TEXT("captured_native_body_filters_and_PHAT_profiles"), Signatures);
    Report.SetStringField(TEXT("authored_sword_responses_32_channels"), AuthoredSwordResponses);
    Report.SetStringField(TEXT("admitted_sword_responses_32_channels"), Output.SwordResponses);
    Report.SetNumberField(TEXT("sword_channel"), static_cast<int32>(SwordChannel));
    Report.SetNumberField(TEXT("victim_channel"), static_cast<int32>(Output.VictimChannel));
    Report.SetStringField(TEXT("encounter_head_com_cm"), Encounter.ToString());
    Report.SetStringField(TEXT("training_mesh"), Blade->GetStaticMesh()->GetPathName());
    Report.SetStringField(TEXT("sword_class"), Sword->GetClass()->GetPathName());
    Report.SetStringField(TEXT("holder_carrier"), HolderCarrier.ToString());
    Report.SetStringField(TEXT("victim_carrier"), VictimCarrier.ToString());
    Report.SetStringField(TEXT("physics_asset"), VictimSource.PhysicsAssetPath);
    if (RigBoundsIntersections != 0)
    { Error = TEXT("Outer-blade placement does not isolate the two rigs' body bounds; contact layout needs adjustment, not rig retuning."); return false; }
    const auto Counts = [&]()
    {
        FProphecyJoltWorldDiagnostics D;
        return World->GetDiagnostics(D).IsSuccess() && !D.bFaulted && D.BodyCount == 45 && D.ConstraintCount == 43
            && D.GenericJointCount == 1 && D.SuppressedBodyPairCount == 1 && Coordinator->GetRegisteredStepClientCount() == 3;
    };
    if (!Counts()) { Error = TEXT("Expected two 22-body rigs, one held blade/grip and only 22 owner exclusions."); return false; }
    Report.SetStringField(TEXT("stage"), TEXT("held_blade_head_depenetration"));
    TArray<TSharedPtr<FJsonValue>> Samples;
    for (int32 Frame = 1; Frame <= 12; ++Frame)
    {
        if (!HolderCharacter->PublishAuthoredTargets(StepSeconds, Error)
            || !VictimCharacter->PublishAuthoredTargets(StepSeconds, Error)
            || !HolderCharacter->StepAndPublish(StepSeconds, Error)) return false;
        FProphecyJoltBodyState Head, BladeState;
        if (!World->ReadBody(VictimHead, Head).IsSuccess() || !World->ReadBody(SwordHandle, BladeState).IsSuccess()
            || Head.PositionCm.ContainsNaN() || Head.CenterOfMassPositionCm.ContainsNaN()
            || Head.CenterOfMassVelocityCmPerSecond.ContainsNaN() || Head.AngularVelocityRadiansPerSecond.ContainsNaN()
            || Head.Rotation.ContainsNaN() || BladeState.PositionCm.ContainsNaN()
            || BladeState.CenterOfMassPositionCm.ContainsNaN() || BladeState.CenterOfMassVelocityCmPerSecond.ContainsNaN()
            || BladeState.AngularVelocityRadiansPerSecond.ContainsNaN() || BladeState.Rotation.ContainsNaN() || !Counts()
            || Holder->GetHeldSword() != Sword || !SwordBody->IsJoltBody() || Blade->IsAnySimulatingPhysics()
            || Blade->GetCollisionEnabled() != ECollisionEnabled::QueryOnly)
        { Error = TEXT("Contact step lost finite state, held grip, ownership, or Chaos-free query receiver."); return false; }
        Output.HeadStates.Add(Head);
        auto Sample = MakeShared<FJsonObject>();
        Sample->SetNumberField(TEXT("frame"), Frame);
        Sample->SetNumberField(TEXT("head_displacement_cm"), FVector::Distance(Head.CenterOfMassPositionCm, Encounter));
        Sample->SetNumberField(TEXT("head_speed_cm_s"), Head.CenterOfMassVelocityCmPerSecond.Length());
        Sample->SetStringField(TEXT("head_com_cm"), Head.CenterOfMassPositionCm.ToString());
        Sample->SetStringField(TEXT("head_velocity_cm_s"), Head.CenterOfMassVelocityCmPerSecond.ToString());
        Samples.Add(MakeShared<FJsonValueObject>(Sample)); Report.SetArrayField(TEXT("samples"), Samples);
    }
    FProphecyJoltWorldDiagnostics D;
    const bool bSteps = World->GetDiagnostics(D).IsSuccess() && D.CompletedSteps == 12
        && HolderCharacter->GetRevision() == VictimCharacter->GetRevision();
    Holder->Destroy(); Victim->Destroy();
    const bool bClean = World->GetDiagnostics(D).IsSuccess() && D.BodyCount == 0 && D.ConstraintCount == 0
        && D.SuppressedBodyPairCount == 0 && Coordinator->GetRegisteredStepClientCount() == 0;
    Report.SetBoolField(TEXT("shared_steps_and_cleanup_passed"), bSteps && bClean);
    if (!bSteps || !bClean) { Error = TEXT("Shared contact steps or native lifecycle cleanup failed."); return false; }
    Report.SetStringField(TEXT("stage"), TEXT("complete"));
    return true;
}

void FighterContactCommand(const TArray<FString>& Args)
{
    if (Args.Num() != 1 || FPaths::IsRelative(Args[0]) || FPaths::FileExists(Args[0]))
    { UE_LOG(LogTemp, Error, TEXT("Prophecy.Jolt.SwordFighterContactFixture requires one new absolute JSON path.")); return; }
    auto Report = MakeShared<FJsonObject>();
    Report->SetStringField(TEXT("scope"), TEXT("Actual held Training blade initially intersects the second manual fighter's head. Two fresh worlds differ only in transient sword-to-victim Block/Ignore response. Tests contact/depenetration causality with unchanged PHAT limits and drives; no swing, inference, cutting, rendering, performance or full-fight acceptance."));
    Report->SetBoolField(TEXT("assets_saved"), false);
    FString Error;
    auto Preflight = MakeShared<FJsonObject>();
    bool bPassed = StandaloneFixture::CaptureTrainingSword(*Preflight, Error);
    Report->SetBoolField(TEXT("asset_preflight_passed"), bPassed);
    FFighterContactTrial Trials[2];
    for (int32 Index = 0; bPassed && Index < 2; ++Index)
    {
        auto Trial = MakeShared<FJsonObject>();
        Report->SetObjectField(Index == 0 ? TEXT("authored_contact_on") : TEXT("control_contact_off"), Trial);
        bPassed = FighterContactTrial(Index == 0, *Trial, Trials[Index], Error);
    }
    if (bPassed)
    {
        bool bSameInitial = Trials[0].InitialStates.Num() == 45 && Trials[1].InitialStates.Num() == 45;
        for (int32 Index = 0; bSameInitial && Index < 45; ++Index)
        {
            const auto& A = Trials[0].InitialStates[Index]; const auto& B = Trials[1].InitialStates[Index];
            bSameInitial = A.PositionCm.Equals(B.PositionCm, 1.0e-5) && A.Rotation.Equals(B.Rotation, 1.0e-6)
                && A.CenterOfMassPositionCm.Equals(B.CenterOfMassPositionCm, 1.0e-5)
                && A.CenterOfMassVelocityCmPerSecond.Equals(B.CenterOfMassVelocityCmPerSecond, 1.0e-5)
                && A.AngularVelocityRadiansPerSecond.Equals(B.AngularVelocityRadiansPerSecond, 1.0e-6)
                && A.bDynamic == B.bDynamic && A.bActive == B.bActive;
        }
        bool bOnlyFilter = Trials[0].RigSignatures == Trials[1].RigSignatures
            && Trials[0].VictimChannel == Trials[1].VictimChannel
            && Trials[0].SwordResponses.Len() == 32 && Trials[1].SwordResponses.Len() == 32;
        for (int32 Channel = 0; bOnlyFilter && Channel < 32; ++Channel)
            bOnlyFilter = Channel == static_cast<int32>(Trials[0].VictimChannel)
                ? Trials[0].SwordResponses[Channel] == TCHAR('0' + ECR_Block) && Trials[1].SwordResponses[Channel] == TCHAR('0' + ECR_Ignore)
                : Trials[0].SwordResponses[Channel] == Trials[1].SwordResponses[Channel];
        double MaxPositionDelta = 0, MaxVelocityDelta = 0;
        for (int32 Frame = 0; Frame < Trials[0].HeadStates.Num() && Frame < Trials[1].HeadStates.Num(); ++Frame)
        {
            MaxPositionDelta = FMath::Max(MaxPositionDelta, FVector::Distance(Trials[0].HeadStates[Frame].CenterOfMassPositionCm,
                Trials[1].HeadStates[Frame].CenterOfMassPositionCm));
            MaxVelocityDelta = FMath::Max(MaxVelocityDelta, FVector::Distance(Trials[0].HeadStates[Frame].CenterOfMassVelocityCmPerSecond,
                Trials[1].HeadStates[Frame].CenterOfMassVelocityCmPerSecond));
        }
        Report->SetBoolField(TEXT("all_45_initial_native_states_match"), bSameInitial);
        Report->SetBoolField(TEXT("only_sword_victim_filter_differs"), bOnlyFilter);
        Report->SetNumberField(TEXT("max_contact_control_head_position_delta_cm"), MaxPositionDelta);
        Report->SetNumberField(TEXT("max_contact_control_head_velocity_delta_cm_s"), MaxVelocityDelta);
        bPassed = bSameInitial && bOnlyFilter && Trials[0].HeadStates.Num() == 12 && Trials[1].HeadStates.Num() == 12
            && FMath::IsFinite(MaxPositionDelta) && FMath::IsFinite(MaxVelocityDelta)
            && MaxPositionDelta > 0.05 && MaxVelocityDelta > 1.0;
        if (!bPassed) Error = TEXT("Matched trials did not establish isolated held-sword contact causality; inspect recorded signatures and native motion.");
    }
    if (!bPassed && Error.IsEmpty()) Error = TEXT("Fighter contact fixture failed at the recorded stage.");
    Report->SetBoolField(TEXT("success"), bPassed); Report->SetStringField(TEXT("error"), Error);
    FString Text;
    const bool bSerialized = FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Text));
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Args[0]), true);
    const bool bSaved = bSerialized && FFileHelper::SaveStringToFile(Text, *Args[0], FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
        &IFileManager::Get(), FILEWRITE_NoReplaceExisting);
    if (!bPassed || !bSaved)
    { UE_LOG(LogTemp, Error, TEXT("Sword/fighter contact failed: %s; report=%s; saved=%d"), *Error, *Args[0], bSaved); }
    else
    { UE_LOG(LogTemp, Display, TEXT("Sword/fighter contact passed: %s"), *Args[0]); }
}
FAutoConsoleCommand FighterContactConsoleCommand(TEXT("Prophecy.Jolt.SwordFighterContactFixture"),
    TEXT("Actual held sword/head contact with isolated authored Block versus Ignore control; one new absolute JSON path."),
    FConsoleCommandWithArgsDelegate::CreateStatic(&FighterContactCommand));
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySwordMagnetizationTest,
    "Prophecy.Jolt.Sword.IndependentHandMagnetization",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecySwordMagnetizationTest::RunTest(const FString&)
{
    using namespace ProphecyJolt::SwordFixture;
    FWorldFixture Fixture;
    const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
        .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
    Fixture.World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
    if (!Fixture.World || !GEngine) return false;
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(Fixture.World);
    Fixture.World->GetWorldSettings()->bGlobalGravitySet=true;
    Fixture.World->GetWorldSettings()->GlobalGravityZ=0.f;
    Fixture.World->InitializeActorsForPlay(FURL());Fixture.World->GetWorldSettings()->NotifyBeginPlay();
    auto* World=Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltWorldSettings Settings;Settings.GravityCmPerSecondSquared=FVector::ZeroVector;Settings.WorkerThreads=0;
    if (!World || !World->InitializeSimulation(Settings).IsSuccess()) return false;
    AProphecyAgent* Agent=nullptr;FString Error;
    if (!PrepareAgent(Fixture,Agent,Error) || !Agent->EquipSword(true)) { AddError(Error);return false; }
    auto* Character=Agent->GetJoltCharacterComponent();
    auto* Sword=Agent->GetHeldSword();
    auto* Blade=Cast<UStaticMeshComponent>(Sword->GetRootComponent());
    auto* Body=Sword->FindComponentByClass<UProphecyJoltBodyComponent>();
    FProphecyJoltBodyHandle Handle;FTransform Origin;
    if (!Body || !Body->GetBodyHandle(Handle) || !Body->GetBodyOriginToComponent(Origin)) return false;
    Body->bAutomaticStep=false;
    FTransform ComponentTarget=Agent->SwordGripTransform*Agent->GetPoseReferenceMesh()->GetSocketTransform(Agent->SwordHandSocket);
    ComponentTarget.RemoveScaling();
    const FTransform Expected=Origin*ComponentTarget;
    FProphecyJoltWorldDiagnostics Before,After;World->GetDiagnostics(Before);
    if (!TestTrue(TEXT("Break the grip without dropping the sword"),UProphecySwordPhysicsLibrary::BreakSwordGripConstraint(Agent))) return false;
    World->GetDiagnostics(After);
    TestTrue(TEXT("Only one joint removed; held item and body survive"),After.GenericJointCount+1==Before.GenericJointCount
        && After.BodyCount==Before.BodyCount && Agent->GetHeldSword()==Sword && World->OwnsBody(Handle));
    TestTrue(TEXT("Repeated break is safe"),UProphecySwordPhysicsLibrary::BreakSwordGripConstraint(Agent));
    // Isolate drive response; do not change the user's scene, collider geometry or CCD setting.
    Blade->SetCollisionResponseToAllChannels(ECR_Ignore);
    FProphecyJoltCollisionUpdate Collision;Collision.Handle=Handle;Collision.Responses=FCollisionResponseContainer(ECR_Ignore);
    if (!World->UpdateBodyCollision(MakeArrayView(&Collision,1)).IsSuccess()
        || !World->SetBodyRuntimeSettings(Handle,false,0,0,false).IsSuccess()) return false;
    Agent->bWorldMagnetizationEnabled=true;
    Agent->WorldMagnetizationLinearStrengthScale=1;
    Agent->WorldMagnetizationAngularStrengthScale=1;
    Agent->SetAllBodyMagnetization(false,0,0);
    auto ResetBlade=[&](float Angle=0.f)
    {
        const auto Result=World->SetBodyPose(Handle,FTransform(FQuat(FVector::UpVector,Angle)*Expected.GetRotation(),Expected.GetLocation()+FVector(16,0,0)));
        if (!Result.IsSuccess()) { AddError(Result.Message);return false; }
        if (!Body->SetBodyVelocity(FVector::ZeroVector,FVector::ZeroVector,true,Error)) { AddError(Error);return false; }
        return true;
    };
    auto Step=[&]()
    {
        if (!Character->PublishAuthoredTargets(StepSeconds,Error)) { AddError(Error);return false; }
        if (!Character->StepAndPublish(StepSeconds,Error)) { AddError(Error);return false; }
        return true;
    };
    FProphecyJoltBodyState State;
    Agent->SetBodyMagnetization(TEXT("hand_r"),true,1,1);
    if (!ResetBlade() || !Step() || !Body->GetBodyState(State)) return false;
    TestTrue(TEXT("Constraint-free sword reaches authored hand-offset target, not actual hand"),State.PositionCm.Equals(Expected.GetLocation(),.002));
    Agent->WorldMagnetizationLinearStrengthScale=.5f;
    Agent->WorldMagnetizationAngularStrengthScale=.5f;
    Agent->SetBodyMagnetization(TEXT("hand_r"),true,.5f,.5f);
    if (!ResetBlade() || !Step() || !Body->GetBodyState(State)) return false;
    TestTrue(TEXT("Sword inherits global times hand linear strength"),State.PositionCm.Equals(Expected.GetLocation()+FVector(12,0,0),.002));
    Agent->SetBodyMagnetization(TEXT("hand_r"),true,0,.5f);
    if (!ResetBlade(.1f) || !Step() || !Body->GetBodyState(State)) return false;
    TestTrue(TEXT("Sword inherits independent angular strength"),FMath::IsNearlyEqual(State.AngularVelocityRadiansPerSecond.Z,-.1*.25/StepSeconds,.001));
    Agent->SetBodyMagnetization(TEXT("hand_r"),false,1,1);
    if (!ResetBlade() || !Step() || !Body->GetBodyState(State)) return false;
    TestTrue(TEXT("Hand disable clears sword drive immediately"),State.PositionCm.Equals(Expected.GetLocation()+FVector(16,0,0),.002));
    Agent->SetBodyMagnetization(TEXT("hand_r"),true,1,1);
    Agent->bWorldMagnetizationEnabled=false;
    if (!ResetBlade() || !Step() || !Body->GetBodyState(State)) return false;
    TestTrue(TEXT("Global disable clears sword drive"),State.PositionCm.Equals(Expected.GetLocation()+FVector(16,0,0),.002));
    Agent->bWorldMagnetizationEnabled=true;
    if (!TestTrue(TEXT("Drop keeps physical item"),Agent->DropSword()==Sword)) return false;
    if (!ResetBlade() || !Step() || !Body->GetBodyState(State)) return false;
    TestTrue(TEXT("Dropped sword no longer magnetised"),State.PositionCm.Equals(Expected.GetLocation()+FVector(16,0,0),.002));
    return !HasAnyErrors();
}
#include "PhysicsEngine/PhysicsSettings.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySwordAttackCollisionTest,
    "Prophecy.Jolt.Sword.AttackCollisionPhases",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecySwordAttackCollisionTest::RunTest(const FString&)
{
    using namespace ProphecyJolt::SwordFixture;
    FWorldFixture Fixture;
    const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
        .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
    Fixture.World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
    if (!Fixture.World || !GEngine) return false;
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(Fixture.World);
    Fixture.World->InitializeActorsForPlay(FURL());Fixture.World->GetWorldSettings()->NotifyBeginPlay();
    auto* World=Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltWorldSettings Settings;Settings.GravityCmPerSecondSquared=FVector::ZeroVector;Settings.WorkerThreads=0;
    if (!World || !World->InitializeSimulation(Settings).IsSuccess()) return false;
    AProphecyAgent* Agent=nullptr;FString Error;
    if (!PrepareAgent(Fixture,Agent,Error)) { AddError(Error);return false; }
    for (bool bSimulated:{true,false})
    {
        if (!TestTrue(TEXT("Equip mode"),Agent->EquipSword(bSimulated))) return false;
        auto* Sword=Agent->GetHeldSword();auto* Blade=Cast<UStaticMeshComponent>(Sword->GetRootComponent());
        auto* Body=Sword->FindComponentByClass<UProphecyJoltBodyComponent>();
        FProphecyJoltBodyHandle Handle;if (!Body || !Body->GetBodyHandle(Handle)) return false;
        // Preserve an asymmetric authored response, not just a hard-coded BlockAll reset.
        Blade->SetCollisionResponseToChannel(ECC_Visibility,ECR_Ignore);
        const auto Original=Blade->GetCollisionResponseToChannels();
        FProphecyJoltWorldDiagnostics Before;World->GetDiagnostics(Before);
        bool bBodyDefault = false;
        if (!Agent->GetJoltBodyPairSelfCollisionEnabled(TEXT("hand_r"), TEXT("head"), bBodyDefault, Error)
            || !TestTrue(TEXT("Body test pair initially collides"), bBodyDefault)) return false;
        auto CheckBody = [&](bool Expected)
        {
            bool Actual = !Expected;
            TestTrue(TEXT("Attack body pair follows phase"),
                Agent->GetJoltBodyPairSelfCollisionEnabled(TEXT("hand_r"), TEXT("head"), Actual, Error) && Actual == Expected);
        };
        auto Check=[&](bool bAllowed)
        {
            const auto Expected=bAllowed?Original:FCollisionResponseContainer(ECR_Ignore);
            FProphecyJoltCollisionUpdate Native;FProphecyJoltWorldDiagnostics Now;World->GetDiagnostics(Now);
            TestTrue(TEXT("UE receiver collision follows phase"),Blade->GetCollisionResponseToChannels()==Expected);
            TestTrue(TEXT("Native Jolt collision follows phase"),World->ReadBodyCollision(Handle,Native).IsSuccess() && Native.Responses==Expected);
            TestEqual(TEXT("Kinematic contact gate follows phase"),ProphecySwordAttackCollision::IsAllowed(Agent),bAllowed);
            TestTrue(TEXT("No body or joint recreation"),Now.BodyCount==Before.BodyCount && Now.ConstraintCount==Before.ConstraintCount
                && Now.GenericJointCount==Before.GenericJointCount && World->OwnsBody(Handle));
        };
        for (FName Family:{FName(TEXT("slashl")),FName(TEXT("slashrd")),FName(TEXT("pike")),FName(TEXT("hookl")),FName(TEXT("headbutt"))})
        {
            Agent->NotifySwordAttackState(true);
            ProphecySwordAttackCollision::Begin(Agent,Family);Check(false);CheckBody(false);
            auto* Controller=Agent->FindComponentByClass<UProphecySwordComponent>();
            if (!Controller) return false;
            Controller->RefreshOwnerCollision();
            FProphecyJoltWorldDiagnostics Suppressed;World->GetDiagnostics(Suppressed);
            TestTrue(TEXT("Before Hit sword suppresses owner body pairs"),Suppressed.SuppressedBodyPairCount>Before.SuppressedBodyPairCount);
            ProphecySwordAttackCollision::Armed(Agent);
            CheckBody(false); // Armed only changes the weapon's external collision gate.
            Check(Family==TEXT("pike") || Family.ToString().StartsWith(TEXT("slash")));
            ProphecySwordAttackCollision::Hit(Agent);Check(true);CheckBody(true);
            FProphecyJoltWorldDiagnostics Restored;World->GetDiagnostics(Restored);
            TestEqual(TEXT("Hit restores native owner pairs to normal grip-only exclusions"),Restored.SuppressedBodyPairCount,Before.SuppressedBodyPairCount);
            TestTrue(TEXT("Hit does not end attack context"),Agent->IsSwordAttackActive());
            TestFalse(TEXT("Hit is latched for deferred grip/rebind"),ProphecySwordAttackCollision::SuppressesOwner(Agent));
            Controller->RefreshOwnerCollision();World->GetDiagnostics(Restored);
            TestEqual(TEXT("Refresh after Hit keeps owner collisions restored"),Restored.SuppressedBodyPairCount,Before.SuppressedBodyPairCount);
            ProphecySwordAttackCollision::Refresh(Agent);Check(true); // latched through recovery/rebind
            ProphecySwordAttackCollision::Hit(Agent);Check(true); // repeated Hit is harmless
            Agent->NotifySwordAttackState(false);Check(true);
        }
        ProphecySwordAttackCollision::Begin(Agent,TEXT("pike"));Check(false);
        ProphecySwordAttackCollision::Hit(Agent);Check(false); // weapon still requires Armed
        Agent->NotifySwordAttackState(false);Check(true);CheckBody(true); // shared cancel/failure path
        ProphecySwordAttackCollision::Begin(Agent,TEXT("slashl"));ProphecySwordAttackCollision::Armed(Agent);
        ProphecySwordAttackCollision::Begin(Agent,TEXT("hookr"));Check(false);
        ProphecySwordAttackCollision::Armed(Agent);Check(false);
        ProphecySwordAttackCollision::Hit(Agent);Check(true);
        ProphecySwordAttackCollision::End(Agent);Check(true);
        ProphecySwordAttackCollision::Begin(Agent,TEXT("slashl"));
        ProphecySwordAttackCollision::Armed(Agent);Check(true);
        ProphecySwordAttackCollision::RetargetFamily(Agent,TEXT("pike"),false,false);Check(true);
        ProphecySwordAttackCollision::RetargetFamily(Agent,TEXT("hookl"),true,false);Check(false);
        ProphecySwordAttackCollision::Hit(Agent);Check(true);
        ProphecySwordAttackCollision::RetargetFamily(Agent,TEXT("kickr"),false,false);Check(true);
        ProphecySwordAttackCollision::RetargetFamily(Agent,TEXT("slashr"),true,true);Check(true);
        ProphecySwordAttackCollision::RetargetFamily(Agent,TEXT("jabl"),true,true);Check(true);
        ProphecySwordAttackCollision::End(Agent);Check(true);
        ProphecySwordAttackCollision::Begin(Agent,TEXT("hookl"));
        auto* Dropped=Agent->DropSword();
        CheckBody(false); // Dropping the weapon does not end body suppression.
        TestTrue(TEXT("Drop restores collision before releasing ownership"),Dropped==Sword && Blade->GetCollisionResponseToChannels()==Original);
        ProphecySwordAttackCollision::End(Agent);CheckBody(true);
        if (Dropped) Dropped->Destroy();else return false;
    }
    // Ordinary kinematic presentation uses the same UE filter without a Jolt body.
    Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic);
    if (!Agent->EquipSword(false)) return false;
    auto* Blade=Cast<UStaticMeshComponent>(Agent->GetHeldSword()->GetRootComponent());
    const auto Original=Blade->GetCollisionResponseToChannels();
    ProphecySwordAttackCollision::Begin(Agent,TEXT("pike"));
    TestTrue(TEXT("Kinematic sword ignores all channels before Armed"),Blade->GetCollisionResponseToChannels()==FCollisionResponseContainer(ECR_Ignore));
    ProphecySwordAttackCollision::Armed(Agent);
    TestTrue(TEXT("Kinematic sword restores original channels on Armed"),Blade->GetCollisionResponseToChannels()==Original);
    ProphecySwordAttackCollision::End(Agent);
    ProphecySwordAttackCollision::Begin(Agent,TEXT("kickl"));
    ProphecySwordAttackCollision::Armed(Agent);
    TestTrue(TEXT("Kinematic melee stays suppressed on Armed"),Blade->GetCollisionResponseToChannels()==FCollisionResponseContainer(ECR_Ignore));
    ProphecySwordAttackCollision::Hit(Agent);
    TestTrue(TEXT("Kinematic melee restores on Hit"),Blade->GetCollisionResponseToChannels()==Original);
    ProphecySwordAttackCollision::End(Agent);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltDivergentAdmissionTest,
    "Prophecy.Jolt.Character.DivergentBodyAndSocketAdmission",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltDivergentAdmissionTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::SwordFixture;
    FWorldFixture Fixture;
    const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
        .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
    Fixture.World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
    if (!TestNotNull(TEXT("Transient character world"), Fixture.World)
        || !TestNotNull(TEXT("Engine"), GEngine)) return false;
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(Fixture.World);
    Fixture.World->InitializeActorsForPlay(FURL());
    Fixture.World->GetWorldSettings()->NotifyBeginPlay();
    auto* World = Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    if (!TestNotNull(TEXT("Shared Jolt world"), World)) return false;
    FProphecyJoltWorldSettings Settings;
    Settings.GravityCmPerSecondSquared = FVector::ZeroVector;
    Settings.WorkerThreads = 0;
    if (!TestTrue(TEXT("Initialize native world"), World->InitializeSimulation(Settings).IsSuccess())) return false;
    FString Error;
    AProphecyAgent* Agent = nullptr;
    if (!PrepareAgent(Fixture, Agent, Error)) { AddError(Error); return false; }

    // Reuse the real fixture's ordinary mode restoration, then leave its visual/NN pose untouched
    // while the Chaos bodies acquire a different rigid pose, as happens before a startup handoff.
    Agent->DisableJoltPhysicalAnimation();
    if (!TestTrue(TEXT("Return to ordinary Chaos Physical"), Agent->SetSimulationMode(EProphecyAgentSimulationMode::Physical))) return false;
    auto* Mesh = Agent->GetPoseReferenceMesh();
    Agent->bWorldMagnetizationEnabled = true;
    Agent->WorldMagnetizationLinearStrengthScale = 1.0f;
    Agent->WorldMagnetizationAngularStrengthScale = 1.0f;
    Agent->SetAllBodyMagnetization(true, 1.0f, 1.0f);
    FProphecyJoltRigSnapshot Original;
    if (!ProphecyJolt::Rig::CaptureLiveRig(*Mesh, Original, Error)) { AddError(Error); return false; }
    double Mass = 0.0;
    FVector Pivot = FVector::ZeroVector;
    for (const auto& Body : Original.Bodies)
    {
        Mass += Body.MassKg;
        Pivot += (Body.MassFrameToBodyOrigin * Body.BodyOriginToWorld).GetLocation() * Body.MassKg;
    }
    if (!TestTrue(TEXT("Actual rig has positive captured mass"), Mass > 0.0)) return false;
    Pivot /= Mass;
    const FVector Displacement(40.0, 0.0, 0.0);
    const FQuat Rotation(FVector::UpVector, FMath::DegreesToRadians(20.0));
    TArray<FTransform> DisplacedBodies;
    for (const auto& Body : Original.Bodies)
    {
        FBodyInstance* Instance = Mesh->GetBodyInstance(Body.BodyName);
        if (!TestNotNull(TEXT("Original Chaos body"), Instance)) return false;
        const FTransform Moved(Rotation * Body.BodyOriginToWorld.GetRotation(),
            Pivot + Rotation.RotateVector(Body.BodyOriginToWorld.GetLocation() - Pivot) + Displacement);
        DisplacedBodies.Add(Moved);
        Instance->SetBodyTransform(Moved, ETeleportType::TeleportPhysics, true);
        Instance->SetLinearVelocity(FVector::ZeroVector, false);
        Instance->SetAngularVelocityInRadians(FVector::ZeroVector, false);
        const FTransform Socket = Mesh->GetSocketTransform(Body.BodyName, RTS_World);
        TestTrue(TEXT("Socket retains its unshifted visual position"),
            Socket.GetLocation().Equals(Body.BodyOriginToWorld.GetLocation(), 0.02));
        TestTrue(TEXT("Native body and displayed bone deliberately disagree in rotation"),
            Moved.GetRotation().AngularDistance(Socket.GetRotation()) > FMath::DegreesToRadians(19.0));
    }
    if (HasAnyErrors()) return false;
    if (!TestTrue(TEXT("Admit divergent native body state"), Agent->EnableJoltPhysicalAnimation())) return false;
    auto* Character = Agent->GetJoltCharacterComponent();
    if (!TestNotNull(TEXT("Live Jolt character"), Character)
        || !TestTrue(TEXT("Admission completed synchronously"), Character->IsJoltPhysical() && !Character->IsEnablePending())) return false;
    Character->bAutomaticStep = false;
    const auto ReadAndCheckPose = [&](bool bCheckInitial, FVector& OutCenter) -> bool
    {
        OutCenter = FVector::ZeroVector;
        for (int32 Index = 0; Index < Original.Bodies.Num(); ++Index)
        {
            const auto& Body = Original.Bodies[Index];
            FProphecyJoltBodyHandle Handle;
            FProphecyJoltBodyState State;
            if (!Character->GetBodyHandle(Body.BodyName, Handle) || !World->ReadBody(Handle, State).IsSuccess()) return false;
            const FTransform Socket = Mesh->GetSocketTransform(Body.BodyName, RTS_World);
            const FBodyInstance* QueryBody = Mesh->GetBodyInstance(Body.BodyName);
            if (!QueryBody || !QueryBody->IsValidBodyInstance()) return false;
            const FTransform Query = QueryBody->GetUnrealWorldTransform(false, true);
            TestTrue(*FString::Printf(TEXT("%s rendered bone follows native origin"), *Body.BodyName.ToString()),
                Socket.GetLocation().Equals(State.PositionCm, 0.02) && Socket.GetRotation().Equals(State.Rotation, 1.0e-5));
            TestTrue(*FString::Printf(TEXT("%s query body follows native origin"), *Body.BodyName.ToString()),
                Query.GetLocation().Equals(State.PositionCm, 0.02) && Query.GetRotation().Equals(State.Rotation, 1.0e-5));
            if (bCheckInitial)
                TestTrue(TEXT("Admission preserves actual captured physical pose"),
                    State.PositionCm.Equals(DisplacedBodies[Index].GetLocation(), 0.02)
                    && State.Rotation.Equals(DisplacedBodies[Index].GetRotation(), 1.0e-5));
            OutCenter += State.CenterOfMassPositionCm * Body.MassKg;
        }
        OutCenter /= Mass;
        return true;
    };
    FVector Before, After;
    if (!TestTrue(TEXT("Read all admitted bodies"), ReadAndCheckPose(true, Before))) return false;
    // Internal PHAT constraints and self contacts cannot translate the whole rig's center of mass.
    // With no gravity/environment and zero initial velocity, this recovery requires the unchanged
    // authored targets; baking the capture discrepancy into those targets leaves the rig displaced.
    if (!Character->PublishAuthoredTargets(StepSeconds, Error) || !Character->StepAndPublish(StepSeconds, Error))
    { AddError(Error); return false; }
    if (!TestTrue(TEXT("Read all stepped bodies"), ReadAndCheckPose(false, After))) return false;
    TestTrue(TEXT("Drive recovers toward the unshifted authored pose"),
        FVector::DotProduct(After - Before, Displacement.GetSafeNormal()) < -5.0);
    Agent->DisableJoltPhysicalAnimation();
    FProphecyJoltWorldDiagnostics Diagnostics;
    TestTrue(TEXT("Explicit cleanup retires the complete rig"), World->GetDiagnostics(Diagnostics).IsSuccess()
        && Diagnostics.BodyCount == 0 && Diagnostics.ConstraintCount == 0);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltAngularLimitControlsTest,
    "Prophecy.Jolt.Character.AngularLimitControls",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltAngularLimitControlsTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::SwordFixture;
    // Match the existing sword fixtures: finish actual collision/Blueprint loading before
    // constructing the live character whose ownership and joint changes are under test.
    FJsonObject Preflight;
    FString PreflightError;
    if (!ProphecyJolt::StandaloneFixture::CaptureTrainingSword(Preflight, PreflightError))
    { AddError(PreflightError); return false; }
    UClass* SwordClass = LoadClass<AActor>(nullptr, TEXT("/Game/_mygame/sword/A_Sword.A_Sword_C"));
    if (!TestNotNull(TEXT("Actual sword Blueprint class"), SwordClass)) return false;
    TArray<FProphecyJoltBodyState> ControlInitial;
    double HeadMotionDegrees[2] = {};
    for (int32 Trial = 0; Trial < 2; ++Trial)
    {
        FWorldFixture Fixture;
        const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
            .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
            .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
        Fixture.World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
        if (!TestNotNull(TEXT("Angular control world"), Fixture.World) || !TestNotNull(TEXT("Engine"), GEngine)) return false;
        GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(Fixture.World);
        Fixture.World->InitializeActorsForPlay(FURL());
        Fixture.World->GetWorldSettings()->NotifyBeginPlay();
        auto* World = Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
        FProphecyJoltWorldSettings Settings;
        Settings.GravityCmPerSecondSquared = FVector::ZeroVector;
        Settings.WorkerThreads = 0;
        if (!World || !TestTrue(TEXT("Initialize angular control world"), World->InitializeSimulation(Settings).IsSuccess())) return false;
        FString Error;
        AProphecyAgent* Agent = nullptr;
        FProphecyJoltRigSnapshot Captured;
        if (!PrepareAgent(Fixture, Agent, Error, PoseId, FTransform(FVector(0, 0, 400)), &Captured))
        { AddError(Error); return false; }
        Agent->DisableJoltPhysicalAnimation();
        if (!TestTrue(TEXT("Restore source Physical mode"), Agent->SetSimulationMode(EProphecyAgentSimulationMode::Physical))) return false;
        auto* Mesh = Agent->GetPoseReferenceMesh();
        const auto* Asset = Mesh->GetPhysicsAsset();
        const auto CheckProfiles = [&](bool bAuthored) -> bool
        {
            if (!Asset || Mesh->Constraints.Num() != Asset->ConstraintSetup.Num()) return false;
            for (int32 Index = 0; Index < Mesh->Constraints.Num(); ++Index)
            {
                const auto* Joint = Mesh->Constraints[Index];
                const UPhysicsConstraintTemplate* Template = Asset->ConstraintSetup[Index];
                if (!Joint || !Template) return false;
                const auto& Actual = Joint->ProfileInstance;
                const auto& Expected = Template->DefaultInstance.ProfileInstance;
                if (Actual.ConeLimit.Swing1Motion != (bAuthored ? Expected.ConeLimit.Swing1Motion.GetValue() : ACM_Free)
                    || Actual.ConeLimit.Swing2Motion != (bAuthored ? Expected.ConeLimit.Swing2Motion.GetValue() : ACM_Free)
                    || Actual.TwistLimit.TwistMotion != (bAuthored ? Expected.TwistLimit.TwistMotion.GetValue() : ACM_Free)
                    || (bAuthored && (Actual.ConeLimit.Swing1LimitDegrees != Expected.ConeLimit.Swing1LimitDegrees
                        || Actual.ConeLimit.Swing2LimitDegrees != Expected.ConeLimit.Swing2LimitDegrees
                        || Actual.TwistLimit.TwistLimitDegrees != Expected.TwistLimit.TwistLimitDegrees))) return false;
            }
            return true;
        };
        if (!TestTrue(TEXT("Base toggle frees source Chaos angular limits"), Agent->SetUseAuthoredAngularLimits(false) && CheckProfiles(false))
            || !TestTrue(TEXT("Base toggle restores exact PHAT angular fields before admission"), Agent->SetUseAuthoredAngularLimits(true) && CheckProfiles(true))
            || !TestTrue(TEXT("Admit existing Free values"), Agent->SetUseAuthoredAngularLimits(false) && Agent->EnableJoltPhysicalAnimation())) return false;
        auto* Character = Agent->GetJoltCharacterComponent();
        Character->bAutomaticStep = false;
        Agent->SwordBlueprint = TSoftClassPtr<AActor>(SwordClass);
        FProphecyJoltBodyHandle EquipHand;
        FProphecyJoltBodyState EquipHandState;
        if (!TestTrue(TEXT("Free receiver profiles survive admission"), CheckProfiles(false))
            || !TestTrue(TEXT("Actual sword class is loaded before equip"), Agent->SwordBlueprint.Get() == SwordClass
                && SwordClass->GetPathName() == TEXT("/Game/_mygame/sword/A_Sword.A_Sword_C")
                && !SwordClass->HasAnyClassFlags(CLASS_Abstract | CLASS_NewerVersionExists))
            || !TestTrue(TEXT("Actual sword grip bone is available"), Mesh->DoesSocketExist(Agent->SwordHandSocket))
            || !TestTrue(TEXT("Re-admitted character owns the current native hand before equip"),
                Agent->IsJoltPhysicalAnimationEnabled() && Character->IsJoltPhysical()
                && !Character->IsEnablePending() && !Character->IsKinematicRestorePending() && !Character->IsSteppingStopped()
                && Character->GetBodyHandle(Mesh->GetSocketBoneName(Agent->SwordHandSocket), EquipHand)
                && World->ReadBody(EquipHand, EquipHandState).IsSuccess() && EquipHandState.bDynamic
                && Mesh->GetCollisionEnabled() == ECollisionEnabled::QueryOnly && !Mesh->IsAnySimulatingPhysics())) return false;
        const bool bEquipped = Agent->EquipSword(true);
        if (!TestTrue(TEXT("Equip actual sword before live angular edits"), bEquipped))
        {
            AActor* RetainedSword = Agent->GetHeldSword();
            const auto* RetainedBody = RetainedSword ? RetainedSword->FindComponentByClass<UProphecyJoltBodyComponent>() : nullptr;
            AddError(FString::Printf(TEXT("Equip diagnostics: trial=%d class=%s socket=%s bone=%s character=%s active=%d pending=%d stopped=%d error=%s sword=%s body=%s body_active=%d body_pending=%d body_error=%s"),
                Trial, *GetPathNameSafe(Agent->SwordBlueprint.Get()), *Agent->SwordHandSocket.ToString(),
                *Mesh->GetSocketBoneName(Agent->SwordHandSocket).ToString(), *GetPathNameSafe(Character),
                Character->IsJoltPhysical(), Character->IsEnablePending(), Character->IsSteppingStopped(), *Character->GetLastError(),
                *GetPathNameSafe(RetainedSword), *GetPathNameSafe(RetainedBody), RetainedBody && RetainedBody->IsJoltBody(),
                RetainedBody && RetainedBody->IsEnablePending(), RetainedBody ? *RetainedBody->GetLastError() : TEXT("not retained")));
            return false;
        }
        AActor* Sword = Agent->GetHeldSword();
        auto* Blade = Sword ? Sword->FindComponentByClass<UProphecyJoltBodyComponent>() : nullptr;
        if (!TestNotNull(TEXT("Native sword owner"), Blade)) return false;
        Blade->bAutomaticStep = false;
        FProphecyJoltBodyHandle SwordHandle;
        if (!TestTrue(TEXT("Read held sword identity"), Blade->GetBodyHandle(SwordHandle))) return false;
        TArray<FProphecyJoltBodyHandle> Handles;
        TArray<FProphecyJoltBodyState> Before;
        for (const auto& Source : Captured.Bodies)
        {
            auto& Handle = Handles.AddDefaulted_GetRef();
            auto& State = Before.AddDefaulted_GetRef();
            if (!Character->GetBodyHandle(Source.BodyName, Handle) || !World->ReadBody(Handle, State).IsSuccess()) return false;
        }
        // Possession and range changes select the real registered solver type.
        // No test-only override of player identity or frame-by-frame polling.
        TestEqual(TEXT("Unpossessed character has no speculative wrappers"), Character->GetSpeculativeSwingJointCount(), 0);
        APlayerController* Player = Fixture.World->SpawnActor<APlayerController>();
        if (!TestNotNull(TEXT("Player controller for possession policy"), Player)) return false;
        Player->bAutoManageActiveCameraTarget = false;
        Player->Possess(Agent);
        TestTrue(TEXT("Fixture agent is possessed by the player controller"), Agent->GetController() == Player);
        TestEqual(TEXT("Player's free joints stay native"), Character->GetSpeculativeSwingJointCount(), 0);
        if (!Agent->SetPhysicalJointAngularLimits(TEXT("hand_l"), ACM_Limited, 45, ACM_Limited, 45, ACM_Limited, 45, Error)) return false;
        TestEqual(TEXT("Only the player's limited wrist receives a wrapper"), Character->GetSpeculativeSwingJointCount(), 1);
        Agent->SetJoltJointLimitPredictionEnabled(false);
        TestFalse(TEXT("Runtime prediction preference is disabled"), Agent->IsJoltJointLimitPredictionEnabled());
        TestEqual(TEXT("Disabling prediction removes the extra solver wrapper"), Character->GetSpeculativeSwingJointCount(), 0);
        const FConstraintInstance* Wrist = nullptr;
        for (const FConstraintInstance* Joint : Mesh->Constraints)
            if (Joint && (Joint->ConstraintBone1 == TEXT("hand_l") || Joint->ConstraintBone2 == TEXT("hand_l"))) Wrist = Joint;
        TestTrue(TEXT("Prediction off preserves the requested 45-degree wrist profile"), Wrist
            && Wrist->ProfileInstance.ConeLimit.Swing1Motion == ACM_Limited
            && Wrist->ProfileInstance.ConeLimit.Swing2Motion == ACM_Limited
            && Wrist->ProfileInstance.TwistLimit.TwistMotion == ACM_Limited
            && Wrist->ProfileInstance.ConeLimit.Swing1LimitDegrees == 45.0f
            && Wrist->ProfileInstance.ConeLimit.Swing2LimitDegrees == 45.0f
            && Wrist->ProfileInstance.TwistLimit.TwistLimitDegrees == 45.0f);
        Player->UnPossess();
        Player->Possess(Agent);
        TestEqual(TEXT("Possession does not override disabled prediction"), Character->GetSpeculativeSwingJointCount(), 0);
        Agent->SetJoltJointLimitPredictionEnabled(true);
        TestTrue(TEXT("Prediction can be re-enabled at runtime"), Agent->IsJoltJointLimitPredictionEnabled());
        TestEqual(TEXT("Re-enabling prediction restores the existing limited wrist wrapper"), Character->GetSpeculativeSwingJointCount(), 1);
        Player->UnPossess();
        TestEqual(TEXT("Unpossession immediately removes wrapper"), Character->GetSpeculativeSwingJointCount(), 0);
        Player->Possess(Agent);
        TestEqual(TEXT("Re-possession restores limited wrist correction"), Character->GetSpeculativeSwingJointCount(), 1);
        if (!Agent->SetPhysicalJointAngularLimits(TEXT("hand_l"), ACM_Locked, 0, ACM_Locked, 0, ACM_Locked, 0, Error)) return false;
        TestEqual(TEXT("Player's locked wrist is the native joint"), Character->GetSpeculativeSwingJointCount(), 0);
        if (!Agent->SetUseAuthoredAngularLimits(false)) return false;
        Player->UnPossess();

        Agent->bWorldMagnetizationEnabled = true;
        Agent->WorldMagnetizationLinearStrengthScale = Agent->WorldMagnetizationAngularStrengthScale = 1.0f;
        Agent->SetAllBodyMagnetization(true, 1.0f, 1.0f);
        Agent->SetBodyMagnetization(TEXT("head"), true, 1.0f, 0.0f);
        if (!Character->PublishAuthoredTargets(StepSeconds, Error)) { AddError(Error); return false; }
        if (!TestTrue(TEXT("Base toggle restores PHAT on active Jolt rig"), Agent->SetUseAuthoredAngularLimits(true) && CheckProfiles(true))) return false;
        for (FName Child : { FName(TEXT("hand_r")), FName(TEXT("hand_l")), FName(TEXT("foot_r")) })
        {
            TArray<FConstraintProfileProperties> Original;
            int32 Selected = INDEX_NONE;
            if (!TestTrue(TEXT("Resolve actual child-to-parent PHAT joint"),
                ProphecyAngularLimits::PrepareParentJoint(*Mesh, Child, Original, Selected, Error))) return false;
            const FName Parent = Child == TEXT("hand_r") ? FName(TEXT("lowerarm_r"))
                : Child == TEXT("hand_l") ? FName(TEXT("lowerarm_l")) : FName(TEXT("calf_r"));
            const auto& Joint = *Mesh->Constraints[Selected];
            if (!TestTrue(TEXT("Child selects its parent connection, not a descendant"),
                (Joint.ConstraintBone1 == Child && Joint.ConstraintBone2 == Parent)
                || (Joint.ConstraintBone2 == Child && Joint.ConstraintBone1 == Parent))) return false;
            if (!TestTrue(TEXT("Set one live joint with mixed angular modes"),
                Agent->SetPhysicalJointAngularLimits(Child, ACM_Limited, 17.0f, ACM_Locked, 0.0f, ACM_Free, 180.0f, Error))) return false;
            const auto& Changed = Joint.ProfileInstance;
            TestTrue(TEXT("Requested angular fields mirrored after native success"),
                Changed.ConeLimit.Swing1Motion == ACM_Limited && Changed.ConeLimit.Swing1LimitDegrees == 17.0f
                && Changed.ConeLimit.Swing2Motion == ACM_Locked && Changed.TwistLimit.TwistMotion == ACM_Free);
            for (int32 Index = 0; Index < Original.Num(); ++Index)
                if (Index != Selected) TestTrue(TEXT("Other anatomical joints retain their angular settings"),
                    ProphecyAngularLimits::Equal(Original[Index], Mesh->Constraints[Index]->ProfileInstance));
            TestTrue(TEXT("Restore only the selected joint to PHAT"), Agent->ResetPhysicalJointAngularLimits(Child, Error) && CheckProfiles(true));
        }
        for (FName Child : { FName(TEXT("lowerarm_r")), FName(TEXT("lowerarm_l")) })
        {
            TestTrue(TEXT("Forearm single-axis node accepts full-range other axes"),
                Agent->SetPhysicalJointAngularLimits(Child, ACM_Limited, 180, ACM_Limited, 180, ACM_Limited, 1, Error));
            TestTrue(TEXT("Restore forearm after endpoint test"), Agent->ResetPhysicalJointAngularLimits(Child, Error));
        }
        TestFalse(TEXT("Unknown child rejected"), Agent->SetPhysicalJointAngularLimits(TEXT("missing_joint_bone"), ACM_Limited, 20, ACM_Limited, 20, ACM_Limited, 20, Error));
        TestFalse(TEXT("Root without a parent joint rejected"), Agent->ResetPhysicalJointAngularLimits(TEXT("root"), Error));
        TestFalse(TEXT("Out-of-range angle rejected before mutation"), Agent->SetPhysicalJointAngularLimits(TEXT("hand_r"), ACM_Limited, 181, ACM_Limited, 20, ACM_Limited, 20, Error));
        TestTrue(TEXT("Rejected requests leave all joints unchanged"), CheckProfiles(true));
        if (!TestTrue(TEXT("Base toggle frees active Jolt rig"), Agent->SetUseAuthoredAngularLimits(false) && CheckProfiles(false))) return false;
        for (int32 Index = 0; Index < Handles.Num(); ++Index)
        {
            FProphecyJoltBodyHandle Current;
            FProphecyJoltBodyState State;
            if (!Character->GetBodyHandle(Captured.Bodies[Index].BodyName, Current) || !World->ReadBody(Current, State).IsSuccess()) return false;
            TestTrue(TEXT("Toggle preserves body handles, poses and velocities without stepping"),
                Current.WorldLifetime == Handles[Index].WorldLifetime && Current.Slot == Handles[Index].Slot
                && Current.Generation == Handles[Index].Generation && State.PositionCm.Equals(Before[Index].PositionCm, 0)
                && State.Rotation.Equals(Before[Index].Rotation, 0)
                && State.CenterOfMassVelocityCmPerSecond.Equals(Before[Index].CenterOfMassVelocityCmPerSecond, 0)
                && State.AngularVelocityRadiansPerSecond.Equals(Before[Index].AngularVelocityRadiansPerSecond, 0));
        }
        FProphecyJoltWorldDiagnostics D;
        TestTrue(TEXT("Live angular changes preserve anatomical joints, fixed grip and exclusions"), World->GetDiagnostics(D).IsSuccess()
            && D.BodyCount == 23 && D.ConstraintCount == 22 && D.GenericJointCount == 1
            && D.SuppressedBodyPairCount == 1 && D.CompletedSteps == 0);
        FProphecyBodyMagnetizationSettings HeadDrive;
        TestTrue(TEXT("Angular edits retain existing physical-animation controls"), Agent->GetBodyMagnetizationSettings(TEXT("head"), HeadDrive)
            && HeadDrive.bMagnetizationEnabled && HeadDrive.LinearStrengthScale == 1.0f && HeadDrive.AngularStrengthScale == 0.0f);
        const auto* HeadJoint = Captured.Joints.FindByPredicate([](const auto& Joint) { return Joint.Bone1 == TEXT("head") || Joint.Bone2 == TEXT("head"); });
        if (!TestNotNull(TEXT("Actual PHAT head joint"), HeadJoint)) return false;
        const FName ParentName = HeadJoint->Bone1 == TEXT("head") ? HeadJoint->Bone2 : HeadJoint->Bone1;
        FProphecyJoltBodyHandle Head, Parent;
        if (!Character->GetBodyHandle(TEXT("head"), Head) || !Character->GetBodyHandle(ParentName, Parent)) return false;
        // These are the ordinary UE setters on the retained QueryOnly mesh, not a native test bypass.
        if (Trial == 1)
        {
            FConstraintInstance* Joint = Mesh->Constraints[HeadJoint->SourceConstraintIndex];
            Joint->SetAngularSwing1Limit(ACM_Locked, 0.0f);
            Joint->SetAngularSwing2Limit(ACM_Locked, 0.0f);
            Joint->SetAngularTwistLimit(ACM_Locked, 0.0f);
        }
        if (Trial == 0) ControlInitial = Before;
        else for (int32 Index = 0; Index < Before.Num(); ++Index)
            TestTrue(TEXT("Free and live-locked controls begin with identical native body states"),
                Before[Index].PositionCm.Equals(ControlInitial[Index].PositionCm, 0.0001)
                && Before[Index].Rotation.Equals(ControlInitial[Index].Rotation, 0.00001)
                && Before[Index].CenterOfMassVelocityCmPerSecond.Equals(ControlInitial[Index].CenterOfMassVelocityCmPerSecond, 0.0001)
                && Before[Index].AngularVelocityRadiansPerSecond.Equals(ControlInitial[Index].AngularVelocityRadiansPerSecond, 0.00001));
        FProphecyJoltBodyState HeadBefore, ParentBefore, HeadAfter, ParentAfter;
        if (!World->ReadBody(Head, HeadBefore).IsSuccess() || !World->ReadBody(Parent, ParentBefore).IsSuccess()
            || !World->SetBodyVelocity(Head, HeadBefore.CenterOfMassVelocityCmPerSecond, FVector(0, 0, 12), true).IsSuccess()) return false;
        const FQuat RelativeBefore = ParentBefore.Rotation.Inverse() * HeadBefore.Rotation;
        for (int32 Step = 0; Step < 8; ++Step)
            if (!Character->StepAndPublish(StepSeconds, Error)) { AddError(Error); return false; }
        if (!World->ReadBody(Head, HeadAfter).IsSuccess() || !World->ReadBody(Parent, ParentAfter).IsSuccess()) return false;
        const FQuat RelativeAfter = ParentAfter.Rotation.Inverse() * HeadAfter.Rotation;
        HeadMotionDegrees[Trial] = FMath::RadiansToDegrees(RelativeBefore.GetNormalized().AngularDistance(RelativeAfter.GetNormalized()));
        FProphecyJoltBodyHandle CurrentSword;
        TestTrue(TEXT("Stepping retains the exact held sword and grip"), Agent->GetHeldSword() == Sword
            && Blade->GetBodyHandle(CurrentSword) && CurrentSword.WorldLifetime == SwordHandle.WorldLifetime
            && CurrentSword.Slot == SwordHandle.Slot && CurrentSword.Generation == SwordHandle.Generation
            && World->GetDiagnostics(D).IsSuccess() && !D.bFaulted && D.GenericJointCount == 1
            && D.SuppressedBodyPairCount == 1 && Character->GetRevision() == 9);
        Agent->HideSword();
        Agent->DisableJoltPhysicalAnimation();
        TestTrue(TEXT("Angular frontend fixture cleans up all native ownership"), World->GetDiagnostics(D).IsSuccess()
            && D.BodyCount == 0 && D.ConstraintCount == 0 && D.SuppressedBodyPairCount == 0);
        if (HasAnyErrors()) return false;
    }
    AddInfo(FString::Printf(TEXT("Head relative rotation: free %.6f degrees, live UE locked %.6f degrees"), HeadMotionDegrees[0], HeadMotionDegrees[1]));
    TestTrue(TEXT("Free angular motion is exercised"), HeadMotionDegrees[0] > 10.0);
    TestTrue(TEXT("Next preparation applies live UE angular locks to actual Jolt motion"),
        HeadMotionDegrees[1] < HeadMotionDegrees[0] * 0.25 + 1.0);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltHighMagnetizationSafetyTest,
    "Prophecy.Jolt.Character.HighMagnetizationSafety",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltHighMagnetizationSafetyTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::SwordFixture;
    // Exercise the ordinary character coordinator, including its one/two-substep paths,
    // without depending on or saving the user's current project physics settings.
    struct FScopedSubstepping
    {
        UPhysicsSettings* Settings = UPhysicsSettings::Get();
        bool bPreviousSubstepping = Settings->bSubstepping;
        float PreviousMaxDelta = Settings->MaxSubstepDeltaTime;
        int32 PreviousMaxSteps = Settings->MaxSubsteps;
        FScopedSubstepping()
        {
            Settings->bSubstepping = true;
            Settings->MaxSubstepDeltaTime = 1.0f / 60.0f;
            Settings->MaxSubsteps = 2;
        }
        ~FScopedSubstepping()
        {
            Settings->bSubstepping = bPreviousSubstepping;
            Settings->MaxSubstepDeltaTime = PreviousMaxDelta;
            Settings->MaxSubsteps = PreviousMaxSteps;
        }
    } Substepping;
    constexpr int32 RequestedSteps = 360;
    const auto FiniteTransform = [](const FTransform& Transform)
    {
        return !Transform.ContainsNaN() && Transform.GetRotation().IsNormalized();
    };
    for (int32 Trial = 0; Trial < 4; ++Trial)
    {
        const float Gain = Trial < 2 ? 1.0f : 10.0f;
        const float DeltaSeconds = Trial % 2 == 0 ? 1.0f / 60.0f : 1.0f / 30.0f;
        const int32 ExpectedCollisionSteps = Trial % 2 == 0 ? 1 : 2;
        const FString Label = FString::Printf(TEXT("gain %.0f at %.0f Hz"), Gain, 1.0f / DeltaSeconds);
        FWorldFixture Fixture;
        const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
            .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
            .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
        Fixture.World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
        if (!TestNotNull(TEXT("High magnetization character world"), Fixture.World)
            || !TestNotNull(TEXT("Engine"), GEngine)) return false;
        GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(Fixture.World);
        Fixture.World->InitializeActorsForPlay(FURL());
        Fixture.World->GetWorldSettings()->NotifyBeginPlay();
        auto* World = Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
        if (!TestNotNull(TEXT("High magnetization native world"), World)) return false;
        FProphecyJoltWorldSettings Settings;
        Settings.GravityCmPerSecondSquared = FVector::ZeroVector;
        Settings.WorkerThreads = 2;
        if (!TestTrue(TEXT("Initialize threaded high magnetization world"), World->InitializeSimulation(Settings).IsSuccess())) return false;
        FString Error;
        AProphecyAgent* Agent = nullptr;
        FProphecyJoltRigSnapshot Captured;
        if (!PrepareAgent(Fixture, Agent, Error, PoseId, FTransform(FVector(0, 0, 400)), &Captured))
        { AddError(Label + TEXT(": ") + Error); return false; }
        auto* Character = Agent->GetJoltCharacterComponent();
        auto* Mesh = Agent->GetPoseReferenceMesh();
        if (!TestTrue(TEXT("Full simulated Jolt character owns the real PHAT rig"), Character && Mesh
            && Character->IsJoltPhysical() && !Character->IsEnablePending() && !Character->IsSteppingStopped()
            && Captured.Bodies.Num() == 22 && Captured.Joints.Num() == 21
            && Mesh->GetCollisionEnabled() == ECollisionEnabled::QueryOnly && !Mesh->IsAnySimulatingPhysics())) return false;
        Agent->bWorldMagnetizationEnabled = true;
        Agent->WorldMagnetizationLinearStrengthScale = Gain;
        Agent->WorldMagnetizationAngularStrengthScale = Gain;
        Agent->SetAllBodyMagnetization(true, 1.0f, 1.0f);
        if (!TestTrue(TEXT("Retain authored PHAT limits during high gain stress"), Agent->SetUseAuthoredAngularLimits(true))) return false;
        FProphecyNNPoseSnapshot Authored;
        if (!TestTrue(TEXT("Read real authored target pose"), FProphecyNNPoseStore::GetAgentLocalPose(PoseId, Authored))) return false;
        TArray<FProphecyJoltBodyHandle> Handles;
        TArray<FVector> InitialPositions;
        for (const auto& Source : Captured.Bodies)
        {
            auto& Handle = Handles.AddDefaulted_GetRef();
            FProphecyJoltBodyState State;
            if (!Character->GetBodyHandle(Source.BodyName, Handle) || !World->ReadBody(Handle, State).IsSuccess())
            { AddError(Label + TEXT(": failed to read admitted body ") + Source.BodyName.ToString()); return false; }
            InitialPositions.Add(State.PositionCm);
        }
        FProphecyJoltBodyHandle Head;
        FProphecyJoltBodyState HeadBefore;
        if (!TestTrue(TEXT("Apply a finite head disturbance to an active anatomical joint"),
            Character->GetBodyHandle(TEXT("head"), Head) && World->ReadBody(Head, HeadBefore).IsSuccess()
            && World->SetBodyVelocity(Head, FVector(150, -75, 25), FVector(0, 0, 12), true).IsSuccess())) return false;
        const auto PublishedPoseIsFinite = [&]()
        {
            if (!FiniteTransform(Mesh->GetComponentTransform())
                || Mesh->GetComponentSpaceTransforms().Num() != Authored.BoneNames.Num()) return false;
            for (const FTransform& Transform : Mesh->GetComponentSpaceTransforms())
                if (!FiniteTransform(Transform)) return false;
            for (const auto& Source : Captured.Bodies)
            {
                const FBodyInstance* QueryBody = Mesh->GetBodyInstance(Source.BodyName);
                if (!QueryBody || !QueryBody->IsValidBodyInstance()
                    || !FiniteTransform(QueryBody->GetUnrealWorldTransform(false, true))
                    || !FiniteTransform(Mesh->GetSocketTransform(Source.BodyName, RTS_World))) return false;
            }
            return true;
        };
        if (!TestTrue(TEXT("Admission publishes a finite complete skeleton and query bodies"), PublishedPoseIsFinite())) return false;
        int32 SuccessfulSteps = 0;
        bool bContainedFault = false;
        double MaximumBodyMovementCm = 0.0;
        double MaximumSpeedCmPerSecond = 0.0;
        FProphecyJoltWorldDiagnostics Diagnostics;
        for (int32 Step = 0; Step < RequestedSteps; ++Step)
        {
            // Both previous/current targets deliberately agree: the test drives actual motion
            // without relying on engine ticks, animation interpolation time or NN inference.
            const double Time = (Step + 1) * double(DeltaSeconds);
            const FTransform TargetCarrier(FQuat(FVector::UpVector, FMath::DegreesToRadians(15.0 * FMath::Sin(Time * 2.0))),
                FVector(20.0 * FMath::Sin(Time * 3.0), 10.0 * FMath::Sin(Time * 2.0), 400.0 + 5.0 * FMath::Sin(Time)));
            FProphecyNNPoseStore::SetAgentLocalPose(PoseId, Authored.BoneNames, Authored.LocalTransforms,
                Authored.ComponentTransforms, Authored.ComponentTransforms, TargetCarrier, TargetCarrier, Time, false);
            if (!Character->PublishAuthoredTargets(DeltaSeconds, Error))
            { AddError(Label + TEXT(": target preparation failed: ") + Error); return false; }
            const uint64 BeforeRevision = Character->GetRevision();
            if (!World->GetDiagnostics(Diagnostics).IsSuccess()) return false;
            const uint64 BeforeSteps = Diagnostics.CompletedSteps;
            const TArray<FTransform> BeforePose = Mesh->GetComponentSpaceTransforms();
            const FTransform BeforeCarrier = Mesh->GetComponentTransform();
            const auto PublishedPoseIsUnchanged = [&]()
            {
                const auto& AfterPose = Mesh->GetComponentSpaceTransforms();
                if (!BeforeCarrier.Equals(Mesh->GetComponentTransform(), 0.0) || BeforePose.Num() != AfterPose.Num()) return false;
                for (int32 Bone = 0; Bone < BeforePose.Num(); ++Bone)
                    if (!BeforePose[Bone].Equals(AfterPose[Bone], 0.0)) return false;
                return true;
            };
            const bool bStepped = Character->StepAndPublish(DeltaSeconds, Error);
            if (!TestTrue(*(Label + TEXT(": every published pose remains finite")), PublishedPoseIsFinite())
                || !TestTrue(TEXT("Read completed/faulted world diagnostics"), World->GetDiagnostics(Diagnostics).IsSuccess())) return false;
            if (!bStepped)
            {
                // A setup/client-publication failure must not masquerade as a contained solver failure.
                const bool bExpectedFailure = Gain > 1.0f && Diagnostics.bFaulted && !Diagnostics.Failure.IsEmpty()
                    && Diagnostics.LastUpdateErrorBits == (1u << 3) // Pinned native NumericalFailure; not capacity/setup failure.
                    && Error == Diagnostics.Failure && Character->IsSteppingStopped()
                    && Character->GetRevision() == BeforeRevision && Diagnostics.CompletedSteps == BeforeSteps
                    && PublishedPoseIsUnchanged();
                if (!TestTrue(*(Label + TEXT(": native numerical failure stops before publishing the failed step")), bExpectedFailure))
                { AddError(Error); return false; }
                const FString FirstError = Error;
                for (int32 Retry = 0; Retry < 3; ++Retry)
                {
                    FString RetryError;
                    const bool bRetried = Character->StepAndPublish(DeltaSeconds, RetryError);
                    const auto NativeRetry = World->Step(DeltaSeconds, ExpectedCollisionSteps);
                    if (!TestTrue(TEXT("Stopped character and faulted native world reject repeated stepping"),
                        !bRetried && RetryError == FirstError && NativeRetry.Code == EProphecyJoltWorldResult::PhysicsFailure
                        && World->GetDiagnostics(Diagnostics).IsSuccess() && Diagnostics.CompletedSteps == BeforeSteps
                        && Character->GetRevision() == BeforeRevision && PublishedPoseIsUnchanged() && PublishedPoseIsFinite())) return false;
                }
                bContainedFault = true;
                AddInfo(FString::Printf(TEXT("%s safely stopped after %d completed steps: %s"), *Label, SuccessfulSteps, *FirstError));
                break;
            }
            ++SuccessfulSteps;
            if (!TestTrue(TEXT("Successful step uses the expected worker/substep configuration and publishes exactly once"),
                !Diagnostics.bFaulted && !Character->IsSteppingStopped() && Diagnostics.Settings.WorkerThreads == 2
                && Diagnostics.LastCollisionSteps == ExpectedCollisionSteps && Diagnostics.CompletedSteps == BeforeSteps + 1
                && Character->GetRevision() == BeforeRevision + 1)) return false;
            for (int32 Index = 0; Index < Handles.Num(); ++Index)
            {
                FProphecyJoltBodyState State;
                if (!World->ReadBody(Handles[Index], State).IsSuccess() || State.PositionCm.ContainsNaN()
                    || State.Rotation.ContainsNaN() || !State.Rotation.IsNormalized()
                    || State.CenterOfMassVelocityCmPerSecond.ContainsNaN() || State.AngularVelocityRadiansPerSecond.ContainsNaN())
                { AddError(Label + TEXT(": successful step exposed an invalid native body")); return false; }
                MaximumBodyMovementCm = FMath::Max(MaximumBodyMovementCm, FVector::Distance(State.PositionCm, InitialPositions[Index]));
                MaximumSpeedCmPerSecond = FMath::Max(MaximumSpeedCmPerSecond, State.CenterOfMassVelocityCmPerSecond.Length());
            }
        }
        TestTrue(*(Label + TEXT(": all requested steps complete or high gain is explicitly contained")),
            SuccessfulSteps == RequestedSteps || bContainedFault);
        if (Gain == 1.0f)
            TestTrue(TEXT("Ordinary strength keeps moving through all 360 steps"), !bContainedFault
                && SuccessfulSteps == RequestedSteps && MaximumBodyMovementCm > 5.0 && MaximumSpeedCmPerSecond > 1.0);
        if (!bContainedFault)
            TestTrue(TEXT("Completed stress trial exercised physical movement"), MaximumBodyMovementCm > 5.0 && MaximumSpeedCmPerSecond > 1.0);
        TestTrue(TEXT("Safety handling does not silently reduce the requested world gain"),
            Agent->WorldMagnetizationLinearStrengthScale == Gain && Agent->WorldMagnetizationAngularStrengthScale == Gain);
        AddInfo(FString::Printf(TEXT("%s: completed=%d/%d contained=%d max_body_movement_cm=%.6f max_speed_cm_s=%.6f"),
            *Label, SuccessfulSteps, RequestedSteps, bContainedFault, MaximumBodyMovementCm, MaximumSpeedCmPerSecond));
        Agent->DisableJoltPhysicalAnimation();
        if (!TestTrue(TEXT("Normal and faulted character cleanup retires every body and anatomical joint"),
            !Character->IsJoltPhysical() && World->GetDiagnostics(Diagnostics).IsSuccess()
            && Diagnostics.BodyCount == 0 && Diagnostics.ConstraintCount == 0 && Diagnostics.SuppressedBodyPairCount == 0)
            || !TestTrue(TEXT("Threaded native world shuts down cleanly after stress"), World->ShutdownSimulation().IsSuccess())) return false;
        if (HasAnyErrors()) return false;
    }
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltAuthoredTrajectoryTest,
    "Prophecy.Jolt.Character.AuthoredTrajectoryAcrossSubstepChanges",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltAuthoredTrajectoryTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::SwordFixture;
    struct FScopedSubstepping
    {
        UPhysicsSettings* Settings = UPhysicsSettings::Get();
        bool bPreviousSubstepping = Settings->bSubstepping;
        float PreviousMaxDelta = Settings->MaxSubstepDeltaTime;
        int32 PreviousMaxSteps = Settings->MaxSubsteps;
        FScopedSubstepping()
        {
            Settings->bSubstepping = true;
            Settings->MaxSubstepDeltaTime = 0.016667f;
            Settings->MaxSubsteps = 64;
        }
        ~FScopedSubstepping()
        {
            Settings->bSubstepping = bPreviousSubstepping;
            Settings->MaxSubstepDeltaTime = PreviousMaxDelta;
            Settings->MaxSubsteps = PreviousMaxSteps;
        }
    } Substepping;
    struct FStationarySample { FVector Position, Velocity; };
    TArray<FStationarySample> StationarySamples;
    FVector StationaryInitialPelvis = FVector::ZeroVector;
    // A matched stationary trial verifies the reference pose is a resting fixture, then measures
    // the residual solver response. The moving trial must add only the requested rigid translation.
    for (int32 Trial = 0; Trial < 2; ++Trial)
    {
    const bool bMoving = Trial == 1;
    FWorldFixture Fixture;
    const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
        .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
    Fixture.World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
    if (!TestNotNull(TEXT("Authored trajectory character world"), Fixture.World)
        || !TestNotNull(TEXT("Engine"), GEngine)) return false;
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(Fixture.World);
    Fixture.World->InitializeActorsForPlay(FURL());
    Fixture.World->GetWorldSettings()->NotifyBeginPlay();
    auto* World = Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    if (!TestNotNull(TEXT("Authored trajectory native world"), World)) return false;
    FProphecyJoltWorldSettings Settings;
    Settings.GravityCmPerSecondSquared = FVector::ZeroVector;
    Settings.WorkerThreads = 0;
    if (!TestTrue(TEXT("Initialize isolated trajectory world"), World->InitializeSimulation(Settings).IsSuccess())) return false;
    FString Error;
    AProphecyAgent* Agent = nullptr;
    FProphecyJoltRigSnapshot Captured;
    if (!PrepareAgent(Fixture, Agent, Error, PoseId, FTransform(FVector(0, 0, 400)), &Captured))
    { AddError(Error); return false; }
    auto* Character = Agent->GetJoltCharacterComponent();
    if (!TestTrue(TEXT("Trajectory exercises the actual 22-body, 21-joint dynamic character"),
        Character && Character->IsJoltPhysical() && !Character->IsEnablePending()
        && Captured.Bodies.Num() == 22 && Captured.Joints.Num() == 21)) return false;
    Agent->bWorldMagnetizationEnabled = true;
    Agent->WorldMagnetizationLinearStrengthScale = 1.0f;
    Agent->WorldMagnetizationAngularStrengthScale = 1.0f;
    Agent->SetAllBodyMagnetization(true, 1.0f, 1.0f);
    // Isolate authored-target timing: the reference pose is not guaranteed to satisfy the asset's
    // angular limits. Free those limits only in this fixture, preserving every PHAT linear anchor,
    // and remove self contacts, gravity and environmental contacts in both matched trials.
    if (!Agent->SetJoltSelfCollisionEnabled(false, Error)) { AddError(Error); return false; }
    if (!TestTrue(TEXT("Free angular limits only for the trajectory fixture"), Agent->SetUseAuthoredAngularLimits(false))) return false;
    const auto* PhysicalMesh = Agent->GetPoseReferenceMesh();
    double MaximumInitialAnchorSeparationCm = 0.0;
    for (const FProphecyJoltRigJoint& Joint : Captured.Joints)
    {
        const FConstraintInstance* Live = PhysicalMesh->Constraints[Joint.SourceConstraintIndex];
        if (!TestTrue(TEXT("Trajectory retains each anatomical linear lock and frees only angular limits"), Live
            && Live->ProfileInstance.LinearLimit.XMotion == Joint.CurrentProfile.LinearLimit.XMotion
            && Live->ProfileInstance.LinearLimit.YMotion == Joint.CurrentProfile.LinearLimit.YMotion
            && Live->ProfileInstance.LinearLimit.ZMotion == Joint.CurrentProfile.LinearLimit.ZMotion
            && Live->ProfileInstance.ConeLimit.Swing1Motion == ACM_Free
            && Live->ProfileInstance.ConeLimit.Swing2Motion == ACM_Free
            && Live->ProfileInstance.TwistLimit.TwistMotion == ACM_Free)) return false;
        const FVector Anchor1 = (Joint.Frame1 * Captured.Bodies[Joint.Body1Index].BodyOriginToWorld).GetLocation();
        const FVector Anchor2 = (Joint.Frame2 * Captured.Bodies[Joint.Body2Index].BodyOriginToWorld).GetLocation();
        MaximumInitialAnchorSeparationCm = FMath::Max(MaximumInitialAnchorSeparationCm, FVector::Distance(Anchor1, Anchor2));
    }
    if (!bMoving) AddInfo(FString::Printf(TEXT("Trajectory fixture initial PHAT anchor separation: max %.9f cm"), MaximumInitialAnchorSeparationCm));
    FProphecyNNPoseSnapshot Authored;
    if (!TestTrue(TEXT("Read authored reference pose"), FProphecyNNPoseStore::GetAgentLocalPose(PoseId, Authored))) return false;
    const int32 PelvisIndex = Authored.BoneNames.IndexOfByKey(TEXT("pelvis"));
    if (!TestTrue(TEXT("Authored pose contains a pelvis transform"), Authored.ComponentTransforms.IsValidIndex(PelvisIndex))) return false;
    const FTransform InitialCarrier = Authored.ComponentWorldTransform;
    const FVector InitialPelvis = (Authored.ComponentTransforms[PelvisIndex] * InitialCarrier).GetLocation();
    if (!bMoving) StationaryInitialPelvis = InitialPelvis;
    else if (!TestTrue(TEXT("Stationary and translating trials have identical authored initial pelvis"),
        InitialPelvis.Equals(StationaryInitialPelvis, 1.0e-6))) return false;
    const auto PublishAt = [&](double DisplacementCm, double SourceTime, float DeltaSeconds)
    {
        FTransform Carrier = InitialCarrier;
        Carrier.AddToTranslation(FVector(DisplacementCm, 0, 0));
        // Equal source endpoints bypass NN interpolation only in this fixture. The character must
        // construct the previous/current trajectory from successful authored publications itself.
        FProphecyNNPoseStore::SetAgentLocalPose(PoseId, Authored.BoneNames, Authored.LocalTransforms,
            Authored.ComponentTransforms, Authored.ComponentTransforms, Carrier, Carrier, SourceTime, false);
        return Character->PublishAuthoredTargets(DeltaSeconds, Error);
    };
    // Let the real PHAT constraints settle while seeding completed-step target history.
    for (int32 Step = 0; Step < 12; ++Step)
    {
        if (!PublishAt(0.0, 0.0, 0.0166668f) || !Character->StepAndPublish(0.0166668f, Error))
        { AddError(Error); return false; }
    }
    constexpr int32 RequestedSteps = 240;
    constexpr double SpeedCmPerSecond = 180.0;
    // These allow 0.5 mm of translation error and <0.3% speed error. In particular, merely
    // reaching the correct endpoint while ending every two-substep frame at zero speed must fail.
    constexpr double PositionToleranceCm = 0.05;
    constexpr double VelocityToleranceCmPerSecond = 0.5;
    double Time = 0.0;
    double MaximumEndpointErrorCm = 0.0;
    double MaximumVelocityErrorCmPerSecond = 0.0;
    double MaximumTrackingChangeCm = 0.0;
    double MaximumStationarySpeedCmPerSecond = 0.0;
    FVector PreviousTrackingError = FVector::ZeroVector;
    FProphecyJoltWorldDiagnostics Diagnostics;
    for (int32 Step = 0; Step < RequestedSteps; ++Step)
    {
        // Captured adjacent frame durations straddle the original configured step threshold.
        const float DeltaSeconds = Step % 2 == 0 ? 0.0166668f : 0.0170364f;
        const int32 ExpectedCollisionSteps = Step % 2 == 0 ? 1 : 2;
        const double PreviousDisplacement = bMoving ? SpeedCmPerSecond * Time : 0.0;
        Time += double(DeltaSeconds);
        const double Displacement = bMoving ? SpeedCmPerSecond * Time : 0.0;
        if (Step >= RequestedSteps / 2)
        {
            // The last publication wins, but neither a superseded nor an identical publication
            // before the same physical step may replace the previous completed frame's start.
            const double Provisional = Step % 3 == 0
                ? FMath::Lerp(PreviousDisplacement, Displacement, 0.75) : Displacement;
            if (!PublishAt(Provisional, Time, DeltaSeconds)) { AddError(Error); return false; }
        }
        if (!PublishAt(Displacement, Time, DeltaSeconds) || !Character->StepAndPublish(DeltaSeconds, Error))
        { AddError(Error); return false; }
        FTransform Pelvis;
        FVector Velocity, AngularVelocity;
        bool bSimulating = false;
        if (!TestTrue(TEXT("Read actual dynamic pelvis and native completed substep count"),
            Character->GetBodyState(TEXT("pelvis"), Pelvis, Velocity, AngularVelocity, bSimulating) && bSimulating
            && World->GetDiagnostics(Diagnostics).IsSuccess() && Diagnostics.LastCollisionSteps == ExpectedCollisionSteps
            && Diagnostics.BodyCount == 22 && Diagnostics.ConstraintCount == 21)) return false;
        if (!TestTrue(TEXT("Actual pelvis state remains finite in both matched trials"),
            !Pelvis.ContainsNaN() && !Velocity.ContainsNaN() && !AngularVelocity.ContainsNaN())) return false;
        if (!bMoving)
        {
            StationarySamples.Add({Pelvis.GetLocation(), Velocity});
            MaximumStationarySpeedCmPerSecond = FMath::Max(MaximumStationarySpeedCmPerSecond, Velocity.Length());
            if (Velocity.Length() > VelocityToleranceCmPerSecond)
            {
                AddError(FString::Printf(TEXT("Stationary trajectory fixture is not at rest at step %d: velocity=(%s), speed=%.9f cm/s, initial_anchor_separation=%.9f cm"),
                    Step, *Velocity.ToString(), Velocity.Length(), MaximumInitialAnchorSeparationCm));
                return false;
            }
            continue;
        }
        const FStationarySample& Control = StationarySamples[Step];
        const FVector TrackingError = Pelvis.GetLocation() - Control.Position - FVector(Displacement, 0, 0);
        const FVector VelocityResidual = Velocity - Control.Velocity - FVector(SpeedCmPerSecond, 0, 0);
        const double EndpointError = TrackingError.Length();
        const double VelocityError = VelocityResidual.Length();
        const double TrackingChange = Step == 0 ? 0.0 : (TrackingError - PreviousTrackingError).Length();
        MaximumEndpointErrorCm = FMath::Max(MaximumEndpointErrorCm, EndpointError);
        MaximumVelocityErrorCmPerSecond = FMath::Max(MaximumVelocityErrorCmPerSecond, VelocityError);
        MaximumTrackingChangeCm = FMath::Max(MaximumTrackingChangeCm, TrackingChange);
        if (!FMath::IsFinite(EndpointError) || !FMath::IsFinite(VelocityError)
            || EndpointError > PositionToleranceCm || VelocityError > VelocityToleranceCmPerSecond
            || TrackingChange > PositionToleranceCm)
        {
            AddError(FString::Printf(TEXT("Trajectory step %d (%d substeps, duplicate=%d): endpoint_error_cm=%.9f velocity_error_cm_s=%.9f tracking_change_cm=%.9f actual_velocity=(%s) stationary_velocity=(%s) residual_velocity=(%s)"),
                Step, ExpectedCollisionSteps, Step >= RequestedSteps / 2, EndpointError, VelocityError, TrackingChange,
                *Velocity.ToString(), *Control.Velocity.ToString(), *VelocityResidual.ToString()));
            return false;
        }
        PreviousTrackingError = TrackingError;
    }
    if (!bMoving)
        AddInfo(FString::Printf(TEXT("Matched stationary 22-body rig with free angular limits: max pelvis speed=%.9f cm/s"),
            MaximumStationarySpeedCmPerSecond));
    else
        AddInfo(FString::Printf(TEXT("Real 22-body rig relative to stationary control: %d alternating steps, final %d with duplicate publications; max_endpoint_cm=%.9f max_velocity_error_cm_s=%.9f max_tracking_change_cm=%.9f"),
            RequestedSteps, RequestedSteps / 2, MaximumEndpointErrorCm, MaximumVelocityErrorCmPerSecond, MaximumTrackingChangeCm));
    Agent->DisableJoltPhysicalAnimation();
    TestTrue(TEXT("Trajectory cleanup retires every actual body and anatomical joint"), World->GetDiagnostics(Diagnostics).IsSuccess()
        && Diagnostics.BodyCount == 0 && Diagnostics.ConstraintCount == 0 && Diagnostics.SuppressedBodyPairCount == 0);
    TestTrue(TEXT("Trajectory native world shuts down cleanly"), World->ShutdownSimulation().IsSuccess());
    if (HasAnyErrors()) return false;
    }
    return !HasAnyErrors();
}

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
            && (bJolt || Diagnostics.SuppressedBodyPairCount == 0)
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
    if (!TestTrue(TEXT("Explicit active disable selects Chaos and preserves Sim"),
        !Agent->IsJoltPhysicalAnimationSelected()
        && CheckOwnership(EProphecyAgentSimulationMode::Physical, false))) return false;
    if (!TestTrue(TEXT("Explicit enable can select Jolt again"), Agent->EnableJoltPhysicalAnimation()
        && CheckOwnership(EProphecyAgentSimulationMode::Physical, true))
        || !Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic)) return false;
    Agent->DisableJoltPhysicalAnimation(); // Already Kinematic: clear the retained choice too.
    if (!TestTrue(TEXT("HalfSim preserves mode while selecting Jolt for the next Sim"),
        Agent->SetSimulationMode(EProphecyAgentSimulationMode::HalfSim) && Agent->EnableJoltPhysicalAnimation()
        && Agent->IsJoltPhysicalAnimationSelected() && CheckOwnership(EProphecyAgentSimulationMode::HalfSim, false)
        && Agent->SetSimulationMode(EProphecyAgentSimulationMode::Physical)
        && CheckOwnership(EProphecyAgentSimulationMode::Physical, true))) return false;

    // A switch from a finalized-pose callback must restore Chaos only after that finalizer unwinds.
    for (bool bRequestKinematic : { false, true })
    {
        if (!Agent->EnableJoltPhysicalAnimation() || !Character->PublishAuthoredTargets(StepSeconds, Error)) return false;
        bool bDisabledFromFinalizer = false;
        const auto Finalized = Mesh->RegisterOnBoneTransformsFinalizedDelegate(
            FOnBoneTransformsFinalizedMultiCast::FDelegate::CreateLambda([&]()
            {
                if (bDisabledFromFinalizer) return;
                bDisabledFromFinalizer = true;
                Agent->DisableJoltPhysicalAnimation();
                if (bRequestKinematic) Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic);
            }));
        Character->StepAndPublish(StepSeconds, Error); // The callback intentionally removes the publishing rig.
        Mesh->UnregisterOnBoneTransformsFinalizedDelegate(Finalized);
        if (!TestTrue(TEXT("Finalizer backend switch restores the requested controller at the same boundary"),
            bDisabledFromFinalizer && CheckOwnership(bRequestKinematic
                ? EProphecyAgentSimulationMode::Kinematic : EProphecyAgentSimulationMode::Physical, false))) return false;
    }
    if (!Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic)) return false;
    Agent->DisableJoltPhysicalAnimation();
    if (!Agent->SetSimulationMode(EProphecyAgentSimulationMode::Physical)) return false;

    // Exercise real late-world-tick admission/cancellation, without editing coordinator flags.
    bool bRequested = false, bPending = false, bCancelled = false, bDisablePreservedSim = false;
    const FDelegateHandle LateRequest = FWorldDelegates::OnWorldPostActorTick.AddLambda(
        [&](UWorld* TickingWorld, ELevelTick, float)
        {
            if (TickingWorld != Fixture.World || bRequested) return;
            bRequested = true;
            const bool bAccepted = Agent->EnableJoltPhysicalAnimation();
            bPending = bAccepted && Character->IsEnablePending() && !Character->IsJoltPhysical();
            Agent->DisableJoltPhysicalAnimation();
            bDisablePreservedSim = !Character->IsEnablePending() && CheckOwnership(EProphecyAgentSimulationMode::Physical, false);
            Agent->EnableJoltPhysicalAnimation();
            bCancelled = Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic)
                && !Character->IsEnablePending() && !Character->OnDeferredEnableCompleted.IsBound();
        });
    Fixture.World->Tick(LEVELTICK_All, StepSeconds);
    FWorldDelegates::OnWorldPostActorTick.Remove(LateRequest);
    Fixture.World->Tick(LEVELTICK_All, StepSeconds);
    if (!TestTrue(TEXT("Cancelled deferred admission preserves mode and cannot latch a new Jolt preference"), bRequested && bPending && bDisablePreservedSim && bCancelled
        && CheckOwnership(EProphecyAgentSimulationMode::Kinematic, false)
        && Agent->SetSimulationMode(EProphecyAgentSimulationMode::Physical)
        && CheckOwnership(EProphecyAgentSimulationMode::Physical, false))) return false;
    TestTrue(TEXT("Backend preference fixture leaves no orphan rig"),
        Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic)
        && CheckOwnership(EProphecyAgentSimulationMode::Kinematic, false));
    TestTrue(TEXT("Backend preference native world shuts down cleanly"), World->ShutdownSimulation().IsSuccess());
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltRuntimeSelfCollisionControlsTest,
    "Prophecy.Jolt.Character.RuntimeSelfCollisionControls",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltRuntimeSelfCollisionControlsTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::SwordFixture;
    FJsonObject Preflight;
    FString Error;
    if (!ProphecyJolt::StandaloneFixture::CaptureTrainingSword(Preflight, Error)) { AddError(Error); return false; }
    UClass* SwordClass = LoadClass<AActor>(nullptr, TEXT("/Game/_mygame/sword/A_Sword.A_Sword_C"));
    if (!TestNotNull(TEXT("Actual sword Blueprint class"), SwordClass)) return false;
    FWorldFixture Fixture;
    const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
        .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
    Fixture.World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
    if (!TestNotNull(TEXT("Self-collision controls world"), Fixture.World) || !TestNotNull(TEXT("Engine"), GEngine)) return false;
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(Fixture.World);
    Fixture.World->InitializeActorsForPlay(FURL());
    Fixture.World->GetWorldSettings()->NotifyBeginPlay();
    auto* World = Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltWorldSettings Settings;
    Settings.GravityCmPerSecondSquared = FVector::ZeroVector;
    Settings.WorkerThreads = 2;
    if (!World || !TestTrue(TEXT("Initialize self-collision controls world"), World->InitializeSimulation(Settings).IsSuccess())) return false;
    AProphecyAgent* Agent = nullptr;
    FProphecyJoltRigSnapshot Captured;
    if (!PrepareAgent(Fixture, Agent, Error, PoseId, FTransform(FVector(0, 0, 400)), &Captured)) { AddError(Error); return false; }
    auto* Character = Agent->GetJoltCharacterComponent();
    auto* Mesh = Agent->GetPoseReferenceMesh();
    Agent->SwordBlueprint = TSoftClassPtr<AActor>(SwordClass);
    if (!TestTrue(TEXT("Equip actual sword before runtime self-collision edits"), Agent->EquipSword(true))) return false;
    AActor* Sword = Agent->GetHeldSword();
    auto* Blade = Sword ? Sword->FindComponentByClass<UProphecyJoltBodyComponent>() : nullptr;
    if (!TestNotNull(TEXT("Held native sword"), Blade)) return false;
    Blade->bAutomaticStep = false;
    FProphecyJoltBodyHandle SwordHandle;
    FProphecyJoltBodyState SwordBefore;
    if (!Blade->GetBodyHandle(SwordHandle) || !World->ReadBody(SwordHandle, SwordBefore).IsSuccess()) return false;
    FProphecyJoltBodyHandle MovingHead;
    if (!TestTrue(TEXT("Seed nonzero motion before policy-only changes"), Character->GetBodyHandle(TEXT("head"), MovingHead)
        && World->SetBodyVelocity(MovingHead, FVector(25, -10, 5), FVector(0, 1.5, 0), true).IsSuccess())) return false;
    TArray<FName> BodyNames;
    TArray<FProphecyJoltBodyHandle> Handles;
    TArray<FProphecyJoltBodyState> Before;
    for (const auto& Source : Captured.Bodies)
    {
        BodyNames.Add(Source.BodyName);
        auto& Handle = Handles.AddDefaulted_GetRef();
        auto& State = Before.AddDefaulted_GetRef();
        if (!Character->GetBodyHandle(Source.BodyName, Handle) || !World->ReadBody(Handle, State).IsSuccess()) return false;
    }
    const auto PairKey = [](int32 A, int32 B) { return (uint64(FMath::Min(A, B)) << 32) | uint32(FMath::Max(A, B)); };
    TSet<uint64> AuthoredDisabled;
    for (const auto& Pair : Captured.DisabledPairs) AuthoredDisabled.Add(PairKey(Pair.Body1Index, Pair.Body2Index));
    int32 PairA = INDEX_NONE, PairB = INDEX_NONE;
    for (int32 A = 0; A < BodyNames.Num() && PairA == INDEX_NONE; ++A)
        for (int32 B = A + 1; B < BodyNames.Num(); ++B)
            if (!AuthoredDisabled.Contains(PairKey(A, B))) { PairA = A; PairB = B; break; }
    if (!TestTrue(TEXT("Real PHAT provides both enabled pairs and authored exclusions"), PairA != INDEX_NONE && !Captured.DisabledPairs.IsEmpty())) return false;
    const TArray<FName> OneBody = { BodyNames[PairA] };
    const auto CheckMatrix = [&](bool bMasterEnabled, const TSet<int32>& DisabledBodies, const TSet<uint64>& DisabledPairs)
    {
        for (int32 A = 0; A < BodyNames.Num(); ++A)
            for (int32 B = A + 1; B < BodyNames.Num(); ++B)
            {
                bool bActual = false, bReverse = false;
                const bool bExpected = bMasterEnabled && !AuthoredDisabled.Contains(PairKey(A, B))
                    && !DisabledBodies.Contains(A) && !DisabledBodies.Contains(B) && !DisabledPairs.Contains(PairKey(A, B));
                if (!Agent->GetJoltBodyPairSelfCollisionEnabled(BodyNames[A], BodyNames[B], bActual, Error)
                    || !Agent->GetJoltBodyPairSelfCollisionEnabled(BodyNames[B], BodyNames[A], bReverse, Error)
                    || bActual != bExpected || bReverse != bExpected)
                { AddError(FString::Printf(TEXT("Self-collision pair %s/%s expected=%d actual=%d reverse=%d: %s"),
                    *BodyNames[A].ToString(), *BodyNames[B].ToString(), bExpected, bActual, bReverse, *Error)); return false; }
            }
        return true;
    };
    const auto SameBody = [](const FProphecyJoltBodyState& A, const FProphecyJoltBodyState& B)
    {
        return A.PositionCm.Equals(B.PositionCm, 0) && A.Rotation.Equals(B.Rotation, 0)
            && A.CenterOfMassVelocityCmPerSecond.Equals(B.CenterOfMassVelocityCmPerSecond, 0)
            && A.AngularVelocityRadiansPerSecond.Equals(B.AngularVelocityRadiansPerSecond, 0);
    };
    const auto SameHandle = [](const FProphecyJoltBodyHandle& A, const FProphecyJoltBodyHandle& B)
    { return A.WorldLifetime == B.WorldLifetime && A.Slot == B.Slot && A.Generation == B.Generation; };
    const auto CheckPreserved = [&]()
    {
        for (int32 Index = 0; Index < BodyNames.Num(); ++Index)
        {
            FProphecyJoltBodyHandle Current;
            FProphecyJoltBodyState State;
            if (!Character->GetBodyHandle(BodyNames[Index], Current) || !SameHandle(Current, Handles[Index])
                || !World->ReadBody(Current, State).IsSuccess() || !SameBody(State, Before[Index])) return false;
        }
        for (const auto& Source : Captured.Joints)
        {
            const FConstraintInstance* Joint = Mesh->Constraints[Source.SourceConstraintIndex];
            if (!Joint) return false;
            const auto& A = Joint->ProfileInstance;
            const auto& B = Source.CurrentProfile;
            if (A.ConeLimit.Swing1Motion != B.ConeLimit.Swing1Motion || A.ConeLimit.Swing2Motion != B.ConeLimit.Swing2Motion
                || A.TwistLimit.TwistMotion != B.TwistLimit.TwistMotion || A.ConeLimit.Swing1LimitDegrees != B.ConeLimit.Swing1LimitDegrees
                || A.ConeLimit.Swing2LimitDegrees != B.ConeLimit.Swing2LimitDegrees || A.TwistLimit.TwistLimitDegrees != B.TwistLimit.TwistLimitDegrees
                || A.bDisableCollision != B.bDisableCollision) return false;
        }
        FProphecyJoltBodyHandle CurrentSword;
        FProphecyJoltBodyState CurrentSwordState;
        FProphecyJoltWorldDiagnostics D;
        return Agent->GetHeldSword() == Sword && Blade->GetBodyHandle(CurrentSword) && SameHandle(CurrentSword, SwordHandle)
            && World->ReadBody(CurrentSword, CurrentSwordState).IsSuccess() && SameBody(CurrentSwordState, SwordBefore)
            && World->GetDiagnostics(D).IsSuccess() && !D.bFaulted && D.BodyCount == 23 && D.ConstraintCount == 22
            && D.GenericJointCount == 1 && D.SuppressedBodyPairCount == 1 && D.CompletedSteps == 0
            && Mesh->GetCollisionEnabled() == ECollisionEnabled::QueryOnly && !Mesh->IsAnySimulatingPhysics();
    };
    const TSet<int32> BodyOverlay = { PairA };
    const TSet<uint64> PairOverlay = { PairKey(PairA, PairB) };
    if (!TestTrue(TEXT("Initial runtime self-collision matches every captured PHAT pair"), CheckMatrix(true, {}, {}))
        || !TestTrue(TEXT("Individual pair disable is symmetric"), Agent->SetJoltBodyPairSelfCollisionEnabled(BodyNames[PairA], BodyNames[PairB], false, Error)
            && CheckMatrix(true, {}, PairOverlay))
        || !TestTrue(TEXT("Body, pair and master layers compose"), Agent->SetJoltBodiesSelfCollisionEnabled(OneBody, false, Error)
            && Agent->SetJoltSelfCollisionEnabled(false, Error) && CheckMatrix(false, BodyOverlay, PairOverlay))
        || !TestTrue(TEXT("Pair enable removes only the pair layer"), Agent->SetJoltBodyPairSelfCollisionEnabled(BodyNames[PairB], BodyNames[PairA], true, Error)
            && CheckMatrix(false, BodyOverlay, {}))
        || !TestTrue(TEXT("Master enable preserves disabled body membership"), Agent->SetJoltSelfCollisionEnabled(true, Error)
            && CheckMatrix(true, BodyOverlay, {}))
        || !TestTrue(TEXT("Body enable restores the authored matrix"), Agent->SetJoltBodiesSelfCollisionEnabled(OneBody, true, Error)
            && CheckMatrix(true, {}, {}))) return false;
    if (!TestTrue(TEXT("Reset clears all active runtime layers together"),
        Agent->SetJoltBodyPairSelfCollisionEnabled(BodyNames[PairA], BodyNames[PairB], false, Error)
        && Agent->SetJoltBodiesSelfCollisionEnabled(OneBody, false, Error) && Agent->SetJoltSelfCollisionEnabled(false, Error)
        && CheckMatrix(false, BodyOverlay, PairOverlay) && Agent->ResetJoltSelfCollision(Error) && CheckMatrix(true, {}, {}))) return false;
    const auto& AuthoredPair = Captured.DisabledPairs[0];
    if (!TestTrue(TEXT("Explicit enable cannot override an authored exclusion"), Agent->SetJoltBodyPairSelfCollisionEnabled(
            BodyNames[AuthoredPair.Body1Index], BodyNames[AuthoredPair.Body2Index], true, Error) && CheckMatrix(true, {}, {}))) return false;
    const FName Missing(TEXT("__missing_self_collision_test_bone__"));
    const TArray<FName> InvalidBatch = { BodyNames[PairA], Missing };
    bool bIgnored = false;
    if (!TestTrue(TEXT("Invalid body in batch rejects the whole request"), !Agent->SetJoltBodiesSelfCollisionEnabled(InvalidBatch, false, Error)
            && !Error.IsEmpty() && CheckMatrix(true, {}, {}))
        || !TestTrue(TEXT("Invalid pair, identical pair and invalid subtree are refused atomically"),
            !Agent->SetJoltBodyPairSelfCollisionEnabled(BodyNames[PairA], Missing, false, Error)
            && !Agent->SetJoltBodyPairSelfCollisionEnabled(BodyNames[PairA], BodyNames[PairA], false, Error)
            && !Agent->GetJoltBodyPairSelfCollisionEnabled(BodyNames[PairA], Missing, bIgnored, Error)
            && !Agent->SetJoltSelfCollisionBelow(Missing, false, true, Error) && CheckMatrix(true, {}, {}))) return false;
    const FReferenceSkeleton& Skeleton = Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
    const auto DescendantBodies = [&](int32 Ancestor, bool bIncludeSelf)
    {
        TSet<int32> Indices;
        for (int32 Body = 0; Body < BodyNames.Num(); ++Body)
        {
            int32 Bone = Skeleton.FindBoneIndex(BodyNames[Body]);
            if (!bIncludeSelf && Bone == Ancestor) continue;
            while (Bone != INDEX_NONE && Bone != Ancestor) Bone = Skeleton.GetParentIndex(Bone);
            if (Bone == Ancestor) Indices.Add(Body);
        }
        return Indices;
    };
    int32 NonBodyAncestor = INDEX_NONE, BodyAncestor = INDEX_NONE;
    for (int32 Bone = 0; Bone < Skeleton.GetNum(); ++Bone)
    {
        const bool bHasBody = BodyNames.Contains(Skeleton.GetBoneName(Bone));
        const auto Descendants = DescendantBodies(Bone, false);
        if (!Descendants.IsEmpty() && Descendants.Num() < BodyNames.Num())
        {
            if (bHasBody && BodyAncestor == INDEX_NONE) BodyAncestor = Bone;
            if (!bHasBody && NonBodyAncestor == INDEX_NONE) NonBodyAncestor = Bone;
        }
    }
    // The non-body root is also a valid useful subtree when this PHAT has no intermediate helper ancestor.
    if (NonBodyAncestor == INDEX_NONE && !BodyNames.Contains(Skeleton.GetBoneName(0))) NonBodyAncestor = 0;
    if (!TestTrue(TEXT("Actual skeleton supplies both body and non-body subtree ancestors"), BodyAncestor != INDEX_NONE && NonBodyAncestor != INDEX_NONE)) return false;
    for (const int32 Ancestor : { BodyAncestor, NonBodyAncestor })
        for (const bool bIncludeSelf : { false, true })
        {
            const auto Disabled = DescendantBodies(Ancestor, bIncludeSelf);
            if (!TestTrue(TEXT("Subtree disables descendant-versus-all rig pairs with exact include-self semantics"),
                    Agent->SetJoltSelfCollisionBelow(Skeleton.GetBoneName(Ancestor), false, bIncludeSelf, Error) && CheckMatrix(true, Disabled, {}))
                || !TestTrue(TEXT("Subtree re-enable restores only its body layer"),
                    Agent->SetJoltSelfCollisionBelow(Skeleton.GetBoneName(Ancestor), true, bIncludeSelf, Error) && CheckMatrix(true, {}, {}))) return false;
        }
    const TArray<FName> NonBodyBatch = { BodyNames[PairA], Skeleton.GetBoneName(NonBodyAncestor) };
    if (!TestTrue(TEXT("Exact-body API rejects a valid skeleton helper bone without a partial mutation"),
            !Agent->SetJoltBodiesSelfCollisionEnabled(NonBodyBatch, false, Error) && CheckMatrix(true, {}, {}))
        || !TestTrue(TEXT("Repeated no-op settings and reset preserve all native ownership, motion and PHAT limits"),
            Agent->SetJoltSelfCollisionEnabled(true, Error) && Agent->SetJoltSelfCollisionEnabled(true, Error)
            && Agent->ResetJoltSelfCollision(Error) && Agent->ResetJoltSelfCollision(Error) && CheckMatrix(true, {}, {}) && CheckPreserved())) return false;
    Agent->bWorldMagnetizationEnabled = true;
    Agent->WorldMagnetizationLinearStrengthScale = Agent->WorldMagnetizationAngularStrengthScale = 1.0f;
    Agent->SetAllBodyMagnetization(true, 1.0f, 1.0f);
    for (int32 Step = 0; Step < 4; ++Step)
        if (!Agent->SetJoltSelfCollisionEnabled(Step % 2 != 0, Error)
            || !Character->PublishAuthoredTargets(StepSeconds, Error) || !Character->StepAndPublish(StepSeconds, Error))
        { AddError(Error); return false; }
    FProphecyJoltWorldDiagnostics D;
    FProphecyJoltBodyHandle CurrentSword;
    if (!TestTrue(TEXT("Live changes keep stepping with the original held sword and grip"),
        World->GetDiagnostics(D).IsSuccess() && !D.bFaulted && D.CompletedSteps == 4 && D.GenericJointCount == 1
        && Agent->GetHeldSword() == Sword && Blade->GetBodyHandle(CurrentSword) && SameHandle(CurrentSword, SwordHandle)
        && Agent->SetJoltBodyPairSelfCollisionEnabled(BodyNames[PairA], BodyNames[PairB], false, Error))) return false;
    Agent->HideSword();
    Agent->DisableJoltPhysicalAnimation();
    if (!TestTrue(TEXT("Inactive characters refuse every Jolt self-collision control"),
        !Agent->SetJoltSelfCollisionEnabled(false, Error) && !Agent->SetJoltBodiesSelfCollisionEnabled(OneBody, false, Error)
        && !Agent->SetJoltSelfCollisionBelow(Skeleton.GetBoneName(BodyAncestor), false, true, Error)
        && !Agent->SetJoltBodyPairSelfCollisionEnabled(BodyNames[PairA], BodyNames[PairB], false, Error)
        && !Agent->ResetJoltSelfCollision(Error) && !Agent->GetJoltBodyPairSelfCollisionEnabled(BodyNames[PairA], BodyNames[PairB], bIgnored, Error)
        && !Error.IsEmpty() && World->GetDiagnostics(D).IsSuccess() && D.BodyCount == 0 && D.ConstraintCount == 0)) return false;
    if (!TestTrue(TEXT("Rebind starts with the authored collision matrix and no retained runtime layers"),
        Agent->SetSimulationMode(EProphecyAgentSimulationMode::Physical) && Agent->EnableJoltPhysicalAnimation()
        && Agent->GetJoltCharacterComponent()->IsJoltPhysical() && CheckMatrix(true, {}, {}))) return false;
    Agent->GetJoltCharacterComponent()->bAutomaticStep = false;
    Agent->DisableJoltPhysicalAnimation();
    TestTrue(TEXT("Self-collision fixture releases rig, sword and suppression ownership"), World->GetDiagnostics(D).IsSuccess()
        && D.BodyCount == 0 && D.ConstraintCount == 0 && D.GenericJointCount == 0 && D.SuppressedBodyPairCount == 0);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltStandardMeshForcesTest,
    "Prophecy.Jolt.PhysicsCommands.StandardSkeletalNodesAndChaosFallback",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltStandardMeshForcesTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::SwordFixture;
    FWorldFixture Fixture;
    FString Error;
    const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
        .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
    Fixture.World = UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
    if (!Fixture.World || !GEngine) return false;
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(Fixture.World);
    Fixture.World->InitializeActorsForPlay(FURL());
    Fixture.World->GetWorldSettings()->NotifyBeginPlay();
    auto* World = Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltWorldSettings Settings; Settings.GravityCmPerSecondSquared = FVector::ZeroVector;
    if (!World || !World->InitializeSimulation(Settings).IsSuccess()) return false;
    AProphecyAgent* Agent = nullptr;
    FProphecyJoltRigSnapshot Captured;
    if (!PrepareAgent(Fixture,Agent,Error,PoseId,FTransform(FVector(0,0,400)),&Captured)) { AddError(Error); return false; }
    USkeletalMeshComponent* Mesh = Agent->GetPoseReferenceMesh();
    auto* Character = Agent->GetJoltCharacterComponent();
    auto Read = [&](FName Bone)
    {
        FProphecyJoltBodyHandle Handle; FProphecyJoltBodyState State;
        if (!Character->GetBodyHandle(Bone,Handle) || !World->ReadBody(Handle,State).IsSuccess()) AddError(TEXT("Missing fixture bone"));
        return State;
    };
    Mesh->SetAllPhysicsLinearVelocity(FVector::ZeroVector);
    Mesh->SetAllPhysicsAngularVelocityInRadians(FVector::ZeroVector);
    // Call the inherited Blueprint UFunction, not a newly named Jolt wrapper.
    struct FImpulseParams { FVector Impulse; FName BoneName; bool bVelChange; } Params{FVector(17,-9,4),TEXT("foot_l"),true};
    Mesh->ProcessEvent(Mesh->FindFunctionChecked(TEXT("AddImpulse")), &Params);
    for (const auto& Body : Captured.Bodies)
        TestTrue(TEXT("Blueprint AddImpulse changes only selected native bone"), Read(Body.BodyName).CenterOfMassVelocityCmPerSecond.Equals(
            Body.BodyName == Params.BoneName ? Params.Impulse : FVector::ZeroVector, 0.001));
    TestFalse(TEXT("Receiver stays Chaos-query-only"), Mesh->IsAnySimulatingPhysics());
    Mesh->AddAngularImpulseInDegrees(FVector(90,0,0),TEXT("foot_l"),true);
    TestTrue(TEXT("Degree wrapper reaches Jolt radians override"),Read(TEXT("foot_l")).AngularVelocityRadiansPerSecond.Equals(FVector(PI/2,0,0),0.001));
    Mesh->SetAllPhysicsLinearVelocity(FVector::ZeroVector);
    Mesh->AddImpulseToAllBodiesBelow(FVector(7,0,0),TEXT("calf_l"),true,false);
    for (const auto& Body : Captured.Bodies)
    {
        const bool Below = Mesh->BoneIsChildOf(Body.BodyName,TEXT("calf_l"));
        TestTrue(TEXT("Below-bone selection preserves Include Self"),Read(Body.BodyName).CenterOfMassVelocityCmPerSecond.Equals(
            Below ? FVector(7,0,0) : FVector::ZeroVector,0.001));
    }
    Mesh->SetAllPhysicsLinearVelocity(FVector::ZeroVector);
    Mesh->AddImpulse(FVector(3,0,0),NAME_None,true);
    const FName Root = Mesh->GetPhysicsAsset()->SkeletalBodySetups[Mesh->RootBodyData.BodyIndex]->BoneName;
    TestTrue(TEXT("None targets UE's root physics body"), Read(Root).CenterOfMassVelocityCmPerSecond.Equals(FVector(3,0,0),0.001));
    Mesh->SetAllPhysicsLinearVelocity(FVector::ZeroVector);
    const FVector Origin(1000,0,400);
    double TotalMass = 0;
    for (const auto& Body : Captured.Bodies) TotalMass += Character->GetCapturedBodyMassKg(Body.BodyName);
    Mesh->AddRadialImpulse(Origin,10000,100,RIF_Linear,false);
    for (const auto& Body : Captured.Bodies)
    {
        const auto State = Read(Body.BodyName);
        const FVector Delta = State.CenterOfMassPositionCm - Origin;
        const FVector Expected = Delta.GetSafeNormal() * (100.0 / TotalMass) * (1.0 - Delta.Size()/10000.0);
        TestTrue(TEXT("Skeletal radial impulse distributes by total rig mass and linear falloff"), State.CenterOfMassVelocityCmPerSecond.Equals(Expected,0.002));
    }
    Mesh->SetAllPhysicsLinearVelocity(FVector::ZeroVector);
    Mesh->bIgnoreRadialImpulse = true;
    Mesh->AddRadialImpulse(Origin,10000,100,RIF_Constant,true);
    TestTrue(TEXT("Ignore Radial Impulse is honored"),Read(Root).CenterOfMassVelocityCmPerSecond.IsNearlyZero());
    Mesh->bIgnoreRadialImpulse = false;
    Mesh->AddImpulse(FVector(99,0,0),TEXT("not_a_bone"),true);
    TestTrue(TEXT("Missing bone does not hit root"),Read(Root).CenterOfMassVelocityCmPerSecond.IsNearlyZero());
    Agent->SetAllBodyMagnetization(false,0,0);
    if (!Character->PublishAuthoredTargets(0.01f,Error)) { AddError(Error); return false; }
    Mesh->SetAllPhysicsAngularVelocityInRadians(FVector::ZeroVector);
    struct FForceParams { FVector Force; FName BoneName; bool bAccelChange; } ForceParams{FVector(100,200,300),TEXT("foot_l"),false};
    Mesh->ProcessEvent(Mesh->FindFunctionChecked(TEXT("AddForce")), &ForceParams);
    if (!World->Step(0.01f,1).IsSuccess()) return false;
    FVector Momentum = FVector::ZeroVector;
    for (const auto& Body : Captured.Bodies) Momentum += Read(Body.BodyName).CenterOfMassVelocityCmPerSecond * Character->GetCapturedBodyMassKg(Body.BodyName);
    TestTrue(TEXT("Blueprint AddForce reaches articulated Jolt rig and contributes the expected total momentum"),Momentum.Equals(ForceParams.Force*0.01,0.03));
    Agent->DisableJoltPhysicalAnimation();
    if (!TestTrue(TEXT("Disable Jolt restores Chaos simulation"),Mesh->IsSimulatingPhysics(TEXT("foot_l")))) return false;
    auto* ChaosBody = Mesh->GetBodyInstance(TEXT("foot_l"));
    if (!ChaosBody || !ChaosBody->GetPhysicsActor()) return false;
    // UE queues external impulses for its next physics step; GetPhysicsLinearVelocity
    // still returns the last solved velocity at this point.
    const FVector BeforeChaos = ChaosBody->GetPhysicsActor()->GetGameThreadAPI().LinearImpulseVelocity();
    Mesh->AddImpulse(FVector(11,0,0),TEXT("foot_l"),true);
    TestTrue(TEXT("Same standard node queues the exact expected velocity impulse in Chaos"),
        FVector(ChaosBody->GetPhysicsActor()->GetGameThreadAPI().LinearImpulseVelocity()).Equals(BeforeChaos+FVector(11,0,0),0.002));
    Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltRuntimeBoneMaterialsTest,
    "Prophecy.Jolt.Character.RuntimeBoneMaterials",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltRuntimeBoneMaterialsTest::RunTest(const FString& Parameters)
{
    using namespace ProphecyJolt::SwordFixture;
    FWorldFixture Fixture;
    FString Error;
    const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
        .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
    Fixture.World = UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
    if (!Fixture.World || !GEngine) return false;
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(Fixture.World);
    Fixture.World->InitializeActorsForPlay(FURL());
    Fixture.World->GetWorldSettings()->NotifyBeginPlay();
    auto* World=Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltWorldSettings Settings; Settings.GravityCmPerSecondSquared=FVector::ZeroVector;
    if (!World || !World->InitializeSimulation(Settings).IsSuccess()) return false;
    AProphecyAgent* Agent=nullptr;
    FProphecyJoltRigSnapshot Captured;
    if (!PrepareAgent(Fixture,Agent,Error,PoseId,FTransform(FVector(0,0,400)),&Captured)) { AddError(Error); return false; }
    auto* Character=Agent->GetJoltCharacterComponent();
    const TArray<FName> Feet={TEXT("foot_l"),TEXT("foot_r")};
    TArray<FProphecyJoltBodyHandle> Handles;
    TArray<FProphecyJoltBodyMaterial> Originals;
    for (const auto& Body:Captured.Bodies)
    {
        FProphecyJoltBodyHandle H; FProphecyJoltBodyMaterial M;
        if (!Character->GetBodyHandle(Body.BodyName,H) || !World->ReadBodyMaterial(H,M).IsSuccess()) return false;
        Handles.Add(H); Originals.Add(M);
    }
    auto* PM=NewObject<UPhysicalMaterial>(Agent,NAME_None,RF_Transient);
    PM->Friction=0; PM->Restitution=0;
    PM->bOverrideFrictionCombineMode=true; PM->FrictionCombineMode=EFrictionCombineMode::Min;
    PM->bOverrideRestitutionCombineMode=true; PM->RestitutionCombineMode=EFrictionCombineMode::Min;
    auto Check=[&](bool Left, bool Right)
    {
        for (int32 I=0; I<Captured.Bodies.Num(); ++I)
        {
            FProphecyJoltBodyMaterial M;
            if (!World->ReadBodyMaterial(Handles[I],M).IsSuccess()) return false;
            const FName Bone=Captured.Bodies[I].BodyName;
            const bool Override=(Left && Bone==Feet[0]) || (Right && Bone==Feet[1]);
            const auto Expected=Override ? FProphecyJoltBodyMaterial{0,0,1,1} : Originals[I];
            if (M.Friction!=Expected.Friction || M.Restitution!=Expected.Restitution
                || M.FrictionCombineMode!=Expected.FrictionCombineMode || M.RestitutionCombineMode!=Expected.RestitutionCombineMode) return false;
        }
        return true;
    };
    if (!TestTrue(TEXT("Foot-only override leaves every other body unchanged"),
        Agent->SetJoltBodiesPhysicalMaterialOverride(Feet,PM,Error) && Check(true,true))) return false;
    const TArray<FName> Bad={Feet[0],TEXT("missing_body")};
    TestTrue(TEXT("Invalid selection causes no partial reset"),!Agent->ResetJoltBodiesPhysicalMaterialOverride(Bad,Error) && Check(true,true));
    TestFalse(TEXT("Empty selection is not whole-skeleton reset"),Agent->ResetJoltBodiesPhysicalMaterialOverride({},Error));
    TestTrue(TEXT("One-foot reset restores only that foot"),Agent->ResetJoltBodiesPhysicalMaterialOverride({Feet[0]},Error) && Check(false,true));
    TestTrue(TEXT("Duplicate bones are harmless and None resets original values"),
        Agent->SetJoltBodiesPhysicalMaterialOverride({Feet[1],Feet[1]},nullptr,Error) && Check(false,false));
    TestTrue(TEXT("Repeated overrides do not overwrite reset baseline"),
        Agent->SetJoltBodiesPhysicalMaterialOverride(Feet,PM,Error) && Agent->SetJoltBodiesPhysicalMaterialOverride(Feet,PM,Error)
        && Agent->ResetJoltBodiesPhysicalMaterialOverride(Feet,Error) && Check(false,false));
    // Effective values are copies, not live UObject polling.
    Agent->SetJoltBodiesPhysicalMaterialOverride(Feet,PM,Error);
    PM->Friction=0.4f;
    TestTrue(TEXT("Changing shared asset data is not polled"),Check(true,true));
    Agent->ResetJoltBodiesPhysicalMaterialOverride(Feet,Error);
    const auto* UEFoot=Agent->GetPoseReferenceMesh()->GetBodyInstance(Feet[0]);
    TestTrue(TEXT("Override does not replace the UE query receiver material"),UEFoot && UEFoot->GetSimplePhysicalMaterial()!=PM);
    Agent->SetJoltBodiesPhysicalMaterialOverride(Feet,PM,Error);
    Agent->DisableJoltPhysicalAnimation();
    TestFalse(TEXT("Inactive Jolt refuses material override"),Agent->SetJoltBodiesPhysicalMaterialOverride(Feet,PM,Error));
    if (!TestTrue(TEXT("Rebind succeeds"),Agent->EnableJoltPhysicalAnimation())) return false;
    Character=Agent->GetJoltCharacterComponent();
    for (int32 I=0; I<Captured.Bodies.Num(); ++I)
        if (!Character->GetBodyHandle(Captured.Bodies[I].BodyName,Handles[I])) return false;
    TestTrue(TEXT("Rebind drops temporary overrides"),Check(false,false));
    // Standard component node must dispatch to the live Jolt rig as well as UE.
    auto* Mesh=Agent->GetPoseReferenceMesh();
    auto CheckAll=[&](float Friction,float Restitution,uint8 FrictionMode,uint8 RestitutionMode)
    {
        for (const auto& Handle:Handles)
        {
            FProphecyJoltBodyMaterial M;
            if (!World->ReadBodyMaterial(Handle,M).IsSuccess() || M.Friction!=Friction || M.Restitution!=Restitution
                || M.FrictionCombineMode!=FrictionMode || M.RestitutionCombineMode!=RestitutionMode) return false;
        }
        return true;
    };
    PM->Friction=.25f;PM->Restitution=.75f;
    struct FMaterialParams { UPhysicalMaterial* Material; } Params{PM};
    Mesh->ProcessEvent(Mesh->FindFunctionChecked(TEXT("SetPhysMaterialOverride")),&Params);
    TestTrue(TEXT("Standard Blueprint material node updates all live Jolt bodies"),CheckAll(.25f,.75f,1,1));
    TestTrue(TEXT("Standard node retains the UE query material"),Mesh->GetBodyInstance(Feet[0])->GetSimplePhysicalMaterial()==PM);
    PM->Friction=.5f;
    Mesh->SetPhysMaterialOverride(PM);
    TestTrue(TEXT("Calling setter again refreshes the same asset's changed coefficients"),CheckAll(.5f,.75f,1,1));
    Agent->DisableJoltPhysicalAnimation();
    TestTrue(TEXT("Rebind with authored component override succeeds"),Agent->EnableJoltPhysicalAnimation());
    for (int32 I=0; I<Captured.Bodies.Num(); ++I)
        if (!Character->GetBodyHandle(Captured.Bodies[I].BodyName,Handles[I])) return false;
    TestTrue(TEXT("Component override survives rig recreation"),CheckAll(.5f,.75f,1,1));
    Params.Material=nullptr;
    Mesh->ProcessEvent(Mesh->FindFunctionChecked(TEXT("SetPhysMaterialOverride")),&Params);
    TestTrue(TEXT("Clearing component override restores per-body fallback, not admission override"),Check(false,false));
    Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltLocomotionDampingBelowTest,
    "Prophecy.Jolt.Character.LocomotionDampingBelow",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyJoltLocomotionDampingBelowTest::RunTest(const FString&)
{
    using namespace ProphecyJolt::SwordFixture;
    FWorldFixture Fixture;FString Error;
    const auto Values=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
        .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
    Fixture.World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Values);
    if (!Fixture.World || !GEngine) return false;
    GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(Fixture.World);
    Fixture.World->InitializeActorsForPlay(FURL());Fixture.World->GetWorldSettings()->NotifyBeginPlay();
    auto* World=Fixture.World->GetSubsystem<UProphecyJoltWorldSubsystem>();
    FProphecyJoltWorldSettings Settings;Settings.GravityCmPerSecondSquared=FVector::ZeroVector;
    if (!World || !World->InitializeSimulation(Settings).IsSuccess()) return false;
    AProphecyAgent* Agent=nullptr;
    if (!PrepareAgent(Fixture,Agent,Error)) { AddError(Error);return false; }
    using D=UProphecyJointDampingLibrary;
    auto Read=[&](FName Bone) { float Value=-1;D::GetJoltJointAngularDamping(Agent,Bone,Value);return Value; };
    TestEqual(TEXT("Exclude parent selects only wrist PHAT joint"),
        D::SetJoltJointLocomotionDampingBelow(Agent,TEXT("lowerarm_l"),false,10,20,30,40,Error),1);
    TestEqual(TEXT("Excluded elbow unchanged"),Read(TEXT("lowerarm_l")),0.f);
    TestEqual(TEXT("Wrist uses walk sheathed profile"),Read(TEXT("hand_l")),10.f);
    TestEqual(TEXT("Opposite wrist unchanged"),Read(TEXT("hand_r")),0.f);
    TestEqual(TEXT("Include parent selects elbow and wrist"),
        D::SetJoltJointLocomotionDampingBelow(Agent,TEXT("lowerarm_l"),true,10,20,30,40,Error),2);
    TestEqual(TEXT("Included elbow updated"),Read(TEXT("lowerarm_l")),10.f);
    TestEqual(TEXT("Invalid rates change no joints"),
        D::SetJoltJointLocomotionDampingBelow(Agent,TEXT("lowerarm_l"),true,99,-1,99,99,Error),0);
    TestEqual(TEXT("Invalid call preserves previous value"),Read(TEXT("hand_l")),10.f);
    Agent->NotifySwordAttackState(true);
    TestEqual(TEXT("Attack suppresses descendant damping"),Read(TEXT("hand_l")),0.f);
    Agent->NotifySwordAttackState(false);
    TestEqual(TEXT("Attack exit restores descendant profile"),Read(TEXT("hand_l")),10.f);
    TestEqual(TEXT("All zero clears both joint profiles"),
        D::SetJoltJointLocomotionDampingBelow(Agent,TEXT("lowerarm_l"),true,0,0,0,0,Error),2);
    TestEqual(TEXT("Wrist returns to zero"),Read(TEXT("hand_l")),0.f);
    Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic);
    return !HasAnyErrors();
}

#endif
