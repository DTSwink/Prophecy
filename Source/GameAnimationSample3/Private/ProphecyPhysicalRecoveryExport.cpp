// Explicit robotics export. No gameplay tick, Blueprint edits or source-asset mutation.
#include "CoreMinimal.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/PhysicsConstraintTemplate.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "ProphecyJoltRig.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/Package.h"

namespace ProphecyPhysicalRecoveryExport
{
using FObject = TSharedPtr<FJsonObject>;
TArray<TSharedPtr<FJsonValue>> Vector(const FVector& V)
{
    return {MakeShared<FJsonValueNumber>(V.X), MakeShared<FJsonValueNumber>(V.Y), MakeShared<FJsonValueNumber>(V.Z)};
}
TArray<TSharedPtr<FJsonValue>> Quat(const FQuat& Q)
{
    return {MakeShared<FJsonValueNumber>(Q.X), MakeShared<FJsonValueNumber>(Q.Y),
        MakeShared<FJsonValueNumber>(Q.Z), MakeShared<FJsonValueNumber>(Q.W)};
}
FObject Transform(const FTransform& T)
{
    auto J = MakeShared<FJsonObject>();
    J->SetArrayField(TEXT("position_cm"), Vector(T.GetLocation()));
    J->SetArrayField(TEXT("rotation_xyzw"), Quat(T.GetRotation()));
    J->SetArrayField(TEXT("scale"), Vector(T.GetScale3D()));
    return J;
}
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
};

bool Capture(FJsonObject& Report, FString& Error)
{
    auto* Asset = LoadObject<UPhysicsAsset>(nullptr,
        TEXT("/Game/Characters/UEFN_Mannequin/Rigs/PA_UEFN_Mannequin.PA_UEFN_Mannequin"));
    auto* MeshAsset = LoadObject<USkeletalMesh>(nullptr,
        TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
    if (!Asset || !MeshAsset) { Error = TEXT("Original mannequin or PHAT missing."); return false; }
    const bool DirtyAsset = Asset->GetOutermost()->IsDirty(), DirtyMesh = MeshAsset->GetOutermost()->IsDirty();
    FWorldFixture Fixture;
    if (!Fixture.World || !Fixture.World->GetPhysicsScene()) { Error = TEXT("Transient physics world failed."); return false; }
    FActorSpawnParameters Params;
    Params.ObjectFlags |= RF_Transient;
    auto* Actor = Fixture.World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, Params);
    auto* Mesh = NewObject<USkeletalMeshComponent>(Actor, TEXT("RoboticsSourceRig"), RF_Transient);
    Actor->AddInstanceComponent(Mesh);
    Actor->SetRootComponent(Mesh);
    Mesh->SetSkeletalMesh(MeshAsset);
    Mesh->SetPhysicsAsset(Asset);
    Mesh->SetCollisionProfileName(TEXT("PhysicsActor"));
    Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    Mesh->bUpdateJointsFromAnimation = false;
    Mesh->bEnablePerPolyCollision = false;
    Mesh->BodyInstance.bAutoWeld = false;
    Mesh->RegisterComponent();
    Mesh->SetAllBodiesSimulatePhysics(true);
    Mesh->SetComponentTickEnabled(false);
    FProphecyJoltRigSnapshot Rig;
    if (!ProphecyJolt::Rig::CaptureLiveRig(*Mesh, Rig, Error)) return false;
    FProphecyJoltPreparedRig Prepared;
    if (!Prepared.Build(Rig, Error)) return false;

    Report.SetNumberField(TEXT("schema"), 2);
    Report.SetStringField(TEXT("mesh"), MeshAsset->GetPathName());
    Report.SetStringField(TEXT("physics_asset"), Asset->GetPathName());
    Report.SetStringField(TEXT("scope"), TEXT("Original PHAT in reference pose, unit scale, transient world; zero simulation steps, no agent or Blueprint."));
    Report.SetStringField(TEXT("basis"), TEXT("Unreal/Jolt numerical XYZ; position cm, quaternion XYZW, mass kg, inertia kg*cm^2."));
    const auto& Ref = MeshAsset->GetRefSkeleton();
    TArray<FTransform> Component;
    TArray<TSharedPtr<FJsonValue>> Skeleton;
    for (int32 I = 0; I < Ref.GetNum(); ++I)
    {
        const int32 Parent = Ref.GetParentIndex(I);
        const auto Local = Ref.GetRefBonePose()[I];
        Component.Add(Parent < 0 ? Local : Local * Component[Parent]);
        auto B = MakeShared<FJsonObject>();
        B->SetStringField(TEXT("name"), Ref.GetBoneName(I).ToString());
        B->SetNumberField(TEXT("parent"), Parent);
        B->SetObjectField(TEXT("local"), Transform(Local));
        B->SetObjectField(TEXT("component"), Transform(Component[I]));
        Skeleton.Add(MakeShared<FJsonValueObject>(B));
    }
    Report.SetArrayField(TEXT("skeleton"), Skeleton);
    TArray<TSharedPtr<FJsonValue>> Bodies;
    for (int32 I = 0; I < Rig.Bodies.Num(); ++I)
    {
        const auto& B = Rig.Bodies[I];
        auto J = MakeShared<FJsonObject>();
        J->SetStringField(TEXT("name"), B.BodyName.ToString());
        J->SetNumberField(TEXT("bone_index"), B.BoneIndex);
        J->SetObjectField(TEXT("reference"), Transform(B.BodyOriginToWorld));
        J->SetNumberField(TEXT("mass_kg"), B.MassKg);
        J->SetObjectField(TEXT("mass_frame"), Transform(B.MassFrameToBodyOrigin));
        J->SetArrayField(TEXT("raw_inertia_kg_cm2"), Vector(B.PrincipalInertiaKgCmSquared));
        double EffectiveMass; FQuat EffectiveRotation; FVector EffectiveInertia;
        if (!Prepared.GetBodyMassSummary(I, EffectiveMass, EffectiveRotation, EffectiveInertia))
        { Error = TEXT("Prepared mass export failed."); return false; }
        J->SetNumberField(TEXT("jolt_mass_kg"), EffectiveMass);
        J->SetArrayField(TEXT("jolt_inertia_rotation_xyzw"), Quat(EffectiveRotation));
        J->SetArrayField(TEXT("jolt_inertia_kg_cm2"), Vector(EffectiveInertia));
        J->SetBoolField(TEXT("inertia_conditioning"), B.bInertiaConditioning);
        J->SetNumberField(TEXT("linear_damping"), B.LinearDamping);
        J->SetNumberField(TEXT("angular_damping"), B.AngularDamping);
        J->SetBoolField(TEXT("gravity_enabled"), B.bGravityEnabled);
        J->SetBoolField(TEXT("ccd"), B.bCCD);
        J->SetBoolField(TEXT("macd"), B.bMACD);
        J->SetNumberField(TEXT("max_linear_velocity_cm_s"), B.MaxLinearVelocityCmPerSecond);
        J->SetNumberField(TEXT("max_angular_velocity_rad_s"), B.MaxAngularVelocityRadiansPerSecond);
        J->SetNumberField(TEXT("position_solver_iterations"), B.PositionSolverIterations);
        J->SetNumberField(TEXT("velocity_solver_iterations"), B.VelocitySolverIterations);
        J->SetNumberField(TEXT("projection_solver_iterations"), B.ProjectionSolverIterations);
        J->SetStringField(TEXT("material"), B.PhysicalMaterialPath);
        J->SetNumberField(TEXT("friction"), B.Friction);
        J->SetNumberField(TEXT("static_friction"), B.StaticFriction);
        J->SetNumberField(TEXT("friction_combine_mode"), B.EffectiveFrictionCombineMode);
        J->SetNumberField(TEXT("restitution_combine_mode"), B.EffectiveRestitutionCombineMode);
        J->SetNumberField(TEXT("restitution"), B.Restitution);
        TArray<TSharedPtr<FJsonValue>> Shapes;
        for (const auto& S : B.Shapes)
        {
            auto G = MakeShared<FJsonObject>();
            const TCHAR* Kind = S.Kind == EProphecyJoltRigShape::Sphere ? TEXT("sphere") :
                S.Kind == EProphecyJoltRigShape::Box ? TEXT("box") :
                S.Kind == EProphecyJoltRigShape::Capsule ? TEXT("capsule") : TEXT("convex");
            G->SetStringField(TEXT("kind"), Kind);
            G->SetObjectField(TEXT("local"), Transform(S.LocalToBodyOrigin));
            G->SetNumberField(TEXT("radius_cm"), S.RadiusCm);
            G->SetArrayField(TEXT("half_extent_cm"), Vector(S.BoxHalfExtentCm));
            G->SetNumberField(TEXT("cylinder_length_cm"), S.CapsuleCylinderLengthCm);
            G->SetBoolField(TEXT("simulated"), S.bNativeSimulationEnabled);
            G->SetNumberField(TEXT("native_margin_cm"), S.NativeCollisionMarginCm);
            TArray<TSharedPtr<FJsonValue>> Vertices;
            for (const auto& V : S.ConvexVerticesCm) Vertices.Add(MakeShared<FJsonValueArray>(Vector(V)));
            G->SetArrayField(TEXT("vertices_cm"), Vertices);
            Shapes.Add(MakeShared<FJsonValueObject>(G));
        }
        J->SetArrayField(TEXT("shapes"), Shapes);
        Bodies.Add(MakeShared<FJsonValueObject>(J));
    }
    Report.SetArrayField(TEXT("bodies"), Bodies);
    TArray<TSharedPtr<FJsonValue>> Joints;
    for (const auto& C : Rig.Joints)
    {
        const auto& P = C.CurrentProfile;
        auto J = MakeShared<FJsonObject>();
        J->SetStringField(TEXT("name"), C.JointName.ToString());
        J->SetNumberField(TEXT("child"), C.Body1Index);
        J->SetNumberField(TEXT("parent"), C.Body2Index);
        J->SetObjectField(TEXT("child_frame"), Transform(C.Frame1));
        J->SetObjectField(TEXT("parent_frame"), Transform(C.Frame2));
        J->SetArrayField(TEXT("angular_modes_twist_swing2_swing1"), Vector(FVector(
            P.TwistLimit.TwistMotion, P.ConeLimit.Swing2Motion, P.ConeLimit.Swing1Motion)));
        J->SetArrayField(TEXT("angular_limits_deg_twist_swing2_swing1"), Vector(FVector(
            P.TwistLimit.TwistLimitDegrees, P.ConeLimit.Swing2LimitDegrees, P.ConeLimit.Swing1LimitDegrees)));
        J->SetArrayField(TEXT("linear_modes"), Vector(FVector(P.LinearLimit.XMotion, P.LinearLimit.YMotion, P.LinearLimit.ZMotion)));
        J->SetBoolField(TEXT("soft_swing"), P.ConeLimit.bSoftConstraint);
        J->SetBoolField(TEXT("soft_twist"), P.TwistLimit.bSoftConstraint);
        FString Profile;
        FConstraintProfileProperties::StaticStruct()->ExportText(Profile, &P, nullptr, nullptr, PPF_None, nullptr);
        J->SetStringField(TEXT("original_profile_text"), Profile);
        Joints.Add(MakeShared<FJsonValueObject>(J));
    }
    Report.SetArrayField(TEXT("joints"), Joints);
    TArray<TSharedPtr<FJsonValue>> Pairs;
    for (const auto& P : Rig.DisabledPairs)
        Pairs.Add(MakeShared<FJsonValueArray>(TArray<TSharedPtr<FJsonValue>>{
            MakeShared<FJsonValueNumber>(P.Body1Index), MakeShared<FJsonValueNumber>(P.Body2Index)}));
    Report.SetArrayField(TEXT("disabled_pairs"), Pairs);
    if (Asset->GetOutermost()->IsDirty() != DirtyAsset || MeshAsset->GetOutermost()->IsDirty() != DirtyMesh)
    { Error = TEXT("Unexpected asset dirty-state change."); return false; }
    return true;
}
void Run(const TArray<FString>& Args)
{
    const FString Name = Args.IsEmpty() ? TEXT("rig.json") : Args[0];
    if (Name != FPaths::GetCleanFilename(Name) || !Name.EndsWith(TEXT(".json")))
    {
        UE_LOG(LogTemp, Error, TEXT("Robotics export expects a JSON filename within Saved/Robotics."));
        return;
    }
    const FString Path = FPaths::ConvertRelativePathToFull(FPaths::ProjectSavedDir() / TEXT("Robotics") / Name);
    auto Report = MakeShared<FJsonObject>();
    FString Error;
    const bool Success = Capture(*Report, Error);
    Report->SetBoolField(TEXT("success"), Success);
    Report->SetStringField(TEXT("error"), Error);
    FString Json;
    FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Json));
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path), true);
    FFileHelper::SaveStringToFile(Json, *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    UE_LOG(LogTemp, Display, TEXT("Physical recovery export: %s (%s), %s"), Success ? TEXT("OK") : TEXT("FAILED"), *Error, *Path);
}
FAutoConsoleCommand Command(TEXT("Prophecy.Robotics.ExportRig"), TEXT("Export original mannequin PHAT to Saved/Robotics/rig.json without changing assets."),
    FConsoleCommandWithArgsDelegate::CreateStatic(&Run));
}
