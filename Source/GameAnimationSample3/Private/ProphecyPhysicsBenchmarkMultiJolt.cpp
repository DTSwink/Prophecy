#include "ProphecyPhysicsBenchmark.h"

#include "ProphecyAgent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltCharacterProfiling.h"
#include "ProphecyJoltBenchmarkProcessorControl.h"
#include "ProphecyJoltCharacterWorldSubsystem.h"
#include "ProphecyJoltPoseAnimInstance.h"
#include "ProphecyJoltPostPhysicsQueryValidation.h"
#include "ProphecyJoltRig.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyNNLocomotionAnimInstance.h"
#include "ProphecyPhysicsBenchmarkRigAudit.h"
#include "Components/BoxComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Misc/CommandLine.h"
#include "Misc/DefaultValueHelper.h"
#include "Misc/Parse.h"
#include "Misc/ScopeExit.h"
#include "PhysicalMaterials/PhysicalMaterial.h"

namespace ProphecySterileBench::LiveJolt
{
bool CountChaosDynamicBodies(UWorld& World, int32& OutCount, FString& Error);
TSharedPtr<FJsonObject> DiagnosticsJson(const FProphecyJoltWorldDiagnostics& Diagnostics);
}

namespace ProphecySterileBench::MultiJolt
{
constexpr int32 BodiesPerAgent = 22;
constexpr int32 JointsPerAgent = 21;
constexpr int32 BonesPerAgent = 88;
constexpr float StepSeconds = 1.0f / 60.0f;
constexpr double PositionToleranceCm = 0.02;
constexpr double AngleToleranceDegrees = 0.02;
constexpr double ScaleTolerance = 1.0e-4;

bool ValidateCharacter(USkeletalMeshComponent& Physical, const USkeletalMesh* ExpectedMesh,
    const FProphecyJoltRigSnapshot& SourceRig, const FProphecyJoltWorldDiagnostics& Diagnostics,
    uint64 ExpectedRevision, bool bExpectedAutomatic, TSet<int32>& WorldBodySlots,
    FJsonObject& Row, FString& Error)
{
    AProphecyAgent* Agent = Cast<AProphecyAgent>(Physical.GetOwner());
    UProphecyJoltCharacterComponent* Character = Agent ? Agent->GetJoltCharacterComponent() : nullptr;
    if (!Agent || !Character || !Agent->IsJoltPhysicalAnimationEnabled() || !Character->IsJoltPhysical()
        || Agent->GetSimulationMode() != EProphecyAgentSimulationMode::Physical || Agent->GetPoseReferenceMesh() != &Physical)
    { Error = TEXT("Agent, binding and retained PhysicalMesh disagree about Jolt ownership."); return false; }
    if (Character->IsSteppingStopped() || !Character->GetLastError().IsEmpty())
    { Error = FString::Printf(TEXT("Character stepping stopped: %s"), *Character->GetLastError()); return false; }
    const auto* Anim = Cast<UProphecyJoltPoseAnimInstance>(Physical.GetAnimInstance());
    const uint64 Revision = Character->GetRevision();
    Row.SetNumberField(TEXT("completed_revision"), static_cast<double>(Revision));
    if (Revision != ExpectedRevision || !Anim || Anim->GetCompletedPoseRevision() != Revision
        || Character->bAutomaticStep != bExpectedAutomatic || !Character->IsRegistered() || Character->IsComponentTickEnabled())
    { Error = TEXT("The character and its pose AnimInstance must advance exactly once with the shared world step."); return false; }
    if (Physical.GetCollisionEnabled() != ECollisionEnabled::QueryOnly || Physical.IsAnySimulatingPhysics())
    { Error = TEXT("PhysicalMesh must retain query identity with native Chaos simulation disabled."); return false; }

    double MaxLinearSpeed = 0.0, MaxAngularSpeed = 0.0;
    for (const FProphecyJoltRigBody& SourceBody : SourceRig.Bodies)
    {
        FProphecyJoltBodyHandle Handle;
        FTransform BodyWorld;
        FVector Linear, Angular;
        bool bSimulating = false;
        if (!Character->GetBodyHandle(SourceBody.BodyName, Handle)
            || !Character->GetBodyState(SourceBody.BodyName, BodyWorld, Linear, Angular, bSimulating)
            || !bSimulating || !Handle.IsSet() || Handle.WorldLifetime != Diagnostics.WorldLifetime
            || WorldBodySlots.Contains(Handle.Slot) || BodyWorld.ContainsNaN() || !BodyWorld.GetRotation().IsNormalized()
            || Linear.ContainsNaN() || Angular.ContainsNaN())
        { Error = FString::Printf(TEXT("Invalid, stale or cross-rig duplicate body %s."), *SourceBody.BodyName.ToString()); return false; }
        WorldBodySlots.Add(Handle.Slot);
        MaxLinearSpeed = FMath::Max(MaxLinearSpeed, Linear.Size());
        MaxAngularSpeed = FMath::Max(MaxAngularSpeed, Angular.Size());
    }
    Row.SetNumberField(TEXT("validated_dynamic_rig_bodies"), SourceRig.Bodies.Num());
    Row.SetNumberField(TEXT("max_body_linear_speed_cm_s"), MaxLinearSpeed);
    Row.SetNumberField(TEXT("max_body_angular_speed_rad_s"), MaxAngularSpeed);

    const USkeletalMesh* Asset = Physical.GetSkeletalMeshAsset();
    if (!Asset || Asset != ExpectedMesh || Asset->GetRefSkeleton().GetNum() != BonesPerAgent)
    { Error = TEXT("PhysicalMesh must retain the complete 88-bone fixture skeleton."); return false; }
    const FReferenceSkeleton& Skeleton = Asset->GetRefSkeleton();
    TArray<FName> Names;
    TArray<FTransform> Feedback;
    Names.Reserve(Skeleton.GetNum());
    Feedback.SetNum(Skeleton.GetNum());
    for (int32 Bone = 0; Bone < Skeleton.GetNum(); ++Bone) Names.Add(Skeleton.GetBoneName(Bone));
    if (!Agent->SampleActualComponentPose(Names, Feedback))
    { Error = TEXT("Actual NN feedback could not read every completed skeleton bone."); return false; }
    const USceneComponent* FeedbackReference = Agent->GetAgentMesh() && Agent->GetAgentMesh()->IsRegistered()
        ? Agent->GetAgentMesh() : &Physical;
    const FTransform ReferenceWorld = FeedbackReference->GetComponentTransform();
    if (ReferenceWorld.ContainsNaN() || !ReferenceWorld.GetRotation().IsNormalized())
    { Error = TEXT("NN feedback reference transform is invalid."); return false; }
    double MaxPosition = 0.0, MaxAngle = 0.0, MaxScale = 0.0, PositionSquared = 0.0;
    FName WorstPositionBone, WorstAngleBone;
    for (int32 Bone = 0; Bone < Names.Num(); ++Bone)
    {
        const FTransform SocketWorld = Physical.GetSocketTransform(Names[Bone], RTS_World);
        const FTransform RenderFeedback = SocketWorld.GetRelativeTransform(ReferenceWorld);
        if (Feedback[Bone].ContainsNaN() || RenderFeedback.ContainsNaN() || SocketWorld.ContainsNaN()
            || !Feedback[Bone].GetRotation().IsNormalized() || !RenderFeedback.GetRotation().IsNormalized()
            || !SocketWorld.GetRotation().IsNormalized())
        { Error = FString::Printf(TEXT("Invalid rendered or feedback transform at %s."), *Names[Bone].ToString()); return false; }
        const double Position = FVector::Distance(Feedback[Bone].GetLocation(), RenderFeedback.GetLocation());
        const double Angle = FMath::RadiansToDegrees(Feedback[Bone].GetRotation().GetNormalized()
            .AngularDistance(RenderFeedback.GetRotation().GetNormalized()));
        const double Scale = (Feedback[Bone].GetScale3D() - RenderFeedback.GetScale3D()).GetAbsMax();
        PositionSquared += Position * Position;
        if (Position > MaxPosition) { MaxPosition = Position; WorstPositionBone = Names[Bone]; }
        if (Angle > MaxAngle) { MaxAngle = Angle; WorstAngleBone = Names[Bone]; }
        MaxScale = FMath::Max(MaxScale, Scale);
    }
    Row.SetNumberField(TEXT("validated_skeleton_bones"), Names.Num());
    Row.SetNumberField(TEXT("max_feedback_render_position_cm"), MaxPosition);
    Row.SetNumberField(TEXT("rms_feedback_render_position_cm"), FMath::Sqrt(PositionSquared / Names.Num()));
    Row.SetNumberField(TEXT("max_feedback_render_angle_degrees"), MaxAngle);
    Row.SetNumberField(TEXT("max_feedback_render_scale_difference"), MaxScale);
    Row.SetStringField(TEXT("worst_position_bone"), WorstPositionBone.ToString());
    Row.SetStringField(TEXT("worst_angle_bone"), WorstAngleBone.ToString());
    if (MaxPosition > PositionToleranceCm || MaxAngle > AngleToleranceDegrees || MaxScale > ScaleTolerance)
    {
        Error = FString::Printf(TEXT("Completed feedback/render disagreement: %.9f cm (%s), %.9f degrees (%s), scale %.9f."),
            MaxPosition, *WorstPositionBone.ToString(), MaxAngle, *WorstAngleBone.ToString(), MaxScale);
        return false;
    }
    Row.SetBoolField(TEXT("success"), true);
    return true;
}

bool ValidateDisabled(AProphecyAgent& Agent, USkeletalMeshComponent& Physical, FString& Error)
{
    const UProphecyJoltCharacterComponent* Character = Agent.GetJoltCharacterComponent();
    if (!Character || Agent.GetSimulationMode() != EProphecyAgentSimulationMode::Kinematic
        || Agent.IsJoltPhysicalAnimationEnabled() || Character->IsJoltPhysical() || Character->GetRevision() != 0
        || Character->IsComponentTickEnabled() || Character->IsKinematicRestorePending()
        || Agent.GetPoseReferenceMesh() != &Physical || Physical.IsAnySimulatingPhysics()
        || !Physical.GetAnimInstance() || Physical.GetAnimInstance()->GetClass() != UProphecyNNLocomotionAnimInstance::StaticClass())
    { Error = TEXT("A disabled crowd member failed its public Physical-to-Kinematic lifecycle transition."); return false; }
    return true;
}
}

bool UProphecyPhysicsBenchmarkSubsystem::InitializeMultiJoltCase(FString& Error)
{
    namespace Multi = ProphecySterileBench::MultiJolt;
    namespace Live = ProphecySterileBench::LiveJolt;
    namespace Json = ProphecySterileBench::RigAudit;
    Error.Reset();
    if (!Before || !Cases.IsValidIndex(CaseIndex) || Count < 2 || Meshes.Num() != Count || !GetWorld())
    { Error = TEXT("JoltCrowd requires at least two prepared manual agents and a pre-handoff audit."); return false; }
    auto* Owner = GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    auto* Coordinator = GetWorld()->GetSubsystem<UProphecyJoltCharacterWorldSubsystem>();
    if (!Owner || !Coordinator || Coordinator->GetRegisteredCharacterCount() != 0)
    { Error = TEXT("JoltCrowd requires an empty shared character coordinator and native world owner."); return false; }
    auto Provenance = MakeShared<FJsonObject>();
    Before->SetObjectField(TEXT("multi_jolt_handoff"), Provenance);
    Provenance->SetStringField(TEXT("automatic_tick_group"), Coordinator->GetAutomaticTickGroup() == TG_DuringPhysics
        ? TEXT("TG_DuringPhysics") : TEXT("TG_PrePhysics"));
    Provenance->SetNumberField(TEXT("automatic_step_count_before"), static_cast<double>(Coordinator->GetAutomaticStepCount()));
    Provenance->SetStringField(TEXT("scope"), TEXT("Separated live manual agents share one world step. Native 30 Hz authored pose source; no NN inference or Chaos trajectory equivalence gate."));
    Provenance->SetStringField(TEXT("contact_scope"), TEXT("Captured WorldStatic-only body policy. This fixture does not enable self, inter-character or other moving-body contacts."));
    Provenance->SetStringField(TEXT("angular_policy"), TEXT("User-approved hard angular limits at original PHAT angles; no retuning or claim of soft response equivalence."));
    Provenance->SetStringField(TEXT("jolt_commit"), TEXT("e77f175595e64cb44218cc9d9d56fc365ad0e36a"));
    Provenance->SetNumberField(TEXT("characters"), Count);
    Provenance->SetNumberField(TEXT("placement_grid_spacing_cm"), 600.0);
    TArray<TSharedPtr<FJsonValue>> Captures;
    for (int32 AgentIndex = 0; AgentIndex < Meshes.Num(); ++AgentIndex)
    {
        USkeletalMeshComponent* Physical = Meshes[AgentIndex];
        AProphecyAgent* Agent = IsValid(Physical) ? Cast<AProphecyAgent>(Physical->GetOwner()) : nullptr;
        if (!Agent || Agent->GetPoseReferenceMesh() != Physical || Physical->GetSkeletalMeshAsset() != MeshAsset
            || !MeshAsset || MeshAsset->GetRefSkeleton().GetNum() != Multi::BonesPerAgent)
        { Error = FString::Printf(TEXT("JoltCrowd source agent %d lost its native manual PhysicalMesh or 88-bone skeleton."), AgentIndex); return false; }
        auto Capture = MakeShared<FProphecyJoltRigSnapshot>();
        if (!ProphecyJolt::Rig::CaptureLiveRig(*Physical, *Capture, Error)) return false;
        if (Capture->Bodies.Num() != Multi::BodiesPerAgent || Capture->Joints.Num() != Multi::JointsPerAgent)
        { Error = FString::Printf(TEXT("JoltCrowd source agent %d must have 22 bodies and 21 joints."), AgentIndex); return false; }
        if (AgentIndex == 0) ManualInitialRig = Capture;
        for (int32 BodyIndex = 0; BodyIndex < Capture->Bodies.Num(); ++BodyIndex)
            if (Capture->Bodies[BodyIndex].BodyName != ManualInitialRig->Bodies[BodyIndex].BodyName)
            { Error = TEXT("Crowd source body ordering differs between agents."); return false; }
        auto Source = MakeShared<FJsonObject>();
        Source->SetNumberField(TEXT("agent_index"), AgentIndex);
        Source->SetStringField(TEXT("source_capture_id"), Capture->CaptureId.ToString());
        Source->SetStringField(TEXT("physical_component"), Physical->GetPathName());
        Source->SetStringField(TEXT("physics_asset"), GetPathNameSafe(Physical->GetPhysicsAsset()));
        Source->SetNumberField(TEXT("bodies"), Capture->Bodies.Num());
        Source->SetNumberField(TEXT("joints"), Capture->Joints.Num());
        Source->SetNumberField(TEXT("disabled_pairs"), Capture->DisabledPairs.Num());
        Source->SetObjectField(TEXT("source_component_world"), Json::Transform(Physical->GetComponentTransform()));
        Captures.Add(MakeShared<FJsonValueObject>(Source));
    }
    Provenance->SetArrayField(TEXT("source_captures"), Captures);
    int32 ChaosBefore = 0;
    if (!Live::CountChaosDynamicBodies(*GetWorld(), ChaosBefore, Error)) return false;
    Provenance->SetNumberField(TEXT("source_chaos_dynamic_bodies"), ChaosBefore);
    if (ChaosBefore != Count * Multi::BodiesPerAgent)
    { Error = FString::Printf(TEXT("JoltCrowd expected %d native Chaos dynamic bodies, found %d."), Count * Multi::BodiesPerAgent, ChaosBefore); return false; }

    const uint64 RequiredBodies = uint64(Count) * Multi::BodiesPerAgent + (Cases[CaseIndex].Floor ? 1u : 0u);
    if (RequiredBodies > MAX_uint32 / 16u)
    { Error = TEXT("JoltCrowd resource capacities exceed the native integer range."); return false; }
    FProphecyJoltWorldSettings Settings;
    Settings.GravityCmPerSecondSquared = Cases[CaseIndex].Floor ? FVector(0, 0, GetWorld()->GetGravityZ()) : FVector::ZeroVector;
    Settings.MaxBodies = uint32(RequiredBodies);
    Settings.MaxBodyPairs = uint32(RequiredBodies * 8u);
    Settings.MaxContactConstraints = uint32(RequiredBodies * 16u);
    Settings.TempAllocatorBytes = 32u * 1024u * 1024u;
    Settings.WorkerThreads = 3;
    FString RequestedWorkers;
    if (FParse::Value(FCommandLine::Get(), TEXT("PhysicsBenchJoltWorkerThreads="), RequestedWorkers)
        && (!FDefaultValueHelper::ParseInt(RequestedWorkers, Settings.WorkerThreads)
            || Settings.WorkerThreads < 0 || Settings.WorkerThreads > 32))
    { Error = TEXT("PhysicsBenchJoltWorkerThreads must be an integer from 0 to 32."); return false; }
    const FProphecyJoltWorldStatus Initialized = Owner->InitializeSimulation(Settings);
    if (!Initialized.IsSuccess()) { Error = Initialized.Message; return false; }
    Provenance->SetArrayField(TEXT("gravity_cm_s2"), Json::Vector(Settings.GravityCmPerSecondSquared));
    Provenance->SetNumberField(TEXT("max_bodies"), Settings.MaxBodies);
    Provenance->SetNumberField(TEXT("max_body_pairs"), Settings.MaxBodyPairs);
    Provenance->SetNumberField(TEXT("max_contact_constraints"), Settings.MaxContactConstraints);
    Provenance->SetNumberField(TEXT("temporary_allocator_bytes"), Settings.TempAllocatorBytes);
    Provenance->SetNumberField(TEXT("worker_threads"), Settings.WorkerThreads);
    if (Cases[CaseIndex].Floor)
    {
        UBoxComponent* SourceFloor = nullptr;
        for (AActor* Actor : Actors)
        {
            if (!IsValid(Actor)) continue;
            TInlineComponentArray<UBoxComponent*> Boxes(Actor);
            for (UBoxComponent* Box : Boxes)
            {
                if (SourceFloor) { Error = TEXT("JoltCrowd has more than one box floor candidate."); return false; }
                SourceFloor = Box;
            }
        }
        if (!SourceFloor || !SourceFloor->IsRegistered() || SourceFloor->IsSimulatingPhysics()
            || SourceFloor->GetCollisionObjectType() != ECC_WorldStatic)
        { Error = TEXT("JoltCrowd floor must be the registered static UBoxComponent from this case."); return false; }
        const FTransform FloorWorld = SourceFloor->GetComponentTransform();
        if (FloorWorld.ContainsNaN() || !FloorWorld.GetRotation().IsNormalized() || FloorWorld.GetScale3D().GetMin() <= 0.0)
        { Error = TEXT("JoltCrowd source floor has an invalid transform or nonpositive scale."); return false; }
        const UPhysicalMaterial* Material = SourceFloor->BodyInstance.GetSimplePhysicalMaterial();
        if (!Material) { Error = TEXT("JoltCrowd source floor has no simple physical material."); return false; }
        FProphecyJoltFixtureBodySettings Floor;
        Floor.bDynamic = false;
        // Keep the existing floor component as contact identity as well as geometry provenance.
        Floor.AssociatedObject = SourceFloor;
        Floor.PositionCm = FloorWorld.GetLocation();
        // Optional contact workload for hit-event benchmarking. The retained NN crowd
        // keeps its physical feet above the floor; raise only the native contact plane
        // relative to unchanged mover/NN inputs, identically in the on and off trials.
        float ContactFloorLiftCm = 0.0f;
        FParse::Value(FCommandLine::Get(), TEXT("PhysicsBenchContactFloorLiftCm="), ContactFloorLiftCm);
        if (!FMath::IsFinite(ContactFloorLiftCm) || ContactFloorLiftCm < 0.0f || ContactFloorLiftCm > 100.0f)
        { Error = TEXT("Contact benchmark floor lift must be finite and within 0..100 cm."); return false; }
        Floor.PositionCm.Z += ContactFloorLiftCm;
        Floor.Rotation = FloorWorld.GetRotation();
        Floor.Friction = Material->Friction;
        Floor.Restitution = Material->Restitution;
        const FVector HalfExtent = SourceFloor->GetScaledBoxExtent();
        FProphecyJoltBodyHandle FloorHandle;
        const FProphecyJoltWorldStatus Created = Owner->CreateBox(HalfExtent, 0.0, Floor, FloorHandle);
        if (!Created.IsSuccess()) { Error = Created.Message; return false; }
        auto FloorJson = MakeShared<FJsonObject>();
        FloorJson->SetStringField(TEXT("source_component"), SourceFloor->GetPathName());
        FloorJson->SetObjectField(TEXT("source_world_transform"), Json::Transform(FloorWorld));
        FloorJson->SetArrayField(TEXT("baked_half_extent_cm"), Json::Vector(HalfExtent));
        FloorJson->SetNumberField(TEXT("convex_radius_cm"), 0.0);
        FloorJson->SetNumberField(TEXT("contact_benchmark_floor_lift_cm"), ContactFloorLiftCm);
        FloorJson->SetStringField(TEXT("physical_material"), Material->GetPathName());
        FloorJson->SetNumberField(TEXT("friction"), Floor.Friction);
        FloorJson->SetNumberField(TEXT("restitution"), Floor.Restitution);
        FloorJson->SetStringField(TEXT("contact_scope"), TEXT("Actual fixture geometry, transform and scalar material values mirrored; Jolt contact solver and material combine policy apply."));
        Provenance->SetObjectField(TEXT("floor"), FloorJson);
    }
    else Provenance->SetField(TEXT("floor"), MakeShared<FJsonValueNull>());

    for (int32 AgentIndex = 0; AgentIndex < Meshes.Num(); ++AgentIndex)
    {
        AProphecyAgent* Agent = CastChecked<AProphecyAgent>(Meshes[AgentIndex]->GetOwner());
        if (!Agent->EnableJoltPhysicalAnimation())
        {
            const auto* Character = Agent->GetJoltCharacterComponent();
            Error = FString::Printf(TEXT("JoltCrowd agent %d activation failed: %s"), AgentIndex,
                Character ? *Character->GetLastError() : TEXT("No character binding was created."));
            return false;
        }
        const auto* Character = Agent->GetJoltCharacterComponent();
        if (!Character || !Character->IsJoltPhysical() || Character->IsSteppingStopped() || !Character->bAutomaticStep
            || !Character->IsRegistered() || Character->IsComponentTickEnabled() || Character->GetRevision() != 1 || Agent->GetPoseReferenceMesh() != Meshes[AgentIndex])
        { Error = FString::Printf(TEXT("JoltCrowd agent %d did not prime revision 1 with retained PhysicalMesh and automatic shared stepping."), AgentIndex); return false; }
    }
    FProphecyJoltWorldDiagnostics Diagnostics;
    const FProphecyJoltWorldStatus Read = Owner->GetDiagnostics(Diagnostics);
    if (!Read.IsSuccess()) { Error = Read.Message; return false; }
    Provenance->SetObjectField(TEXT("after_creation"), Live::DiagnosticsJson(Diagnostics));
    TArray<TSharedPtr<FJsonValue>> ComponentTicks;
    TInlineComponentArray<UActorComponent*> FirstAgentComponents(Meshes[0]->GetOwner());
    for (const UActorComponent* Component : FirstAgentComponents)
    {
        auto Tick = MakeShared<FJsonObject>();
        Tick->SetStringField(TEXT("name"), Component->GetName());
        Tick->SetStringField(TEXT("class"), Component->GetClass()->GetName());
        Tick->SetBoolField(TEXT("enabled"), Component->IsComponentTickEnabled());
        Tick->SetBoolField(TEXT("registered"), Component->PrimaryComponentTick.IsTickFunctionRegistered());
        ComponentTicks.Add(MakeShared<FJsonValueObject>(Tick));
    }
    Provenance->SetArrayField(TEXT("first_agent_component_ticks_after_handoff"), ComponentTicks);
    int32 ChaosAfter = 0;
    if (!Live::CountChaosDynamicBodies(*GetWorld(), ChaosAfter, Error)) return false;
    Provenance->SetNumberField(TEXT("chaos_dynamic_bodies_after_creation"), ChaosAfter);
    Provenance->SetNumberField(TEXT("coordinator_characters"), Coordinator->GetRegisteredCharacterCount());
    if (!Diagnostics.bInitialized || Diagnostics.bFaulted || Diagnostics.LastUpdateErrorBits || Diagnostics.CompletedSteps != 0
        || Diagnostics.BodyCount != RequiredBodies || Diagnostics.ConstraintCount != uint32(Count * Multi::JointsPerAgent)
        || Coordinator->GetRegisteredCharacterCount() != Count || Coordinator->IsSteppingStopped() || ChaosAfter != 0)
    { Error = TEXT("JoltCrowd handoff did not create exactly the requested rigs, one unstepped world and zero Chaos dynamics."); return false; }
    LastLiveJoltRevision = 1;
    LiveJoltFrames.Reset();
    Provenance->SetNumberField(TEXT("initial_completed_revision"), 1);
    return true;
}

bool UProphecyPhysicsBenchmarkSubsystem::ValidateMultiJoltFrame(FString& Error)
{
    namespace Profile = ProphecyJolt::CharacterProfiling;
    const Profile::FFrame CharacterFrame = Profile::EndFrame();
    namespace Multi = ProphecySterileBench::MultiJolt;
    namespace Live = ProphecySterileBench::LiveJolt;
    Error.Reset();
    auto Row = MakeShared<FJsonObject>();
    Row->SetNumberField(TEXT("sample_frame"), Frame - Warmup);
    auto Fail = [&](const FString& Message)
    {
        Error = FString::Printf(TEXT("JoltCrowd frame %d: %s"), Frame - Warmup, *Message);
        Row->SetBoolField(TEXT("success"), false);
        Row->SetStringField(TEXT("error"), Error);
        if (Before) Before->SetObjectField(TEXT("multi_jolt_failed_frame"), Row);
        return false;
    };
    if (!ManualInitialRig || Count < 2 || Meshes.Num() != Count || !Cases.IsValidIndex(CaseIndex) || !GetWorld())
        return Fail(TEXT("The source rig, case or complete retained crowd is missing."));
    auto* Owner = GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    auto* Coordinator = GetWorld()->GetSubsystem<UProphecyJoltCharacterWorldSubsystem>();
    if (!Owner || !Coordinator || Coordinator->GetRegisteredCharacterCount() != Count
        || !Coordinator->HasAutomaticStepOwners() || Coordinator->IsSteppingStopped())
        return Fail(TEXT("Shared coordinator ownership/count or automatic stepping is invalid."));
    FProphecyJoltWorldDiagnostics Diagnostics;
    const FProphecyJoltWorldStatus Read = Owner->GetDiagnostics(Diagnostics);
    if (!Read.IsSuccess()) return Fail(Read.Message);
    Row->SetObjectField(TEXT("jolt"), Live::DiagnosticsJson(Diagnostics));
    auto PhaseMs = MakeShared<FJsonObject>();
    auto PhaseCalls = MakeShared<FJsonObject>();
    for (int32 Phase = 0; Phase < Profile::PhaseCount; ++Phase)
    {
        PhaseMs->SetNumberField(Profile::PhaseNames[Phase], CharacterFrame.Seconds[Phase] * 1000.0);
        PhaseCalls->SetNumberField(Profile::PhaseNames[Phase], CharacterFrame.Calls[Phase]);
    }
    Row->SetObjectField(TEXT("character_cpu_ms"), PhaseMs);
    Row->SetObjectField(TEXT("character_cpu_calls"), PhaseCalls);
    Row->SetObjectField(TEXT("processor_provenance"), Profile::ProcessorFrameJson(CharacterFrame));
    if (!ProphecyJolt::BenchmarkProcessorControl::ValidateObservedFrame(CharacterFrame, Error)) return Fail(Error);
    Row->SetNumberField(TEXT("coordinator_characters"), Coordinator->GetRegisteredCharacterCount());
    const ETickingGroup ConfiguredGroup = Coordinator->GetAutomaticTickGroup();
    Row->SetNumberField(TEXT("automatic_tick_group"), int32(ConfiguredGroup));
    Row->SetNumberField(TEXT("actual_automatic_tick_group"), int32(Coordinator->GetLastAutomaticTickGroup()));
    Row->SetNumberField(TEXT("actual_automatic_end_tick_group"), int32(Coordinator->GetLastAutomaticEndTickGroup()));
    Row->SetNumberField(TEXT("automatic_observed_world_tick_group"), int32(Coordinator->GetLastAutomaticWorldTickGroup()));
    Row->SetNumberField(TEXT("automatic_step_engine_frame"), static_cast<double>(Coordinator->GetLastAutomaticStepEngineFrame()));
    Row->SetNumberField(TEXT("validation_engine_frame"), static_cast<double>(GFrameCounter));
    Row->SetNumberField(TEXT("automatic_step_count"), static_cast<double>(Coordinator->GetAutomaticStepCount()));
    if (!Before || !Before->HasTypedField<EJson::Object>(TEXT("multi_jolt_handoff")))
        return Fail(TEXT("The automatic-step baseline provenance is missing."));
    const uint64 AutomaticBefore = static_cast<uint64>(Before->GetObjectField(TEXT("multi_jolt_handoff"))
        ->GetNumberField(TEXT("automatic_step_count_before")));
    if ((ConfiguredGroup != TG_PrePhysics && ConfiguredGroup != TG_DuringPhysics)
        || Coordinator->GetLastAutomaticTickGroup() != ConfiguredGroup
        || Coordinator->GetLastAutomaticEndTickGroup() != ConfiguredGroup
        || Coordinator->GetLastAutomaticWorldTickGroup() != ConfiguredGroup
        || Coordinator->GetLastAutomaticStepEngineFrame() != GFrameCounter
        || Coordinator->GetAutomaticStepCount() != AutomaticBefore + uint64(LiveJoltFrames.Num()) + 1)
        return Fail(TEXT("The automatic shared step did not execute exactly once in the configured group during this frame."));
    if (!Diagnostics.bInitialized || Diagnostics.bFaulted || Diagnostics.LastUpdateErrorBits
        || Diagnostics.BodyCount != uint32(Count * Multi::BodiesPerAgent + (Cases[CaseIndex].Floor ? 1 : 0))
        || Diagnostics.ConstraintCount != uint32(Count * Multi::JointsPerAgent)
        || Diagnostics.CompletedSteps != uint64(LiveJoltFrames.Num() + 1) || Diagnostics.LastCollisionSteps != 1
        || !FMath::IsNearlyEqual(Diagnostics.LastRequestedDeltaSeconds, Multi::StepSeconds))
        return Fail(TEXT("Expected 22N bodies, 21N joints, optional floor and exactly one fixed world step per measured frame."));
    int32 ChaosDynamic = 0;
    FString ReadError;
    if (!Live::CountChaosDynamicBodies(*GetWorld(), ChaosDynamic, ReadError)) return Fail(ReadError);
    Row->SetNumberField(TEXT("chaos_dynamic_bodies"), ChaosDynamic);
    if (ChaosDynamic != 0) return Fail(TEXT("A native Chaos dynamic body remains in the crowd fixture world."));
    TSet<int32> Slots;
    TArray<TSharedPtr<FJsonValue>> AgentsJson;
    double MaxPosition = 0.0, MaxAngle = 0.0, MaxScale = 0.0;
    const uint64 ExpectedRevision = LastLiveJoltRevision + 1;
    const TArray<TSharedPtr<FJsonValue>>* PreviousAgents = nullptr;
    if (!LiveJoltFrames.IsEmpty())
    {
        const TSharedPtr<FJsonObject> PreviousFrame = LiveJoltFrames.Last()->AsObject();
        if (!PreviousFrame || !PreviousFrame->TryGetArrayField(TEXT("agents"), PreviousAgents)
            || !PreviousAgents || PreviousAgents->Num() != Meshes.Num())
            return Fail(TEXT("The previous measured frame lost its complete query-validation cohort."));
    }
    for (int32 AgentIndex = 0; AgentIndex < Meshes.Num(); ++AgentIndex)
    {
        if (!IsValid(Meshes[AgentIndex])) return Fail(FString::Printf(TEXT("Retained mesh %d is invalid."), AgentIndex));
        auto AgentJson = MakeShared<FJsonObject>();
        AgentJson->SetNumberField(TEXT("agent_index"), AgentIndex);
        if (!Multi::ValidateCharacter(*Meshes[AgentIndex], MeshAsset, *ManualInitialRig, Diagnostics,
            ExpectedRevision, true, Slots, *AgentJson, ReadError))
        {
            Row->SetObjectField(TEXT("failed_agent"), AgentJson);
            return Fail(FString::Printf(TEXT("Agent %d: %s"), AgentIndex, *ReadError));
        }
        const TSharedPtr<FJsonObject> PreviousAgent = PreviousAgents ? (*PreviousAgents)[AgentIndex]->AsObject() : nullptr;
        if ((PreviousAgents && !PreviousAgent)
            || !Multi::ValidatePostPhysicsQueries(*Meshes[AgentIndex], *ManualInitialRig, PreviousAgent.Get(), *AgentJson, ReadError))
        {
            Row->SetObjectField(TEXT("failed_agent"), AgentJson);
            return Fail(FString::Printf(TEXT("Agent %d post-EndPhysics queries: %s"), AgentIndex, *ReadError));
        }
        MaxPosition = FMath::Max(MaxPosition, AgentJson->GetNumberField(TEXT("max_feedback_render_position_cm")));
        MaxAngle = FMath::Max(MaxAngle, AgentJson->GetNumberField(TEXT("max_feedback_render_angle_degrees")));
        MaxScale = FMath::Max(MaxScale, AgentJson->GetNumberField(TEXT("max_feedback_render_scale_difference")));
        AgentsJson.Add(MakeShared<FJsonValueObject>(AgentJson));
    }
    Row->SetArrayField(TEXT("agents"), AgentsJson);
    Row->SetNumberField(TEXT("completed_revision"), static_cast<double>(ExpectedRevision));
    Row->SetNumberField(TEXT("validated_dynamic_rig_bodies"), Slots.Num());
    Row->SetNumberField(TEXT("validated_skeleton_bones"), Count * Multi::BonesPerAgent);
    Row->SetNumberField(TEXT("max_feedback_render_position_cm"), MaxPosition);
    Row->SetNumberField(TEXT("max_feedback_render_angle_degrees"), MaxAngle);
    Row->SetNumberField(TEXT("max_feedback_render_scale_difference"), MaxScale);
    Row->SetBoolField(TEXT("success"), true);
    LiveJoltFrames.Add(MakeShared<FJsonValueObject>(Row));
    LastLiveJoltRevision = ExpectedRevision;
    return true;
}

bool UProphecyPhysicsBenchmarkSubsystem::SaveMultiJoltCase(TSharedPtr<FJsonObject> CaseResult, FString& Error)
{
    namespace Profile = ProphecyJolt::CharacterProfiling;
    namespace Multi = ProphecySterileBench::MultiJolt;
    namespace Live = ProphecySterileBench::LiveJolt;
    Error.Reset();
    if (!CaseResult || !ManualInitialRig || Count < 2 || Meshes.Num() != Count || LiveJoltFrames.Num() != Samples
        || !Cases.IsValidIndex(CaseIndex) || !GetWorld())
    { Error = TEXT("JoltCrowd report requires the complete crowd and every requested validated frame."); return false; }
    auto Summary = MakeShared<FJsonObject>();
    CaseResult->SetObjectField(TEXT("multi_jolt_validation"), Summary);
    CaseResult->SetArrayField(TEXT("multi_jolt_frames"), LiveJoltFrames);
    Summary->SetBoolField(TEXT("success"), false);
    auto Fail = [&](const FString& Message) { Error = Message; Summary->SetStringField(TEXT("error"), Error); return false; };
    CaseResult->SetStringField(TEXT("timing_scope"), TEXT("One synchronous shared Jolt world step plus target publication and full skeletal presentation for N live agents. All-body/all-88-bone validation runs after world timing; frame intervals include validation overhead. NullRHI is not rendered FPS or a direct Chaos speedup measurement."));
    CaseResult->SetStringField(TEXT("pose_error_scope"), TEXT("Each completed Agent.SampleActualComponentPose result is compared to its retained PhysicalMesh sockets in the inherited AgentMesh feedback frame. No Chaos trajectory equivalence gate."));
    Summary->SetStringField(TEXT("contact_scope"), TEXT("Captured static-only contacts; self and inter-character collision remain outside this fixture."));
    Summary->SetStringField(TEXT("feedback_scope"), TEXT("Native authored pose store, including helper/finger skeleton presentation; no NN model inference or recurrent manager update."));
    Summary->SetStringField(TEXT("render_scope"), TEXT("Normal completed AnimInstance evaluation and sockets; no rasterized pixels, blood render targets or stain validation in this case."));
    Summary->SetStringField(TEXT("chaos_count_scope"), TEXT("Deduplicated valid BodyInstances from registered primitive components; native nonstatic, nonkinematic actor state in this fixture world."));
    Summary->SetStringField(TEXT("query_validation_scope"), TEXT("After EndPhysics and outside world-tick timing: all native query body X/R versus completed bone/socket poses; per-agent head rays against the retained native geometry and original mesh/bone. Own movement-capsule occlusion is predicted from actual native simple-query geometry/filter. If all six normal candidates are occluded, an unfiltered trace must first verify that capsule blocker; a second diagnostic trace ignores only that verified capsule and must hit the original head. Per-frame rows explicitly distinguish filtered coverage, which makes no normal head/blood visibility claim. Motion-edge rays remain unfiltered and must entirely miss the preceding exact GT query AABB plus 0.04 cm clearance. No production collision flags or fixture poses are changed."));
    Summary->SetNumberField(TEXT("characters"), Count);
    Summary->SetNumberField(TEXT("frames"), LiveJoltFrames.Num());
    Summary->SetNumberField(TEXT("bones_per_character"), Multi::BonesPerAgent);
    Summary->SetNumberField(TEXT("position_tolerance_cm"), Multi::PositionToleranceCm);
    Summary->SetNumberField(TEXT("angle_tolerance_degrees"), Multi::AngleToleranceDegrees);
    Summary->SetNumberField(TEXT("scale_tolerance"), Multi::ScaleTolerance);
    double MaxPosition = 0.0, MaxAngle = 0.0, MaxScale = 0.0, SumStepMs = 0.0;
    double SumCharacterMs[Profile::PhaseCount] = {};
    TMap<FString, double> SumNativeParts;
    int32 DisjointPreviousBoundsRays = 0;
    TSet<int32> AgentsWithDisjointPreviousBoundsRays;
    double MaxQueryPosition = 0.0, MaxQueryAngle = 0.0;
    for (const TSharedPtr<FJsonValue>& FrameValue : LiveJoltFrames)
    {
        const auto Row = FrameValue->AsObject();
        for (const TSharedPtr<FJsonValue>& AgentValue : Row->GetArrayField(TEXT("agents")))
        {
            const auto AgentRow = AgentValue->AsObject();
            const auto Queries = AgentRow->GetObjectField(TEXT("post_endphysics_queries"));
            MaxQueryPosition = FMath::Max(MaxQueryPosition, Queries->GetNumberField(TEXT("max_query_bone_position_cm")));
            MaxQueryAngle = FMath::Max(MaxQueryAngle, Queries->GetNumberField(TEXT("max_query_bone_angle_degrees")));
            if (Queries->GetBoolField(TEXT("disjoint_previous_aabb_ray")))
            {
                ++DisjointPreviousBoundsRays;
                AgentsWithDisjointPreviousBoundsRays.Add(static_cast<int32>(AgentRow->GetNumberField(TEXT("agent_index"))));
            }
        }
        MaxPosition = FMath::Max(MaxPosition, Row->GetNumberField(TEXT("max_feedback_render_position_cm")));
        MaxAngle = FMath::Max(MaxAngle, Row->GetNumberField(TEXT("max_feedback_render_angle_degrees")));
        MaxScale = FMath::Max(MaxScale, Row->GetNumberField(TEXT("max_feedback_render_scale_difference")));
        SumStepMs += Row->GetObjectField(TEXT("jolt"))->GetNumberField(TEXT("last_step_ms"));
        for (const auto& Part : Row->GetObjectField(TEXT("jolt"))->GetObjectField(TEXT("step_parts_ms"))->Values)
            SumNativeParts.FindOrAdd(Part.Key) += Part.Value->AsNumber();
        const auto Phases = Row->GetObjectField(TEXT("character_cpu_ms"));
        for (int32 Phase = 0; Phase < Profile::PhaseCount; ++Phase)
            SumCharacterMs[Phase] += Phases->GetNumberField(Profile::PhaseNames[Phase]);
    }
    Summary->SetNumberField(TEXT("max_feedback_render_position_cm"), MaxPosition);
    Summary->SetNumberField(TEXT("max_feedback_render_angle_degrees"), MaxAngle);
    Summary->SetNumberField(TEXT("max_feedback_render_scale_difference"), MaxScale);
    Summary->SetNumberField(TEXT("mean_synchronous_jolt_step_ms"), SumStepMs / LiveJoltFrames.Num());
    auto MeanNativeParts = MakeShared<FJsonObject>();
    for (const auto& Part : SumNativeParts)
        MeanNativeParts->SetNumberField(Part.Key, Part.Value / LiveJoltFrames.Num());
    Summary->SetObjectField(TEXT("mean_native_step_parts_ms"), MeanNativeParts);
    Summary->SetStringField(TEXT("native_step_parts_scope"), TEXT("Packet preparation, activation, PhysicsSystem::Update including the servo listener, and sample capture partition the historical synchronous Jolt step timer. Post-update validation is additional inside native_step_total. None of these scopes is a rendered frame time."));
    auto MeanCharacterMs = MakeShared<FJsonObject>();
    for (int32 Phase = 0; Phase < Profile::PhaseCount; ++Phase)
        MeanCharacterMs->SetNumberField(Profile::PhaseNames[Phase], SumCharacterMs[Phase] / LiveJoltFrames.Num());
    Summary->SetObjectField(TEXT("mean_character_cpu_ms"), MeanCharacterMs);
    Summary->SetStringField(TEXT("character_cpu_scope"), TEXT("Explicit benchmark-only GT wall timers. completed_pose_serial includes each character's serial publication and fallback body_read/compose. compose_batch_wall is the separate joined batch stage including GT input capture/body_read and worker composition; add these two disjoint totals for completed-pose staging plus publication. Body, animation/proxy/query and validation phases are children; do not add them again. coordinator_total includes both stages and native Step; AgentTick includes target publication. Timers add overhead; batch wall time is not summed worker CPU time."));
    auto* Owner = GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    auto* Coordinator = GetWorld()->GetSubsystem<UProphecyJoltCharacterWorldSubsystem>();
    if (!Owner || !Coordinator) return Fail(TEXT("JoltCrowd teardown lost the native owner or coordinator."));
    Summary->SetNumberField(TEXT("max_query_bone_position_cm"), MaxQueryPosition);
    Summary->SetNumberField(TEXT("max_query_bone_angle_degrees"), MaxQueryAngle);
    Summary->SetNumberField(TEXT("disjoint_previous_query_bounds_rays"), DisjointPreviousBoundsRays);
    Summary->SetNumberField(TEXT("agents_with_disjoint_previous_query_bounds_rays"), AgentsWithDisjointPreviousBoundsRays.Num());
    Summary->SetBoolField(TEXT("motion_edge_evidence_present"), DisjointPreviousBoundsRays > 0);
    Summary->SetBoolField(TEXT("external_post_endphysics_control_required"), Coordinator->GetAutomaticTickGroup() == TG_DuringPhysics);
    Summary->SetStringField(TEXT("external_post_endphysics_control_test"), TEXT("Prophecy.Jolt.QueryPose.PostEndPhysicsPreservesNewerExternalPose"));
    Summary->SetStringField(TEXT("external_post_endphysics_control_scope"), TEXT("DuringPhysics acceptance requires a passing matching-source foundation run of the named controlled 150 cm scene test. This benchmark does not execute or certify that external evidence. Natural crowd motion-edge coverage is reported only; all per-frame native body pose and head-ray checks remain mandatory."));
    TArray<AProphecyAgent*> Agents;
    TArray<UProphecyJoltCharacterComponent*> Characters;
    TArray<TArray<FProphecyJoltBodyHandle>> OldHandles;
    OldHandles.SetNum(Count);
    for (int32 AgentIndex = 0; AgentIndex < Count; ++AgentIndex)
    {
        AProphecyAgent* Agent = IsValid(Meshes[AgentIndex]) ? Cast<AProphecyAgent>(Meshes[AgentIndex]->GetOwner()) : nullptr;
        auto* Character = Agent ? Agent->GetJoltCharacterComponent() : nullptr;
        if (!Agent || !Character || !Character->IsJoltPhysical() || Character->GetRevision() != LastLiveJoltRevision)
            return Fail(TEXT("JoltCrowd teardown lost a current synchronized character binding."));
        Agents.Add(Agent);
        Characters.Add(Character);
        for (const FProphecyJoltRigBody& Body : ManualInitialRig->Bodies)
        {
            FProphecyJoltBodyHandle Handle;
            if (!Character->GetBodyHandle(Body.BodyName, Handle)) return Fail(TEXT("Could not capture every crowd body handle before removal."));
            OldHandles[AgentIndex].Add(Handle);
        }
    }
    // Callback regressions are outside every measured frame. Keep actual NN publications intact:
    // only the synthetic fixture owns the complete authored 88-bone source used by this mutation.
    for (auto* Character : Characters) Character->bAutomaticStep = false;
    auto Invalidation = MakeShared<FJsonObject>();
    Summary->SetObjectField(TEXT("completed_pose_callback_invalidation"), Invalidation);
    Invalidation->SetBoolField(TEXT("exercised"), false);
    if (NNJoltState.IsValid())
    {
        Invalidation->SetStringField(TEXT("reason"), TEXT("Actual NN case: synthetic pose-store mutation is deliberately not exercised."));
    }
    else
    {
        const int32 LaterIndex = Count - 1;
        int32 PoseId = INDEX_NONE;
        float PoseInterval = 0.0f;
        bool bInterpolatePose = false;
        FProphecyNNPoseSnapshot Original;
        const FReferenceSkeleton& Skeleton = MeshAsset->GetRefSkeleton();
        const int32 RootBone = 0;
        const FName RootName = Skeleton.GetBoneName(RootBone);
        const bool bRootIsPhysical = ManualInitialRig->Bodies.ContainsByPredicate(
            [RootBone](const FProphecyJoltRigBody& Body) { return Body.BoneIndex == RootBone; });
        if (Skeleton.GetParentIndex(RootBone) != INDEX_NONE || bRootIsPhysical
            || !Agents[LaterIndex]->GetNNPoseDataSource(PoseId, PoseInterval, bInterpolatePose)
            || !FProphecyNNPoseStore::GetAgentLocalPose(PoseId, Original) || !Original.IsValid()
            || Original.BoneNames.Num() != Multi::BonesPerAgent || !Original.bHasComponentWorldTransform
            || Original.PreviousComponentTransforms.Num() != Original.BoneNames.Num()
            || Original.ComponentTransforms.Num() != Original.BoneNames.Num())
            return Fail(TEXT("Callback invalidation requires the synthetic full source and an authored, nonphysical skeleton root."));
        const int32 RootPoseIndex = Original.BoneNames.IndexOfByKey(RootName);
        if (!Original.LocalTransforms.IsValidIndex(RootPoseIndex))
            return Fail(TEXT("Callback invalidation source does not contain the skeleton root."));
        const bool bOriginalAttackPresentation = FProphecyNNPoseStore::UsesAttackPresentation(PoseId);
        const FTransform OriginalRoot = Original.LocalTransforms[RootPoseIndex];
        const auto BeforeLocal = Meshes[LaterIndex]->GetBoneSpaceTransformsView();
        if (!BeforeLocal.IsValidIndex(RootBone) || !BeforeLocal[RootBone].Equals(OriginalRoot, 1.0e-6))
            return Fail(TEXT("Callback invalidation requires the initial displayed helper to match its authored source."));
        FTransform ExpectedRoot = OriginalRoot;
        ExpectedRoot.AddToTranslation(FVector(11.0, 0.0, 0.0));
        TArray<FTransform> ChangedLocal = Original.LocalTransforms;
        ChangedLocal[RootPoseIndex] = ExpectedRoot;
        const uint64 CallbackFrame = GFrameCounter;
        const uint64 BeforeRevision = Characters[LaterIndex]->GetRevision();
        FProphecyJoltWorldDiagnostics BeforeInvalidation;
        if (!Owner->GetDiagnostics(BeforeInvalidation).IsSuccess())
            return Fail(TEXT("Could not inspect native world before callback invalidation."));
        bool bCallbackRan = false, bSourceMutated = false, bRepublished = false;
        bool bLaterPublicationPending = false, bSameEngineFrame = false;
        FString CallbackError;
        FDelegateHandle MutationCallback;
        MutationCallback = Meshes[0]->RegisterOnBoneTransformsFinalizedDelegate(
            FOnBoneTransformsFinalizedMultiCast::FDelegate::CreateLambda([&]()
            {
                if (bCallbackRan) return;
                bCallbackRan = true;
                // Keep the executing functor alive; unregister after StepAndPublish returns.
                bSameEngineFrame = GFrameCounter == CallbackFrame;
                bLaterPublicationPending = Characters[LaterIndex]->GetRevision() == BeforeRevision;
                // Only the local helper changes. Previous/current component-space body targets,
                // carriers, source time, layout and attack-presentation setting remain the same.
                FProphecyNNPoseStore::SetAgentLocalPose(PoseId, Original.BoneNames, ChangedLocal,
                    Original.PreviousComponentTransforms, Original.ComponentTransforms,
                    Original.PreviousComponentWorldTransform, Original.ComponentWorldTransform,
                    Original.SourceTimeSeconds, bOriginalAttackPresentation);
                bSourceMutated = true;
                bRepublished = Characters[LaterIndex]->PublishAuthoredTargets(Multi::StepSeconds, CallbackError);
            }));
        Profile::BeginFrame();
        const bool bInvalidationStep = Characters[0]->StepAndPublish(Multi::StepSeconds, Error);
        const Profile::FFrame InvalidationProfile = Profile::EndFrame();
        Meshes[0]->UnregisterOnBoneTransformsFinalizedDelegate(MutationCallback);
        // Restore even if the callback or publication failed. This restores source values, not
        // the monotonic store revision; never rewind a production publication identifier.
        FString RestoreError;
        bool bRestored = true;
        if (bSourceMutated)
        {
            FProphecyNNPoseStore::SetAgentLocalPose(PoseId, Original.BoneNames, Original.LocalTransforms,
                Original.PreviousComponentTransforms, Original.ComponentTransforms,
                Original.PreviousComponentWorldTransform, Original.ComponentWorldTransform,
                Original.SourceTimeSeconds, bOriginalAttackPresentation);
            bRestored = Characters[LaterIndex]->PublishAuthoredTargets(Multi::StepSeconds, RestoreError);
        }
        if (!bInvalidationStep || !bCallbackRan || !bRepublished || !bSameEngineFrame
            || !bLaterPublicationPending || !bRestored)
            return Fail(FString::Printf(TEXT("Same-frame authored callback invalidation failed: step=%d callback=%d publish=%d pending=%d same_frame=%d restore=%d. %s %s %s"),
                bInvalidationStep, bCallbackRan, bRepublished, bLaterPublicationPending, bSameEngineFrame, bRestored,
                *Error, *CallbackError, *RestoreError));
        const auto PublishedLocal = Meshes[LaterIndex]->GetBoneSpaceTransformsView();
        const FTransform ExpectedWorld = ExpectedRoot * Meshes[LaterIndex]->GetComponentTransform();
        const FTransform PublishedWorld = Meshes[LaterIndex]->GetSocketTransform(RootName, RTS_World);
        const double LocalPositionError = PublishedLocal.IsValidIndex(RootBone)
            ? FVector::Distance(PublishedLocal[RootBone].GetLocation(), ExpectedRoot.GetLocation()) : TNumericLimits<double>::Max();
        const double WorldPositionError = FVector::Distance(PublishedWorld.GetLocation(), ExpectedWorld.GetLocation());
        const double ActualShift = PublishedLocal.IsValidIndex(RootBone)
            ? FVector::Distance(PublishedLocal[RootBone].GetLocation(), OriginalRoot.GetLocation()) : 0.0;
        if (!PublishedLocal.IsValidIndex(RootBone) || !PublishedLocal[RootBone].Equals(ExpectedRoot, 1.0e-6)
            || !PublishedWorld.Equals(ExpectedWorld, Multi::PositionToleranceCm) || ActualShift < 10.99)
            return Fail(FString::Printf(TEXT("A later character published stale authored helper data: local_error=%.9f cm world_error=%.9f cm actual_shift=%.9f cm."),
                LocalPositionError, WorldPositionError, ActualShift));
        const bool bSerialDiagnostic = FParse::Param(FCommandLine::Get(), TEXT("ProphecyJoltSerialCompose"));
        const uint32 BatchCalls = InvalidationProfile.Calls[static_cast<int32>(Profile::EPhase::ComposeBatch)];
        const uint32 SerialCalls = InvalidationProfile.Calls[static_cast<int32>(Profile::EPhase::Compose)];
        if (BatchCalls != (bSerialDiagnostic ? 0u : 1u) || SerialCalls != (bSerialDiagnostic ? uint32(Count) : 1u))
            return Fail(FString::Printf(TEXT("Callback invalidation did not exercise its expected composition path: batch=%u serial=%u serial_diagnostic=%d."),
                BatchCalls, SerialCalls, bSerialDiagnostic));
        FProphecyJoltWorldDiagnostics AfterInvalidation;
        if (!Owner->GetDiagnostics(AfterInvalidation).IsSuccess() || AfterInvalidation.bFaulted
            || AfterInvalidation.LastUpdateErrorBits || AfterInvalidation.CompletedSteps != BeforeInvalidation.CompletedSteps + 1
            || AfterInvalidation.BodyCount != BeforeInvalidation.BodyCount
            || AfterInvalidation.ConstraintCount != BeforeInvalidation.ConstraintCount
            || Coordinator->GetRegisteredCharacterCount() != Count || Coordinator->IsSteppingStopped())
            return Fail(TEXT("Authored callback invalidation changed world ownership or failed its one shared step."));
        TSet<int32> InvalidationSlots;
        for (int32 AgentIndex = 0; AgentIndex < Count; ++AgentIndex)
        {
            FJsonObject UnusedRow;
            if (!Multi::ValidateCharacter(*Meshes[AgentIndex], MeshAsset, *ManualInitialRig, AfterInvalidation,
                BeforeRevision + 1, false, InvalidationSlots, UnusedRow, Error)) return Fail(Error);
        }
        Invalidation->SetBoolField(TEXT("exercised"), true);
        Invalidation->SetBoolField(TEXT("success"), true);
        Invalidation->SetBoolField(TEXT("batch_path_exercised"), !bSerialDiagnostic);
        Invalidation->SetBoolField(TEXT("later_publication_was_pending"), bLaterPublicationPending);
        Invalidation->SetBoolField(TEXT("same_engine_frame"), bSameEngineFrame);
        Invalidation->SetBoolField(TEXT("original_authored_values_restored"), bRestored);
        Invalidation->SetStringField(TEXT("helper_bone"), RootName.ToString());
        Invalidation->SetStringField(TEXT("scope"), TEXT("First character finalizer changes the later character's local-only authored root by 11 cm and republishes before its completed consume. Body target arrays are retained. Actual completed local and world root, all bodies and all 88 feedback/socket poses are validated; source values are restored afterward. Outside measured samples."));
        Invalidation->SetNumberField(TEXT("source_character_index"), 0);
        Invalidation->SetNumberField(TEXT("changed_character_index"), LaterIndex);
        Invalidation->SetNumberField(TEXT("batch_calls"), BatchCalls);
        Invalidation->SetNumberField(TEXT("serial_compose_calls"), SerialCalls);
        Invalidation->SetNumberField(TEXT("authored_local_shift_cm"), ActualShift);
        Invalidation->SetNumberField(TEXT("local_position_error_cm"), LocalPositionError);
        Invalidation->SetNumberField(TEXT("world_position_error_cm"), WorldPositionError);
        Invalidation->SetObjectField(TEXT("after_callback_step"), Live::DiagnosticsJson(AfterInvalidation));
    }
    const uint64 RemovalBaseRevision = Characters[0]->GetRevision();
    FProphecyJoltWorldDiagnostics BeforeRemoval;
    if (!Owner->GetDiagnostics(BeforeRemoval).IsSuccess()) return Fail(TEXT("Could not inspect native world before crowd removal."));
    const int32 RemovedIndex = Count - 1;
    // Exercise real callback removal and a fresh kinematic pose before any later re-enable can repair
    // the class accidentally. The temporary source is isolated from every actual NN publication.
    auto RestoreAudit = MakeShared<FJsonObject>();
    Summary->SetObjectField(TEXT("callback_kinematic_restore"), RestoreAudit);
    RestoreAudit->SetBoolField(TEXT("success"), false);
    const auto ExerciseRemoval = [&]() -> bool
    {
        AProphecyAgent* RemovedAgent = Agents[RemovedIndex];
        USkeletalMeshComponent* RemovedMesh = Meshes[RemovedIndex];
        UProphecyJoltCharacterComponent* RemovedCharacter = Characters[RemovedIndex];
        int32 OriginalPoseId = INDEX_NONE;
        float OriginalInterval = 0.0f;
        bool bOriginalInterpolate = false;
        if (!RemovedAgent->GetNNPoseDataSource(OriginalPoseId, OriginalInterval, bOriginalInterpolate))
        { Error = TEXT("Removal regression requires the original NN source binding."); return false; }
        const int32 ProbePoseId = MIN_int32;
        FProphecyNNPoseSnapshot ExistingProbe;
        if (FProphecyNNPoseStore::GetAgentLocalPose(ProbePoseId, ExistingProbe))
        { Error = TEXT("Removal regression temporary pose ID is occupied."); return false; }
        const FName ProbeBone(TEXT("head"));
        const int32 ProbeBoneIndex = MeshAsset->GetRefSkeleton().FindBoneIndex(ProbeBone);
        const auto BeforeLocal = RemovedMesh->GetBoneSpaceTransformsView();
        if (!BeforeLocal.IsValidIndex(ProbeBoneIndex))
        { Error = TEXT("Removal regression requires the retained head bone."); return false; }
        const FTransform OriginalHead = BeforeLocal[ProbeBoneIndex];
        const TArray<FName> ProbeNames { ProbeBone };
        TArray<FTransform> ProbeLocal { OriginalHead };
        ProbeLocal[0].AddToTranslation(FVector(17.0, 0.0, 0.0));
        FProphecyNNPoseStore::SetAgentLocalPose(ProbePoseId, ProbeNames, ProbeLocal);
        ON_SCOPE_EXIT
        {
            RemovedAgent->ConfigureNNPoseDataSource(OriginalPoseId, OriginalInterval, bOriginalInterpolate);
            if (auto* RestoredAnim = Cast<UProphecyNNLocomotionAnimInstance>(RemovedMesh->GetAnimInstance()))
            {
                RestoredAnim->AgentId = OriginalPoseId;
                RestoredAnim->NNPoseIntervalSeconds = OriginalInterval;
                RestoredAnim->bInterpolateNNPose = bOriginalInterpolate;
                RemovedAgent->ApplyNNPoseKinematically(0.0f);
            }
            FProphecyNNPoseStore::ClearAgentPose(ProbePoseId);
        };
        const uint64 RemovalFrame = GFrameCounter;
        bool bCallbackRan = false, bDisableSucceeded = false, bNativeRemovedInCallback = false;
        bool bClassRetainedInCallback = false, bReentrantModesRefused = false;
        FDelegateHandle Callback = RemovedMesh->RegisterOnBoneTransformsFinalizedDelegate(
            FOnBoneTransformsFinalizedMultiCast::FDelegate::CreateLambda([&]()
            {
                if (bCallbackRan) return;
                bCallbackRan = true;
                // The executing delegate remains bound until the outer refresh and restore return.
                bDisableSucceeded = RemovedAgent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic);
                FProphecyJoltWorldDiagnostics During;
                bNativeRemovedInCallback = !RemovedCharacter->IsJoltPhysical()
                    && !RemovedMesh->IsAnySimulatingPhysics()
                    && Coordinator->GetRegisteredCharacterCount() == RemovedIndex
                    && Owner->GetDiagnostics(During).IsSuccess()
                    && During.BodyCount == uint32(RemovedIndex * Multi::BodiesPerAgent + (Cases[CaseIndex].Floor ? 1 : 0))
                    && During.ConstraintCount == uint32(RemovedIndex * Multi::JointsPerAgent);
                for (const FProphecyJoltBodyHandle& Handle : OldHandles[RemovedIndex])
                {
                    FProphecyJoltBodyState Unused;
                    bNativeRemovedInCallback &= Owner->ReadBody(Handle, Unused).Code == EProphecyJoltWorldResult::InvalidHandle;
                }
                bClassRetainedInCallback = RemovedCharacter->IsKinematicRestorePending()
                    && Cast<UProphecyJoltPoseAnimInstance>(RemovedMesh->GetAnimInstance()) != nullptr;
                bReentrantModesRefused = !RemovedAgent->EnableJoltPhysicalAnimation()
                    && !RemovedAgent->SetSimulationMode(EProphecyAgentSimulationMode::Physical)
                    && !RemovedAgent->SetSimulationMode(EProphecyAgentSimulationMode::HalfSim);
                RemovedAgent->ConfigureNNPoseDataSource(ProbePoseId, OriginalInterval, false);
            }));
        const bool bStepSucceeded = Characters[0]->StepAndPublish(Multi::StepSeconds, Error);
        RemovedMesh->UnregisterOnBoneTransformsFinalizedDelegate(Callback);
        if (!bStepSucceeded || !bCallbackRan || !bDisableSucceeded || !bNativeRemovedInCallback
            || !bClassRetainedInCallback || !bReentrantModesRefused || GFrameCounter != RemovalFrame
            || !Multi::ValidateDisabled(*RemovedAgent, *RemovedMesh, Error))
        { if (Error.IsEmpty()) Error = TEXT("Callback removal did not finish a safe same-frame NN restoration."); return false; }
        const auto FirstLocal = RemovedMesh->GetBoneSpaceTransformsView();
        if (!FirstLocal.IsValidIndex(ProbeBoneIndex) || !FirstLocal[ProbeBoneIndex].Equals(ProbeLocal[0], 1.0e-5))
        { Error = TEXT("Removal returned without consuming the new NN source in its restored AnimInstance."); return false; }
        const double FirstShift = FVector::Distance(FirstLocal[ProbeBoneIndex].GetLocation(), OriginalHead.GetLocation());
        // A second publication in the same engine frame proves the restored proxy continues consuming
        // fresh source revisions rather than merely retaining the completed Jolt pose or a reference pose.
        ProbeLocal[0].AddToTranslation(FVector(7.0, 0.0, 0.0));
        FProphecyNNPoseStore::SetAgentLocalPose(ProbePoseId, ProbeNames, ProbeLocal);
        if (!RemovedAgent->ApplyNNPoseKinematically(0.0f))
        { Error = TEXT("Restored NN AnimInstance rejected its next kinematic pose."); return false; }
        const auto SecondLocal = RemovedMesh->GetBoneSpaceTransformsView();
        if (GFrameCounter != RemovalFrame || !SecondLocal.IsValidIndex(ProbeBoneIndex)
            || !SecondLocal[ProbeBoneIndex].Equals(ProbeLocal[0], 1.0e-5)
            || !Multi::ValidateDisabled(*RemovedAgent, *RemovedMesh, Error))
        { if (Error.IsEmpty()) Error = TEXT("Restored NN AnimInstance retained stale same-frame pose data."); return false; }
        RestoreAudit->SetBoolField(TEXT("success"), true);
        RestoreAudit->SetBoolField(TEXT("same_engine_frame"), true);
        RestoreAudit->SetBoolField(TEXT("native_ownership_removed_inside_callback"), bNativeRemovedInCallback);
        RestoreAudit->SetBoolField(TEXT("class_change_waited_for_callback_return"), bClassRetainedInCallback);
        RestoreAudit->SetBoolField(TEXT("reentrant_modes_refused"), bReentrantModesRefused);
        RestoreAudit->SetStringField(TEXT("restored_anim_class"), RemovedMesh->GetAnimInstance()->GetClass()->GetPathName());
        RestoreAudit->SetStringField(TEXT("probe_bone"), ProbeBone.ToString());
        RestoreAudit->SetNumberField(TEXT("first_local_shift_cm"), FirstShift);
        RestoreAudit->SetNumberField(TEXT("second_local_shift_cm"), FVector::Distance(SecondLocal[ProbeBoneIndex].GetLocation(), OriginalHead.GetLocation()));
        return true;
    };
    if (!ExerciseRemoval()) return Fail(Error);
    Summary->SetBoolField(TEXT("removed_during_bone_finalization"), true);
    FProphecyJoltWorldDiagnostics AfterRemoval;
    if (!Owner->GetDiagnostics(AfterRemoval).IsSuccess() || !AfterRemoval.bInitialized || AfterRemoval.bFaulted
        || AfterRemoval.BodyCount != uint32(RemovedIndex * Multi::BodiesPerAgent + (Cases[CaseIndex].Floor ? 1 : 0))
        || AfterRemoval.ConstraintCount != uint32(RemovedIndex * Multi::JointsPerAgent)
        || AfterRemoval.CompletedSteps != BeforeRemoval.CompletedSteps + 1 || Coordinator->GetRegisteredCharacterCount() != RemovedIndex)
        return Fail(TEXT("Callback removal changed survivor ownership or failed its single shared world step."));
    Summary->SetObjectField(TEXT("after_one_removed"), Live::DiagnosticsJson(AfterRemoval));
    for (const FProphecyJoltBodyHandle& Handle : OldHandles[RemovedIndex])
    {
        FProphecyJoltBodyState Unused;
        if (Owner->ReadBody(Handle, Unused).Code != EProphecyJoltWorldResult::InvalidHandle)
            return Fail(TEXT("The removed crowd member left a native body handle valid."));
    }
    for (int32 AgentIndex = 0; AgentIndex < RemovedIndex; ++AgentIndex) Characters[AgentIndex]->bAutomaticStep = false;
    if (Coordinator->HasAutomaticStepOwners()) return Fail(TEXT("Survivors retained an automatic owner after explicit-step handoff."));
    // Retain each rig's latest immutable packet. This extra lifecycle step is outside measured samples.
    if (!Characters[0]->StepAndPublish(Multi::StepSeconds, Error)) return Fail(Error);
    FProphecyJoltWorldDiagnostics AfterSurvivorStep;
    if (!Owner->GetDiagnostics(AfterSurvivorStep).IsSuccess() || !AfterSurvivorStep.bInitialized || AfterSurvivorStep.bFaulted
        || AfterSurvivorStep.LastUpdateErrorBits || AfterSurvivorStep.CompletedSteps != BeforeRemoval.CompletedSteps + 2
        || AfterSurvivorStep.BodyCount != AfterRemoval.BodyCount || AfterSurvivorStep.ConstraintCount != AfterRemoval.ConstraintCount
        || Coordinator->GetRegisteredCharacterCount() != RemovedIndex || Coordinator->IsSteppingStopped())
        return Fail(TEXT("The survivor cohort did not advance through exactly one shared explicit world step."));
    TSet<int32> SurvivorSlots;
    TArray<TSharedPtr<FJsonValue>> SurvivorRows;
    for (int32 AgentIndex = 0; AgentIndex < RemovedIndex; ++AgentIndex)
    {
        auto AgentJson = MakeShared<FJsonObject>();
        AgentJson->SetNumberField(TEXT("agent_index"), AgentIndex);
        if (!Multi::ValidateCharacter(*Meshes[AgentIndex], MeshAsset, *ManualInitialRig, AfterSurvivorStep,
            RemovalBaseRevision + 2, false, SurvivorSlots, *AgentJson, Error)) return Fail(Error);
        for (int32 BodyIndex = 0; BodyIndex < ManualInitialRig->Bodies.Num(); ++BodyIndex)
        {
            FProphecyJoltBodyHandle Current;
            FProphecyJoltBodyState BodyState;
            const auto& Previous = OldHandles[AgentIndex][BodyIndex];
            if (!Characters[AgentIndex]->GetBodyHandle(ManualInitialRig->Bodies[BodyIndex].BodyName, Current)
                || Current.WorldLifetime != Previous.WorldLifetime || Current.Slot != Previous.Slot || Current.Generation != Previous.Generation
                || !Owner->ReadBody(Previous, BodyState).IsSuccess())
                return Fail(TEXT("Removing a peer invalidated or replaced a surviving body's exact handle."));
        }
        SurvivorRows.Add(MakeShared<FJsonValueObject>(AgentJson));
    }
    if (!Multi::ValidateDisabled(*Agents[RemovedIndex], *Meshes[RemovedIndex], Error)) return Fail(Error);
    Summary->SetArrayField(TEXT("survivors_after_explicit_step"), SurvivorRows);
    Summary->SetObjectField(TEXT("after_survivor_step"), Live::DiagnosticsJson(AfterSurvivorStep));
    Summary->SetNumberField(TEXT("survivor_handles_preserved"), SurvivorSlots.Num());
    Summary->SetNumberField(TEXT("removed_handles_rejected"), OldHandles[RemovedIndex].Num());
    // SaveMultiJoltCase runs from OnWorldPostActorTick, after this frame's dependency graph and steps.
    // A re-enable here must queue the complete handoff, keeping this removed agent under Chaos until
    // the next pre-actor boundary. This regression cancels before that boundary without ticking recursively.
    auto LateAdmission = MakeShared<FJsonObject>();
    Summary->SetObjectField(TEXT("late_admission_cancellation"), LateAdmission);
    LateAdmission->SetBoolField(TEXT("success"), false);
    LateAdmission->SetStringField(TEXT("request_phase"), TEXT("OnWorldPostActorTick"));
    LateAdmission->SetBoolField(TEXT("next_frame_admission_exercised"), false);
    LateAdmission->SetBoolField(TEXT("next_frame_cancellation_drain_exercised"), false);
    auto LateFail = [&](const FString& Message)
    {
        LateAdmission->SetStringField(TEXT("error"), Message);
        return Fail(Message);
    };
    if (!GetWorld()->bInTick || Characters[RemovedIndex]->IsEnablePending())
        return LateFail(TEXT("Late admission regression requires post-actor tick and a fully removed, non-pending agent."));
    TArray<TArray<FProphecyJoltBodyState>> BeforePendingStates;
    BeforePendingStates.SetNum(RemovedIndex);
    for (int32 AgentIndex = 0; AgentIndex < RemovedIndex; ++AgentIndex)
        for (const FProphecyJoltBodyHandle& Handle : OldHandles[AgentIndex])
        {
            FProphecyJoltBodyState State;
            if (!Owner->ReadBody(Handle, State).IsSuccess())
                return LateFail(TEXT("A survivor body was stale before the late admission request."));
            BeforePendingStates[AgentIndex].Add(State);
        }
    int32 ChaosBeforeRequest = 0;
    if (!Live::CountChaosDynamicBodies(*GetWorld(), ChaosBeforeRequest, Error) || ChaosBeforeRequest != 0)
        return LateFail(Error.IsEmpty() ? TEXT("Late admission baseline unexpectedly has Chaos dynamic bodies.") : Error);
    const auto CheckUnchangedNativeRegistry = [&](const TCHAR* Phase)
    {
        FProphecyJoltWorldDiagnostics Current;
        if (!Owner->GetDiagnostics(Current).IsSuccess() || !Current.bInitialized || Current.bFaulted
            || Current.LastUpdateErrorBits || Current.WorldLifetime != AfterSurvivorStep.WorldLifetime
            || Current.CompletedSteps != AfterSurvivorStep.CompletedSteps
            || Current.BodyCount != AfterSurvivorStep.BodyCount || Current.ConstraintCount != AfterSurvivorStep.ConstraintCount
            || Current.BodyCreationFailures != AfterSurvivorStep.BodyCreationFailures
            || Coordinator->GetRegisteredCharacterCount() != RemovedIndex || Coordinator->IsSteppingStopped()
            || Coordinator->HasAutomaticStepOwners())
        {
            Error = FString::Printf(TEXT("Late admission %s changed native ownership, registrations or world steps."), Phase);
            return false;
        }
        return true;
    };
    // Backend selection now preserves simulation mode. Explicitly request Physical
    // for this legacy deferred-admission probe; measured crowd work is unchanged.
    if (!Agents[RemovedIndex]->SetSimulationMode(EProphecyAgentSimulationMode::Physical)
        || !Agents[RemovedIndex]->EnableJoltPhysicalAnimation()
        || Agents[RemovedIndex]->GetJoltCharacterComponent() != Characters[RemovedIndex]
        || !Characters[RemovedIndex]->IsEnablePending() || Characters[RemovedIndex]->IsJoltPhysical()
        || Characters[RemovedIndex]->IsSteppingStopped() || Characters[RemovedIndex]->GetRevision() != 0
        || !Characters[RemovedIndex]->GetLastError().IsEmpty() || Characters[RemovedIndex]->IsComponentTickEnabled()
        || Agents[RemovedIndex]->GetSimulationMode() != EProphecyAgentSimulationMode::Physical
        || Agents[RemovedIndex]->IsJoltPhysicalAnimationEnabled() || !Meshes[RemovedIndex]->IsAnySimulatingPhysics())
        return LateFail(TEXT("Post-actor enable did not remain pending with its existing Chaos PhysicalMesh authoritative."));
    if (!CheckUnchangedNativeRegistry(TEXT("request"))) return LateFail(Error);
    int32 ChaosDuringPending = 0;
    if (!Live::CountChaosDynamicBodies(*GetWorld(), ChaosDuringPending, Error) || ChaosDuringPending != Multi::BodiesPerAgent)
        return LateFail(Error.IsEmpty() ? TEXT("Only the pending agent's 22 Chaos bodies should be dynamic.") : Error);
    LateAdmission->SetNumberField(TEXT("chaos_dynamic_bodies_while_pending"), ChaosDuringPending);
    LateAdmission->SetNumberField(TEXT("native_bodies_while_pending"), AfterSurvivorStep.BodyCount);
    LateAdmission->SetNumberField(TEXT("native_joints_while_pending"), AfterSurvivorStep.ConstraintCount);
    LateAdmission->SetNumberField(TEXT("registered_characters_while_pending"), Coordinator->GetRegisteredCharacterCount());
    // Heap-owned observer stays safe even if a failing implementation unexpectedly retains the delegate.
    const TSharedRef<int32> CompletionCount = MakeShared<int32>(0);
    Characters[RemovedIndex]->OnDeferredEnableCompleted.AddLambda(
        [CompletionCount](bool, const FString&) { ++CompletionCount.Get(); });
    if (!Agents[RemovedIndex]->EnableJoltPhysicalAnimation()
        || !Characters[RemovedIndex]->EnablePhysicalAnimation(Error)
        || !Characters[RemovedIndex]->IsEnablePending() || CompletionCount.Get() != 0
        || !CheckUnchangedNativeRegistry(TEXT("repeated request")))
        return LateFail(Error.IsEmpty() ? TEXT("Repeated pending enables were not idempotent.") : Error);
    if (!Agents[RemovedIndex]->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic)
        || !Multi::ValidateDisabled(*Agents[RemovedIndex], *Meshes[RemovedIndex], Error)
        || Characters[RemovedIndex]->IsEnablePending() || !Characters[RemovedIndex]->GetLastError().IsEmpty()
        || Characters[RemovedIndex]->OnDeferredEnableCompleted.IsBound() || CompletionCount.Get() != 0)
        return LateFail(Error.IsEmpty() ? TEXT("Kinematic did not cancel pending admission without a deferred result callback.") : Error);
    if (!CheckUnchangedNativeRegistry(TEXT("cancellation"))) return LateFail(Error);
    int32 ChaosAfterCancellation = 0;
    if (!Live::CountChaosDynamicBodies(*GetWorld(), ChaosAfterCancellation, Error) || ChaosAfterCancellation != 0)
        return LateFail(Error.IsEmpty() ? TEXT("Pending cancellation left native Chaos dynamic bodies active.") : Error);
    int32 UnchangedSurvivorBodies = 0;
    for (int32 AgentIndex = 0; AgentIndex < RemovedIndex; ++AgentIndex)
    {
        if (Characters[AgentIndex]->GetRevision() != RemovalBaseRevision + 2 || !Characters[AgentIndex]->IsJoltPhysical()
            || Characters[AgentIndex]->IsSteppingStopped() || !Characters[AgentIndex]->GetLastError().IsEmpty())
            return LateFail(TEXT("Pending request/cancellation changed a survivor's completed revision or health."));
        for (int32 BodyIndex = 0; BodyIndex < OldHandles[AgentIndex].Num(); ++BodyIndex)
        {
            FProphecyJoltBodyHandle CurrentHandle;
            FProphecyJoltBodyState Current;
            const auto& Handle = OldHandles[AgentIndex][BodyIndex];
            const auto& Previous = BeforePendingStates[AgentIndex][BodyIndex];
            if (!Characters[AgentIndex]->GetBodyHandle(ManualInitialRig->Bodies[BodyIndex].BodyName, CurrentHandle)
                || CurrentHandle.WorldLifetime != Handle.WorldLifetime || CurrentHandle.Slot != Handle.Slot
                || CurrentHandle.Generation != Handle.Generation || !Owner->ReadBody(Handle, Current).IsSuccess()
                || Current.PositionCm != Previous.PositionCm || Current.Rotation != Previous.Rotation
                || Current.CenterOfMassPositionCm != Previous.CenterOfMassPositionCm
                || Current.CenterOfMassVelocityCmPerSecond != Previous.CenterOfMassVelocityCmPerSecond
                || Current.AngularVelocityRadiansPerSecond != Previous.AngularVelocityRadiansPerSecond
                || Current.bDynamic != Previous.bDynamic || Current.bActive != Previous.bActive)
                return LateFail(TEXT("A pending request/cancellation replaced or advanced a surviving native body."));
            ++UnchangedSurvivorBodies;
        }
    }
    for (const FProphecyJoltBodyHandle& Handle : OldHandles[RemovedIndex])
    {
        FProphecyJoltBodyState Unused;
        if (Owner->ReadBody(Handle, Unused).Code != EProphecyJoltWorldResult::InvalidHandle)
            return LateFail(TEXT("Late admission/cancellation resurrected a removed native body handle."));
    }
    LateAdmission->SetNumberField(TEXT("chaos_dynamic_bodies_after_cancellation"), ChaosAfterCancellation);
    LateAdmission->SetNumberField(TEXT("completion_callbacks_on_cancellation"), CompletionCount.Get());
    LateAdmission->SetNumberField(TEXT("survivor_body_states_unchanged"), UnchangedSurvivorBodies);
    LateAdmission->SetBoolField(TEXT("repeated_pending_enable_idempotent"), true);
    LateAdmission->SetBoolField(TEXT("pending_token_cleared"), true);
    LateAdmission->SetBoolField(TEXT("completion_delegate_cleared"), true);
    LateAdmission->SetStringField(TEXT("coverage_limit"), TEXT("Immediate post-actor request, idempotence and mode cancellation only. No next-frame admission/drain, deferred failure callback or recursive World.Tick is exercised."));
    LateAdmission->SetBoolField(TEXT("success"), true);

    // Direct component cleanup has no Agent wrapper to update its cached mode. Observe the mode
    // from the restored NN finalizer itself, before DisablePhysicalAnimation returns.
    bool bDirectCleanupSawNN = false, bDirectCleanupModeCorrect = true;
    const FDelegateHandle DirectCleanupCallback = Meshes[0]->RegisterOnBoneTransformsFinalizedDelegate(
        FOnBoneTransformsFinalizedMultiCast::FDelegate::CreateLambda([&]()
        {
            if (Cast<UProphecyNNLocomotionAnimInstance>(Meshes[0]->GetAnimInstance()))
            {
                bDirectCleanupSawNN = true;
                bDirectCleanupModeCorrect &= Agents[0]->GetSimulationMode() == EProphecyAgentSimulationMode::Kinematic;
            }
        }));
    Characters[0]->DisablePhysicalAnimation();
    Meshes[0]->UnregisterOnBoneTransformsFinalizedDelegate(DirectCleanupCallback);
    if (!bDirectCleanupSawNN || !bDirectCleanupModeCorrect
        || !Multi::ValidateDisabled(*Agents[0], *Meshes[0], Error))
        return Fail(Error.IsEmpty() ? TEXT("Direct component cleanup exposed a non-kinematic mode to the restored NN proxy.") : Error);
    RestoreAudit->SetBoolField(TEXT("direct_component_cleanup_kinematic"), true);
    for (int32 AgentIndex = 1; AgentIndex < RemovedIndex; ++AgentIndex)
        if (!Agents[AgentIndex]->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic)
            || !Multi::ValidateDisabled(*Agents[AgentIndex], *Meshes[AgentIndex], Error))
            return Fail(Error.IsEmpty() ? TEXT("Failed to disable a surviving crowd member.") : Error);
    FProphecyJoltWorldDiagnostics AfterDisable;
    if (!Owner->GetDiagnostics(AfterDisable).IsSuccess() || !AfterDisable.bInitialized || AfterDisable.bFaulted
        || AfterDisable.LastUpdateErrorBits || AfterDisable.BodyCount != (Cases[CaseIndex].Floor ? 1u : 0u)
        || AfterDisable.ConstraintCount != 0 || AfterDisable.CompletedSteps != AfterSurvivorStep.CompletedSteps
        || Coordinator->GetRegisteredCharacterCount() != 0 || Coordinator->HasAutomaticStepOwners())
        return Fail(TEXT("Crowd teardown must retain only the initialized world and optional floor, with no constraints or registered characters."));
    int32 RejectedHandles = 0;
    for (const auto& RigHandles : OldHandles)
        for (const FProphecyJoltBodyHandle& Handle : RigHandles)
        {
            FProphecyJoltBodyState Unused;
            if (Owner->ReadBody(Handle, Unused).Code != EProphecyJoltWorldResult::InvalidHandle)
                return Fail(TEXT("Crowd teardown retained a previously published body handle."));
            ++RejectedHandles;
        }
    int32 ChaosAfter = 0;
    if (!Live::CountChaosDynamicBodies(*GetWorld(), ChaosAfter, Error)) return Fail(Error);
    if (ChaosAfter != 0) return Fail(TEXT("Crowd teardown re-enabled a native Chaos dynamic body."));
    Summary->SetObjectField(TEXT("after_disable"), Live::DiagnosticsJson(AfterDisable));
    Summary->SetNumberField(TEXT("coordinator_characters_after_disable"), Coordinator->GetRegisteredCharacterCount());
    Summary->SetNumberField(TEXT("chaos_dynamic_bodies_after_disable"), ChaosAfter);
    Summary->SetNumberField(TEXT("stale_handles_rejected"), RejectedHandles);
    Summary->SetNumberField(TEXT("extra_unmeasured_lifecycle_steps"), 2);
    Summary->SetBoolField(TEXT("returned_kinematic"), true);
    Summary->SetBoolField(TEXT("success"), true);
    return true;
}
