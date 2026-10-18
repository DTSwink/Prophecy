#include "ProphecyBombLibrary.h"
#if WITH_EDITOR
#include "Engine/StaticMesh.h"
#include "StaticMeshAttributes.h"
#include "MeshDescription.h"
#include "PhysicsEngine/BodySetup.h"
#include "Materials/MaterialInterface.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#endif

TArray<UStaticMesh*> UProphecyBombLibrary::PrepareBombMeshes(const FString& GeometryFile)
{
    TArray<UStaticMesh*> Result;
#if WITH_EDITOR
    FString Text;TSharedPtr<FJsonObject> Root;
    if(!FFileHelper::LoadFileToString(Text,*GeometryFile) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Root))return Result;
    auto* Source=LoadObject<UStaticMesh>(nullptr,*(Root->GetStringField(TEXT("source"))));
    if(!Source)return Result;
    for(const auto& Item:Root->GetArrayField(TEXT("meshes")))
    {
        const auto Data=Item->AsObject();const FString Name=Data->GetStringField(TEXT("name"));
        const FString Path=TEXT("/Game/_mygame/BombGenerated/")+Name;
        auto* Existing=LoadObject<UStaticMesh>(nullptr,*(Path+TEXT(".")+Name),nullptr,LOAD_NoWarn);
        auto* Package=CreatePackage(*Path);
        auto* Mesh=Existing?Existing:NewObject<UStaticMesh>(Package,*Name,RF_Public|RF_Standalone);
        Mesh->GetStaticMaterials()=Source->GetStaticMaterials();
        FMeshDescription Description;FStaticMeshAttributes Attributes(Description);Attributes.Register();
        auto Positions=Attributes.GetVertexPositions();auto Normals=Attributes.GetVertexInstanceNormals();
        auto UVs=Attributes.GetVertexInstanceUVs();UVs.SetNumChannels(2);
        auto Tangents=Attributes.GetVertexInstanceTangents();auto Signs=Attributes.GetVertexInstanceBinormalSigns();auto Colors=Attributes.GetVertexInstanceColors();
        const auto& Vertices=Data->GetArrayField(TEXT("vertices"));TArray<FVertexID> IDs;
        TArray<FVector> Hull;
        for(const auto& Value:Vertices)
        {
            const auto& V=Value->AsArray();const FVertexID ID=Description.CreateVertex();IDs.Add(ID);
            Positions[ID]=FVector3f(V[0]->AsNumber(),V[1]->AsNumber(),V[2]->AsNumber());Hull.Add(FVector(Positions[ID]));
        }
        const FPolygonGroupID Group=Description.CreatePolygonGroup();
        Attributes.GetPolygonGroupMaterialSlotNames()[Group]=Mesh->GetStaticMaterials()[0].MaterialSlotName;
        const auto& Triangles=Data->GetArrayField(TEXT("triangles"));
        for(int32 T=0;T<Triangles.Num();T+=3)
        {
            TArray<FVertexInstanceID> Corners;
            for(int32 C=0;C<3;++C)
            {
                const int32 Index=Triangles[T+C]->AsNumber();const auto& V=Vertices[Index]->AsArray();
                auto ID=Description.CreateVertexInstance(IDs[Index]);Corners.Add(ID);
                Normals[ID]=FVector3f(V[3]->AsNumber(),V[4]->AsNumber(),V[5]->AsNumber());
                UVs.Set(ID,0,FVector2f(V[6]->AsNumber(),V[7]->AsNumber()));
                UVs.Set(ID,1,FVector2f(V[12]->AsNumber(),0));
                Tangents[ID]=FVector3f(V[8]->AsNumber(),V[9]->AsNumber(),V[10]->AsNumber());
                Signs[ID]=V[11]->AsNumber();Colors[ID]=FVector4f(1,1,1,1);
            }
            Description.CreatePolygon(Group,Corners);
        }
        if(Mesh->GetNumSourceModels()==0)Mesh->AddSourceModel();auto& Settings=Mesh->GetSourceModel(0).BuildSettings;
        Settings.bRecomputeNormals=false;Settings.bRecomputeTangents=false;Settings.bGenerateLightmapUVs=false;
        Mesh->CreateMeshDescription(0,MoveTemp(Description));Mesh->CommitMeshDescription(0);
        Mesh->CreateBodySetup();auto* Body=Mesh->GetBodySetup();
        Body->InvalidatePhysicsData();Body->AggGeom.EmptyElements();
        if(Data->GetBoolField(TEXT("whole")) && Source->GetBodySetup())Body->CopyBodyPropertiesFrom(Source->GetBodySetup());
        else
        {
            FKConvexElem Convex;Convex.VertexData=MoveTemp(Hull);Convex.UpdateElemBox();Body->AggGeom.ConvexElems.Add(MoveTemp(Convex));
            Body->CollisionTraceFlag=CTF_UseSimpleAsComplex;
        }
        Mesh->Build(false);Body->CreatePhysicsMeshes();Mesh->MarkPackageDirty();Result.Add(Mesh);
    }
#endif
    return Result;
}
