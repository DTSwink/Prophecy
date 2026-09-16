#include "ProphecyPhysicsBenchmark.h"

#include "ProphecyAgent.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltBloodFixture.h"
#include "ProphecyJoltISMBloodFixture.h"
#include "ProphecyJoltPoseAnimInstance.h"
#include "ProphecyJoltRig.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyPhysicsBenchmarkRigAudit.h"
#include "Chaos/ChaosEngineInterface.h"
#include "Components/BoxComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "Physics/PhysicsInterfaceCore.h"
#include "PhysicsEngine/BodyInstance.h"
#include "Misc/CommandLine.h"

namespace ProphecySterileBench::LiveJolt
{
constexpr int32 ExpectedBodies = 22;
constexpr int32 ExpectedJoints = 21;
constexpr int32 ExpectedBones = 88;
constexpr double PositionToleranceCm = 0.02;
constexpr double AngleToleranceDegrees = 0.02;
constexpr double ScaleTolerance = 1.0e-4;

bool CountChaosDynamicBodies(UWorld& World, int32& OutCount, FString& Error)
{
    OutCount = 0;
    // Read native actor state, not only bSimulatePhysics. In UE's interface IsDynamic also includes
    // kinematic actors, so both predicates are necessary. Query proxies may remain kinematic.
    TSet<const FBodyInstance*> Visited;
    auto ReadBody = [&](const FBodyInstance* Body)
    {
        if (!Body || Visited.Contains(Body) || !Body->IsValidBodyInstance()) return true;
        Visited.Add(Body);
        const bool bRead = FPhysicsCommand::ExecuteRead(Body->GetPhysicsActor(), [&](const FPhysicsActorHandle& Actor)
        {
            if (FPhysicsInterface::IsDynamic(Actor) && !FPhysicsInterface::IsKinematic_AssumesLocked(Actor)) ++OutCount;
        });
        if (!bRead) Error = TEXT("Live Jolt audit could not read a valid Chaos body actor.");
        return bRead;
    };
    for (TActorIterator<AActor> It(&World); It; ++It)
    {
        TInlineComponentArray<UPrimitiveComponent*> Components(*It);
        for (UPrimitiveComponent* Component : Components)
        {
            if (!Component || !Component->IsRegistered()) continue;
            if (const auto* Skeletal = Cast<USkeletalMeshComponent>(Component))
            {
                for (const FBodyInstance* Body : Skeletal->Bodies) if (!ReadBody(Body)) return false;
            }
            else if (!ReadBody(Component->GetBodyInstance())) return false;
        }
    }
    return true;
}

bool ValidateMassWeightedPoseError(AProphecyAgent& Agent, UProphecyJoltCharacterComponent& Character,
    UProphecyJoltWorldSubsystem& Owner, const FProphecyJoltRigSnapshot& Capture, FJsonObject& Report, FString& Error)
{
    namespace Json = ProphecySterileBench::RigAudit;
    TArray<FName> PoseBoneNames;
    TArray<FTransform> Future, Presented;
    float Alpha = 0.0f;
    if (!Agent.ReadNNFutureWorldPose(PoseBoneNames, Future, Presented, Alpha) || PoseBoneNames.Num() != Presented.Num())
    { Error = TEXT("Pose-error control could not read the existing presented target pose."); return false; }
    FVector ExpectedLinear = FVector::ZeroVector, ExpectedAngular = FVector::ZeroVector;
    float ExpectedMass = 0.0f;
    TSet<int32> SeenSlots;
    for (const FProphecyJoltRigBody& Source : Capture.Bodies)
    {
        const int32 TargetIndex = PoseBoneNames.IndexOfByKey(Source.BodyName);
        FProphecyJoltBodyHandle Handle;
        FProphecyJoltBodyState Native;
        if (!Presented.IsValidIndex(TargetIndex) || !Character.GetBodyHandle(Source.BodyName, Handle)
            || !Owner.ReadBody(Handle, Native).IsSuccess() || !Native.bDynamic || SeenSlots.Contains(Handle.Slot))
        { Error = TEXT("Pose-error control requires each original dynamic body exactly once with its original target."); return false; }
        SeenSlots.Add(Handle.Slot);
        const FTransform& Target = Presented[TargetIndex];
        ExpectedLinear += Source.MassKg * (Native.PositionCm - Target.GetLocation());
        FQuat Delta = (Native.Rotation * Target.GetRotation().Inverse()).GetNormalized();
        if (Delta.W < 0.0) Delta = Delta * -1.0;
        // UE's ToAxisAndAngle chooses an arbitrary axis for tiny rotations. Use the
        // imaginary direction and asin here so the control also resolves sub-milliradian errors.
        const FVector Imaginary(Delta.X, Delta.Y, Delta.Z);
        const double SinHalfAngle = Imaginary.Size();
        if (SinHalfAngle > 0.0)
            ExpectedAngular += Source.MassKg * (Imaginary / SinHalfAngle)
                * (2.0 * FMath::Asin(FMath::Min(1.0, SinHalfAngle)));
        ExpectedMass += float(Source.MassKg);
    }
    FVector ActualLinear, ActualAngular;
    float ActualMass = 0.0f;
    int32 ActualCount = 0;
    const bool bReported = Agent.GetMassWeightedPoseError(ActualLinear, ActualAngular, ActualMass, ActualCount);
    const double LinearDifference = FVector::Distance(ActualLinear, ExpectedLinear);
    const double AngularDifference = FVector::Distance(ActualAngular, ExpectedAngular);
    Report.SetBoolField(TEXT("api_succeeded"), bReported);
    Report.SetNumberField(TEXT("body_count"), ActualCount);
    Report.SetNumberField(TEXT("expected_unique_bodies"), SeenSlots.Num());
    Report.SetNumberField(TEXT("mass_kg"), ActualMass);
    Report.SetNumberField(TEXT("captured_mass_kg"), ExpectedMass);
    Report.SetArrayField(TEXT("linear_error_kg_cm"), Json::Vector(ActualLinear));
    Report.SetArrayField(TEXT("expected_linear_error_kg_cm"), Json::Vector(ExpectedLinear));
    Report.SetArrayField(TEXT("angular_error_kg_radians"), Json::Vector(ActualAngular));
    Report.SetArrayField(TEXT("expected_angular_error_kg_radians"), Json::Vector(ExpectedAngular));
    Report.SetNumberField(TEXT("linear_difference_kg_cm"), LinearDifference);
    Report.SetNumberField(TEXT("angular_difference_kg_radians"), AngularDifference);
    Report.SetNumberField(TEXT("target_interpolation_alpha"), Alpha);
    Report.SetStringField(TEXT("scope"), TEXT("Actual API versus separate pre-handoff captured masses and direct native body-origin readback; existing Presented targets, shortest world angular error, unique native body slots."));
    const bool bValid = bReported && ActualCount == ExpectedBodies && ActualCount == SeenSlots.Num()
        && FMath::IsNearlyEqual(ActualMass, ExpectedMass, 1.0e-5f)
        && FMath::IsFinite(LinearDifference) && LinearDifference <= 1.0e-5
        && FMath::IsFinite(AngularDifference) && AngularDifference <= 1.0e-5;
    Report.SetBoolField(TEXT("success"), bValid);
    if (!bValid) Error = TEXT("GetMassWeightedPoseError disagreed with captured-mass native body-origin aggregation.");
    return bValid;
}

TSharedPtr<FJsonObject> DiagnosticsJson(const FProphecyJoltWorldDiagnostics& D)
{
    auto Row = MakeShared<FJsonObject>();
    Row->SetBoolField(TEXT("initialized"), D.bInitialized);
    Row->SetBoolField(TEXT("faulted"), D.bFaulted);
    Row->SetBoolField(TEXT("no_lock_idle_body_reads"), D.bNoLockIdleBodyReads);
    Row->SetStringField(TEXT("world_lifetime"), D.WorldLifetime.ToString());
    Row->SetNumberField(TEXT("completed_steps"), static_cast<double>(D.CompletedSteps));
    Row->SetNumberField(TEXT("bodies"), D.BodyCount);
    Row->SetNumberField(TEXT("active_bodies"), D.ActiveRigidBodyCount);
    Row->SetNumberField(TEXT("constraints"), D.ConstraintCount);
    Row->SetNumberField(TEXT("worker_threads"), D.Settings.WorkerThreads);
    Row->SetNumberField(TEXT("job_concurrency"), D.JobConcurrency);
    Row->SetNumberField(TEXT("last_step_ms"), D.LastStepWallSeconds * 1000.0);
    auto Parts = MakeShared<FJsonObject>();
    Parts->SetNumberField(TEXT("servo_packet_prepare"), D.LastServoPrepareWallSeconds * 1000.0);
    Parts->SetNumberField(TEXT("servo_activation"), D.LastActivationWallSeconds * 1000.0);
    Parts->SetNumberField(TEXT("physics_update_including_servo"), D.LastPhysicsUpdateWallSeconds * 1000.0);
    Parts->SetNumberField(TEXT("servo_sample_capture"), D.LastServoCaptureWallSeconds * 1000.0);
    Parts->SetNumberField(TEXT("post_update_validation"), D.LastValidationWallSeconds * 1000.0);
    Row->SetObjectField(TEXT("step_parts_ms"), Parts);
    Row->SetNumberField(TEXT("last_step_seconds"), D.LastRequestedDeltaSeconds);
    Row->SetNumberField(TEXT("last_collision_steps"), D.LastCollisionSteps);
    Row->SetNumberField(TEXT("update_error_bits"), D.LastUpdateErrorBits);
    Row->SetNumberField(TEXT("temporary_peak_bytes"), static_cast<double>(D.TempPeakBytes));
    return Row;
}
}

bool UProphecyPhysicsBenchmarkSubsystem::InitializeLiveJoltCase(FString& Error)
{
    namespace Live = ProphecySterileBench::LiveJolt;
    namespace Json = ProphecySterileBench::RigAudit;
    Error.Reset();
    if (!Before || !Cases.IsValidIndex(CaseIndex) || Meshes.Num() != 1 || !IsValid(Meshes[0]))
    { Error = TEXT("Live Jolt initialization requires one prepared manual mesh and its pre-handoff audit."); return false; }
    USkeletalMeshComponent* Physical = Meshes[0];
    AProphecyAgent* Agent = Cast<AProphecyAgent>(Physical->GetOwner());
    UProphecyJoltWorldSubsystem* Owner = GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    if (!Agent || !Owner || Agent->GetPoseReferenceMesh() != Physical || !Physical->GetSkeletalMeshAsset()
        || Physical->GetSkeletalMeshAsset()->GetRefSkeleton().GetNum() != Live::ExpectedBones)
    { Error = TEXT("Live Jolt requires the existing manual PhysicalMesh, all 88 bones and a game-world owner."); return false; }

    ManualInitialRig = MakeShared<FProphecyJoltRigSnapshot>();
    if (!ProphecyJolt::Rig::CaptureLiveRig(*Physical, *ManualInitialRig, Error)) return false;
    if (ManualInitialRig->Bodies.Num() != Live::ExpectedBodies || ManualInitialRig->Joints.Num() != Live::ExpectedJoints)
    { Error = TEXT("Live Jolt source rig must contain 22 bodies and 21 joints."); return false; }
    int32 ChaosBefore = 0;
    if (!Live::CountChaosDynamicBodies(*GetWorld(), ChaosBefore, Error)) return false;
    if (ChaosBefore != Live::ExpectedBodies)
    { Error = FString::Printf(TEXT("Live Jolt handoff expected 22 native Chaos dynamic bodies, found %d."), ChaosBefore); return false; }

    auto Provenance = MakeShared<FJsonObject>();
    Before->SetObjectField(TEXT("live_jolt_handoff"), Provenance);
    Provenance->SetStringField(TEXT("scope"), TEXT("One live manual agent, native 30 Hz authored pose source, automatic Jolt stepping and completed physical skeletal pose. Functional consistency; no Chaos trajectory equivalence requirement."));
    Provenance->SetStringField(TEXT("source_capture_id"), ManualInitialRig->CaptureId.ToString());
    Provenance->SetStringField(TEXT("source_capture_scope"), TEXT("Read-only snapshot immediately before binding; the character captures its own equivalent initialization snapshot without advancing physics."));
    Provenance->SetStringField(TEXT("physical_component"), Physical->GetPathName());
    Provenance->SetStringField(TEXT("skeletal_mesh"), Physical->GetSkeletalMeshAsset()->GetPathName());
    Provenance->SetStringField(TEXT("physics_asset"), GetPathNameSafe(Physical->GetPhysicsAsset()));
    Provenance->SetNumberField(TEXT("source_chaos_dynamic_bodies"), ChaosBefore);
    Provenance->SetNumberField(TEXT("source_bodies"), ManualInitialRig->Bodies.Num());
    Provenance->SetNumberField(TEXT("source_joints"), ManualInitialRig->Joints.Num());
    Provenance->SetNumberField(TEXT("source_disabled_pairs"), ManualInitialRig->DisabledPairs.Num());
    Provenance->SetStringField(TEXT("angular_policy"), TEXT("User-approved hard PHAT angular limits with original angle values; soft flags are provenance, not equivalent response."));
    Provenance->SetStringField(TEXT("jolt_commit"), TEXT("e77f175595e64cb44218cc9d9d56fc365ad0e36a"));
    TArray<TSharedPtr<FJsonValue>> Notes;
    for (const FString& Note : ManualInitialRig->CoverageNotes) Notes.Add(MakeShared<FJsonValueString>(Note));
    Provenance->SetArrayField(TEXT("capture_coverage_notes"), Notes);

    auto Check = [&Error](const FProphecyJoltWorldStatus& Status)
    {
        if (!Status.IsSuccess()) Error = Status.Message;
        return Status.IsSuccess();
    };
    FProphecyJoltWorldSettings Settings;
    Settings.GravityCmPerSecondSquared = Cases[CaseIndex].Floor ? FVector(0, 0, GetWorld()->GetGravityZ()) : FVector::ZeroVector;
    if (!Check(Owner->InitializeSimulation(Settings))) return false;
    Provenance->SetArrayField(TEXT("gravity_cm_s2"), Json::Vector(Settings.GravityCmPerSecondSquared));
    if (Cases[CaseIndex].Floor)
    {
        UBoxComponent* SourceFloor = nullptr;
        for (AActor* Actor : Actors)
        {
            if (!IsValid(Actor)) continue;
            TInlineComponentArray<UBoxComponent*> Boxes(Actor);
            for (UBoxComponent* Box : Boxes)
            {
                if (SourceFloor) { Error = TEXT("Live Jolt fixture has more than one box floor candidate."); return false; }
                SourceFloor = Box;
            }
        }
        if (!SourceFloor || !SourceFloor->IsRegistered() || SourceFloor->IsSimulatingPhysics()
            || SourceFloor->GetCollisionObjectType() != ECC_WorldStatic)
        { Error = TEXT("Live Jolt floor must be the registered static UBoxComponent from this case."); return false; }
        const FTransform FloorWorld = SourceFloor->GetComponentTransform();
        const FVector Scale = FloorWorld.GetScale3D();
        if (FloorWorld.ContainsNaN() || !FloorWorld.GetRotation().IsNormalized() || Scale.GetMin() <= 0.0)
        { Error = TEXT("Live Jolt floor has an invalid transform or nonpositive scale."); return false; }
        const UPhysicalMaterial* Material = SourceFloor->BodyInstance.GetSimplePhysicalMaterial();
        if (!Material) { Error = TEXT("Live Jolt floor has no simple physical material."); return false; }
        FProphecyJoltFixtureBodySettings Floor;
        Floor.bDynamic = false;
        Floor.PositionCm = FloorWorld.GetLocation();
        Floor.Rotation = FloorWorld.GetRotation();
        Floor.Friction = Material->Friction;
        Floor.Restitution = Material->Restitution;
        const FVector HalfExtent = SourceFloor->GetScaledBoxExtent();
        FProphecyJoltBodyHandle Handle;
        if (!Check(Owner->CreateBox(HalfExtent, 0.0, Floor, Handle))) return false;
        auto FloorJson = MakeShared<FJsonObject>();
        FloorJson->SetStringField(TEXT("source_component"), SourceFloor->GetPathName());
        FloorJson->SetObjectField(TEXT("source_world_transform"), Json::Transform(FloorWorld));
        FloorJson->SetArrayField(TEXT("baked_half_extent_cm"), Json::Vector(HalfExtent));
        FloorJson->SetNumberField(TEXT("convex_radius_cm"), 0.0);
        FloorJson->SetStringField(TEXT("physical_material"), Material->GetPathName());
        FloorJson->SetNumberField(TEXT("friction"), Floor.Friction);
        FloorJson->SetNumberField(TEXT("restitution"), Floor.Restitution);
        FloorJson->SetStringField(TEXT("contact_scope"), TEXT("Geometry, pose and scalar material values mirrored; Jolt uses its own contact solver and material combine policy."));
        Provenance->SetObjectField(TEXT("floor"), FloorJson);
    }
    else Provenance->SetField(TEXT("floor"), MakeShared<FJsonValueNull>());

    if (!Agent->EnableJoltPhysicalAnimation())
    {
        UProphecyJoltCharacterComponent* Character = Agent->GetJoltCharacterComponent();
        Error = Character ? Character->GetLastError() : TEXT("Agent could not create its Jolt character component.");
        if (Error.IsEmpty()) Error = TEXT("Agent refused live Jolt Physical mode.");
        return false;
    }
    UProphecyJoltCharacterComponent* Character = Agent->GetJoltCharacterComponent();
    if (!Character || !Character->IsJoltPhysical() || !Character->bAutomaticStep || !Character->IsRegistered() || Character->IsComponentTickEnabled()
        || Character->GetRevision() == 0 || Agent->GetPoseReferenceMesh() != Physical)
    { Error = TEXT("Live Jolt handoff did not retain PhysicalMesh and prime an automatically stepped completed pose."); return false; }
    LastLiveJoltRevision = Character->GetRevision();
    LiveJoltFrames.Reset();
    Provenance->SetNumberField(TEXT("initial_completed_revision"), static_cast<double>(LastLiveJoltRevision));
    FProphecyJoltWorldDiagnostics Diagnostics;
    if (!Check(Owner->GetDiagnostics(Diagnostics))) return false;
    Provenance->SetObjectField(TEXT("after_creation"), Live::DiagnosticsJson(Diagnostics));
    auto PoseError = MakeShared<FJsonObject>();
    Provenance->SetObjectField(TEXT("mass_weighted_pose_error"), PoseError);
    if (!Live::ValidateMassWeightedPoseError(*Agent, *Character, *Owner, *ManualInitialRig, *PoseError, Error)) return false;
    return true;
}

bool UProphecyPhysicsBenchmarkSubsystem::ValidateLiveJoltFrame(FString& Error)
{
    namespace Live = ProphecySterileBench::LiveJolt;
    namespace Json = ProphecySterileBench::RigAudit;
    Error.Reset();
    auto Row = MakeShared<FJsonObject>();
    Row->SetNumberField(TEXT("sample_frame"), Frame - Warmup);
    auto Fail = [&](const FString& Message)
    {
        Error = FString::Printf(TEXT("Live Jolt frame %d: %s"), Frame - Warmup, *Message);
        Row->SetBoolField(TEXT("success"), false);
        Row->SetStringField(TEXT("error"), Error);
        if (Before) Before->SetObjectField(TEXT("live_jolt_failed_frame"), Row);
        return false;
    };
    if (!ManualInitialRig || Meshes.Num() != 1 || !IsValid(Meshes[0])) return Fail(TEXT("The source rig or retained mesh is missing."));
    USkeletalMeshComponent* Physical = Meshes[0];
    AProphecyAgent* Agent = Cast<AProphecyAgent>(Physical->GetOwner());
    UProphecyJoltCharacterComponent* Character = Agent ? Agent->GetJoltCharacterComponent() : nullptr;
    UProphecyJoltWorldSubsystem* Owner = GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    if (!Agent || !Character || !Owner || !Agent->IsJoltPhysicalAnimationEnabled() || !Character->IsJoltPhysical()
        || Agent->GetSimulationMode() != EProphecyAgentSimulationMode::Physical || Agent->GetPoseReferenceMesh() != Physical)
        return Fail(TEXT("Agent/character/mesh no longer has authoritative Jolt Physical ownership."));
    if (!Character->GetLastError().IsEmpty()) return Fail(Character->GetLastError());
    const uint64 Revision = Character->GetRevision();
    const UProphecyJoltPoseAnimInstance* Anim = Cast<UProphecyJoltPoseAnimInstance>(Physical->GetAnimInstance());
    Row->SetNumberField(TEXT("completed_revision"), static_cast<double>(Revision));
    if (Revision <= LastLiveJoltRevision || !Anim || Anim->GetCompletedPoseRevision() != Revision
        || !Character->bAutomaticStep || !Character->IsRegistered() || Character->IsComponentTickEnabled())
        return Fail(TEXT("Automatic stepping did not advance the same completed revision consumed by the pose AnimInstance."));
    if (Physical->GetCollisionEnabled() != ECollisionEnabled::QueryOnly || Physical->IsAnySimulatingPhysics())
        return Fail(TEXT("PhysicalMesh must retain query identity with Chaos simulation disabled."));
    FProphecyJoltWorldDiagnostics Diagnostics;
    const FProphecyJoltWorldStatus Status = Owner->GetDiagnostics(Diagnostics);
    if (!Status.IsSuccess()) return Fail(Status.Message);
    Row->SetObjectField(TEXT("jolt"), Live::DiagnosticsJson(Diagnostics));
    const uint32 ExpectedTotal = Live::ExpectedBodies + (Cases[CaseIndex].Floor ? 1u : 0u);
    if (!Diagnostics.bInitialized || Diagnostics.bFaulted || Diagnostics.LastUpdateErrorBits
        || Diagnostics.BodyCount != ExpectedTotal || Diagnostics.ConstraintCount != Live::ExpectedJoints
        || Diagnostics.CompletedSteps != static_cast<uint64>(LiveJoltFrames.Num() + 1)
        || Diagnostics.LastCollisionSteps != 1 || !FMath::IsNearlyEqual(Diagnostics.LastRequestedDeltaSeconds, 1.0f / 60.0f))
        return Fail(TEXT("World diagnostics require 22 rig bodies, optional floor, 21 joints and exactly one fixed step per measured frame."));
    int32 ChaosDynamic = 0;
    FString ReadError;
    if (!Live::CountChaosDynamicBodies(*GetWorld(), ChaosDynamic, ReadError)) return Fail(ReadError);
    Row->SetNumberField(TEXT("chaos_dynamic_bodies"), ChaosDynamic);
    if (ChaosDynamic != 0) return Fail(TEXT("A native Chaos dynamic body remains in the live fixture world."));

    TSet<int32> Slots;
    double MaxLinearSpeed = 0.0, MaxAngularSpeed = 0.0;
    for (const FProphecyJoltRigBody& SourceBody : ManualInitialRig->Bodies)
    {
        FProphecyJoltBodyHandle Handle;
        FTransform BodyWorld;
        FVector Linear, Angular;
        bool bSimulating = false;
        if (!Character->GetBodyHandle(SourceBody.BodyName, Handle)
            || !Character->GetBodyState(SourceBody.BodyName, BodyWorld, Linear, Angular, bSimulating)
            || !bSimulating || !Handle.IsSet() || Handle.WorldLifetime != Diagnostics.WorldLifetime
            || Slots.Contains(Handle.Slot) || BodyWorld.ContainsNaN() || !BodyWorld.GetRotation().IsNormalized()
            || Linear.ContainsNaN() || Angular.ContainsNaN())
            return Fail(FString::Printf(TEXT("Invalid or duplicate completed Jolt body %s."), *SourceBody.BodyName.ToString()));
        Slots.Add(Handle.Slot);
        MaxLinearSpeed = FMath::Max(MaxLinearSpeed, Linear.Size());
        MaxAngularSpeed = FMath::Max(MaxAngularSpeed, Angular.Size());
        if (SourceBody.BodyName == TEXT("pelvis")) Row->SetObjectField(TEXT("completed_pelvis_body_world"), Json::Transform(BodyWorld));
    }
    Row->SetNumberField(TEXT("validated_dynamic_rig_bodies"), Slots.Num());
    Row->SetNumberField(TEXT("max_body_linear_speed_cm_s"), MaxLinearSpeed);
    Row->SetNumberField(TEXT("max_body_angular_speed_rad_s"), MaxAngularSpeed);
    auto PoseError = MakeShared<FJsonObject>();
    Row->SetObjectField(TEXT("mass_weighted_pose_error"), PoseError);
    if (!Live::ValidateMassWeightedPoseError(*Agent, *Character, *Owner, *ManualInitialRig, *PoseError, ReadError)) return Fail(ReadError);

    FProphecyJoltBodyHandle HeadHandle;
    FProphecyJoltBodyState Head;
    if (!Character->GetBodyHandle(TEXT("head"), HeadHandle) || !Owner->ReadBody(HeadHandle, Head).IsSuccess())
        return Fail(TEXT("The query bridge test could not read the completed head body."));
    FProphecyJoltRayHit NativeHit;
    bool bNativeHit = false;
    const auto Query = Owner->RayCast(Head.CenterOfMassPositionCm + FVector(100.0, 0.0, 0.0),
        Head.CenterOfMassPositionCm, NativeHit, bNativeHit);
    FHitResult ReceiverHit;
    if (!Query.IsSuccess() || !bNativeHit || !Character->MakeHitResult(NativeHit, ReceiverHit)
        || ReceiverHit.GetComponent() != Physical || ReceiverHit.GetActor() != Agent
        || ReceiverHit.BoneName.IsNone() || ReceiverHit.FaceIndex != INDEX_NONE
        || !ReceiverHit.ImpactPoint.Equals(NativeHit.PositionCm, 1.0e-6)
        || !ReceiverHit.ImpactNormal.Equals(NativeHit.Normal, 1.0e-6))
        return Fail(TEXT("Jolt query did not resolve to the retained skeletal paint receiver and physical bone."));
    FProphecyJoltRayHit StaleHit = NativeHit;
    ++StaleHit.Handle.Generation;
    FHitResult RejectedHit;
    if (Character->MakeHitResult(StaleHit, RejectedHit))
        return Fail(TEXT("The skeletal hit bridge accepted a stale body generation."));
    Row->SetStringField(TEXT("query_receiver_bone"), ReceiverHit.BoneName.ToString());
    Row->SetBoolField(TEXT("query_receiver_identity_valid"), true);

    const USkeletalMesh* Asset = Physical->GetSkeletalMeshAsset();
    if (!Asset || Asset != MeshAsset || Asset->GetRefSkeleton().GetNum() != Live::ExpectedBones)
        return Fail(TEXT("PhysicalMesh no longer has the complete 88-bone fixture skeleton."));
    const FReferenceSkeleton& Skeleton = Asset->GetRefSkeleton();
    TArray<FName> Names;
    TArray<FTransform> Feedback;
    Names.Reserve(Skeleton.GetNum());
    Feedback.SetNum(Skeleton.GetNum());
    for (int32 Bone = 0; Bone < Skeleton.GetNum(); ++Bone) Names.Add(Skeleton.GetBoneName(Bone));
    if (!Agent->SampleActualComponentPose(Names, Feedback)) return Fail(TEXT("Actual NN feedback could not read every completed skeleton bone."));
    const USceneComponent* FeedbackReference = Agent->GetAgentMesh() && Agent->GetAgentMesh()->IsRegistered()
        ? Agent->GetAgentMesh() : Physical;
    const FTransform ReferenceWorld = FeedbackReference->GetComponentTransform();
    if (ReferenceWorld.ContainsNaN() || !ReferenceWorld.GetRotation().IsNormalized()) return Fail(TEXT("NN feedback reference transform is invalid."));
    double MaxPosition = 0.0, MaxAngle = 0.0, MaxScale = 0.0, PositionSquared = 0.0;
    FName WorstPositionBone, WorstAngleBone;
    for (int32 Bone = 0; Bone < Names.Num(); ++Bone)
    {
        const FTransform SocketWorld = Physical->GetSocketTransform(Names[Bone], RTS_World);
        const FTransform RenderFeedback = SocketWorld.GetRelativeTransform(ReferenceWorld);
        if (Feedback[Bone].ContainsNaN() || RenderFeedback.ContainsNaN() || SocketWorld.ContainsNaN()
            || !Feedback[Bone].GetRotation().IsNormalized() || !RenderFeedback.GetRotation().IsNormalized()
            || !SocketWorld.GetRotation().IsNormalized())
            return Fail(FString::Printf(TEXT("Nonfinite or unnormalized rendered/feedback transform at %s."), *Names[Bone].ToString()));
        const double Position = FVector::Distance(Feedback[Bone].GetLocation(), RenderFeedback.GetLocation());
        const double Angle = FMath::RadiansToDegrees(Feedback[Bone].GetRotation().GetNormalized()
            .AngularDistance(RenderFeedback.GetRotation().GetNormalized()));
        const double Scale = (Feedback[Bone].GetScale3D() - RenderFeedback.GetScale3D()).GetAbsMax();
        PositionSquared += Position * Position;
        if (Position > MaxPosition) { MaxPosition = Position; WorstPositionBone = Names[Bone]; }
        if (Angle > MaxAngle) { MaxAngle = Angle; WorstAngleBone = Names[Bone]; }
        MaxScale = FMath::Max(MaxScale, Scale);
    }
    Row->SetNumberField(TEXT("validated_skeleton_bones"), Names.Num());
    Row->SetNumberField(TEXT("max_feedback_render_position_cm"), MaxPosition);
    Row->SetNumberField(TEXT("rms_feedback_render_position_cm"), FMath::Sqrt(PositionSquared / Names.Num()));
    Row->SetNumberField(TEXT("max_feedback_render_angle_degrees"), MaxAngle);
    Row->SetNumberField(TEXT("max_feedback_render_scale_difference"), MaxScale);
    Row->SetStringField(TEXT("worst_position_bone"), WorstPositionBone.ToString());
    Row->SetStringField(TEXT("worst_angle_bone"), WorstAngleBone.ToString());
    if (MaxPosition > Live::PositionToleranceCm || MaxAngle > Live::AngleToleranceDegrees || MaxScale > Live::ScaleTolerance)
        return Fail(FString::Printf(TEXT("Completed NN feedback/render disagreement: %.9f cm (%s), %.9f degrees (%s), scale %.9f."),
            MaxPosition, *WorstPositionBone.ToString(), MaxAngle, *WorstAngleBone.ToString(), MaxScale));
    Row->SetBoolField(TEXT("success"), true);
    LiveJoltFrames.Add(MakeShared<FJsonValueObject>(Row));
    LastLiveJoltRevision = Revision;
    return true;
}

bool UProphecyPhysicsBenchmarkSubsystem::SaveLiveJoltCase(TSharedPtr<FJsonObject> CaseResult, FString& Error)
{
    namespace Live = ProphecySterileBench::LiveJolt;
    Error.Reset();
    if (!CaseResult || !ManualInitialRig || Meshes.Num() != 1 || !IsValid(Meshes[0]) || LiveJoltFrames.Num() != Samples)
    { Error = TEXT("Live Jolt report requires every requested validated frame and the retained source rig."); return false; }
    auto Summary = MakeShared<FJsonObject>();
    CaseResult->SetObjectField(TEXT("live_jolt_validation"), Summary);
    CaseResult->SetArrayField(TEXT("live_jolt_frames"), LiveJoltFrames);
    CaseResult->SetStringField(TEXT("pose_error_scope"), TEXT("Acceptance compares completed Jolt NN feedback to the normal skeletal socket pose for all 88 bones. Generic Chaos-body/reference-pose audit errors are not a Jolt tracking or parity result."));
    CaseResult->SetStringField(TEXT("timing_scope"), TEXT("World tick includes live automatic Jolt stepping, target publication and completed skeletal evaluation. Detailed validation runs after world timing; frame intervals include validation overhead. One-agent NullRHI diagnostic, not rendered FPS or a speedup claim."));
    Summary->SetNumberField(TEXT("frames"), LiveJoltFrames.Num());
    Summary->SetNumberField(TEXT("bones_per_frame"), Live::ExpectedBones);
    Summary->SetNumberField(TEXT("position_tolerance_cm"), Live::PositionToleranceCm);
    Summary->SetNumberField(TEXT("angle_tolerance_degrees"), Live::AngleToleranceDegrees);
    Summary->SetNumberField(TEXT("scale_tolerance"), Live::ScaleTolerance);
    double MaxPosition = 0.0, MaxAngle = 0.0, MaxScale = 0.0, SumStepMs = 0.0;
    for (const TSharedPtr<FJsonValue>& FrameValue : LiveJoltFrames)
    {
        const TSharedPtr<FJsonObject> Row = FrameValue->AsObject();
        MaxPosition = FMath::Max(MaxPosition, Row->GetNumberField(TEXT("max_feedback_render_position_cm")));
        MaxAngle = FMath::Max(MaxAngle, Row->GetNumberField(TEXT("max_feedback_render_angle_degrees")));
        MaxScale = FMath::Max(MaxScale, Row->GetNumberField(TEXT("max_feedback_render_scale_difference")));
        SumStepMs += Row->GetObjectField(TEXT("jolt"))->GetNumberField(TEXT("last_step_ms"));
    }
    Summary->SetNumberField(TEXT("max_feedback_render_position_cm"), MaxPosition);
    Summary->SetNumberField(TEXT("max_feedback_render_angle_degrees"), MaxAngle);
    Summary->SetNumberField(TEXT("max_feedback_render_scale_difference"), MaxScale);
    Summary->SetNumberField(TEXT("mean_synchronous_jolt_step_ms"), SumStepMs / LiveJoltFrames.Num());
    Summary->SetStringField(TEXT("feedback_scope"), TEXT("Actual Agent.SampleActualComponentPose entry point reads completed physical data in the inherited AgentMesh frame. This fixture uses a native authored pose store; no NN model inference or recurrent manager update runs here."));
    Summary->SetStringField(TEXT("render_scope"), TEXT("Normal completed AnimInstance evaluation and all skeletal sockets, including nonphysical helpers/fingers. NullRHI does not validate rasterized pixels, blood render targets or stain application."));
    Summary->SetStringField(TEXT("chaos_count_scope"), TEXT("Native nonstatic, nonkinematic actor state of valid BodyInstances exposed by registered primitive components in this fixture world, deduplicated by BodyInstance."));

    AProphecyAgent* Agent = Cast<AProphecyAgent>(Meshes[0]->GetOwner());
    UProphecyJoltCharacterComponent* Character = Agent ? Agent->GetJoltCharacterComponent() : nullptr;
    UProphecyJoltWorldSubsystem* Owner = GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    if (!Agent || !Character || !Owner) { Error = TEXT("Live Jolt teardown lost its agent, character or world owner."); return false; }
    if (FParse::Param(FCommandLine::Get(), TEXT("PhysicsBenchBloodValidation")))
    {
        TSharedPtr<FJsonObject> StaticReport, CharacterReport, InstanceReport;
        FString StaticError, CharacterError, InstanceError;
        const bool bStaticPaint = ProphecyJolt::BloodFixture::ValidateStaticCube(*GetWorld(),
            FTransform(FRotator(10.0, 25.0, 0.0), FVector(5000.0, 0.0, 500.0)), StaticReport, StaticError);
        CaseResult->SetObjectField(TEXT("static_blood_mask"), StaticReport);
        FProphecyJoltBodyHandle HeadHandle;
        FProphecyJoltBodyState Head;
        FProphecyJoltRayHit NativeHit;
        FHitResult ReceiverHit;
        bool bHit = false;
        if (!Character->GetBodyHandle(TEXT("head"), HeadHandle) || !Owner->ReadBody(HeadHandle, Head).IsSuccess()
            || !Owner->RayCast(Head.CenterOfMassPositionCm + FVector(100.0, 0.0, 0.0),
                Head.CenterOfMassPositionCm, NativeHit, bHit).IsSuccess()
            || !bHit || !Character->MakeHitResult(NativeHit, ReceiverHit))
        { Error = TEXT("Blood validation lost its completed Jolt hit receiver."); return false; }
        const bool bCharacterPaint = ProphecyJolt::BloodFixture::ValidateCharacterHit(*GetWorld(), *Meshes[0],
            ReceiverHit, CharacterReport, CharacterError);
        CaseResult->SetObjectField(TEXT("character_blood_mask"), CharacterReport);
        const bool bInstancePaint = ProphecyJolt::ISMBloodFixture::ValidatePromotion(*GetWorld(),
            FTransform(FRotator::ZeroRotator, FVector(7000.0, 0.0, 500.0)), InstanceReport, InstanceError);
        CaseResult->SetObjectField(TEXT("instanced_blood_masks"), InstanceReport);
        if (!bStaticPaint || !bCharacterPaint || !bInstancePaint)
        { Error = FString::Printf(TEXT("Blood validation: static=[%s], character=[%s], instances=[%s]"), *StaticError, *CharacterError, *InstanceError); return false; }
    }
    TArray<FProphecyJoltBodyHandle> OldHandles;
    for (const FProphecyJoltRigBody& Body : ManualInitialRig->Bodies)
    {
        FProphecyJoltBodyHandle Handle;
        if (!Character->GetBodyHandle(Body.BodyName, Handle)) { Error = TEXT("Live Jolt teardown could not capture every live body handle."); return false; }
        OldHandles.Add(Handle);
    }
    if (!Agent->SetSimulationMode(EProphecyAgentSimulationMode::Kinematic)
        || Agent->GetSimulationMode() != EProphecyAgentSimulationMode::Kinematic || Agent->IsJoltPhysicalAnimationEnabled()
        || Character->IsJoltPhysical() || Character->GetRevision() != 0 || Character->IsComponentTickEnabled()
        || Agent->GetPoseReferenceMesh() != Meshes[0])
    { Error = TEXT("Live Jolt failed its public Physical-to-Kinematic lifecycle transition."); return false; }
    FProphecyJoltWorldDiagnostics After;
    const FProphecyJoltWorldStatus Read = Owner->GetDiagnostics(After);
    if (!Read.IsSuccess()) { Error = Read.Message; return false; }
    Summary->SetObjectField(TEXT("after_disable"), Live::DiagnosticsJson(After));
    int32 ChaosAfter = 0;
    if (!Live::CountChaosDynamicBodies(*GetWorld(), ChaosAfter, Error)) return false;
    Summary->SetNumberField(TEXT("chaos_dynamic_bodies_after_disable"), ChaosAfter);
    if (!After.bInitialized || After.bFaulted || After.ConstraintCount != 0
        || After.BodyCount != (Cases[CaseIndex].Floor ? 1u : 0u) || ChaosAfter != 0)
    { Error = TEXT("Live Jolt disable must retain the initialized world and optional floor, with no rig constraints/bodies or Chaos dynamic bodies."); return false; }
    for (const FProphecyJoltBodyHandle& Handle : OldHandles)
    {
        FProphecyJoltBodyState Unused;
        if (Owner->ReadBody(Handle, Unused).Code != EProphecyJoltWorldResult::InvalidHandle)
        { Error = TEXT("Live Jolt teardown left a previously published rig handle valid."); return false; }
    }
    Summary->SetNumberField(TEXT("stale_handles_rejected"), OldHandles.Num());
    Summary->SetBoolField(TEXT("returned_kinematic"), true);
    Summary->SetBoolField(TEXT("success"), true);
    // ClearCase owns actor destruction and world shutdown after this completed report boundary.
    return true;
}
