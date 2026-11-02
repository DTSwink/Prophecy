#include "CoreMinimal.h"
#include "HAL/IConsoleManager.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshAttributes.h"
#include "MeshDescription.h"
#include "PhysicsEngine/BodySetup.h"
#include "Materials/MaterialInterface.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "AssetRegistry/AssetRegistryModule.h"

// Offline import of the licensed GLB and its closed, precomputed Voronoi pieces.
static FAutoConsoleCommand OilBottleBake(TEXT("Prophecy.Oil.BakeBottle"),TEXT("Bake prepared oil bottle geometry in the owned setup process."),
FConsoleCommandDelegate::CreateLambda([]
{
    if(!FParse::Param(FCommandLine::Get(),TEXT("ProphecyOilBottleSetup")))return;
    FString Text;TSharedPtr<FJsonObject> Root;
    const FString File=FPaths::ProjectSavedDir()/TEXT("Diagnostics/Oil/Bottle/geometry.json");
    if(!FFileHelper::LoadFileToString(Text,*File) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root))return;
    TArray<FStaticMaterial> Materials;
    for(const auto& M:Root->GetArrayField(TEXT("materials")))
    {
        auto* Material=LoadObject<UMaterialInterface>(nullptr,*M->AsString());if(!Material)return;
        Materials.Emplace(Material,FName(*FString::Printf(TEXT("Slot%d"),Materials.Num())));
    }
    for(const auto& Value:Root->GetArrayField(TEXT("meshes")))
    {
        const auto Data=Value->AsObject();const FString Name=Data->GetStringField(TEXT("name"));
        const FString Folder=Name==TEXT("SM_OilBottle")?TEXT("Meshes/"):TEXT("Debris/");
        const FString Path=TEXT("/Game/_mygame/OilBottle/")+Folder+Name;
        auto* Mesh=LoadObject<UStaticMesh>(nullptr,*(Path+TEXT(".")+Name),nullptr,LOAD_NoWarn);
        const bool bNew=!Mesh;
        if(!Mesh)Mesh=NewObject<UStaticMesh>(CreatePackage(*Path),*Name,RF_Public|RF_Standalone);
        Mesh->GetStaticMaterials()=Materials;
        FMeshDescription Description;FStaticMeshAttributes A(Description);A.Register();
        auto P=A.GetVertexPositions();auto N=A.GetVertexInstanceNormals();auto UV=A.GetVertexInstanceUVs();UV.SetNumChannels(1);
        const auto& Vertices=Data->GetArrayField(TEXT("vertices"));TArray<FVertexID> IDs;TArray<FVector> Hull;
        for(const auto& Row:Vertices)
        {
            const auto& V=Row->AsArray();auto ID=Description.CreateVertex();IDs.Add(ID);
            P[ID]=FVector3f(V[0]->AsNumber(),V[1]->AsNumber(),V[2]->AsNumber());
        }
        TArray<FPolygonGroupID> Groups;
        for(const auto& Material:Materials)
        {auto Group=Description.CreatePolygonGroup();Groups.Add(Group);A.GetPolygonGroupMaterialSlotNames()[Group]=Material.MaterialSlotName;}
        const auto& Tri=Data->GetArrayField(TEXT("triangles"));const auto& Slots=Data->GetArrayField(TEXT("slots"));
        for(int32 T=0;T<Tri.Num();T+=3)
        {
            TArray<FVertexInstanceID> Corners;
            for(int32 C=0;C<3;++C)
            {
                const int32 Index=Tri[T+C]->AsNumber();const auto& V=Vertices[Index]->AsArray();
                auto ID=Description.CreateVertexInstance(IDs[Index]);Corners.Add(ID);
                N[ID]=FVector3f(V[3]->AsNumber(),V[4]->AsNumber(),V[5]->AsNumber());
                UV.Set(ID,0,FVector2f(V[6]->AsNumber(),V[7]->AsNumber()));A.GetVertexInstanceColors()[ID]=FVector4f(1,1,1,1);
            }
            Description.CreatePolygon(Groups[int32(Slots[T/3]->AsNumber())],Corners);
        }
        if(Mesh->GetNumSourceModels()==0)Mesh->AddSourceModel();auto& Settings=Mesh->GetSourceModel(0).BuildSettings;
        Settings.bRecomputeNormals=false;Settings.bRecomputeTangents=true;Settings.bGenerateLightmapUVs=false;
        Mesh->CreateMeshDescription(0,MoveTemp(Description));Mesh->CommitMeshDescription(0);
        Mesh->CreateBodySetup();auto* Body=Mesh->GetBodySetup();Body->InvalidatePhysicsData();Body->AggGeom.EmptyElements();
        for(const auto& Row:Data->GetArrayField(TEXT("hull")))
        {const auto& V=Row->AsArray();Hull.Emplace(V[0]->AsNumber(),V[1]->AsNumber(),V[2]->AsNumber());}
        FKConvexElem Convex;Convex.VertexData=MoveTemp(Hull);Convex.UpdateElemBox();Body->AggGeom.ConvexElems.Add(MoveTemp(Convex));
        Body->CollisionTraceFlag=CTF_UseSimpleAsComplex;
        Mesh->Build(false);Body->CreatePhysicsMeshes();if(bNew)FAssetRegistryModule::AssetCreated(Mesh);Mesh->MarkPackageDirty();
    }
    UE_LOG(LogTemp,Display,TEXT("Oil bottle: baked %d meshes."),Root->GetArrayField(TEXT("meshes")).Num());
}));
