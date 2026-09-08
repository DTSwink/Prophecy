#include "CoreMinimal.h"
#include "AssetToolsModule.h"
#include "IAssetTools.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshAttributes.h"
#include "PhysicsEngine/BodySetup.h"
#include "HAL/IConsoleManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Engine/Blueprint.h"
#include "EdGraph/EdGraph.h"
#include "EdGraph/EdGraphNode.h"
#include "EdGraph/EdGraphPin.h"

namespace
{
void BakeTrainingSword()
{
	const TCHAR* Destination = TEXT("/Game/_mygame/sword/geometry/Sword_GL01_Training");
	if (LoadObject<UStaticMesh>(nullptr, Destination))
	{
		UE_LOG(LogTemp, Warning, TEXT("Training sword mesh already exists; refusing to overwrite it."));
		return;
	}
	FString Text;
	TSharedPtr<FJsonObject> Job;
	if (!FFileHelper::LoadFileToString(Text, *(FPaths::ProjectSavedDir() / TEXT("Sword/exact_mesh_job.json"))) ||
		!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Job) || !Job) return;
	UStaticMesh* Source = LoadObject<UStaticMesh>(nullptr, TEXT("/Game/_mygame/sword/geometry/Sword_GL01"));
	if (!Source) return;
	FMatrix44f Linear = FMatrix44f::Identity;
	const auto& Rows = Job->GetArrayField(TEXT("basis"));
	if (Rows.Num() != 3) return;
	for (int32 I=0; I<3; ++I)
	{
		const auto& Row = Rows[I]->AsArray();
		if (Row.Num() != 3) return;
		for (int32 J=0; J<3; ++J) Linear.M[I][J] = float(Row[J]->AsNumber());
	}
	const FMatrix44f NormalMatrix = Linear.Inverse().GetTransposed();
	UStaticMesh* Mesh = Cast<UStaticMesh>(FModuleManager::LoadModuleChecked<FAssetToolsModule>(TEXT("AssetTools")).Get().DuplicateAsset(
		TEXT("Sword_GL01_Training"), TEXT("/Game/_mygame/sword/geometry"), Source));
	if (!Mesh) return;
	TArray<FVector> CollisionVertices;
	for (int32 LOD=0; LOD<Mesh->GetNumSourceModels(); ++LOD)
	{
		FMeshDescription* Description = Mesh->GetMeshDescription(LOD);
		if (!Description) continue;
		FStaticMeshAttributes Attributes(*Description);
		auto Positions = Attributes.GetVertexPositions();
		auto Normals = Attributes.GetVertexInstanceNormals();
		auto Tangents = Attributes.GetVertexInstanceTangents();
		for (FVertexID V : Description->Vertices().GetElementIDs())
		{
			Positions[V] = FVector3f(Linear.TransformPosition(Positions[V]));
			if (LOD == 0) CollisionVertices.Add(FVector(Positions[V]));
		}
		for (FVertexInstanceID V : Description->VertexInstances().GetElementIDs())
		{
			Normals[V] = FVector3f(NormalMatrix.TransformVector(Normals[V])).GetSafeNormal();
			FVector3f T = FVector3f(Linear.TransformVector(Tangents[V]));
			Tangents[V] = (T - Normals[V] * FVector3f::DotProduct(T, Normals[V])).GetSafeNormal();
		}
		Mesh->CommitMeshDescription(LOD);
		Mesh->GetSourceModel(LOD).BuildSettings.bRecomputeNormals = false;
		Mesh->GetSourceModel(LOD).BuildSettings.bRecomputeTangents = false;
	}
	// A new convex collision hull follows the baked geometry. The original sword
	// mesh, its collider, materials and user Blueprint are never edited.
	Mesh->CreateBodySetup();
	UBodySetup* Body = Mesh->GetBodySetup();
	Body->AggGeom.EmptyElements();
	FKConvexElem& Hull = Body->AggGeom.ConvexElems.AddDefaulted_GetRef();
	Hull.VertexData = CollisionVertices;
	Hull.UpdateElemBox();
	Body->CollisionTraceFlag = CTF_UseSimpleAndComplex;
	Body->InvalidatePhysicsData();
	Body->CreatePhysicsMeshes();
	Mesh->Build(false);
	Mesh->PostEditChange();
	Mesh->MarkPackageDirty();
	UE_LOG(LogTemp, Display, TEXT("Training sword baked: %d vertices. Save only %s after verification."), CollisionVertices.Num(), Destination);
}
FAutoConsoleCommand BakeCommand(TEXT("Prophecy.Sword.BakeTrainingMesh"),
	TEXT("Create an exact training-space sword copy from Saved/Sword/exact_mesh_job.json; never overwrite."),
	FConsoleCommandDelegate::CreateStatic(&BakeTrainingSword));

void InspectSwordBlueprint()
{
	UBlueprint* BP = LoadObject<UBlueprint>(nullptr, TEXT("/Game/_mygame/sword/A_Sword"));
	if (!BP) return;
	TArray<UEdGraph*> Graphs;
	BP->GetAllGraphs(Graphs);
	for (const UEdGraph* Graph : Graphs)
	for (const UEdGraphNode* Node : Graph->Nodes)
	{
		UE_LOG(LogTemp, Display, TEXT("SwordGraph %s %s: %s"), *Graph->GetName(), *Node->GetName(),
			*Node->GetNodeTitle(ENodeTitleType::ListView).ToString());
		for (const UEdGraphPin* Pin : Node->Pins)
		{
			FString Links;
			for (const UEdGraphPin* Other : Pin->LinkedTo) Links += Other->GetOwningNode()->GetName() + TEXT(".") + Other->PinName.ToString() + TEXT(" ");
			UE_LOG(LogTemp, Display, TEXT("SwordPin %s %s = %s -> %s"), *Node->GetName(), *Pin->PinName.ToString(), *Pin->DefaultValue, *Links);
		}
	}
}
FAutoConsoleCommand InspectCommand(TEXT("Prophecy.Sword.InspectBlueprint"), TEXT("Read-only graph inventory for the existing sword Blueprint."),
	FConsoleCommandDelegate::CreateStatic(&InspectSwordBlueprint));
}
