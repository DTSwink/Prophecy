#include "ProphecyPhysicsBenchmark.h"
#include "ProphecyAgent.h"
#include "ProphecyManualServoCapture.h"
#include "ProphecyJoltRig.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyPhysicsBenchmarkRigAudit.h"
#include "Camera/CameraComponent.h"
#include "GameFramework/SpringArmComponent.h"
#include "GameFramework/PlayerController.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Misc/FileHelper.h"
#include "Misc/EngineVersion.h"
#include "Misc/CommandLine.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace ProphecyManualFixture
{
constexpr int32 PoseId = 991000;
const FVector PhysicalMeshOffset(3.935413, 0.0, -90.022712);

FTransform Carrier(int32 Index)
{
    return FTransform(FVector((Index % 10) * 600, (Index / 10) * 600, 10));
}

void MakePose(USkeletalMesh& Asset, double Time, TArray<FName>& Names,
    TArray<FTransform>& Local, TArray<FTransform>& Component)
{
    const FReferenceSkeleton& Ref = Asset.GetRefSkeleton();
    Local = Ref.GetRefBonePose();
    Names.Reserve(Local.Num());
    Component.SetNum(Local.Num());
    for (int32 Bone = 0; Bone < Local.Num(); ++Bone)
    {
        const FName Name = Ref.GetBoneName(Bone);
        Names.Add(Name);
        if (Name == TEXT("head") || Name == TEXT("upperarm_l") || Name == TEXT("upperarm_r"))
            Local[Bone].SetRotation((Local[Bone].GetRotation() * FQuat(FVector::UpVector, .12 * FMath::Sin(Time * 2))).GetNormalized());
        if (Name == TEXT("pelvis")) Local[Bone].AddToTranslation(FVector(0, 0, 1.5 * FMath::Sin(Time * 2)));
        const int32 Parent = Ref.GetParentIndex(Bone);
        Component[Bone] = Parent == INDEX_NONE ? Local[Bone] : Local[Bone] * Component[Parent];
    }
}

void Publish(USkeletalMesh& Asset, int32 Index, double Time, double WorldTime)
{
    TArray<FName> Names, PreviousNames;
    TArray<FTransform> Local, Current, PreviousLocal, Previous;
    MakePose(Asset, Time, Names, Local, Current);
    MakePose(Asset, FMath::Max(0.0, Time - 1.0 / 30.0), PreviousNames, PreviousLocal, Previous);
    FProphecyNNPoseStore::SetAgentLocalPose(PoseId + Index, Names, Local, Previous, Current,
        Carrier(Index), Carrier(Index), WorldTime, false);
}
}

bool UProphecyPhysicsBenchmarkSubsystem::PrepareManualAgent(int32 Index, bool bFloor, FString& Error)
{
    UPhysicsAsset* PhysicsAsset = LoadObject<UPhysicsAsset>(nullptr,
        TEXT("/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin.PA_UEFN_Mannequin"));
    if (!PhysicsAsset) { Error = TEXT("Manual fixture requires the explicit SCS UEFN Physics Asset"); return false; }

    FTransform ActorTransform = ProphecyManualFixture::Carrier(Index);
    ActorTransform.AddToTranslation(-ProphecyManualFixture::PhysicalMeshOffset);
    AProphecyAgent* Agent = GetWorld()->SpawnActorDeferred<AProphecyAgent>(AProphecyAgent::StaticClass(),
        ActorTransform, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
    if (!Agent) { Error = TEXT("Manual fixture could not spawn its native shell"); return false; }
    Actors.Add(Agent);
    Agent->bManualNNPoseApplication = true;
    Agent->bAutoEnsureStandaloneNNManager = false;
    Agent->AutoPossessAI = EAutoPossessAI::Disabled;
    Agent->AutoPossessPlayer = EAutoReceiveInput::Disabled;
    Agent->bAutoPublishManualFollowerSubstepTargets = true;
    if (FParse::Param(FCommandLine::Get(), TEXT("PhysicsBenchMovementOnly")))
        Agent->bEnableAttackFists = false;

    USkeletalMeshComponent* Physical = NewObject<USkeletalMeshComponent>(Agent, TEXT("PhysicalMesh"));
    Agent->AddInstanceComponent(Physical);
    Physical->SetupAttachment(Agent->GetAgentCapsule());
    Physical->SetRelativeLocation(ProphecyManualFixture::PhysicalMeshOffset);
    Physical->SetSkeletalMesh(MeshAsset);
    Physical->SetPhysicsAsset(PhysicsAsset);
    // A native USkeletalMeshComponent defaults to NoCollision. Create the
    // skeletal body/constraint state before entering the native manual mode.
    Physical->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    Physical->SetCollisionObjectType(ECC_PhysicsBody);
    Physical->SetCollisionResponseToAllChannels(ECR_Ignore);
    Physical->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
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
    Physical->SetCastShadow(false);
    Physical->SetHiddenInGame(true);
    Physical->RegisterComponent();
    Physical->SetAllBodiesSimulatePhysics(false);

    // Same native manual-shell cleanup as the manager, with no manager/NN spawn.
    USkeletalMeshComponent* Inherited = Agent->GetAgentMesh();
    Inherited->SetSkeletalMesh(nullptr);
    Inherited->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Inherited->SetComponentTickEnabled(false);
    Inherited->SetHiddenInGame(true);
    Agent->FinishSpawning(ActorTransform);
    // FinishSpawning registers the inherited default subobject and restores its
    // initial tick setting. It has no asset in this manual shell.
    Inherited->SetComponentTickEnabled(false);
    if (FParse::Param(FCommandLine::Get(), TEXT("PhysicsBenchMovementOnly")))
    {
        // Explicit user-approved movement workload. Keep the native components, but remove
        // their unused transform subtree from the moving capsule as well as disabling ticks.
        USpringArmComponent* SpringArm = Agent->GetAgentSpringArm();
        UCameraComponent* Camera = Agent->GetAgentCamera();
        if (!SpringArm || !Camera || !SpringArm->IsRegistered() || !Camera->IsRegistered()
            || SpringArm->GetAttachParent() != Agent->GetAgentCapsule()
            || Camera->GetAttachParent() != SpringArm || Agent->GetController())
        { Error = TEXT("Movement-only camera detachment requires the unpossessed native camera hierarchy."); return false; }
        for (FConstPlayerControllerIterator Controller = GetWorld()->GetPlayerControllerIterator(); Controller; ++Controller)
            if (Controller->IsValid() && Controller->Get()->GetViewTarget() == Agent)
            { Error = TEXT("Movement-only fixture will not detach a player's active view target."); return false; }
        SpringArm->SetComponentTickEnabled(false);
        Camera->SetComponentTickEnabled(false);
        auto CameraRecord = MakeShared<FJsonObject>();
        CameraRecord->SetNumberField(TEXT("agent_index"), Index);
        CameraRecord->SetStringField(TEXT("agent"), Agent->GetPathName());
        CameraRecord->SetStringField(TEXT("spring_arm"), SpringArm->GetPathName());
        CameraRecord->SetStringField(TEXT("camera"), Camera->GetPathName());
        CameraRecord->SetStringField(TEXT("spring_arm_parent_before"), GetPathNameSafe(SpringArm->GetAttachParent()));
        CameraRecord->SetStringField(TEXT("camera_parent_before"), GetPathNameSafe(Camera->GetAttachParent()));
        const FTransform SpringWorld = SpringArm->GetComponentTransform();
        const FTransform CameraWorld = Camera->GetComponentTransform();
        const FTransform ActorWorld = Agent->GetActorTransform();
        const FTransform InheritedWorld = Inherited->GetComponentTransform();
        const FTransform PhysicalWorld = Physical->GetComponentTransform();
        CameraRecord->SetObjectField(TEXT("spring_arm_world_before"), ProphecySterileBench::RigAudit::Transform(SpringWorld));
        CameraRecord->SetObjectField(TEXT("camera_world_before"), ProphecySterileBench::RigAudit::Transform(CameraWorld));
        SpringArm->DetachFromComponent(FDetachmentTransformRules::KeepWorldTransform);
        CameraRecord->SetStringField(TEXT("spring_arm_parent_after"), GetPathNameSafe(SpringArm->GetAttachParent()));
        CameraRecord->SetStringField(TEXT("camera_parent_after"), GetPathNameSafe(Camera->GetAttachParent()));
        CameraRecord->SetObjectField(TEXT("spring_arm_world_after"), ProphecySterileBench::RigAudit::Transform(SpringArm->GetComponentTransform()));
        CameraRecord->SetObjectField(TEXT("camera_world_after"), ProphecySterileBench::RigAudit::Transform(Camera->GetComponentTransform()));
        const bool bPreservedWorld = SpringArm->GetComponentTransform().Equals(SpringWorld, 1.0e-6)
            && Camera->GetComponentTransform().Equals(CameraWorld, 1.0e-6);
        const bool bPreservedMovement = Agent->GetActorTransform().Equals(ActorWorld, 1.0e-6)
            && Inherited->GetComponentTransform().Equals(InheritedWorld, 1.0e-6)
            && Physical->GetComponentTransform().Equals(PhysicalWorld, 1.0e-6);
        const bool bDetached = !SpringArm->GetAttachParent() && Camera->GetAttachParent() == SpringArm
            && SpringArm->IsRegistered() && Camera->IsRegistered();
        CameraRecord->SetBoolField(TEXT("camera_world_transforms_preserved"), bPreservedWorld);
        CameraRecord->SetBoolField(TEXT("actor_and_mesh_world_transforms_preserved"), bPreservedMovement);
        CameraRecord->SetBoolField(TEXT("registered_subtree_detached"), bDetached);
        MovementCameraDetachments.Add(MakeShared<FJsonValueObject>(CameraRecord));
        if (!bPreservedWorld || !bPreservedMovement || !bDetached)
        { Error = TEXT("Movement-only camera detachment did not preserve the native hierarchy's world state."); return false; }
    }
    Agent->ConfigureNNPoseDataSource(ProphecyManualFixture::PoseId + Index, 1.f / 30.f, true);
    ProphecyManualFixture::Publish(*MeshAsset, Index, 0.0, GetWorld()->GetTimeSeconds());
    Physical->SetAnimInstanceClass(UProphecyNNLocomotionAnimInstance::StaticClass());
    UProphecyNNLocomotionAnimInstance* Anim = Cast<UProphecyNNLocomotionAnimInstance>(Physical->GetAnimInstance());
    if (!Anim) { Error = TEXT("Manual fixture animation initialization failed"); return false; }
    Anim->AgentId = ProphecyManualFixture::PoseId + Index;
    Anim->NNPoseIntervalSeconds = 1.f / 30.f;
    Anim->bInterpolateNNPose = true;
    Physical->TickAnimation(0, false);
    Physical->RefreshBoneTransforms();
    if (!Agent->SetSimulationMode(EProphecyAgentSimulationMode::Physical) || Agent->GetPoseReferenceMesh() != Physical ||
        !Physical->IsAnySimulatingPhysics())
    { Error = TEXT("Manual fixture did not enter Physical mode on PhysicalMesh"); return false; }

    // Explicit isolated contact/discrete fixture, preserving the authored joint
    // profile and all nine CDO body-setting entries (missing entries default on).
    Agent->GetAgentCapsule()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Physical->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    Physical->SetCollisionObjectType(ECC_PhysicsBody);
    Physical->SetCollisionResponseToAllChannels(ECR_Ignore);
    Physical->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
    Physical->SetEnableGravity(bFloor);
    Physical->SetGenerateOverlapEvents(false);
    Physical->SetNotifyRigidBodyCollision(false);
    Physical->AddTickPrerequisiteActor(Agent);
    for (FBodyInstance* Body : Physical->Bodies) if (Body)
    {
        Body->SetPositionSolverIterationCount(Agent->PhysicalPositionSolverIterations);
        Body->SetVelocitySolverIterationCount(Agent->PhysicalVelocitySolverIterations);
        Body->SetProjectionSolverIterationCount(Agent->PhysicalProjectionSolverIterations);
        Body->SetUseCCD(false);
        Body->SetUseMACD(false);
    }
    if (Physical->Bodies.Num() != 22 || Physical->Constraints.Num() != 21)
    { Error = TEXT("Manual fixture expected 22 bodies and 21 authored joints"); return false; }
    Meshes.Add(Physical);
    return true;
}

void UProphecyPhysicsBenchmarkSubsystem::PublishManualPose(int32 Index)
{
    const double Time = static_cast<double>(FMath::Max(0, Frame - Warmup)) / 60.0;
    ProphecyManualFixture::Publish(*MeshAsset, Index, Time, GetWorld()->GetTimeSeconds());
}

bool UProphecyPhysicsBenchmarkSubsystem::CaptureManualRig(FString& Error)
{
    if (FParse::Param(FCommandLine::Get(), TEXT("PhysicsBenchManualChaosOnly")))
    {
        Before->SetStringField(TEXT("jolt_preparation_scope"), TEXT("Explicit Chaos-only controller capture/replay; no Jolt rig import or execution requested by this diagnostic run"));
        return true;
    }
    ManualInitialRig = MakeShared<FProphecyJoltRigSnapshot>();
    if (!ProphecyJolt::Rig::CaptureLiveRig(*Meshes[0], *ManualInitialRig, Error)) return false;
    FProphecyJoltPreparedRig Prepared;
    if (!Prepared.Build(*ManualInitialRig, Error)) return false;
    auto Summary = MakeShared<FJsonObject>();
    Summary->SetStringField(TEXT("capture_id"), ManualInitialRig->CaptureId.ToString());
    Summary->SetNumberField(TEXT("bodies"), Prepared.GetBodyCount());
    Summary->SetNumberField(TEXT("joints"), ManualInitialRig->Joints.Num());
    Summary->SetNumberField(TEXT("disabled_pairs"), ManualInitialRig->DisabledPairs.Num());
    Summary->SetStringField(TEXT("scope"), TEXT("Live body/frame capture plus prepared native shapes and explicit mass/inertia; no Jolt bodies created yet"));
    TArray<TSharedPtr<FJsonValue>> Bodies, Notes;
    for (const FString& Note : ManualInitialRig->CoverageNotes) Notes.Add(MakeShared<FJsonValueString>(Note));
    for (int32 Index = 0; Index < ManualInitialRig->Bodies.Num(); ++Index)
    {
        FVector COM;
        FBox Bounds;
        if (!Prepared.GetBodyGeometrySummary(Index, COM, Bounds, Error)) return false;
        const FProphecyJoltRigBody& Body = ManualInitialRig->Bodies[Index];
        auto B = MakeShared<FJsonObject>();
        B->SetStringField(TEXT("bone"), Body.BodyName.ToString());
        B->SetArrayField(TEXT("prepared_com_cm"), ProphecySterileBench::RigAudit::Vector(COM));
        B->SetArrayField(TEXT("prepared_bounds_min_cm"), ProphecySterileBench::RigAudit::Vector(Bounds.Min));
        B->SetArrayField(TEXT("prepared_bounds_max_cm"), ProphecySterileBench::RigAudit::Vector(Bounds.Max));
        B->SetNumberField(TEXT("authored_shapes"), Body.Shapes.Num());
        B->SetArrayField(TEXT("source_body_scale"), ProphecySterileBench::RigAudit::Vector(Body.SourceBodyScale3D));
        TArray<TSharedPtr<FJsonValue>> Shapes;
        for (const FProphecyJoltRigShape& Shape : Body.Shapes)
        {
            auto S = MakeShared<FJsonObject>();
            S->SetNumberField(TEXT("authored_element_index"), Shape.SourceElementIndex);
            S->SetNumberField(TEXT("native_shape_index"), Shape.SourceNativeShapeIndex);
            S->SetBoolField(TEXT("geometry_from_live_chaos"), Shape.bGeometryCapturedFromNative);
            S->SetNumberField(TEXT("kind"), static_cast<uint8>(Shape.Kind));
            S->SetObjectField(TEXT("collider_to_body_origin"), ProphecySterileBench::RigAudit::Transform(Shape.LocalToBodyOrigin));
            S->SetNumberField(TEXT("radius_cm"), Shape.RadiusCm);
            S->SetNumberField(TEXT("capsule_cylinder_length_cm"), Shape.CapsuleCylinderLengthCm);
            S->SetArrayField(TEXT("box_half_extent_cm"), ProphecySterileBench::RigAudit::Vector(Shape.BoxHalfExtentCm));
            S->SetNumberField(TEXT("native_leaf_margin_cm"), Shape.NativeCollisionMarginCm);
            Shapes.Add(MakeShared<FJsonValueObject>(S));
        }
        B->SetArrayField(TEXT("effective_shapes"), Shapes);
        Bodies.Add(MakeShared<FJsonValueObject>(B));
    }
    Summary->SetArrayField(TEXT("coverage_notes"), Notes);
    Summary->SetArrayField(TEXT("body_geometry"), Bodies);
    Before->SetObjectField(TEXT("jolt_prepared_rig"), Summary);
    return true;
}

bool UProphecyPhysicsBenchmarkSubsystem::RestoreManualReplayState(FString& Error)
{
    if (!ManualSealedCapture || ManualSealedCapture->Steps.IsEmpty() || ManualSealedCapture->Packets.IsEmpty())
    { Error = TEXT("Manual replay has no sealed capture"); return false; }
    AProphecyAgent* Agent = CastChecked<AProphecyAgent>(Meshes[0]->GetOwner());
    Agent->bAutoPublishManualFollowerSubstepTargets = false;
    const auto& Packet = ManualSealedCapture->Packets[0];
    const auto& Step = ManualSealedCapture->Steps[0];
    for (int32 Index = 0; Index < Packet.BodyCount; ++Index)
    {
        FBodyInstance* Body = Meshes[0]->GetBodyInstance(Packet.Bodies[Index].BoneName);
        if (!Body || !Body->IsInstanceSimulatingPhysics() || !Step.Bodies[Index].bValid)
        { Error = TEXT("Manual replay could not resolve an initial body"); return false; }
        const auto& State = Step.Bodies[Index];
        Body->SetBodyTransform(FTransform(State.Rotation, State.Position), ETeleportType::TeleportPhysics, false);
        Body->SetLinearVelocity(State.LinearVelocityBefore, false, false);
        Body->SetAngularVelocityInRadians(State.AngularVelocityBefore, false, false);
    }
    Before = Audit();
    return true;
}

bool UProphecyPhysicsBenchmarkSubsystem::PublishManualReplayFrame(FString& Error)
{
    const int32 Index = Frame - Warmup;
    if (!ManualSealedCapture || !ManualSealedCapture->Packets.IsValidIndex(Index))
    { Error = TEXT("Manual replay exhausted sealed packet input"); return false; }
    return ProphecyManualServoCapture::PublishReplayPacket(
        CastChecked<AProphecyAgent>(Meshes[0]->GetOwner()), ManualSealedCapture->Packets[Index], Error);
}

bool UProphecyPhysicsBenchmarkSubsystem::SaveManualCapture(TSharedPtr<FJsonObject> CaseResult, FString& Error)
{
    using namespace ProphecyManualServoCapture;
    namespace Json = ProphecySterileBench::RigAudit;
    FCapture Capture;
    if (!EndCapture(CastChecked<AProphecyAgent>(Meshes[0]->GetOwner()), Capture, Error)) return false;
    if (Capture.bPacketOverflow || Capture.bStepOverflow || Capture.bBodyOverflow || Capture.FailedPublications ||
        Capture.StalePacketConsumptions || Capture.UnrecordedPacketConsumptions || Capture.MissingBodySamples ||
        Capture.PacketsRecorded != Samples || Capture.StepsRecorded != Samples ||
        Capture.Packets.Num() < Samples || Capture.Steps.Num() < Samples)
    {
        Error = FString::Printf(TEXT("Manual capture incomplete: packets=%d steps=%d expected=%d failed=%llu stale=%llu unrecorded=%llu missing=%llu overflows=%d/%d/%d"),
            Capture.PacketsRecorded, Capture.StepsRecorded, Samples, Capture.FailedPublications,
            Capture.StalePacketConsumptions, Capture.UnrecordedPacketConsumptions, Capture.MissingBodySamples,
            Capture.bPacketOverflow, Capture.bStepOverflow, Capture.bBodyOverflow);
        return false;
    }
    auto Root = MakeShared<FJsonObject>();
    Root->SetNumberField(TEXT("schema_version"), 1);
    Root->SetStringField(TEXT("controller"), TEXT("Existing FManualFollowerSubstepCallback PreIntegrate SetV/SetW"));
    Root->SetStringField(TEXT("scope"), TEXT("Native CDO/SCS-derived diagnostic fixture; exact final body endpoints, not placed Blueprint/NN/rendered validation"));
    Root->SetStringField(TEXT("engine"), FEngineVersion::Current().ToString());
    Root->SetStringField(TEXT("mesh"), MeshAsset->GetPathName());
    Root->SetStringField(TEXT("physics_asset"), Meshes[0]->GetPhysicsAsset()->GetPathName());
    Root->SetStringField(TEXT("fixture"), Cases[CaseIndex].Floor ? TEXT("floor_gravity") : TEXT("air_no_gravity"));
    Root->SetStringField(TEXT("units"), TEXT("UE +X/+Y/+Z; cm, kg, seconds, radians; raw body-origin X/R and COM V/W"));
    Root->SetStringField(TEXT("overrides"), TEXT("No manager/NN; native separate PhysicalMesh; capsule collision off; WorldStatic-only contacts; CCD/MACD off; no extra per-frame wake or impulse"));
    Root->SetStringField(TEXT("tick_order"), TEXT("OnWorldPreActorTick 30Hz pose store -> native Agent PrePhysics auto-publisher -> PhysicalMesh -> physics -> OnWorldPostActorTick"));
    Root->SetStringField(TEXT("angular_policy"), TEXT("Chaos capture retains authored profiles. User-approved Jolt replay uses hard limits at unchanged PHAT angles; no retuning."));
    Root->SetNumberField(TEXT("fixed_frame_seconds"), 1.0 / 60.0);
    Root->SetNumberField(TEXT("policy_interval_seconds"), 1.0 / 30.0);
    Root->SetNumberField(TEXT("warmup_frames"), Warmup);
    Root->SetObjectField(TEXT("initial_audit"), Before);
    Root->SetObjectField(TEXT("final_audit"), CaseResult->GetObjectField(TEXT("after")));
    Root->SetNumberField(TEXT("published_packets"), Capture.PublishedPackets);
    Root->SetNumberField(TEXT("consumed_callbacks"), Capture.ConsumedCallbacks);
    const bool bReplay = Cases[CaseIndex].Mode == 13;
    if (bReplay)
    {
        Root->SetStringField(TEXT("replay_source_file"), ManualSealedCapturePath);
        Root->SetStringField(TEXT("replay_source_sha1"), ManualSealedCaptureHash);
        Root->SetStringField(TEXT("initialization"), TEXT("Fresh native actor with identical stationary warmup, then captured raw body X/R/V/W restored before first replay publication; no claim to restoring solver caches"));
    }

    TArray<TSharedPtr<FJsonValue>> Packets, Steps;
    for (int32 Index = 0; Index < Samples; ++Index)
    {
        const FPacket& Packet = Capture.Packets[Index];
        const FStep& Step = Capture.Steps[Index];
        if (Packet.Sequence != static_cast<uint64>(Index + 1) || Step.Sequence != Packet.Sequence ||
            Step.PacketSequence != Packet.Sequence || Packet.BodyCount != 22 || Step.BodyCount != 22 ||
            !FMath::IsNearlyEqual(Step.CallbackDeltaSeconds, 1.0 / 60.0, 1.e-6) ||
            !FMath::IsNearlyEqual(static_cast<double>(Step.DenominatorSeconds), 1.0 / 60.0, 1.e-6) ||
            Step.bRepeatedPacket || Step.bStaleAfterFailedPublish || Step.bUnrecordedPacket)
        { Error = FString::Printf(TEXT("Manual capture packet/step contract failed at index %d"), Index); return false; }
        auto P = MakeShared<FJsonObject>();
        P->SetNumberField(TEXT("sequence"), Packet.Sequence);
        P->SetNumberField(TEXT("source_sequence"), Packet.SourceSequence);
        P->SetNumberField(TEXT("game_frame"), Packet.GameFrame);
        P->SetNumberField(TEXT("frame_delta_seconds"), Packet.FrameDeltaSeconds);
        P->SetNumberField(TEXT("denominator_seconds"), Packet.MaximumSubstepSeconds);
        auto S = MakeShared<FJsonObject>();
        S->SetNumberField(TEXT("sequence"), Step.Sequence);
        S->SetNumberField(TEXT("packet_sequence"), Step.PacketSequence);
        S->SetNumberField(TEXT("source_sequence"), Step.SourceSequence);
        S->SetNumberField(TEXT("callback_context_time_seconds"), Step.CallbackSimTimeSeconds);
        S->SetNumberField(TEXT("callback_context_delta_seconds"), Step.CallbackDeltaSeconds);
        S->SetNumberField(TEXT("denominator_seconds"), Step.DenominatorSeconds);
        TArray<TSharedPtr<FJsonValue>> Targets, States;
        TSet<FName> UniqueNames;
        for (int32 Bone = 0; Bone < Packet.BodyCount; ++Bone)
        {
            const FBoneTarget& Target = Packet.Bodies[Bone];
            const FBodyStep& Body = Step.Bodies[Bone];
            if (!Body.bValid || Target.BoneName.IsNone() || UniqueNames.Contains(Target.BoneName) ||
                Target.TargetPosition.ContainsNaN() || !Target.TargetRotation.IsNormalized() ||
                Target.ActualBoneWorld.ContainsNaN() || Target.BodyFromBone.ContainsNaN() ||
                Body.Position.ContainsNaN() || !Body.Rotation.IsNormalized() ||
                Body.LinearVelocityBefore.ContainsNaN() || Body.AngularVelocityBefore.ContainsNaN() ||
                Body.LinearVelocityAfter.ContainsNaN() || Body.AngularVelocityAfter.ContainsNaN())
            { Error = TEXT("Manual capture has missing, duplicate or invalid body state"); return false; }
            UniqueNames.Add(Target.BoneName);
            auto T = MakeShared<FJsonObject>();
            T->SetStringField(TEXT("bone"), Target.BoneName.ToString());
            T->SetObjectField(TEXT("actual_bone_world"), Json::Transform(Target.ActualBoneWorld));
            T->SetObjectField(TEXT("body_from_bone"), Json::Transform(Target.BodyFromBone));
            T->SetObjectField(TEXT("target_body_world"), Json::Transform(FTransform(Target.TargetRotation, Target.TargetPosition)));
            T->SetNumberField(TEXT("linear_strength"), Target.LinearStrength);
            T->SetNumberField(TEXT("angular_strength"), Target.AngularStrength);
            Targets.Add(MakeShared<FJsonValueObject>(T));
            auto B = MakeShared<FJsonObject>();
            B->SetStringField(TEXT("bone"), Target.BoneName.ToString());
            B->SetObjectField(TEXT("raw_body_world_before"), Json::Transform(FTransform(Body.Rotation, Body.Position)));
            B->SetArrayField(TEXT("linear_velocity_before_cm_s"), Json::Vector(Body.LinearVelocityBefore));
            B->SetArrayField(TEXT("angular_velocity_before_rad_s"), Json::Vector(Body.AngularVelocityBefore));
            B->SetArrayField(TEXT("linear_velocity_after_cm_s"), Json::Vector(Body.LinearVelocityAfter));
            B->SetArrayField(TEXT("angular_velocity_after_rad_s"), Json::Vector(Body.AngularVelocityAfter));
            States.Add(MakeShared<FJsonValueObject>(B));
        }
        P->SetArrayField(TEXT("bodies"), Targets);
        S->SetArrayField(TEXT("bodies"), States);
        Packets.Add(MakeShared<FJsonValueObject>(P));
        Steps.Add(MakeShared<FJsonValueObject>(S));
    }
    Root->SetArrayField(TEXT("packets"), Packets);
    Root->SetArrayField(TEXT("steps"), Steps);
    bool bReplayMatches = true;
    bool bReplayInputsMatch = true;
    if (bReplay)
    {
        if (!ManualSealedCapture || ManualSealedCapture->Steps.Num() != Capture.Steps.Num())
        { Error = TEXT("Manual replay source length mismatch"); return false; }
        double MaxPosition = 0, MaxAngleDegrees = 0, MaxLinearVelocity = 0, MaxAngularVelocity = 0;
        bool bIdenticalInputs = true, bIdenticalFirstStep = true;
        for (int32 Index = 0; Index < Samples; ++Index)
        {
            if (Capture.Packets[Index].SourceSequence != ManualSealedCapture->Packets[Index].Sequence)
            { Error = TEXT("Manual replay source sequence mismatch"); return false; }
            for (int32 Bone = 0; Bone < 22; ++Bone)
            {
                const FBoneTarget& SourceTarget = ManualSealedCapture->Packets[Index].Bodies[Bone];
                const FBoneTarget& ReplayTarget = Capture.Packets[Index].Bodies[Bone];
                bIdenticalInputs &= SourceTarget.BoneName == ReplayTarget.BoneName
                    && SourceTarget.TargetPosition == ReplayTarget.TargetPosition
                    && SourceTarget.TargetRotation == ReplayTarget.TargetRotation
                    && SourceTarget.LinearStrength == ReplayTarget.LinearStrength
                    && SourceTarget.AngularStrength == ReplayTarget.AngularStrength
                    && ManualSealedCapture->Packets[Index].MaximumSubstepSeconds == Capture.Packets[Index].MaximumSubstepSeconds;
                const FBodyStep& Source = ManualSealedCapture->Steps[Index].Bodies[Bone];
                const FBodyStep& Replay = Capture.Steps[Index].Bodies[Bone];
                if (Index == 0) bIdenticalFirstStep &= Source.Position == Replay.Position && Source.Rotation == Replay.Rotation
                    && Source.LinearVelocityBefore == Replay.LinearVelocityBefore && Source.AngularVelocityBefore == Replay.AngularVelocityBefore
                    && Source.LinearVelocityAfter == Replay.LinearVelocityAfter && Source.AngularVelocityAfter == Replay.AngularVelocityAfter;
                MaxPosition = FMath::Max(MaxPosition, FVector::Distance(Source.Position, Replay.Position));
                // Chaos records float quaternions in double UE storage. Their tiny
                // length error must not turn identical orientations into a nonzero distance.
                MaxAngleDegrees = FMath::Max(MaxAngleDegrees, FMath::RadiansToDegrees(
                    Source.Rotation.GetNormalized().AngularDistance(Replay.Rotation.GetNormalized())));
                MaxLinearVelocity = FMath::Max(MaxLinearVelocity, FVector::Distance(Source.LinearVelocityAfter, Replay.LinearVelocityAfter));
                MaxAngularVelocity = FMath::Max(MaxAngularVelocity, FVector::Distance(Source.AngularVelocityAfter, Replay.AngularVelocityAfter));
            }
        }
        bReplayMatches = bIdenticalInputs && bIdenticalFirstStep && MaxPosition <= 0.01 && MaxAngleDegrees <= 0.01
            && MaxLinearVelocity <= 0.1 && MaxAngularVelocity <= 0.01;
        bReplayInputsMatch = bIdenticalInputs;
        auto Comparison = MakeShared<FJsonObject>();
        Comparison->SetBoolField(TEXT("passed"), bReplayMatches);
        Comparison->SetStringField(TEXT("acceptance_role"), TEXT("Trajectory diagnostic only: user requires working fast functionality, not 1:1 Chaos/Jolt equivalence. Input integrity remains required."));
        Comparison->SetBoolField(TEXT("identical_final_inputs"), bIdenticalInputs);
        Comparison->SetBoolField(TEXT("identical_first_pre_post_servo_state"), bIdenticalFirstStep);
        Comparison->SetStringField(TEXT("orientation_metric"), TEXT("Shortest angular distance between normalized quaternions"));
        Comparison->SetNumberField(TEXT("max_position_cm"), MaxPosition);
        Comparison->SetNumberField(TEXT("max_angle_degrees"), MaxAngleDegrees);
        Comparison->SetNumberField(TEXT("max_post_servo_linear_velocity_cm_s"), MaxLinearVelocity);
        Comparison->SetNumberField(TEXT("max_post_servo_angular_velocity_rad_s"), MaxAngularVelocity);
        Comparison->SetStringField(TEXT("diagnostic_tolerances"), TEXT("0.01cm, 0.01deg, 0.1cm/s, 0.01rad/s; capture/replay check, not production visual acceptance"));
        Root->SetObjectField(TEXT("chaos_replay_comparison"), Comparison);
        CaseResult->SetObjectField(TEXT("chaos_replay_comparison"), Comparison);
    }
    const FString Path = FPaths::GetPath(Output) / (FPaths::GetBaseFilename(Output) +
        (bReplay ? TEXT("-replay") : TEXT("")) +
        (Cases[CaseIndex].Floor ? TEXT("-manual-floor.json") : TEXT("-manual-air.json")));
    if (!IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path), true))
    { Error = TEXT("Could not create manual capture output directory"); return false; }
    FString Text;
    if (!FJsonSerializer::Serialize(Root, TJsonWriterFactory<>::Create(&Text)) ||
        !FFileHelper::SaveStringToFile(Text, *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
            &IFileManager::Get(), FILEWRITE_NoReplaceExisting))
    { Error = TEXT("Could not write new sealed manual capture"); return false; }
    FTCHARToUTF8 Bytes(*Text);
    uint8 Hash[FSHA1::DigestSize];
    FSHA1::HashBuffer(Bytes.Get(), Bytes.Length(), Hash);
    CaseResult->SetStringField(TEXT("manual_capture_file"), FPaths::ConvertRelativePathToFull(Path));
    CaseResult->SetStringField(TEXT("manual_capture_sha1"), BytesToHex(Hash, UE_ARRAY_COUNT(Hash)));
    CaseResult->SetNumberField(TEXT("manual_capture_packets"), Capture.PacketsRecorded);
    CaseResult->SetNumberField(TEXT("manual_capture_steps"), Capture.StepsRecorded);
    if (!bReplay)
    {
        ManualSealedCapture = MakeShared<FCapture>(MoveTemp(Capture));
        ManualSealedCapturePath = FPaths::ConvertRelativePathToFull(Path);
        ManualSealedCaptureHash = BytesToHex(Hash, UE_ARRAY_COUNT(Hash));
    }
    if (!bReplayInputsMatch) { Error = TEXT("Chaos manual replay did not consume the sealed final inputs unchanged"); return false; }
    // Exact Chaos trajectory repeatability is diagnostic under the user's
    // functionality/performance acceptance. Input integrity remains required.
    if (bReplay && !FParse::Param(FCommandLine::Get(), TEXT("PhysicsBenchManualChaosOnly")) &&
        !ReplayManualCaptureInJolt(CaseResult, Error)) return false;
    return true;
}
