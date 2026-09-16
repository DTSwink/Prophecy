#include "ProphecyPhysicsBenchmark.h"
#include "ProphecyJoltBenchmarkChaosPause.h"
#include "ProphecyAgent.h"
#include "ProphecyHitEventTestSink.h"
#include "UObject/StrongObjectPtr.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyPhysicsBenchmarkRigAudit.h"
#include "Camera/CameraComponent.h"
#include "Components/BoxComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/SpringArmComponent.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Misc/ConfigCacheIni.h"
#include "Modules/ModuleManager.h"
#include "UObject/Class.h"
#include "UObject/UObjectGlobals.h"
#include "UObject/UnrealType.h"

struct FProphecyNNOrtThreadingSnapshot
{
    bool bUseGlobalPool = false;
    int32 IntraOpThreads = 0, InterOpThreads = 0;
    uint8 ExecutionMode = 0;
    TSharedPtr<FJsonObject> Json;

    bool HasSameTypedSettings(const FProphecyNNOrtThreadingSnapshot& Other) const
    {
        return bUseGlobalPool == Other.bUseGlobalPool && IntraOpThreads == Other.IntraOpThreads
            && InterOpThreads == Other.InterOpThreads && ExecutionMode == Other.ExecutionMode;
    }
};

struct FProphecyNNJoltBenchmarkState
{
    TWeakObjectPtr<AProphecyNNLocomotionManager> Manager;
    TArray<TWeakObjectPtr<AProphecyAgent>> Agents;
    TArray<int32> PoseIds;
    TArray<uint64> PoseRevisions;
    TArray<FVector> InitialRoots;
    FProphecyNNRuntimeBenchmarkStats InitialStats, LastStats;
    int32 ValidatedFrames = 0, FramesWithoutNNStep = 0;
    TStrongObjectPtr<UProphecyHitEventTestSink> HitSink;
    int64 InitialHits = 0;
    bool bHitEvents = false;
    int32 PhysicalFeedbackMode = 0;
    TSharedPtr<FJsonObject> OrtThreadingBeforeModels, OrtThreadingAfterModels;
};

namespace ProphecySterileBench::NNJolt
{
constexpr double NNHz = 30.0, WorldHz = 60.0;

bool CaptureOrtCpuThreadingSettings(FProphecyNNOrtThreadingSnapshot& Snapshot, FString& Error)
{
    Error.Reset();
    if (!IsInGameThread() || !FModuleManager::Get().IsModuleLoaded(TEXT("NNERuntimeORT")) || !GConfig)
    { Error = TEXT("Capture requires the initialized ORT module and config cache on the game thread."); return false; }
    UClass* SettingsClass = FindObject<UClass>(nullptr, TEXT("/Script/NNERuntimeORT.NNERuntimeORTSettings"));
    const UObject* Settings = SettingsClass ? SettingsClass->GetDefaultObject(false) : nullptr;
#if WITH_EDITOR
    const FName OptionsName(TEXT("EditorThreadingOptions"));
#else
    const FName OptionsName(TEXT("GameThreadingOptions"));
#endif
    const FStructProperty* Options = SettingsClass ? FindFProperty<FStructProperty>(SettingsClass, OptionsName) : nullptr;
    if (!Settings || !Options || !Options->Struct)
    { Error = TEXT("The loaded native ORT threading settings are unavailable."); return false; }
    const void* Values = Options->ContainerPtrToValuePtr<void>(Settings);
    const FBoolProperty* Global = FindFProperty<FBoolProperty>(Options->Struct, TEXT("bUseGlobalThreadPool"));
    const FIntProperty* Intra = FindFProperty<FIntProperty>(Options->Struct, TEXT("IntraOpNumThreads"));
    const FIntProperty* Inter = FindFProperty<FIntProperty>(Options->Struct, TEXT("InterOpNumThreads"));
    const FByteProperty* Execution = FindFProperty<FByteProperty>(Options->Struct, TEXT("ExecutionMode"));
    if (!Global || !Intra || !Inter || !Execution || !Execution->Enum)
    { Error = TEXT("The native ORT threading settings layout differs from the reviewed UE 5.7 source."); return false; }
    const uint8 ExecutionValue = Execution->GetPropertyValue_InContainer(Values);
    if (ExecutionValue > 1)
    { Error = TEXT("The native ORT execution mode is outside its reviewed enum."); return false; }
    Snapshot.bUseGlobalPool = Global->GetPropertyValue_InContainer(Values);
    Snapshot.IntraOpThreads = Intra->GetPropertyValue_InContainer(Values);
    Snapshot.InterOpThreads = Inter->GetPropertyValue_InContainer(Values);
    Snapshot.ExecutionMode = ExecutionValue;
    if (Snapshot.IntraOpThreads < 0 || Snapshot.InterOpThreads < 0)
    { Error = TEXT("Native ORT thread counts cannot be negative."); return false; }
    const FString ExecutionName = Execution->Enum->GetNameStringByValue(ExecutionValue);
    if (ExecutionName != (ExecutionValue == 0 ? TEXT("SEQUENTIAL") : TEXT("PARALLEL")))
    { Error = TEXT("Native ORT execution enum labels differ from reviewed UE 5.7."); return false; }
    Snapshot.Json = MakeShared<FJsonObject>();
    FJsonObject& Out = *Snapshot.Json;
    Out.SetStringField(TEXT("settings_class"), SettingsClass->GetPathName());
    Out.SetStringField(TEXT("selected_options"), OptionsName.ToString());
    Out.SetBoolField(TEXT("use_global_thread_pool"), Snapshot.bUseGlobalPool);
    Out.SetNumberField(TEXT("intra_op_num_threads"), Snapshot.IntraOpThreads);
    Out.SetNumberField(TEXT("inter_op_num_threads"), Snapshot.InterOpThreads);
    Out.SetNumberField(TEXT("execution_mode"), ExecutionValue);
    Out.SetStringField(TEXT("execution_mode_name"), Execution->Enum->GetNameStringByValue(ExecutionValue));
    FString Raw;
    const bool bConfigValuePresent = GConfig && GConfig->GetString(*SettingsClass->GetPathName(),
        *OptionsName.ToString(), Raw, GEngineIni);
    Out.SetBoolField(TEXT("config_value_present"), bConfigValuePresent);
    if (bConfigValuePresent) Out.SetStringField(TEXT("config_value"), Raw);
    Out.SetBoolField(TEXT("commandline_ini_overrides_enabled"), ALLOW_INI_OVERRIDE_FROM_COMMANDLINE != 0);
    // This CDO snapshot establishes selected settings. The environment copied counts during module
    // startup; it does not expose public getters through NNE. Do not claim this observes worker usage.
    Out.SetBoolField(TEXT("session_worker_execution_directly_observed"), false);
    return true;
}


TSharedPtr<FJsonObject> StatsJson(const FProphecyNNRuntimeBenchmarkStats& Stats)
{
    auto Row = MakeShared<FJsonObject>();
    Row->SetNumberField(TEXT("completed_nn_steps"), double(Stats.CompletedNNSteps));
    Row->SetNumberField(TEXT("completed_physical_samples"), double(Stats.CompletedPhysicalSamples));
    Row->SetNumberField(TEXT("failed_physical_samples"), double(Stats.FailedPhysicalSamples));
    Row->SetNumberField(TEXT("build_seconds"), Stats.BuildSeconds);
    Row->SetNumberField(TEXT("inference_seconds"), Stats.InferenceSeconds);
    Row->SetNumberField(TEXT("output_seconds"), Stats.OutputSeconds);
    Row->SetNumberField(TEXT("store_seconds"), Stats.StoreSeconds);
    Row->SetStringField(TEXT("run_runtime"), Stats.RunRuntime);
    Row->SetStringField(TEXT("walk_runtime"), Stats.WalkRuntime);
    Row->SetStringField(TEXT("upper_runtime"), Stats.UpperRuntime);
    Row->SetNumberField(TEXT("run_batch_size"), Stats.RunBatchSize);
    Row->SetNumberField(TEXT("walk_batch_size"), Stats.WalkBatchSize);
    Row->SetNumberField(TEXT("upper_batch_size"), Stats.UpperBatchSize);
    Row->SetNumberField(TEXT("foot_roll_steps"), Stats.FootRollSteps);
    Row->SetNumberField(TEXT("physical_feedback_mode"), Stats.PhysicalFeedbackExecutionMode);
    Row->SetNumberField(TEXT("prepared_physical_samples"), double(Stats.PreparedPhysicalSamples));
    Row->SetNumberField(TEXT("prepared_physical_batches"), double(Stats.PreparedPhysicalBatches));
    return Row;
}

bool ValidateManager(FProphecyNNJoltBenchmarkState& State, int32 Count,
    FProphecyNNRuntimeBenchmarkStats& Stats, FString& Error)
{
    AProphecyNNLocomotionManager* Manager = State.Manager.Get();
    if (!Manager || !Manager->ReadRuntimeBenchmarkStats(Stats) || !Stats.bInitialized
        || !Manager->IsActorTickEnabled() || Manager->bSimBridge || Stats.bSimBridgeActive
        || Manager->InitialPhysicalAgentCount != 0
        || Stats.PhysicalFeedbackExecutionMode != State.PhysicalFeedbackMode
        || (State.PhysicalFeedbackMode == 0 && (Stats.PreparedPhysicalSamples || Stats.PreparedPhysicalBatches))
        || Manager->CrowdSize != Count || Stats.RegisteredAgents != Count
        || !FMath::IsNearlyEqual(Manager->NNUpdateHz, float(NNHz)) || Stats.FootRollSteps != 4
        || Stats.bUsingGPU || Stats.RunRuntime != TEXT("NNERuntimeORTCpu")
        || Stats.WalkRuntime != TEXT("NNERuntimeORTCpu") || Stats.UpperRuntime != TEXT("NNERuntimeORTCpu")
        || Stats.RunBatchSize != 100 || Stats.WalkBatchSize != 100 || Stats.UpperBatchSize != 100)
    { Error = TEXT("NNJoltCrowd lost its real CPU manager, full batches, 30 Hz cadence or four-step foot processing."); return false; }
    return true;
}

bool ValidateLane(FProphecyNNJoltBenchmarkState& State, int32 Lane, bool bRequireJolt, FString& Error)
{
    AProphecyNNLocomotionManager* Manager = State.Manager.Get();
    AProphecyAgent* Agent = State.Agents[Lane].Get();
    if (!Manager || !Agent || Manager->ResolveAgent(Manager->GetAgentHandle(Lane)) != Agent
        || !Agent->bNNInferenceEnabled || !Agent->bManualNNPoseApplication
        || !Agent->bAutoPublishManualFollowerSubstepTargets || !Agent->bUseBlueprintLocomotionInput
        || Agent->LocomotionInput.WorldMoveInput != FVector(0, 1, 0) || Agent->LocomotionInput.bRun
        || Agent->bEnableAttackFists || !Agent->GetAgentSpringArm() || !Agent->GetAgentCamera()
        || Agent->GetAgentSpringArm()->IsComponentTickEnabled() || Agent->GetAgentCamera()->IsComponentTickEnabled())
    { Error = FString::Printf(TEXT("NN lane %d lost its registration, movement intent or explicit movement-only profile."), Lane); return false; }
    const UCapsuleComponent* Capsule = Agent->GetAgentCapsule();
    if (!Capsule || Capsule->GetCollisionEnabled() != ECollisionEnabled::QueryAndPhysics
        || Capsule->GetCollisionResponseToChannel(ECC_WorldStatic) != ECR_Block)
    { Error = TEXT("NNJoltCrowd requires the real managed capsule query path to remain enabled."); return false; }
    if (bRequireJolt && (!Agent->IsJoltPhysicalAnimationEnabled()
        || Agent->GetSimulationMode() != EProphecyAgentSimulationMode::Physical))
    { Error = TEXT("Actual NN feedback lane lost Jolt Physical ownership."); return false; }
    int32 PoseId = INDEX_NONE;
    float Interval = 0;
    bool bInterpolate = false;
    if (!Agent->GetNNPoseDataSource(PoseId, Interval, bInterpolate) || PoseId != State.PoseIds[Lane]
        || !FMath::IsNearlyEqual(Interval, float(1.0 / NNHz)) || !bInterpolate)
    { Error = TEXT("Actual NN lane lost its manager-authored pose identity or interpolation."); return false; }
    FProphecyNNPoseSnapshot Pose;
    if (!FProphecyNNPoseStore::GetAgentLocalPose(PoseId, Pose) || !Pose.bHasComponentWorldTransform
        || Pose.BoneNames.Num() != 25 || Pose.ComponentTransforms.Num() != 25
        || Pose.Revision < State.PoseRevisions[Lane])
    { Error = TEXT("Manager's current 25-bone policy pose is absent or its revision moved backwards."); return false; }
    for (const FTransform& Bone : Pose.ComponentTransforms)
        if (Bone.ContainsNaN() || !Bone.GetRotation().IsNormalized())
        { Error = TEXT("Actual NN output contains a nonfinite or invalid policy bone."); return false; }
    State.PoseRevisions[Lane] = Pose.Revision;
    return true;
}
}

bool UProphecyPhysicsBenchmarkSubsystem::PrepareNNJoltCase(FString& Error)
{
    Error.Reset();
    if (!GetWorld() || Count < 2 || Count > 100 || Meshes.Num() != Count || !Cases[CaseIndex].Floor
        || !FParse::Param(FCommandLine::Get(), TEXT("PhysicsBenchMovementOnly")))
    { Error = TEXT("NNJoltCrowd requires a prepared 2..100-agent floor case and explicit PhysicsBenchMovementOnly."); return false; }
    for (TActorIterator<AProphecyNNLocomotionManager> It(GetWorld()); It; ++It)
    { Error = TEXT("Actual NN fixture requires sole ownership of its transient manager and pose IDs."); return false; }
    FString FeedbackModeText = TEXT("Original");
    FParse::Value(FCommandLine::Get(), TEXT("PhysicsBenchFeedbackMode="), FeedbackModeText);
    const int32 FeedbackMode = FeedbackModeText.Equals(TEXT("Original"), ESearchCase::IgnoreCase) ? 0
        : FeedbackModeText.Equals(TEXT("PreparedSerial"), ESearchCase::IgnoreCase) ? 1
        : FeedbackModeText.Equals(TEXT("PreparedParallel"), ESearchCase::IgnoreCase) ? 2 : INDEX_NONE;
    if (FeedbackMode == INDEX_NONE)
    { Error = TEXT("PhysicsBenchFeedbackMode must be Original, PreparedSerial or PreparedParallel."); return false; }
    TSet<AProphecyAgent*> Expected;
    for (USkeletalMeshComponent* Mesh : Meshes)
    {
        auto* Agent = IsValid(Mesh) ? Cast<AProphecyAgent>(Mesh->GetOwner()) : nullptr;
        if (!Agent || Agent->HasValidAgentHandle() || Agent->GetOwner())
        { Error = TEXT("Actual NN adoption requires unregistered, independent native manual shells."); return false; }
        Expected.Add(Agent);
        // All shells have finished BeginPlay with automatic manager startup disabled. Turning
        // collection eligibility on here does not call EnsureStandaloneNNManager or start a process.
        Agent->SetGeneratePhysicalHitEvents(FParse::Param(FCommandLine::Get(), TEXT("PhysicsBenchHitEvents")));
        Agent->bAutoEnsureStandaloneNNManager = true;
        Agent->SetLocomotionInput(FVector(0, 1, 0), false, FVector(0, 1, 0));
        // The old isolated fixture disabled this component. Restore the current native Physical
        // root policy, preserving its authored channel; actual mover sweeps remain timed.
        Agent->GetAgentCapsule()->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
        Agent->GetAgentCapsule()->SetCollisionResponseToAllChannels(ECR_Ignore);
        Agent->GetAgentCapsule()->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
    }
    int32 Floors = 0;
    for (AActor* Actor : Actors)
    {
        if (!IsValid(Actor)) continue;
        TInlineComponentArray<UBoxComponent*> Boxes(Actor);
        for (UBoxComponent* Box : Boxes)
        {
            // The same box remains the single Jolt floor mirror. Its UE receiver must also
            // answer the real capsule's sweeps; PhysicsOnly would bypass the query path.
            Box->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
            ++Floors;
        }
    }
    if (Floors != 1) { Error = TEXT("Actual NN fixture requires exactly one explicit query/physics floor."); return false; }
    // Read-only provenance outside timed samples. Module startup already selected the environment
    // pool options; capture the loaded CDO without recreating it or touching session settings.
    FProphecyNNOrtThreadingSnapshot OrtBeforeModels, OrtAfterModels;
    if (!ProphecySterileBench::NNJolt::CaptureOrtCpuThreadingSettings(OrtBeforeModels, Error)) return false;
    auto* Manager = GetWorld()->SpawnActorDeferred<AProphecyNNLocomotionManager>(
        AProphecyNNLocomotionManager::StaticClass(), FTransform::Identity, nullptr, nullptr,
        ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if (!Manager) { Error = TEXT("Could not create the transient actual NN manager."); return false; }
    Actors.Add(Manager);
    Manager->SetFlags(RF_Transient);
    Manager->ConfigureSimpleLocomotionTest();
    Manager->CrowdSize = Count;
    Manager->NNUpdateHz = 30.0f;
    Manager->FootRollIntegrationSteps = 4;
    Manager->PreferredRuntime = TEXT("NNERuntimeORTCpu");
    Manager->bSimBridge = false;
    Manager->InitialPhysicalAgentCount = 0; // Adoption preserves the current manual rig; no MACD/drive conversion.
    Manager->BenchmarkWarmupSeconds = 0.0f;
    Manager->BenchmarkSeconds = 0.0f; // Fixture JSON owns reporting; existing native counters still collect.
    if (!Manager->SetPhysicalFeedbackExecutionMode(FeedbackMode))
    { Error = TEXT("Could not set native physical feedback execution before manager BeginPlay."); return false; }
    Manager->FinishSpawning(FTransform::Identity);
    if (!ProphecySterileBench::NNJolt::CaptureOrtCpuThreadingSettings(OrtAfterModels, Error)) return false;
    if (!OrtBeforeModels.HasSameTypedSettings(OrtAfterModels))
    { Error = TEXT("ORT threading settings changed while creating the actual NN models."); return false; }
    auto Pending = MakeShared<FProphecyNNJoltBenchmarkState>();
    Pending->bHitEvents = FParse::Param(FCommandLine::Get(), TEXT("PhysicsBenchHitEvents"));
    Pending->HitSink.Reset(NewObject<UProphecyHitEventTestSink>());
    for (USkeletalMeshComponent* Mesh : Meshes)
        CastChecked<AProphecyAgent>(Mesh->GetOwner())->OnPhysicalHit.AddDynamic(
            Pending->HitSink.Get(), &UProphecyHitEventTestSink::PhysicalHit);
    Pending->OrtThreadingBeforeModels = MoveTemp(OrtBeforeModels.Json);
    Pending->OrtThreadingAfterModels = MoveTemp(OrtAfterModels.Json);
    Pending->Manager = Manager;
    Pending->PhysicalFeedbackMode = FeedbackMode;
    FProphecyNNRuntimeBenchmarkStats Stats;
    if (!ProphecySterileBench::NNJolt::ValidateManager(*Pending, Count, Stats, Error)) return false;
    TArray<TObjectPtr<USkeletalMeshComponent>> OrderedMeshes;
    TSet<int32> SourceIds;
    for (int32 Lane = 0; Lane < Count; ++Lane)
    {
        AProphecyAgent* Agent = Manager->ResolveAgent(Manager->GetAgentHandle(Lane));
        if (!Agent || !Expected.Remove(Agent)) { Error = TEXT("Manager adopted a duplicate/unexpected agent or spawned a replacement shell."); return false; }
        USkeletalMeshComponent* Mesh = Agent->GetPoseReferenceMesh();
        if (!Mesh || !Meshes.Contains(Mesh) || !Mesh->IsAnySimulatingPhysics()
            || Agent->GetSimulationMode() != EProphecyAgentSimulationMode::Physical)
        { Error = FString::Printf(TEXT("NN lane %d did not retain its prepared Physical mesh and Chaos warmup ownership."), Lane); return false; }
        int32 PoseId = INDEX_NONE;
        float Interval = 0;
        bool bInterpolate = false;
        if (!Agent->GetNNPoseDataSource(PoseId, Interval, bInterpolate) || PoseId == INDEX_NONE)
        { Error = FString::Printf(TEXT("NN lane %d has no registered manager pose source."), Lane); return false; }
        if (SourceIds.Contains(PoseId))
        { Error = FString::Printf(TEXT("NN lane %d reused manager pose ID %d."), Lane, PoseId); return false; }
        SourceIds.Add(PoseId);
        // Entering native manual Physical intentionally removes the NN AnimInstance.
        // The servo reads this registered source directly; the first normal Agent tick
        // supplies only the reference/helper/finger proxy while Chaos owns body bones.
        // Do not install or rebind an NN evaluator on top of that physical warmup.
        UE_LOG(LogTemp, Display, TEXT("NNJOLT_ADOPT lane=%d agent=%s mesh=%s pose_id=%d interval=%.9f interpolate=%d anim=%s"),
            Lane, *Agent->GetName(), *Mesh->GetName(), PoseId, Interval, bInterpolate ? 1 : 0,
            *GetNameSafe(Mesh->GetAnimInstance()));
        Pending->Agents.Add(Agent);
        Pending->PoseIds.Add(PoseId);
        Pending->PoseRevisions.Add(0);
        Pending->InitialRoots.Add(Agent->GetRootLowPoint());
        OrderedMeshes.Add(Mesh);
        if (!ProphecySterileBench::NNJolt::ValidateLane(*Pending, Lane, false, Error)) return false;
    }
    if (!Expected.IsEmpty()) { Error = TEXT("Manager failed to adopt every prepared native shell."); return false; }
    // The synthetic bootstrap data cannot accidentally keep animating a stale receiver.
    for (int32 Index = 0; Index < Count; ++Index)
        if (!SourceIds.Contains(991000 + Index)) FProphecyNNPoseStore::ClearAgentPose(991000 + Index);
    Meshes = MoveTemp(OrderedMeshes);
    NNJoltState = MoveTemp(Pending);
    return true;
}

bool UProphecyPhysicsBenchmarkSubsystem::InitializeNNJoltCase(FString& Error)
{
    namespace NN = ProphecySterileBench::NNJolt;
    if (!NNJoltState || !Before || !NN::ValidateManager(*NNJoltState, Count, NNJoltState->InitialStats, Error)) return false;
    if (!NNJoltState->InitialStats.CompletedNNSteps || NNJoltState->InitialStats.FailedPhysicalSamples)
    { Error = TEXT("Actual NN warmup did not complete real inference and successful physical feedback."); return false; }
    NNJoltState->LastStats = NNJoltState->InitialStats;
    NNJoltState->InitialHits = NNJoltState->HitSink->PhysicalHits;
    for (int32 Lane = 0; Lane < Count; ++Lane)
    {
        if (!NN::ValidateLane(*NNJoltState, Lane, false, Error)) return false;
        NNJoltState->InitialRoots[Lane] = NNJoltState->Agents[Lane]->GetRootLowPoint();
    }
    if (!InitializeMultiJoltCase(Error)) return false;
    for (const auto& Agent : NNJoltState->Agents)
        if (Agent->bGeneratePhysicalHitEvents != NNJoltState->bHitEvents)
        { Error = TEXT("Benchmark Agent hit opt-in was changed during setup."); return false; }
    if (!ProphecyJolt::BenchmarkChaosPause::Begin(*this, *GetWorld(), Actors, Error)) return false;
    Before->SetObjectField(TEXT("paused_chaos_diagnostic"), ProphecyJolt::BenchmarkChaosPause::ToJson());
    Before->SetObjectField(TEXT("actual_nn_initial"), NN::StatsJson(NNJoltState->InitialStats));
    if (!NNJoltState->OrtThreadingBeforeModels.IsValid() || !NNJoltState->OrtThreadingAfterModels.IsValid())
    { Error = TEXT("Actual NN scope lost its ORT threading initialization evidence."); return false; }
    auto Scope = MakeShared<FJsonObject>();
    Scope->SetObjectField(TEXT("ort_cpu_threading_before_models"), NNJoltState->OrtThreadingBeforeModels);
    Scope->SetObjectField(TEXT("ort_cpu_threading_after_models"), NNJoltState->OrtThreadingAfterModels);
    Scope->SetNumberField(TEXT("nn_hz"), NN::NNHz);
    Scope->SetNumberField(TEXT("world_and_presentation_hz"), NN::WorldHz);
    Scope->SetNumberField(TEXT("policy_bones"), 25);
    Scope->SetNumberField(TEXT("presented_skeleton_bones"), 88);
    Scope->SetNumberField(TEXT("dynamic_bodies_per_character"), 22);
    Scope->SetBoolField(TEXT("synthetic_publication_after_adoption"), false);
    Scope->SetBoolField(TEXT("movement_only"), true);
    const auto* Manager = NNJoltState->Manager.Get();
    Scope->SetStringField(TEXT("run_model"), Manager->OnnxModelPath);
    Scope->SetStringField(TEXT("walk_model"), Manager->WalkOnnxModelPath);
    Scope->SetStringField(TEXT("upper_model"), Manager->UpperOnnxModelPath);
    Scope->SetStringField(TEXT("run_contract"), Manager->RuntimeContractPath);
    Scope->SetStringField(TEXT("walk_contract"), Manager->WalkRuntimeContractPath);
    Scope->SetStringField(TEXT("upper_contract"), Manager->UpperRuntimeContractPath);
    TArray<TSharedPtr<FJsonValue>> CapsulePolicies;
    for (const auto& Agent : NNJoltState->Agents)
    {
        const UCapsuleComponent* Capsule = Agent->GetAgentCapsule();
        auto Policy = MakeShared<FJsonObject>();
        Policy->SetNumberField(TEXT("object_channel"), int32(Capsule->GetCollisionObjectType()));
        Policy->SetNumberField(TEXT("collision_enabled"), int32(Capsule->GetCollisionEnabled()));
        TArray<TSharedPtr<FJsonValue>> Responses;
        // ECC_MAX also counts a deprecated transient flag that has no stored response.
        const int32 StoredChannelCount = int32(UE_ARRAY_COUNT(Capsule->GetCollisionResponseToChannels().EnumArray));
        for (int32 Channel = 0; Channel < StoredChannelCount; ++Channel)
            Responses.Add(MakeShared<FJsonValueNumber>(int32(Capsule->GetCollisionResponseToChannel(ECollisionChannel(Channel)))));
        Policy->SetArrayField(TEXT("responses_by_channel"), Responses);
        Policy->SetNumberField(TEXT("radius_cm"), Capsule->GetScaledCapsuleRadius());
        Policy->SetNumberField(TEXT("half_height_cm"), Capsule->GetScaledCapsuleHalfHeight());
        CapsulePolicies.Add(MakeShared<FJsonValueObject>(Policy));
    }
    Scope->SetArrayField(TEXT("root_capsule_policies"), CapsulePolicies);
    Scope->SetStringField(TEXT("intent"), TEXT("Public walking input +Y with facing +Y. Existing mover/acceleration/root queries and live physical feedback remain active."));
    Scope->SetStringField(TEXT("contacts"), TEXT("Separated moving crowd. Current Physical root capsules QueryAndPhysics block WorldStatic; retained limb fixture policy blocks WorldStatic only; original PHAT joint angles. Explicit floor participates in both UE queries and Jolt contacts. Inter-character/contact-stress and full production-world geometry are separate workloads."));
    Before->SetObjectField(TEXT("actual_nn_scope"), Scope);
    // Replace inherited synthetic-only description while retaining all native handoff provenance.
    Before->GetObjectField(TEXT("multi_jolt_handoff"))->SetStringField(TEXT("scope"),
        TEXT("Actual CPU locomotion manager publishes at 30 Hz before Agent ticks; one 60 Hz Jolt world step and complete 88-bone presentation. Synthetic bootstrap publication ended before manager warmup."));
    return true;
}

bool UProphecyPhysicsBenchmarkSubsystem::ValidateNNJoltFrame(FString& Error)
{
    namespace NN = ProphecySterileBench::NNJolt;
    if (!ValidateMultiJoltFrame(Error)) return false; // Ends profiling and performs all existing body/pose/query ownership checks.
    FProphecyNNRuntimeBenchmarkStats Stats;
    if (!NNJoltState || !NN::ValidateManager(*NNJoltState, Count, Stats, Error)) return false;
    const auto& Previous = NNJoltState->LastStats;
    if (Stats.CompletedNNSteps < Previous.CompletedNNSteps || Stats.CompletedPhysicalSamples < Previous.CompletedPhysicalSamples)
    { Error = TEXT("Actual NN counters moved backwards."); return false; }
    if (Stats.PreparedPhysicalSamples < Previous.PreparedPhysicalSamples
        || Stats.PreparedPhysicalBatches < Previous.PreparedPhysicalBatches)
    { Error = TEXT("Prepared feedback counters moved backwards."); return false; }
    const uint64 Steps = Stats.CompletedNNSteps - Previous.CompletedNNSteps;
    const uint64 PhysicalSamples = Stats.CompletedPhysicalSamples - Previous.CompletedPhysicalSamples;
    const uint64 PreparedSamples = Stats.PreparedPhysicalSamples - Previous.PreparedPhysicalSamples;
    const uint64 PreparedBatches = Stats.PreparedPhysicalBatches - Previous.PreparedPhysicalBatches;
    const bool bPreparedFeedback = NNJoltState->PhysicalFeedbackMode != 0;
    if (PreparedSamples != (bPreparedFeedback ? PhysicalSamples : 0)
        || PreparedBatches != (bPreparedFeedback ? Steps : 0))
    { Error = TEXT("Prepared feedback failed its exact per-NN-step joined batch/item accounting."); return false; }
    NNJoltState->FramesWithoutNNStep = Steps ? 0 : NNJoltState->FramesWithoutNNStep + 1;
    if (Steps > 1 || NNJoltState->FramesWithoutNNStep > 1 || PhysicalSamples != Steps * uint64(Count)
        || Stats.FailedPhysicalSamples != NNJoltState->InitialStats.FailedPhysicalSamples)
    { Error = TEXT("Actual 30 Hz NN work or per-lane physical resampling cadence failed inside the 60 Hz measured world."); return false; }
    for (int32 Lane = 0; Lane < Count; ++Lane)
    {
        const uint64 PreviousRevision = NNJoltState->PoseRevisions[Lane];
        if (!NN::ValidateLane(*NNJoltState, Lane, true, Error)) return false;
        if (Steps && NNJoltState->PoseRevisions[Lane] <= PreviousRevision)
        { Error = TEXT("A completed actual NN step failed to publish a fresh lane pose."); return false; }
    }
    LiveJoltFrames.Last()->AsObject()->SetObjectField(TEXT("actual_nn"), NN::StatsJson(Stats));
    // Deferred pause admission is after all body/query/NN gates, outside the measured timer.
    if (!ProphecyJolt::BenchmarkChaosPause::ValidateFrame(*this, *LiveJoltFrames.Last()->AsObject(), Error)) return false;
    NNJoltState->LastStats = MoveTemp(Stats);
    ++NNJoltState->ValidatedFrames;
    return true;
}

bool UProphecyPhysicsBenchmarkSubsystem::SaveNNJoltCase(TSharedPtr<FJsonObject> CaseResult, FString& Error)
{
    namespace NN = ProphecySterileBench::NNJolt;
    if (!NNJoltState || NNJoltState->ValidatedFrames != Samples)
    { Error = TEXT("Actual NN case did not validate every requested sample."); return false; }
    const auto& Start = NNJoltState->InitialStats;
    const auto& End = NNJoltState->LastStats;
    const uint64 NNSteps = End.CompletedNNSteps - Start.CompletedNNSteps;
    if (FMath::Abs(double(NNSteps) - double(Samples) * NN::NNHz / NN::WorldHz) > 1.0
        || End.InferenceSeconds <= Start.InferenceSeconds)
    { Error = TEXT("Actual NN case has incomplete 30 Hz model work."); return false; }
    auto Summary = MakeShared<FJsonObject>();
    Summary->SetBoolField(TEXT("success"), false);
    const int64 DeliveredHits = NNJoltState->HitSink->PhysicalHits - NNJoltState->InitialHits;
    Summary->SetBoolField(TEXT("hit_events_enabled"), NNJoltState->bHitEvents);
    Summary->SetNumberField(TEXT("physical_hit_delegates_delivered"), double(DeliveredHits));
    Summary->SetNumberField(TEXT("physical_hits_per_frame"), double(DeliveredHits) / Samples);
    if ((NNJoltState->bHitEvents ? DeliveredHits <= 0 : DeliveredHits != 0) || !NNJoltState->HitSink->bOnlyGameThread)
    {
        Error = FString::Printf(TEXT("Hit-event benchmark delivery mismatch: enabled=%d, measured Agent hits=%lld, total Agent hits=%lld, native dispatched=%llu, GT=%d."),
            NNJoltState->bHitEvents, DeliveredHits, NNJoltState->HitSink->PhysicalHits,
            GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>()->GetDeliveredHitEventCount(), NNJoltState->HitSink->bOnlyGameThread);
        return false;
    }
    Summary->SetNumberField(TEXT("completed_nn_steps"), double(NNSteps));
    Summary->SetNumberField(TEXT("physical_feedback_mode"), End.PhysicalFeedbackExecutionMode);
    Summary->SetNumberField(TEXT("prepared_physical_samples"), double(End.PreparedPhysicalSamples - Start.PreparedPhysicalSamples));
    Summary->SetNumberField(TEXT("prepared_physical_batches"), double(End.PreparedPhysicalBatches - Start.PreparedPhysicalBatches));
    Summary->SetStringField(TEXT("physical_feedback_scope"), TEXT("Mode0 retains immediate serial sampling/math; modes1/2 use identical GT samples and resolved inputs with prepared serial/parallel math. Preparation and joined math wall scopes remain inside manager/world timing. Counts describe completed items and joins, not worker residency. No worker GT-profiler calls, reduced cadence, changed tolerance or NN precision."));
    Summary->SetNumberField(TEXT("completed_physical_samples"), double(End.CompletedPhysicalSamples - Start.CompletedPhysicalSamples));
    const double ToPerWorldFrameMs = 1000.0 / Samples;
    Summary->SetNumberField(TEXT("mean_nn_build_ms_per_world_frame"), (End.BuildSeconds - Start.BuildSeconds) * ToPerWorldFrameMs);
    Summary->SetNumberField(TEXT("mean_nn_inference_ms_per_world_frame"), (End.InferenceSeconds - Start.InferenceSeconds) * ToPerWorldFrameMs);
    Summary->SetNumberField(TEXT("mean_nn_output_ms_per_world_frame"), (End.OutputSeconds - Start.OutputSeconds) * ToPerWorldFrameMs);
    Summary->SetNumberField(TEXT("mean_nn_store_ms_per_world_frame"), (End.StoreSeconds - Start.StoreSeconds) * ToPerWorldFrameMs);
    double MinimumRootTravel = TNumericLimits<double>::Max();
    for (int32 Lane = 0; Lane < Count; ++Lane)
        MinimumRootTravel = FMath::Min(MinimumRootTravel, FVector::Distance(NNJoltState->InitialRoots[Lane], NNJoltState->Agents[Lane]->GetRootLowPoint()));
    Summary->SetNumberField(TEXT("minimum_managed_root_travel_cm"), MinimumRootTravel);
    if (MinimumRootTravel <= 0.01)
    { Error = TEXT("Actual NN moving-crowd case did not advance every managed root."); return false; }
    CaseResult->SetObjectField(TEXT("actual_nn_validation"), Summary);
    // All measured frames are validated. Restore before unmeasured lifecycle checks, which
    // intentionally create and cancel a temporarily Chaos-physical pending admission.
    if (!ProphecyJolt::BenchmarkChaosPause::Restore(*this, Error)) return false;
    CaseResult->SetObjectField(TEXT("paused_chaos_diagnostic"), ProphecyJolt::BenchmarkChaosPause::ToJson());
    if (!SaveMultiJoltCase(CaseResult, Error)) return false;
    Summary->SetBoolField(TEXT("success"), true);
    CaseResult->SetStringField(TEXT("timing_scope"), TEXT("Complete measured 60 Hz actor/physics wall interval including actual CPU manager intent, capsule queries, physical feedback, 30 Hz lower/upper model inference and output, Agent target publication, one Jolt step and full skeletal presentation. All-body/all-bone diagnostics are after WorldMs; frame intervals include them. NN phase means are already inside WorldMs and must not be added again. NullRHI excludes rendering; wall latency is not total CPU summed over worker threads."));
    CaseResult->GetObjectField(TEXT("multi_jolt_validation"))->SetStringField(TEXT("feedback_scope"),
        TEXT("Actual 30 Hz CPU manager recurrent feedback and model output, 60 Hz physical control and full 88-bone presentation; optional fist closing/crowd cameras are explicitly disabled by the movement profile."));
    CaseResult->SetStringField(TEXT("generic_audit_pose_error_scope"),
        TEXT("Legacy before/after pose errors compare against the synthetic reference generator and are not actual NN trajectory errors. The authoritative checks are actual_nn_validation and every multi_jolt_frames feedback/render comparison."));
    return true;
}
