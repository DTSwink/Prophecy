#include "CoreMinimal.h"
#include "Chaos/Convex.h"
#include "Chaos/TriangleMeshImplicitObject.h"
#include "Editor.h"
#include "EditorSupportDelegates.h"
#include "Engine/StaticMesh.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Materials/MaterialInterface.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/SecureHash.h"
#include "PhysicsEngine/BodySetup.h"
#include "ScopedTransaction.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "StaticMeshAttributes.h"
#include "StaticMeshResources.h"
#include "UObject/Package.h"
#include "UObject/UnrealType.h"

namespace ProphecySwordCollisionHull
{
constexpr const TCHAR* AssetPath = TEXT("/Game/_mygame/sword/geometry/Sword_GL01_Training.Sword_GL01_Training");

struct FDigest
{
    FSHA1 SHA;
    template<typename T> void Add(const T& Value) { SHA.Update(reinterpret_cast<const uint8*>(&Value), uint32(sizeof(Value))); }
    void Vector(const FVector& V) { Add(V.X); Add(V.Y); Add(V.Z); }
    FString Finish()
    {
        SHA.Final();
        FSHAHash Hash;
        SHA.GetHash(Hash.Hash);
        return Hash.ToString();
    }
};

struct FUnchangedGeometry
{
    TArray<FVector> SourceVertices;
    TArray<FString> Materials;
    FString SourceHash, RenderHash, ComplexHash;
    int32 RenderLODs = 0, RenderVertices = 0, RenderIndices = 0, QueryMeshes = 0, QueryTriangles = 0;
    const FStaticMeshRenderData* RenderIdentity = nullptr;
};

bool ReadGeometry(UStaticMesh& Mesh, FUnchangedGeometry& Out, FString& Error)
{
    const FMeshDescription* Description = Mesh.GetMeshDescription(0);
    const FStaticMeshRenderData* Render = Mesh.GetRenderData();
    UBodySetup* Body = Mesh.GetBodySetup();
    if (!Description || !Render || !Render->LODResources.Num() || !Body)
    { Error = TEXT("Training mesh requires loaded LOD0 source/render geometry and a BodySetup."); return false; }
    FStaticMeshConstAttributes Attributes(*Description);
    const auto Positions = Attributes.GetVertexPositions();
    FDigest Source;
    for (FVertexID Id : Description->Vertices().GetElementIDs())
    {
        const FVector Position(Positions[Id]);
        if (Position.ContainsNaN()) { Error = TEXT("Source mesh contains a nonfinite vertex."); return false; }
        Out.SourceVertices.Add(Position);
        Source.Add(Id.GetValue()); Source.Vector(Position);
    }
    Out.SourceHash = Source.Finish();
    Out.RenderIdentity = Render;
    Out.RenderLODs = Render->LODResources.Num();
    FDigest RenderDigest;
    for (const FStaticMeshLODResources& LOD : Render->LODResources)
    {
        const auto& P = LOD.VertexBuffers.PositionVertexBuffer;
        const auto& V = LOD.VertexBuffers.StaticMeshVertexBuffer;
        const auto& C = LOD.VertexBuffers.ColorVertexBuffer;
        const int32 IndexCount = int32(LOD.IndexBuffer.GetNumIndices());
        Out.RenderVertices += int32(P.GetNumVertices());
        Out.RenderIndices += IndexCount;
        RenderDigest.Add(P.GetNumVertices()); RenderDigest.Add(V.GetNumTexCoords());
        RenderDigest.Add(C.GetNumVertices()); RenderDigest.Add(LOD.Sections.Num());
        for (uint32 Index = 0; Index < P.GetNumVertices(); ++Index)
        {
            RenderDigest.Vector(FVector(P.VertexPosition(Index)));
            RenderDigest.Add(V.VertexTangentX(Index)); RenderDigest.Add(V.VertexTangentY(Index)); RenderDigest.Add(V.VertexTangentZ(Index));
            for (uint32 UV = 0; UV < V.GetNumTexCoords(); ++UV) RenderDigest.Add(V.GetVertexUV(Index, UV));
        }
        for (uint32 Index = 0; Index < C.GetNumVertices(); ++Index) RenderDigest.Add(C.VertexColor(Index));
        RenderDigest.Add(IndexCount);
        for (int32 Index = 0; Index < IndexCount; ++Index) RenderDigest.Add(LOD.IndexBuffer.GetIndex(Index));
        for (const FStaticMeshSection& Section : LOD.Sections)
        {
            RenderDigest.Add(Section.MaterialIndex); RenderDigest.Add(Section.FirstIndex); RenderDigest.Add(Section.NumTriangles);
            RenderDigest.Add(Section.MinVertexIndex); RenderDigest.Add(Section.MaxVertexIndex); RenderDigest.Add(bool(Section.bEnableCollision));
        }
    }
    Out.RenderHash = RenderDigest.Finish();
    for (const FStaticMaterial& Material : Mesh.GetStaticMaterials())
        Out.Materials.Add(GetPathNameSafe(Material.MaterialInterface) + TEXT("|") + Material.MaterialSlotName.ToString()
            + TEXT("|") + Material.ImportedMaterialSlotName.ToString());
    FDigest Complex;
    Out.QueryMeshes = Body->TriMeshGeometries.Num();
    Complex.Add(Out.QueryMeshes);
    for (const auto& Tri : Body->TriMeshGeometries)
    {
        if (!Tri) { Error = TEXT("Cooked complex collision contains a missing triangle mesh."); return false; }
        const auto& Particles = Tri->Particles();
        const auto& Elements = Tri->Elements();
        const int32 ParticleCount = int32(Particles.Size());
        Complex.Add(ParticleCount); Complex.Add(Elements.GetNumTriangles());
        Out.QueryTriangles += Elements.GetNumTriangles();
        for (int32 Index = 0; Index < ParticleCount; ++Index) Complex.Vector(FVector(Particles.GetX(Index)));
        for (int32 Index = 0; Index < Elements.GetNumTriangles(); ++Index)
        {
            for (int32 Corner = 0; Corner < 3; ++Corner)
            {
                const int32 Vertex = Elements.RequiresLargeIndices()
                    ? int32(Elements.GetLargeIndexBuffer()[Index][Corner]) : int32(Elements.GetSmallIndexBuffer()[Index][Corner]);
                Complex.Add(Vertex);
            }
            Complex.Add(Tri->GetMaterialIndex(Index));
        }
    }
    Out.ComplexHash = Complex.Finish();
    return true;
}

void WriteGeometry(FJsonObject& Report, const TCHAR* Name, const FUnchangedGeometry& Data, const UBodySetup& Body)
{
    auto Row = MakeShared<FJsonObject>();
    Row->SetNumberField(TEXT("source_lod0_vertices"), Data.SourceVertices.Num());
    Row->SetStringField(TEXT("source_lod0_sha1"), Data.SourceHash);
    Row->SetStringField(TEXT("render_buffers_sha1"), Data.RenderHash);
    Row->SetNumberField(TEXT("render_lods"), Data.RenderLODs);
    Row->SetNumberField(TEXT("render_vertices_all_lods"), Data.RenderVertices);
    Row->SetNumberField(TEXT("render_indices_all_lods"), Data.RenderIndices);
    Row->SetStringField(TEXT("cooked_complex_geometry_sha1"), Data.ComplexHash);
    Row->SetNumberField(TEXT("cooked_complex_meshes"), Data.QueryMeshes);
    Row->SetNumberField(TEXT("cooked_complex_triangles"), Data.QueryTriangles);
    Row->SetNumberField(TEXT("authored_convexes"), Body.AggGeom.ConvexElems.Num());
    TArray<TSharedPtr<FJsonValue>> Materials, Authored, Cooked;
    for (const FString& Path : Data.Materials) Materials.Add(MakeShared<FJsonValueString>(Path));
    for (const FKConvexElem& Hull : Body.AggGeom.ConvexElems)
    {
        Authored.Add(MakeShared<FJsonValueNumber>(Hull.VertexData.Num()));
        Cooked.Add(MakeShared<FJsonValueNumber>(Hull.GetChaosConvexMesh() ? Hull.GetChaosConvexMesh()->NumVertices() : 0));
    }
    Row->SetArrayField(TEXT("material_paths_and_slots"), Materials);
    Row->SetArrayField(TEXT("authored_vertices_per_convex"), Authored);
    Row->SetArrayField(TEXT("cooked_vertices_per_convex"), Cooked);
    Report.SetObjectField(Name, Row);
}

bool ReadPoints(const FJsonObject& Job, const TCHAR* Key, TArray<FVector>& Out, FString& Error)
{
    const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
    if (!Job.TryGetArrayField(Key, Values)) { Error = FString::Printf(TEXT("Missing array: %s."), Key); return false; }
    for (const auto& Value : *Values)
    {
        const TArray<TSharedPtr<FJsonValue>>* XYZ = nullptr;
        double X, Y, Z;
        if (!Value || !Value->TryGetArray(XYZ) || XYZ->Num() != 3 || !(*XYZ)[0]->TryGetNumber(X)
            || !(*XYZ)[1]->TryGetNumber(Y) || !(*XYZ)[2]->TryGetNumber(Z)
            || !FMath::IsFinite(X) || !FMath::IsFinite(Y) || !FMath::IsFinite(Z))
        { Error = FString::Printf(TEXT("%s must contain finite numeric [x,y,z] entries."), Key); return false; }
        Out.Emplace(X, Y, Z);
    }
    return true;
}

bool Apply(const FString& JobPath, FJsonObject& Report, FString& Error)
{
    Report.SetStringField(TEXT("asset"), AssetPath);
    Report.SetBoolField(TEXT("asset_saved"), false);
    Report.SetBoolField(TEXT("success"), false);
    if (!IsInGameThread() || !GIsEditor || !GEditor || GEditor->PlayWorld)
    { Error = TEXT("Apply the Training hull on the editor game thread with PIE stopped."); return false; }
    FString Text;
    TSharedPtr<FJsonObject> Job;
    if (!FFileHelper::LoadFileToString(Text, *JobPath)
        || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Job) || !Job)
    { Error = TEXT("Could not read the hull job JSON."); return false; }
    FString Target;
    TArray<FVector> ExpectedSource, Points;
    if (!Job->TryGetStringField(TEXT("asset"), Target) || Target != AssetPath)
    { Error = TEXT("Hull job must name only the exact Training mesh object path."); return false; }
    if (!ReadPoints(*Job, TEXT("source_vertices"), ExpectedSource, Error) || !ReadPoints(*Job, TEXT("hull_vertices"), Points, Error)) return false;
    if (Points.Num() < 4 || Points.Num() > 128)
    { Error = TEXT("Explicit hull requires 4..128 finite input points; no automatic decomposition or simplification is selected."); return false; }
    UStaticMesh* Mesh = LoadObject<UStaticMesh>(nullptr, AssetPath);
    if (!Mesh || Mesh->IsCompiling() || Mesh->GetOutermost()->IsDirty())
    { Error = TEXT("Training mesh must exist, finish compilation, and have no unsaved changes."); return false; }
    UBodySetup* Body = Mesh->GetBodySetup();
    if (!Body || Body->GetOuter() != Mesh || Body->bSharedCookedData || Body->AggGeom.GetElementCount() != 1
        || Body->AggGeom.ConvexElems.Num() != 1 || Body->GetCollisionTraceFlag() != CTF_UseSimpleAndComplex
        || !Body->AggGeom.ConvexElems[0].GetTransform().Equals(FTransform::Identity, 0.0))
    { Error = TEXT("Expected one identity-frame Training convex, owned BodySetup, unshared cooking, and SimpleAndComplex trace policy."); return false; }
    Body->CreatePhysicsMeshes();
    FUnchangedGeometry Before;
    if (!ReadGeometry(*Mesh, Before, Error)) return false;
    WriteGeometry(Report, TEXT("before"), Before, *Body);
    if (ExpectedSource != Before.SourceVertices)
    { Error = TEXT("Job LOD0 source vertices differ from the current Training asset (exact order and float-expanded coordinates required)."); return false; }
    if (!Before.QueryMeshes || !Before.QueryTriangles)
    { Error = TEXT("Expected the existing complex query triangles to remain present."); return false; }
    FProperty* AggProperty = FindFProperty<FProperty>(UBodySetup::StaticClass(), GET_MEMBER_NAME_CHECKED(UBodySetup, AggGeom));
    if (!AggProperty) { Error = TEXT("AggGeom editor notification property is unavailable."); return false; }
    FScopedTransaction Transaction(NSLOCTEXT("Prophecy", "TrainingSwordSimpleHull", "Replace Training Sword Simple Collision Hull"));
    Mesh->Modify(); Body->Modify();
    const FKConvexElem Original = Body->AggGeom.ConvexElems[0];
    const auto RecookAndNotify = [&]()
    {
        Body->InvalidatePhysicsData();
        Body->CreatePhysicsMeshes();
        // BodySetup's scoped AggGeom notification recreates only matching component physics states.
        // Mesh->PostEditChange() would rebuild render geometry and is intentionally unnecessary here.
        FPropertyChangedEvent Changed(AggProperty, EPropertyChangeType::ValueSet);
        Body->PostEditChangeProperty(Changed);
        Mesh->CreateNavCollision(true);
        FEditorSupportDelegates::RedrawAllViewports.Broadcast();
    };
    FKConvexElem& Hull = Body->AggGeom.ConvexElems[0];
    Hull.VertexData = Points;
    Hull.IndexData.Reset(); // Derived hull topology must not retain the old 309-vertex indices.
    Hull.UpdateElemBox();
    RecookAndNotify();
    FUnchangedGeometry After;
    const bool bReadAfter = ReadGeometry(*Mesh, After, Error);
    if (bReadAfter) WriteGeometry(Report, TEXT("after"), After, *Body);
    const auto& Cooked = Hull.GetChaosConvexMesh();
    const bool bHullValid = Cooked && Cooked->IsValidGeometry() && Cooked->NumVertices() >= 4 && Cooked->NumVertices() <= 128
        && FMath::IsFinite(Cooked->GetVolume()) && Cooked->GetVolume() > 0.0 && !FVector(Cooked->GetCenterOfMass()).ContainsNaN();
    const bool bUnchanged = bReadAfter && Before.SourceVertices == After.SourceVertices && Before.SourceHash == After.SourceHash
        && Before.RenderIdentity == After.RenderIdentity && Before.RenderHash == After.RenderHash
        && Before.Materials == After.Materials && Before.ComplexHash == After.ComplexHash;
    Report.SetBoolField(TEXT("source_render_materials_complex_query_unchanged"), bUnchanged);
    Report.SetBoolField(TEXT("cooked_simple_hull_valid"), bHullValid);
    if (!bUnchanged || !bHullValid)
    {
        Body->AggGeom.ConvexElems[0] = Original;
        RecookAndNotify();
        Transaction.Cancel();
        // The package was clean on entry; restore its dirty state only after verifying restoration.
        FUnchangedGeometry Restored;
        FString RestoreError;
        const bool bRestored = ReadGeometry(*Mesh, Restored, RestoreError) && Restored.SourceHash == Before.SourceHash
            && Restored.RenderHash == Before.RenderHash && Restored.ComplexHash == Before.ComplexHash && Restored.Materials == Before.Materials
            && Body->AggGeom.ConvexElems[0].VertexData == Original.VertexData && Body->AggGeom.ConvexElems[0].GetChaosConvexMesh();
        Report.SetBoolField(TEXT("rolled_back"), bRestored);
        if (bRestored) Mesh->GetOutermost()->SetDirtyFlag(false);
        if (Error.IsEmpty()) Error = TEXT("Hull cooking or preservation validation failed; inspect rollback status. Asset was not saved.");
        return false;
    }
    Mesh->MarkPackageDirty();
    Report.SetNumberField(TEXT("cooked_hull_volume_cm3"), Cooked->GetVolume());
    Report.SetBoolField(TEXT("package_dirty_after"), Mesh->GetOutermost()->IsDirty());
    Report.SetBoolField(TEXT("success"), true);
    return true;
}

void Command(const TArray<FString>& Args)
{
    if (Args.Num() != 2 || FPaths::IsRelative(Args[0]) || FPaths::IsRelative(Args[1]) || FPaths::FileExists(Args[1]))
    { UE_LOG(LogTemp, Error, TEXT("Prophecy.Sword.ApplyTrainingHull requires an absolute job path and a new absolute report path.")); return; }
    auto Report = MakeShared<FJsonObject>();
    FString Error;
    const bool bSucceeded = Apply(Args[0], *Report, Error);
    Report->SetStringField(TEXT("error"), Error);
    FString Text;
    const bool bSerialized = FJsonSerializer::Serialize(Report, TJsonWriterFactory<>::Create(&Text));
    const bool bSavedReport = bSerialized && FFileHelper::SaveStringToFile(Text, *Args[1], FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM,
        &IFileManager::Get(), FILEWRITE_NoReplaceExisting);
    if (!bSucceeded || !bSavedReport)
    {
        UE_LOG(LogTemp, Error, TEXT("Training hull command failed: %s; report_written=%d. No asset was saved."), *Error, bSavedReport);
    }
    else
    {
        UE_LOG(LogTemp, Display, TEXT("Training hull validated and left unsaved; report=%s. Save only the Training asset after review."), *Args[1]);
    }
}
FAutoConsoleCommand ConsoleCommand(TEXT("Prophecy.Sword.ApplyTrainingHull"),
    TEXT("Replace only the existing Training simple convex from explicit JSON points; absolute job/report paths; never saves assets."),
    FConsoleCommandWithArgsDelegate::CreateStatic(&Command));
}
