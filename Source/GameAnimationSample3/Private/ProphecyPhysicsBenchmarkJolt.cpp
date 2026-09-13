#include "ProphecyPhysicsBenchmark.h"
#include "ProphecyPhysicsBenchmarkRigAudit.h"
#include "ProphecyJoltRig.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "ProphecyManualServoCapture.h"
#include "Components/BoxComponent.h"
#include "Engine/World.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/ScopeExit.h"
#include "Misc/SecureHash.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

bool UProphecyPhysicsBenchmarkSubsystem::ReplayManualCaptureInJolt(TSharedPtr<FJsonObject> CaseResult, FString& Error)
{
    namespace Json = ProphecySterileBench::RigAudit;
    using namespace ProphecyManualServoCapture;
    if (!ManualInitialRig || !ManualSealedCapture || ManualSealedCapture->Steps.IsEmpty())
    { Error = TEXT("Jolt replay requires a complete sealed Chaos capture and complete rig"); return false; }
    FProphecyJoltRigSnapshot Rig = *ManualInitialRig;
    Rig.CaptureId = FGuid::NewGuid();
    TMap<FName, int32> BodyIndices;
    for (int32 Index = 0; Index < Rig.Bodies.Num(); ++Index) BodyIndices.Add(Rig.Bodies[Index].BodyName, Index);
    const FPacket& FirstPacket = ManualSealedCapture->Packets[0];
    const FStep& FirstStep = ManualSealedCapture->Steps[0];
    for (int32 Index = 0; Index < FirstPacket.BodyCount; ++Index)
    {
        const int32* BodyIndex = BodyIndices.Find(FirstPacket.Bodies[Index].BoneName);
        if (!BodyIndex || !FirstStep.Bodies[Index].bValid)
        { Error = TEXT("Jolt replay initial body mapping is incomplete"); return false; }
        FProphecyJoltRigBody& Body = Rig.Bodies[*BodyIndex];
        Body.BodyOriginToWorld = FTransform(FirstStep.Bodies[Index].Rotation, FirstStep.Bodies[Index].Position);
        Body.CenterOfMassVelocityCmPerSecond = FirstStep.Bodies[Index].LinearVelocityBefore;
        Body.AngularVelocityRadiansPerSecond = FirstStep.Bodies[Index].AngularVelocityBefore;
    }
    FProphecyJoltPreparedRig Prepared;
    if (!Prepared.Build(Rig, Error)) return false;
    UProphecyJoltWorldSubsystem* Owner = GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();
    if (!Owner) { Error = TEXT("Jolt world subsystem is unavailable"); return false; }
    auto Check = [&Error](const FProphecyJoltWorldStatus& Status)
    {
        if (!Status.IsSuccess()) Error = Status.Message;
        return Status.IsSuccess();
    };
    FProphecyJoltWorldSettings Settings;
    const bool bFloor = Cases[CaseIndex].Floor;
    Settings.GravityCmPerSecondSquared = bFloor ? FVector(0, 0, GetWorld()->GetGravityZ()) : FVector::ZeroVector;
    if (!Check(Owner->InitializeSimulation(Settings))) return false;
    ON_SCOPE_EXIT { Owner->ShutdownSimulation(); };
    if (bFloor)
    {
        UBoxComponent* SourceFloor = nullptr;
        for (AActor* Actor : Actors) if (Actor && (SourceFloor = Actor->FindComponentByClass<UBoxComponent>())) break;
        if (!SourceFloor) { Error = TEXT("Jolt replay could not resolve the fixture floor material"); return false; }
        const UPhysicalMaterial* Material = SourceFloor->BodyInstance.GetSimplePhysicalMaterial();
        if (!Material) { Error = TEXT("Fixture floor has no physical material"); return false; }
        FProphecyJoltFixtureBodySettings Floor;
        Floor.bDynamic = false;
        Floor.PositionCm = FVector(0, 0, -10);
        Floor.Friction = Material->Friction;
        Floor.Restitution = Material->Restitution;
        FProphecyJoltBodyHandle FloorHandle;
        if (!Check(Owner->CreateBox(FVector(50000, 50000, 10), 0.0, Floor, FloorHandle))) return false;
    }
    TArray<FProphecyJoltBodyHandle> Handles;
    TArray<FString> Coverage;
    if (!Check(Owner->CreateRigFixture(Rig, Prepared, Handles, Coverage))) return false;
    if (Handles.Num() != 22) { Error = TEXT("Jolt fixture body count differs from sealed rig"); return false; }
    auto Root = MakeShared<FJsonObject>();
    Root->SetNumberField(TEXT("schema_version"), 1);
    Root->SetStringField(TEXT("input_capture"), ManualSealedCapturePath);
    Root->SetStringField(TEXT("input_sha1"), ManualSealedCaptureHash);
    Root->SetStringField(TEXT("jolt_commit"), TEXT("e77f175595e64cb44218cc9d9d56fc365ad0e36a"));
    Root->SetStringField(TEXT("scope"), TEXT("One native 22-body rig consuming complete sealed manual endpoints; independent execution diagnostic, fixture only, production remains Chaos"));
    Root->SetObjectField(TEXT("chaos_replay_comparison"), CaseResult->GetObjectField(TEXT("chaos_replay_comparison")));
    Root->SetStringField(TEXT("angular_policy"), TEXT("User-approved stock hard limits with original PHAT angle values; no retuning. Remaining solver/contact compatibility notes below are not parity claims."));
    Root->SetStringField(TEXT("initialization"), TEXT("Captured raw first-preintegrate body X/R/V/W, captured mass/COM/inertia/geometry/activation; no solver warm-start cache transfer"));
    Root->SetArrayField(TEXT("gravity_cm_s2"), Json::Vector(Settings.GravityCmPerSecondSquared));
    TArray<TSharedPtr<FJsonValue>> Notes, Steps;
    for (const FString& Note : Coverage) Notes.Add(MakeShared<FJsonValueString>(Note));
    Root->SetArrayField(TEXT("coverage_notes"), Notes);
    TArray<FProphecyJoltRigVelocityTarget> Targets;
    Targets.SetNum(22);
    double MaxPositionDifference = 0, MaxAngleDifference = 0, SumPositionSquared = 0;
    double TotalUpdateSeconds = 0, MaxFirstLinearDifference = 0, MaxFirstAngularDifference = 0;
    uint64 Comparisons = 0;
    for (int32 Index = 0; Index < ManualSealedCapture->Packets.Num(); ++Index)
    {
        const FPacket& Packet = ManualSealedCapture->Packets[Index];
        const FStep& Reference = ManualSealedCapture->Steps[Index];
        for (int32 Bone = 0; Bone < 22; ++Bone)
        {
            const FBoneTarget& Input = Packet.Bodies[Bone];
            const int32* BodyIndex = BodyIndices.Find(Input.BoneName);
            if (!BodyIndex) { Error = TEXT("Jolt packet refers to an unmapped body"); return false; }
            Targets[Bone] = { Handles[*BodyIndex], Input.TargetPosition, Input.TargetRotation, Input.LinearStrength, Input.AngularStrength };
        }
        if (!Check(Owner->PublishRigFixtureVelocityTargets(Targets, Packet.MaximumSubstepSeconds)) ||
            !Check(Owner->Step(1.f / 60.f, 1))) return false;
        FProphecyJoltRigServoState Servo;
        FProphecyJoltWorldDiagnostics Diagnostics;
        if (!Check(Owner->ReadRigFixtureServoSamples(Servo)) || !Check(Owner->GetDiagnostics(Diagnostics))) return false;
        if (Servo.InvocationCount != static_cast<uint64>(Index + 1) || Servo.InvalidBodyCount || Servo.Samples.Num() != 22 ||
            !FMath::IsNearlyEqual(Servo.LastIntegrationSeconds, 1.f / 60.f) || Diagnostics.ConstraintCount != 21)
        { Error = TEXT("Jolt fixture callback/body/constraint count failed; no wake or activation fallback applied"); return false; }
        TotalUpdateSeconds += Diagnostics.LastStepWallSeconds;
        auto Step = MakeShared<FJsonObject>();
        Step->SetNumberField(TEXT("input_sequence"), Packet.Sequence);
        Step->SetNumberField(TEXT("integration_seconds"), Servo.LastIntegrationSeconds);
        Step->SetNumberField(TEXT("denominator_seconds"), Servo.DenominatorSeconds);
        TArray<TSharedPtr<FJsonValue>> Bodies;
        for (int32 Bone = 0; Bone < 22; ++Bone)
        {
            const FProphecyJoltRigServoSample& Sample = Servo.Samples[Bone];
            FProphecyJoltBodyState Completed;
            if (!Sample.bValid) { Error = TEXT("Jolt servo did not produce a valid sample for a rig body"); return false; }
            if (!Check(Owner->ReadBody(Targets[Bone].Handle, Completed))) return false;
            const double PositionDifference = FVector::Distance(Sample.PositionCm, Reference.Bodies[Bone].Position);
            MaxPositionDifference = FMath::Max(MaxPositionDifference, PositionDifference);
            SumPositionSquared += PositionDifference * PositionDifference;
            MaxAngleDifference = FMath::Max(MaxAngleDifference,
                FMath::RadiansToDegrees(Sample.Rotation.GetNormalized().AngularDistance(Reference.Bodies[Bone].Rotation.GetNormalized())));
            ++Comparisons;
            if (Index == 0)
            {
                MaxFirstLinearDifference = FMath::Max(MaxFirstLinearDifference,
                    FVector::Distance(Sample.LinearAfterCmPerSecond, Reference.Bodies[Bone].LinearVelocityAfter));
                MaxFirstAngularDifference = FMath::Max(MaxFirstAngularDifference,
                    FVector::Distance(Sample.AngularAfterRadiansPerSecond, Reference.Bodies[Bone].AngularVelocityAfter));
            }
            auto B = MakeShared<FJsonObject>();
            B->SetStringField(TEXT("bone"), Packet.Bodies[Bone].BoneName.ToString());
            B->SetObjectField(TEXT("pre_servo_body_world"), Json::Transform(FTransform(Sample.Rotation, Sample.PositionCm)));
            B->SetArrayField(TEXT("post_servo_linear_cm_s"), Json::Vector(Sample.LinearAfterCmPerSecond));
            B->SetArrayField(TEXT("post_servo_angular_rad_s"), Json::Vector(Sample.AngularAfterRadiansPerSecond));
            B->SetObjectField(TEXT("completed_body_world"), Json::Transform(FTransform(Completed.Rotation, Completed.PositionCm)));
            B->SetNumberField(TEXT("chaos_pre_servo_position_difference_cm"), PositionDifference);
            Bodies.Add(MakeShared<FJsonValueObject>(B));
        }
        Step->SetArrayField(TEXT("bodies"), Bodies);
        Steps.Add(MakeShared<FJsonValueObject>(Step));
    }
    Root->SetArrayField(TEXT("steps"), Steps);
    Root->SetNumberField(TEXT("max_chaos_position_difference_cm"), MaxPositionDifference);
    Root->SetNumberField(TEXT("rms_chaos_position_difference_cm"), FMath::Sqrt(SumPositionSquared / Comparisons));
    Root->SetNumberField(TEXT("max_chaos_angle_difference_degrees"), MaxAngleDifference);
    Root->SetNumberField(TEXT("first_step_post_servo_linear_difference_cm_s"), MaxFirstLinearDifference);
    Root->SetNumberField(TEXT("first_step_post_servo_angular_difference_rad_s"), MaxFirstAngularDifference);
    Root->SetNumberField(TEXT("mean_synchronous_update_ms"), TotalUpdateSeconds * 1000.0 / Steps.Num());
    Root->SetStringField(TEXT("timing_scope"), TEXT("Diagnostic one-agent synchronous Jolt Update including owner validation; not total integration cost or a speedup benchmark"));
    if (!Check(Owner->DestroyRigFixture())) return false;
    FProphecyJoltWorldDiagnostics After;
    if (!Check(Owner->GetDiagnostics(After)) || After.ConstraintCount || After.BodyCount != (bFloor ? 1u : 0u))
    { Error = TEXT("Jolt fixture teardown left bodies or constraints"); return false; }
    Root->SetBoolField(TEXT("completed_and_torn_down"), true);
    const FString Path = FPaths::GetPath(Output) / (FPaths::GetBaseFilename(Output) + (bFloor ? TEXT("-jolt-floor.json") : TEXT("-jolt-air.json")));
    FString Text;
    if (!IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path), true) ||
        !FJsonSerializer::Serialize(Root, TJsonWriterFactory<>::Create(&Text)) ||
        !FFileHelper::SaveStringToFile(Text, *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM, &IFileManager::Get(), FILEWRITE_NoReplaceExisting))
    { Error = TEXT("Could not write new Jolt replay report"); return false; }
    CaseResult->SetStringField(TEXT("jolt_replay_file"), FPaths::ConvertRelativePathToFull(Path));
    CaseResult->SetNumberField(TEXT("jolt_max_position_difference_cm"), MaxPositionDifference);
    return true;
}
