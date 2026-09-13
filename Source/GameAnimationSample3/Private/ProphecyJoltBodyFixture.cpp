#include "CoreMinimal.h"
#include "ProphecyJoltBody.h"
#include "Components/StaticMeshComponent.h"
#include "Dom/JsonObject.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "PhysicsEngine/BodySetup.h"
#include "PhysicsEngine/PhysicsSettings.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "UObject/Package.h"

namespace ProphecyJolt::StandaloneFixture
{
TArray<TSharedPtr<FJsonValue>> Vector(const FVector& V)
{
    return { MakeShared<FJsonValueNumber>(V.X), MakeShared<FJsonValueNumber>(V.Y), MakeShared<FJsonValueNumber>(V.Z) };
}

TSharedPtr<FJsonObject> Transform(const FTransform& T)
{
    auto Result = MakeShared<FJsonObject>();
    Result->SetArrayField(TEXT("position_cm"), Vector(T.GetLocation()));
    Result->SetArrayField(TEXT("scale"), Vector(T.GetScale3D()));
    const FQuat Q = T.GetRotation();
    Result->SetArrayField(TEXT("rotation_xyzw"), { MakeShared<FJsonValueNumber>(Q.X), MakeShared<FJsonValueNumber>(Q.Y),
        MakeShared<FJsonValueNumber>(Q.Z), MakeShared<FJsonValueNumber>(Q.W) });
    return Result;
}

TArray<TSharedPtr<FJsonValue>> Words(const uint32 (&Values)[4])
{
    TArray<TSharedPtr<FJsonValue>> Result;
    for (uint32 Value : Values) Result.Add(MakeShared<FJsonValueNumber>(Value));
    return Result;
}

class FTransientWorld
{
public:
    FTransientWorld()
    {
        const UWorld::InitializationValues Values = UWorld::InitializationValues()
            .AllowAudioPlayback(false).RequiresHitProxies(false).CreatePhysicsScene(true)
            .CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
            .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
        World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
        if (World && GEngine) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    }
    ~FTransientWorld()
    {
        if (!World) return;
        World->DestroyWorld(false);
        if (GEngine) GEngine->DestroyWorldContext(World);
        World->MarkAsGarbage();
    }
    UWorld* World = nullptr;
};

bool CaptureTrainingSword(FJsonObject& Report, FString& Error)
{
    if (!IsInGameThread()) { Error = TEXT("Training sword capture requires the game thread."); return false; }
    if (UPhysicsSettings::Get()->bTickPhysicsAsync)
    { Error = TEXT("Training sword fixture requires the existing synchronous physics setting; the command does not modify it."); return false; }
    UStaticMesh* Asset = LoadObject<UStaticMesh>(nullptr,
        TEXT("/Game/_mygame/sword/geometry/Sword_GL01_Training.Sword_GL01_Training"));
    if (!Asset || !Asset->GetBodySetup()) { Error = TEXT("Actual Training sword mesh or its BodySetup is missing."); return false; }
    const bool bPackageDirtyBefore = Asset->GetOutermost()->IsDirty();
    const UBodySetup* Setup = Asset->GetBodySetup();
    Report.SetStringField(TEXT("asset"), Asset->GetPathName());
    Report.SetStringField(TEXT("scope"), TEXT("Actual Training static-mesh collision asset with native Equip defaults in a new transient physics world. No A_Sword Blueprint, character, scene map, construction script, world tick or Jolt simulation body is created."));
    Report.SetStringField(TEXT("setup_scope"), TEXT("Native source defaults: ProphecyAgent.h SwordGripTransform/SwordMassKg and ProphecySwordComponent.cpp Equip body setup. This is a geometry/mass fixture, not proof of current Blueprint or placed overrides."));
    Report.SetBoolField(TEXT("assets_saved"), false);
    Report.SetNumberField(TEXT("authored_spheres"), Setup->AggGeom.SphereElems.Num());
    Report.SetNumberField(TEXT("authored_boxes"), Setup->AggGeom.BoxElems.Num());
    Report.SetNumberField(TEXT("authored_capsules"), Setup->AggGeom.SphylElems.Num());
    Report.SetNumberField(TEXT("authored_convexes"), Setup->AggGeom.ConvexElems.Num());
    Report.SetNumberField(TEXT("cooked_query_meshes"), Setup->TriMeshGeometries.Num());
    Report.SetNumberField(TEXT("collision_trace_flag"), int32(Setup->GetCollisionTraceFlag()));
    FTransientWorld Fixture;
    if (!Fixture.World || !Fixture.World->GetPhysicsScene()) { Error = TEXT("Transient Chaos world/physics scene creation failed."); return false; }
    FActorSpawnParameters Parameters;
    Parameters.ObjectFlags |= RF_Transient;
    Parameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    AActor* Actor = Fixture.World->SpawnActor<AActor>(AActor::StaticClass(), FTransform::Identity, Parameters);
    if (!Actor) { Error = TEXT("Transient sword actor creation failed."); return false; }
    Actor->SetActorTickEnabled(false);
    auto* Mesh = NewObject<UStaticMeshComponent>(Actor, TEXT("TrainingSwordCaptureMesh"), RF_Transient);
    Actor->AddInstanceComponent(Mesh);
    Actor->SetRootComponent(Mesh);
    Mesh->SetStaticMesh(Asset);
    Mesh->SetMobility(EComponentMobility::Movable);
    const FTransform FixtureTransform(
        FQuat(-0.020187416964488277, -0.10610846088390578, 0.6210491947126335, 0.7762933469197968),
        FVector(1000.0, -400.0, 250.0) + FVector(-7.1119709819428465, 2.7136660691211247, -0.10802111799378267),
        FVector(0.8377267802922563, 0.7661935080608141, 1.3119414990256073));
    Mesh->SetWorldTransform(FixtureTransform);
    Mesh->SetCollisionProfileName(TEXT("PhysicsActor"));
    Mesh->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
    Mesh->SetEnableGravity(true);
    Mesh->SetMassOverrideInKg(NAME_None, 1.0f, true);
    Mesh->BodyInstance.bUseCCD = true;
    Mesh->BodyInstance.PositionSolverIterationCount = 16;
    Mesh->BodyInstance.VelocitySolverIterationCount = 8;
    Mesh->SetGenerateOverlapEvents(false);
    Mesh->SetNotifyRigidBodyCollision(false);
    Mesh->SetHiddenInGame(true);
    Mesh->SetComponentTickEnabled(false);
    Mesh->RegisterComponent();
    Mesh->SetSimulatePhysics(true);
    if (!Mesh->IsSimulatingPhysics()) { Error = TEXT("Actual Training mesh failed to create a native dynamic body."); return false; }
    FProphecyJoltBodySnapshot Snapshot;
    if (!Body::CaptureLiveBody(*Mesh, Snapshot, Error)) return false;
    Report.SetStringField(TEXT("capture_id"), Snapshot.CaptureId.ToString());
    Report.SetObjectField(TEXT("component_world"), Transform(Snapshot.ComponentToWorld));
    Report.SetObjectField(TEXT("body_origin_world"), Transform(Snapshot.Body.BodyOriginToWorld));
    Report.SetObjectField(TEXT("body_origin_to_component"), Transform(Snapshot.BodyOriginToComponent));
    Report.SetObjectField(TEXT("principal_mass_frame_to_body_origin"), Transform(Snapshot.Body.MassFrameToBodyOrigin));
    Report.SetNumberField(TEXT("mass_kg"), Snapshot.Body.MassKg);
    Report.SetArrayField(TEXT("principal_inertia_kg_cm2"), Vector(Snapshot.Body.PrincipalInertiaKgCmSquared));
    Report.SetArrayField(TEXT("com_linear_velocity_cm_s"), Vector(Snapshot.Body.CenterOfMassVelocityCmPerSecond));
    Report.SetArrayField(TEXT("angular_velocity_rad_s"), Vector(Snapshot.Body.AngularVelocityRadiansPerSecond));
    Report.SetArrayField(TEXT("source_build_scale"), Vector(Snapshot.Body.SourceBuildScale3D));
    Report.SetArrayField(TEXT("source_body_scale"), Vector(Snapshot.Body.SourceBodyScale3D));
    Report.SetBoolField(TEXT("ccd"), Snapshot.Body.bCCD);
    Report.SetBoolField(TEXT("macd"), Snapshot.Body.bMACD);
    Report.SetBoolField(TEXT("inertia_conditioning"), Snapshot.Body.bInertiaConditioning);
    Report.SetStringField(TEXT("physical_material"), Snapshot.Body.PhysicalMaterialPath);
    Report.SetNumberField(TEXT("friction"), Snapshot.Body.Friction);
    Report.SetNumberField(TEXT("restitution"), Snapshot.Body.Restitution);
    Report.SetNumberField(TEXT("native_shapes"), Snapshot.NativeShapeCount);
    Report.SetNumberField(TEXT("simulation_shapes"), Snapshot.Body.Shapes.Num());
    Report.SetNumberField(TEXT("authored_convex_input_vertices"), Snapshot.AuthoredConvexInputVertexCount);
    TArray<TSharedPtr<FJsonValue>> Shapes;
    for (const auto& Shape : Snapshot.Body.Shapes)
    {
        auto Row = MakeShared<FJsonObject>();
        Row->SetNumberField(TEXT("authored_element_index"), Shape.SourceElementIndex);
        Row->SetNumberField(TEXT("native_shape_index"), Shape.SourceNativeShapeIndex);
        Row->SetNumberField(TEXT("shape_kind"), int32(Shape.Kind));
        Row->SetObjectField(TEXT("local_to_body_origin"), Transform(Shape.LocalToBodyOrigin));
        Row->SetNumberField(TEXT("native_collision_margin_cm"), Shape.NativeCollisionMarginCm);
        Row->SetArrayField(TEXT("simulation_filter_words"), Words(Shape.NativeSimulationFilterWords));
        Row->SetArrayField(TEXT("query_filter_words"), Words(Shape.NativeQueryFilterWords));
        TArray<TSharedPtr<FJsonValue>> TypeChain;
        for (uint32 Type : Shape.NativeGeometryTypeChain) TypeChain.Add(MakeShared<FJsonValueNumber>(Type));
        Row->SetArrayField(TEXT("native_wrapper_to_leaf_types"), TypeChain);
        TArray<TSharedPtr<FJsonValue>> Vertices;
        for (const FVector& Vertex : Shape.ConvexVerticesCm) Vertices.Add(MakeShared<FJsonValueArray>(Vector(Vertex)));
        Row->SetArrayField(TEXT("cooked_hull_vertices_body_origin_cm"), Vertices);
        Shapes.Add(MakeShared<FJsonValueObject>(Row));
    }
    Report.SetArrayField(TEXT("simulation_geometry"), Shapes);
    TArray<TSharedPtr<FJsonValue>> Queries;
    for (const auto& Query : Snapshot.NonSimulationShapes)
    {
        auto Row = MakeShared<FJsonObject>();
        Row->SetNumberField(TEXT("native_shape_index"), Query.NativeShapeIndex);
        Row->SetNumberField(TEXT("native_geometry_type"), Query.NativeGeometryType);
        Row->SetBoolField(TEXT("query_enabled"), Query.bQueryEnabled);
        Row->SetBoolField(TEXT("simulation_enabled"), Query.bSimulationEnabled);
        Row->SetBoolField(TEXT("effective_simulation_enabled"), false);
        Row->SetArrayField(TEXT("query_filter_words"), Words(Query.QueryFilterWords));
        Row->SetArrayField(TEXT("bounds_min_cm"), Vector(Query.BoundsInBodyOriginCm.Min));
        Row->SetArrayField(TEXT("bounds_max_cm"), Vector(Query.BoundsInBodyOriginCm.Max));
        Queries.Add(MakeShared<FJsonValueObject>(Row));
    }
    Report.SetArrayField(TEXT("non_simulation_geometry_provenance"), Queries);
    if (Snapshot.Body.Shapes.Num() != 1 || Snapshot.Body.Shapes[0].Kind != EProphecyJoltRigShape::Convex)
    { Error = TEXT("Current Training asset no longer has the expected single simulation convex; inspect this report before choosing a different shape contract."); return false; }
    if (!Snapshot.Body.bCCD || !FMath::IsNearlyEqual(Snapshot.Body.MassKg, 1.0, 1.0e-4))
    { Error = TEXT("Training fixture did not retain its native mass override/CCD input."); return false; }
    FProphecyJoltPreparedBody Prepared;
    if (!Prepared.Build(Snapshot, Error)) return false;
    FVector COM;
    FBox Bounds(ForceInit);
    if (!Prepared.GetGeometrySummary(COM, Bounds, Error)) return false;
    Report.SetArrayField(TEXT("prepared_com_body_origin_cm"), Vector(COM));
    Report.SetArrayField(TEXT("prepared_bounds_min_cm"), Vector(Bounds.Min));
    Report.SetArrayField(TEXT("prepared_bounds_max_cm"), Vector(Bounds.Max));
    FProphecyJoltBodySnapshot ReRead;
    if (!Body::CaptureLiveBody(*Mesh, ReRead, Error)) return false;
    if (!Snapshot.Body.BodyOriginToWorld.Equals(ReRead.Body.BodyOriginToWorld, 0.0)
        || !Snapshot.Body.MassFrameToBodyOrigin.Equals(ReRead.Body.MassFrameToBodyOrigin, 0.0)
        || Snapshot.Body.MassKg != ReRead.Body.MassKg
        || Snapshot.Body.PrincipalInertiaKgCmSquared != ReRead.Body.PrincipalInertiaKgCmSquared
        || Snapshot.Body.CenterOfMassVelocityCmPerSecond != ReRead.Body.CenterOfMassVelocityCmPerSecond
        || Snapshot.Body.AngularVelocityRadiansPerSecond != ReRead.Body.AngularVelocityRadiansPerSecond)
    { Error = TEXT("Read-only capture/preparation changed the native source body state."); return false; }
    Report.SetBoolField(TEXT("native_source_state_unchanged"), true);
    Report.SetBoolField(TEXT("asset_package_dirty_before"), bPackageDirtyBefore);
    Report.SetBoolField(TEXT("asset_package_dirty_after"), Asset->GetOutermost()->IsDirty());
    TArray<TSharedPtr<FJsonValue>> Notes;
    for (const FString& Note : Snapshot.CoverageNotes) Notes.Add(MakeShared<FJsonValueString>(Note));
    Report.SetArrayField(TEXT("coverage_notes"), Notes);
    Prepared.Reset();
    return true;
}

void RunTrainingSwordCapture(const TArray<FString>& Args)
{
    if (Args.Num() != 1 || FPaths::IsRelative(Args[0]) || FPaths::FileExists(Args[0]))
    {
        UE_LOG(LogTemp, Error, TEXT("Prophecy.Jolt.CaptureTrainingSword requires one absolute JSON path which does not already exist."));
        return;
    }
    const FString Output = Args[0];
    auto Report = MakeShared<FJsonObject>();
    FString Error;
    const bool bSucceeded = CaptureTrainingSword(*Report, Error);
    Report->SetBoolField(TEXT("success"), bSucceeded);
    Report->SetStringField(TEXT("error"), Error);
    Report->SetBoolField(TEXT("assets_saved"), false);
    FString Text;
    const bool bSerialized = FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Text));
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(Output), true);
    // FILEWRITE_NoReplaceExisting protects against a second capture arriving after the first path check.
    const bool bSaved = bSerialized && FFileHelper::SaveStringToFile(Text, *Output,
        FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM, &IFileManager::Get(), FILEWRITE_NoReplaceExisting);
    if (!bSaved) { UE_LOG(LogTemp, Error, TEXT("Training sword capture could not create its new report: %s"), *Output); }
    else if (!bSucceeded) { UE_LOG(LogTemp, Error, TEXT("Training sword capture failed: %s; report=%s"), *Error, *Output); }
    else { UE_LOG(LogTemp, Display, TEXT("Training sword capture succeeded without asset saves: %s"), *Output); }
}

FAutoConsoleCommand Command(TEXT("Prophecy.Jolt.CaptureTrainingSword"),
    TEXT("Read actual Training sword collider/mass into a transient world; provide one new absolute JSON path. No asset saves or world stepping."),
    FConsoleCommandWithArgsDelegate::CreateStatic(&RunTrainingSwordCapture));
}
