#include "ProphecyPhysicsBenchmark.h"

#include "ProphecyAgent.h"
#include "ProphecyJoltCharacterWorldSubsystem.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyManualServoCapture.h"
#include "ProphecyPhysicsBenchmarkRigAudit.h"
#include "Chaos/ChaosEngineInterface.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "Physics/PhysicsInterfaceCore.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/ConstraintInstance.h"
#include "PhysicsEngine/SkeletalBodySetup.h"

namespace ProphecySterileBench::LiveJolt
{
bool CountChaosDynamicBodies(UWorld& World, int32& OutCount, FString& Error);
}

struct FProphecyManualCrowdState
{
    struct FAgent
    {
        TArray<const void*> NativeBodies;
        TArray<const void*> NativeJoints;
        TArray<FConstraintProfileProperties> Profiles;
        TArray<FProphecyBodyMagnetizationSettings> BodySettings;
    };
    TArray<FAgent> Agents;
    TArray<TSharedPtr<FJsonValue>> Frames;
};

namespace ProphecySterileBench::ManualCrowd
{
constexpr int32 BodiesPerAgent = 22, JointsPerAgent = 21, BonesPerAgent = 88;

bool VerifyNoJoltOwnership(UWorld& World, FString& Error)
{
    if (const auto* Coordinator = World.GetSubsystem<UProphecyJoltCharacterWorldSubsystem>())
        if (Coordinator->GetRegisteredCharacterCount() || Coordinator->HasAutomaticStepOwners())
        { Error = TEXT("ManualCrowd found registered Jolt characters."); return false; }
    if (const auto* Owner = World.GetSubsystem<UProphecyJoltWorldSubsystem>())
    {
        FProphecyJoltWorldDiagnostics Diagnostics;
        const auto Status = Owner->GetDiagnostics(Diagnostics);
        if (!Status.IsSuccess() || Diagnostics.bInitialized || Diagnostics.BodyCount || Diagnostics.ConstraintCount)
        { Error = TEXT("ManualCrowd requires an uninitialized Jolt owner with no native bodies or joints."); return false; }
    }
    return true;
}

bool VerifyUnrecordedCallback(AProphecyAgent& Agent, FString& Error)
{
    ProphecyManualServoCapture::FCapture Unused;
    FString ReadError;
    // ReadCapture never creates a callback/buffer. This exact negative response also distinguishes
    // a real, unrecorded callback from a missing/released callback at the measurement boundaries.
    if (ProphecyManualServoCapture::ReadCapture(&Agent, Unused, ReadError)
        || ReadError != TEXT("This manual callback is not recording."))
    { Error = FString::Printf(TEXT("ManualCrowd requires an existing unrecorded callback: %s"), *ReadError); return false; }
    return true;
}

bool ValidateAgent(USkeletalMeshComponent& Mesh, USkeletalMesh& Asset, int32 AgentIndex,
    FProphecyManualCrowdState::FAgent& State, bool bCaptureIdentity, FJsonObject& Row, FString& Error)
{
    auto* Agent = Cast<AProphecyAgent>(Mesh.GetOwner());
    if (!Agent || Agent->GetPoseReferenceMesh() != &Mesh || Agent->IsJoltPhysicalAnimationEnabled()
        || Agent->GetSimulationMode() != EProphecyAgentSimulationMode::Physical
        || !Agent->bManualNNPoseApplication || !Agent->bAutoPublishManualFollowerSubstepTargets
        || Agent->bAutoEnsureStandaloneNNManager || Mesh.GetSkeletalMeshAsset() != &Asset
        || Mesh.Bodies.Num() != BodiesPerAgent || Mesh.Constraints.Num() != JointsPerAgent
        || Asset.GetRefSkeleton().GetNum() != BonesPerAgent || !Mesh.IsPhysicsStateCreated()
        || Mesh.GetCollisionEnabled() != ECollisionEnabled::QueryAndPhysics)
    { Error = TEXT("Manual agent/controller, retained PhysicalMesh or 22/21/88 rig contract changed."); return false; }
    int32 PoseId = INDEX_NONE;
    float Interval = 0.0f;
    bool bInterpolate = false;
    if (!Agent->GetNNPoseDataSource(PoseId, Interval, bInterpolate) || PoseId != 991000 + AgentIndex
        || !FMath::IsNearlyEqual(Interval, 1.0f / 30.0f) || !bInterpolate)
    { Error = TEXT("ManualCrowd lost its shared 30 Hz fixture pose source."); return false; }
    if (bCaptureIdentity && !VerifyUnrecordedCallback(*Agent, Error)) return false;

    int32 Dynamic = 0, Awake = 0;
    double MaxLinear = 0.0, MaxAngular = 0.0;
    for (int32 BodyIndex = 0; BodyIndex < Mesh.Bodies.Num(); ++BodyIndex)
    {
        FBodyInstance* Body = Mesh.Bodies[BodyIndex];
        if (!Body || !Body->IsValidBodyInstance() || !Body->BodySetup.IsValid() || !Body->IsInstanceSimulatingPhysics())
        { Error = TEXT("A manual body lost its native simulation state."); return false; }
        const auto Native = Body->GetPhysicsActor();
        if (bCaptureIdentity) State.NativeBodies.Add(Native);
        else if (!State.NativeBodies.IsValidIndex(BodyIndex) || State.NativeBodies[BodyIndex] != Native)
        { Error = TEXT("A native manual body was replaced during the measured case."); return false; }
        bool bValid = false;
        const bool bRead = FPhysicsCommand::ExecuteRead(Native, [&](const FPhysicsActorHandle& Locked)
        {
            const FTransform Pose = Body->GetUnrealWorldTransform_AssumesLocked(false, true);
            const FVector V = FPhysicsInterface::GetLinearVelocity_AssumesLocked(Locked);
            const FVector W = FPhysicsInterface::GetAngularVelocity_AssumesLocked(Locked);
            bValid = FPhysicsInterface::IsDynamic(Locked) && !FPhysicsInterface::IsKinematic_AssumesLocked(Locked)
                && !Pose.ContainsNaN() && Pose.GetRotation().IsNormalized() && !V.ContainsNaN() && !W.ContainsNaN();
            if (bValid)
            {
                ++Dynamic;
                Awake += !FPhysicsInterface::IsSleeping(Locked);
                MaxLinear = FMath::Max(MaxLinear, V.Size());
                MaxAngular = FMath::Max(MaxAngular, W.Size());
            }
        });
        if (!bRead || !bValid) { Error = TEXT("A native manual body is non-dynamic, unreadable or nonfinite."); return false; }
        FProphecyBodyMagnetizationSettings Settings;
        Agent->GetBodyMagnetizationSettings(Body->BodySetup->BoneName, Settings);
        if (bCaptureIdentity) State.BodySettings.Add(Settings);
        else if (!FProphecyBodyMagnetizationSettings::StaticStruct()->CompareScriptStruct(
            &Settings, &State.BodySettings[BodyIndex], PPF_None))
        { Error = TEXT("Effective body controller settings changed during the measured case."); return false; }
    }
    for (int32 JointIndex = 0; JointIndex < Mesh.Constraints.Num(); ++JointIndex)
    {
        FConstraintInstance* Joint = Mesh.Constraints[JointIndex];
        if (!Joint || !Joint->IsValidConstraintInstance() || Joint->IsBroken())
        { Error = TEXT("A manual anatomical constraint is invalid or broken."); return false; }
        const void* Native = Joint->GetPhysicsConstraintRef().Constraint;
        if (bCaptureIdentity)
        {
            State.NativeJoints.Add(Native);
            State.Profiles.Add(Joint->ProfileInstance);
        }
        else if (State.NativeJoints[JointIndex] != Native
            || !FConstraintProfileProperties::StaticStruct()->CompareScriptStruct(
                &Joint->ProfileInstance, &State.Profiles[JointIndex], PPF_None))
        { Error = TEXT("A manual joint identity or its authored effective profile changed during measurement."); return false; }
    }
    TArray<FName> Names;
    TArray<FTransform> Feedback;
    for (int32 Bone = 0; Bone < BonesPerAgent; ++Bone) Names.Add(Asset.GetRefSkeleton().GetBoneName(Bone));
    Feedback.SetNum(BonesPerAgent);
    if (!Agent->SampleActualComponentPose(Names, Feedback))
    { Error = TEXT("Manual NN feedback failed to read the complete 88-bone pose."); return false; }
    const USceneComponent* Reference = Agent->GetAgentMesh() && Agent->GetAgentMesh()->IsRegistered()
        ? Agent->GetAgentMesh() : &Mesh;
    const FTransform ReferenceWorld = Reference->GetComponentTransform();
    double MaxPosition = 0.0, MaxAngle = 0.0;
    for (int32 Bone = 0; Bone < BonesPerAgent; ++Bone)
    {
        const FTransform Socket = Mesh.GetSocketTransform(Names[Bone], RTS_World).GetRelativeTransform(ReferenceWorld);
        if (Socket.ContainsNaN() || Feedback[Bone].ContainsNaN() || !Socket.GetRotation().IsNormalized()
            || !Feedback[Bone].GetRotation().IsNormalized())
        { Error = TEXT("Manual render/feedback pose contains an invalid bone transform."); return false; }
        MaxPosition = FMath::Max(MaxPosition, FVector::Distance(Socket.GetLocation(), Feedback[Bone].GetLocation()));
        MaxAngle = FMath::Max(MaxAngle, FMath::RadiansToDegrees(Socket.GetRotation().GetNormalized()
            .AngularDistance(Feedback[Bone].GetRotation().GetNormalized())));
    }
    if (MaxPosition > 0.02 || MaxAngle > 0.02)
    { Error = TEXT("Manual feedback and retained mesh sockets disagree beyond 0.02 cm/degrees."); return false; }
    Row.SetNumberField(TEXT("agent_index"), AgentIndex);
    Row.SetNumberField(TEXT("native_dynamic_bodies"), Dynamic);
    Row.SetNumberField(TEXT("awake_bodies"), Awake);
    Row.SetNumberField(TEXT("valid_native_joints"), Mesh.Constraints.Num());
    Row.SetNumberField(TEXT("validated_skeleton_bones"), BonesPerAgent);
    Row.SetNumberField(TEXT("max_linear_speed_cm_s"), MaxLinear);
    Row.SetNumberField(TEXT("max_angular_speed_rad_s"), MaxAngular);
    Row.SetNumberField(TEXT("max_feedback_render_position_cm"), MaxPosition);
    Row.SetNumberField(TEXT("max_feedback_render_angle_degrees"), MaxAngle);
    Row.SetBoolField(TEXT("success"), true);
    return true;
}
}

bool UProphecyPhysicsBenchmarkSubsystem::InitializeManualCrowdCase(FString& Error)
{
    namespace Manual = ProphecySterileBench::ManualCrowd;
    Error.Reset();
    if (!Before || !GetWorld() || !MeshAsset || Count < 1 || Count > 100 || Meshes.Num() != Count)
    { Error = TEXT("ManualCrowd requires 1..100 completely prepared native manual agents."); return false; }
    if (!Manual::VerifyNoJoltOwnership(*GetWorld(), Error)) return false;
    auto Pending = MakeShared<FProphecyManualCrowdState>();
    Pending->Agents.SetNum(Count);
    TArray<TSharedPtr<FJsonValue>> AgentsJson;
    TSet<const void*> BodyIdentities, JointIdentities;
    for (int32 Index = 0; Index < Count; ++Index)
    {
        auto Row = MakeShared<FJsonObject>();
        if (!IsValid(Meshes[Index]) || !Manual::ValidateAgent(*Meshes[Index], *MeshAsset, Index,
            Pending->Agents[Index], true, *Row, Error)) return false;
        for (const void* Body : Pending->Agents[Index].NativeBodies)
        {
            if (BodyIdentities.Contains(Body)) { Error = TEXT("Duplicate native body across manual agents."); return false; }
            BodyIdentities.Add(Body);
        }
        for (const void* Joint : Pending->Agents[Index].NativeJoints)
        {
            if (JointIdentities.Contains(Joint)) { Error = TEXT("Duplicate native joint across manual agents."); return false; }
            JointIdentities.Add(Joint);
        }
        AgentsJson.Add(MakeShared<FJsonValueObject>(Row));
    }
    int32 ChaosDynamic = 0;
    if (!ProphecySterileBench::LiveJolt::CountChaosDynamicBodies(*GetWorld(), ChaosDynamic, Error)) return false;
    if (ChaosDynamic != Count * Manual::BodiesPerAgent)
    { Error = TEXT("ManualCrowd world contains an unexpected number of native Chaos dynamic bodies."); return false; }
    auto Provenance = MakeShared<FJsonObject>();
    Provenance->SetArrayField(TEXT("agents"), AgentsJson);
    Provenance->SetNumberField(TEXT("native_chaos_dynamic_bodies"), ChaosDynamic);
    Provenance->SetNumberField(TEXT("native_anatomical_joints"), JointIdentities.Num());
    Provenance->SetNumberField(TEXT("placement_grid_spacing_cm"), 600.0);
    Provenance->SetNumberField(TEXT("authored_pose_hz"), 30.0);
    Provenance->SetNumberField(TEXT("world_tick_hz"), 60.0);
    Provenance->SetBoolField(TEXT("capture_recording_enabled"), false);
    Provenance->SetStringField(TEXT("scope"), TEXT("Existing PrepareManualAgent and PublishManualPose shared with JoltCrowd. Native Chaos SetV/SetW callback with unchanged effective PHAT limits, strengths and solver settings; stationary warmup, then native 30 Hz source. No NN inference, handoff, recording, replay or trajectory-equivalence gate."));
    Before->SetObjectField(TEXT("manual_crowd"), Provenance);
    ManualCrowdState = MoveTemp(Pending);
    return true;
}

bool UProphecyPhysicsBenchmarkSubsystem::ValidateManualCrowdFrame(FString& Error)
{
    namespace Manual = ProphecySterileBench::ManualCrowd;
    auto Row = MakeShared<FJsonObject>();
    Row->SetNumberField(TEXT("sample_frame"), Frame - Warmup);
    auto Fail = [&](const FString& Message)
    {
        Error = FString::Printf(TEXT("ManualCrowd frame %d: %s"), Frame - Warmup, *Message);
        Row->SetBoolField(TEXT("success"), false);
        Row->SetStringField(TEXT("error"), Error);
        if (Before) Before->SetObjectField(TEXT("manual_crowd_failed_frame"), Row);
        return false;
    };
    if (!ManualCrowdState || ManualCrowdState->Agents.Num() != Count || Meshes.Num() != Count || !GetWorld())
        return Fail(TEXT("Manual crowd state or retained meshes are missing."));
    FString ReadError;
    if (!Manual::VerifyNoJoltOwnership(*GetWorld(), ReadError)) return Fail(ReadError);
    int32 ChaosDynamic = 0, Awake = 0;
    if (!ProphecySterileBench::LiveJolt::CountChaosDynamicBodies(*GetWorld(), ChaosDynamic, ReadError)) return Fail(ReadError);
    if (ChaosDynamic != Count * Manual::BodiesPerAgent) return Fail(TEXT("Native Chaos dynamic count changed."));
    TArray<TSharedPtr<FJsonValue>> AgentsJson;
    for (int32 Index = 0; Index < Count; ++Index)
    {
        auto AgentRow = MakeShared<FJsonObject>();
        if (!IsValid(Meshes[Index]) || !Manual::ValidateAgent(*Meshes[Index], *MeshAsset, Index,
            ManualCrowdState->Agents[Index], false, *AgentRow, ReadError))
            return Fail(FString::Printf(TEXT("Agent %d: %s"), Index, *ReadError));
        Awake += int32(AgentRow->GetNumberField(TEXT("awake_bodies")));
        AgentsJson.Add(MakeShared<FJsonValueObject>(AgentRow));
    }
    Row->SetArrayField(TEXT("agents"), AgentsJson);
    Row->SetNumberField(TEXT("native_chaos_dynamic_bodies"), ChaosDynamic);
    Row->SetNumberField(TEXT("valid_native_joints"), Count * Manual::JointsPerAgent);
    Row->SetNumberField(TEXT("awake_bodies"), Awake);
    Row->SetBoolField(TEXT("all_dynamic_bodies_awake"), Awake == ChaosDynamic);
    Row->SetBoolField(TEXT("success"), true);
    ManualCrowdState->Frames.Add(MakeShared<FJsonValueObject>(Row));
    return true;
}

bool UProphecyPhysicsBenchmarkSubsystem::SaveManualCrowdCase(TSharedPtr<FJsonObject> CaseResult, FString& Error)
{
    namespace Manual = ProphecySterileBench::ManualCrowd;
    if (!CaseResult || !ManualCrowdState || ManualCrowdState->Frames.Num() != Samples || Meshes.Num() != Count)
    { Error = TEXT("ManualCrowd did not validate every requested sample."); return false; }
    auto Summary = MakeShared<FJsonObject>();
    CaseResult->SetObjectField(TEXT("manual_crowd_validation"), Summary);
    CaseResult->SetArrayField(TEXT("manual_crowd_frames"), ManualCrowdState->Frames);
    Summary->SetBoolField(TEXT("success"), false);
    int32 MinimumAwake = Count * Manual::BodiesPerAgent;
    for (const auto& Value : ManualCrowdState->Frames)
        MinimumAwake = FMath::Min(MinimumAwake, int32(Value->AsObject()->GetNumberField(TEXT("awake_bodies"))));
    Summary->SetNumberField(TEXT("characters"), Count);
    Summary->SetNumberField(TEXT("validated_frames"), ManualCrowdState->Frames.Num());
    Summary->SetNumberField(TEXT("native_bodies"), Count * Manual::BodiesPerAgent);
    Summary->SetNumberField(TEXT("native_joints"), Count * Manual::JointsPerAgent);
    Summary->SetNumberField(TEXT("minimum_awake_bodies"), MinimumAwake);
    Summary->SetBoolField(TEXT("all_bodies_awake_every_frame"), MinimumAwake == Count * Manual::BodiesPerAgent);
    Summary->SetBoolField(TEXT("recording_enabled"), false);
    Summary->SetStringField(TEXT("sleep_scope"), TEXT("No extra wakes or sleeping-setting changes. Awake bodies are measured explicitly; sleeping source bodies preclude claiming an identical fully-active solver workload."));
    CaseResult->SetStringField(TEXT("timing_scope"), TEXT("Same WorldMs boundary as JoltCrowd: native 30 Hz pose generation/publication inside the 60 Hz actor/physics tick, production manual callback and ordinary skeletal work. Initialization and all-body/all-bone validation are outside WorldMs; frame intervals include validation overhead. No capture recorder or NN inference. NullRHI is not rendered FPS; this is wall latency, not total CPU summed over worker threads."));
    CaseResult->SetStringField(TEXT("pose_error_scope"), TEXT("Generic Audit target errors are diagnostic only: its instantaneous endpoint is not the manual interpolated BodyFromBone target. This mode validates finite dynamic state, stable body/joint ownership and full feedback/socket consistency; no Chaos-Jolt trajectory equivalence gate."));
    Summary->SetStringField(TEXT("contact_scope"), TEXT("Same explicit WorldStatic-only fixture filter as JoltCrowd; no inter-character or self contacts. Actual Chaos angular profiles remain unchanged; JoltCrowd uses the authorized hard limits at their original angles."));
    for (USkeletalMeshComponent* Mesh : Meshes)
    {
        auto* Agent = Cast<AProphecyAgent>(Mesh->GetOwner());
        if (!Agent || !Manual::VerifyUnrecordedCallback(*Agent, Error)) return false;
        if (!Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic) || Mesh->IsAnySimulatingPhysics())
        { Error = TEXT("ManualCrowd failed its public transition back to Kinematic."); return false; }
    }
    int32 Remaining = 0;
    if (!ProphecySterileBench::LiveJolt::CountChaosDynamicBodies(*GetWorld(), Remaining, Error)) return false;
    if (Remaining != 0 || !Manual::VerifyNoJoltOwnership(*GetWorld(), Error))
    { if (Error.IsEmpty()) Error = TEXT("ManualCrowd teardown left a native dynamic body."); return false; }
    Summary->SetNumberField(TEXT("chaos_dynamic_after_kinematic_teardown"), Remaining);
    Summary->SetBoolField(TEXT("success"), true);
    return true;
}
