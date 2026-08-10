#include "Components/StaticMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Editor.h"
#include "Engine/Selection.h"
#include "Engine/StaticMesh.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Interface_CollisionDataProviderCore.h"
#include "LandscapeComponent.h"
#include "LandscapeProxy.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "PhysicsEngine/AggregateGeom.h"
#include "PhysicsEngine/BodySetup.h"
#include "Policies/PrettyJsonPrintPolicy.h"
#include "Serialization/JsonWriter.h"

DEFINE_LOG_CATEGORY_STATIC(LogProphecySimCollisionExport, Log, All);

namespace {

// Snapshot units are fixed at meters so the standalone core never inherits UE centimeters.
constexpr double CentimetersToMeters = 0.01;
constexpr int32 SphereLatitudeSegments = 8;
constexpr int32 RoundShapeSlices = 12;
constexpr int32 CapsuleHemisphereSegments = 5;

struct FExportedCollisionObject
{
	FString StableId;
	FString Label;
	FString ActorClass;
	FString Component;
	FString CollisionSource;
	TArray<FVector> Vertices;
	TArray<FIntVector> Indices;
};

void AddTriangle(FExportedCollisionObject& Object, const FVector& First, const FVector& Second, const FVector& Third)
{
	const int32 Base = Object.Vertices.Num();
	Object.Vertices.Add(First);
	Object.Vertices.Add(Second);
	Object.Vertices.Add(Third);
	Object.Indices.Emplace(Base, Base + 1, Base + 2);
}

FVector SpherePoint(const double Latitude, const double Longitude, const double Radius)
{
	const double RingRadius = FMath::Cos(Latitude) * Radius;
	return FVector(
		RingRadius * FMath::Cos(Longitude),
		RingRadius * FMath::Sin(Longitude),
		FMath::Sin(Latitude) * Radius);
}

void AddSphere(FExportedCollisionObject& Object, const FTransform& ShapeToWorld, const double Radius)
{
	for (int32 LatitudeIndex = 0; LatitudeIndex < SphereLatitudeSegments; ++LatitudeIndex)
	{
		const double Latitude0 = -UE_HALF_PI + UE_PI * static_cast<double>(LatitudeIndex) / SphereLatitudeSegments;
		const double Latitude1 = -UE_HALF_PI + UE_PI * static_cast<double>(LatitudeIndex + 1) / SphereLatitudeSegments;
		for (int32 Slice = 0; Slice < RoundShapeSlices; ++Slice)
		{
			const double Longitude0 = UE_TWO_PI * static_cast<double>(Slice) / RoundShapeSlices;
			const double Longitude1 = UE_TWO_PI * static_cast<double>(Slice + 1) / RoundShapeSlices;
			const FVector First = ShapeToWorld.TransformPosition(SpherePoint(Latitude0, Longitude0, Radius));
			const FVector Second = ShapeToWorld.TransformPosition(SpherePoint(Latitude0, Longitude1, Radius));
			const FVector Third = ShapeToWorld.TransformPosition(SpherePoint(Latitude1, Longitude0, Radius));
			const FVector Fourth = ShapeToWorld.TransformPosition(SpherePoint(Latitude1, Longitude1, Radius));
			AddTriangle(Object, First, Second, Third);
			AddTriangle(Object, Second, Fourth, Third);
		}
	}
}

void AddBox(FExportedCollisionObject& Object, const FTransform& ShapeToWorld, const FVector& Extent)
{
	const FVector Corners[] = {
		{-Extent.X, -Extent.Y, -Extent.Z}, {Extent.X, -Extent.Y, -Extent.Z},
		{Extent.X, Extent.Y, -Extent.Z}, {-Extent.X, Extent.Y, -Extent.Z},
		{-Extent.X, -Extent.Y, Extent.Z}, {Extent.X, -Extent.Y, Extent.Z},
		{Extent.X, Extent.Y, Extent.Z}, {-Extent.X, Extent.Y, Extent.Z}};
	const int32 Faces[][3] = {
		{0, 2, 1}, {0, 3, 2}, {4, 5, 6}, {4, 6, 7},
		{0, 1, 5}, {0, 5, 4}, {1, 2, 6}, {1, 6, 5},
		{2, 3, 7}, {2, 7, 6}, {3, 0, 4}, {3, 4, 7}};
	for (const int32 (&Face)[3] : Faces)
	{
		AddTriangle(Object,
			ShapeToWorld.TransformPosition(Corners[Face[0]]),
			ShapeToWorld.TransformPosition(Corners[Face[1]]),
			ShapeToWorld.TransformPosition(Corners[Face[2]]));
	}
}

void AddCapsule(FExportedCollisionObject& Object, const FTransform& ShapeToWorld,
	const double Radius, const double CylinderLength)
{
	struct FProfilePoint
	{
		double RingRadius;
		double Height;
	};
	TArray<FProfilePoint> Profile;
	const double HalfCylinder = CylinderLength * 0.5;
	Profile.Add({0.0, -HalfCylinder - Radius});
	for (int32 Segment = 1; Segment <= CapsuleHemisphereSegments; ++Segment)
	{
		const double Angle = -UE_HALF_PI + UE_HALF_PI * static_cast<double>(Segment) / CapsuleHemisphereSegments;
		Profile.Add({FMath::Cos(Angle) * Radius, -HalfCylinder + FMath::Sin(Angle) * Radius});
	}
	if (CylinderLength > UE_SMALL_NUMBER)
	{
		Profile.Add({Radius, HalfCylinder});
	}
	for (int32 Segment = 1; Segment <= CapsuleHemisphereSegments; ++Segment)
	{
		const double Angle = UE_HALF_PI * static_cast<double>(Segment) / CapsuleHemisphereSegments;
		Profile.Add({FMath::Cos(Angle) * Radius, HalfCylinder + FMath::Sin(Angle) * Radius});
	}

	for (int32 Ring = 0; Ring + 1 < Profile.Num(); ++Ring)
	{
		for (int32 Slice = 0; Slice < RoundShapeSlices; ++Slice)
		{
			const double Angle0 = UE_TWO_PI * static_cast<double>(Slice) / RoundShapeSlices;
			const double Angle1 = UE_TWO_PI * static_cast<double>(Slice + 1) / RoundShapeSlices;
			const FProfilePoint& Lower = Profile[Ring];
			const FProfilePoint& Upper = Profile[Ring + 1];
			const FVector First = ShapeToWorld.TransformPosition(
				{Lower.RingRadius * FMath::Cos(Angle0), Lower.RingRadius * FMath::Sin(Angle0), Lower.Height});
			const FVector Second = ShapeToWorld.TransformPosition(
				{Lower.RingRadius * FMath::Cos(Angle1), Lower.RingRadius * FMath::Sin(Angle1), Lower.Height});
			const FVector Third = ShapeToWorld.TransformPosition(
				{Upper.RingRadius * FMath::Cos(Angle0), Upper.RingRadius * FMath::Sin(Angle0), Upper.Height});
			const FVector Fourth = ShapeToWorld.TransformPosition(
				{Upper.RingRadius * FMath::Cos(Angle1), Upper.RingRadius * FMath::Sin(Angle1), Upper.Height});
			AddTriangle(Object, First, Second, Third);
			AddTriangle(Object, Second, Fourth, Third);
		}
	}
}

FTransform WithoutScale(FTransform Transform)
{
	Transform.SetScale3D(FVector::OneVector);
	return Transform;
}

bool AddSimpleCollision(const FTransform& ComponentToWorld, const FString& SourcePath,
    const UBodySetup& BodySetup,
	FExportedCollisionObject& Object, TArray<FString>& Warnings)
{
	const FKAggregateGeom& Geometry = BodySetup.AggGeom;
	const FVector Scale = ComponentToWorld.GetScale3D();
	const FTransform ComponentWithoutScale = WithoutScale(ComponentToWorld);
	const int32 FirstTriangle = Object.Indices.Num();

	for (const FKSphereElem& Element : Geometry.SphereElems)
	{
		const FKSphereElem Scaled = Element.GetFinalScaled(Scale, FTransform::Identity);
		AddSphere(Object, Scaled.GetTransform() * ComponentWithoutScale, Scaled.Radius);
	}
	for (const FKBoxElem& Element : Geometry.BoxElems)
	{
		const FKBoxElem Scaled = Element.GetFinalScaled(Scale, FTransform::Identity);
		AddBox(Object, Scaled.GetTransform() * ComponentWithoutScale,
			FVector(Scaled.X, Scaled.Y, Scaled.Z) * 0.5);
	}
	for (const FKSphylElem& Element : Geometry.SphylElems)
	{
		const FKSphylElem Scaled = Element.GetFinalScaled(Scale, FTransform::Identity);
		AddCapsule(Object, Scaled.GetTransform() * ComponentWithoutScale, Scaled.Radius, Scaled.Length);
	}
	for (const FKConvexElem& Element : Geometry.ConvexElems)
	{
		const int32 VertexBase = Object.Vertices.Num();
		const FTransform ElementToWorld = Element.GetTransform() * ComponentToWorld;
		for (const FVector& Vertex : Element.VertexData)
		{
			Object.Vertices.Add(ElementToWorld.TransformPosition(Vertex));
		}
		const TArray<int32> ConvexIndices = Element.IndexData.Num() > 0
			? Element.IndexData
			: Element.GetChaosConvexIndices();
		for (int32 Index = 0; Index + 2 < ConvexIndices.Num(); Index += 3)
		{
			Object.Indices.Emplace(VertexBase + ConvexIndices[Index],
				VertexBase + ConvexIndices[Index + 1], VertexBase + ConvexIndices[Index + 2]);
		}
	}

	const int32 UnsupportedCount = Geometry.TaperedCapsuleElems.Num() + Geometry.LevelSetElems.Num() +
		Geometry.SkinnedLevelSetElems.Num() + Geometry.MLLevelSetElems.Num() +
		Geometry.SkinnedTriangleMeshElems.Num();
	if (UnsupportedCount > 0)
	{
		Warnings.Add(FString::Printf(TEXT("%s: %d unsupported simple collision element(s) were not exported."),
			*SourcePath, UnsupportedCount));
	}
	return Object.Indices.Num() > FirstTriangle;
}

bool AddComplexCollision(const FTransform& ComponentToWorld, UStaticMesh& StaticMesh,
	FExportedCollisionObject& Object)
{
	FTriMeshCollisionData CollisionData;
	if (!StaticMesh.GetPhysicsTriMeshData(&CollisionData, true) || CollisionData.Indices.IsEmpty())
	{
		return false;
	}
	const int32 VertexBase = Object.Vertices.Num();
	for (const FVector3f& Vertex : CollisionData.Vertices)
	{
		Object.Vertices.Add(ComponentToWorld.TransformPosition(FVector(Vertex)));
	}
	for (const FTriIndices& Triangle : CollisionData.Indices)
	{
		Object.Indices.Emplace(VertexBase + Triangle.v0, VertexBase + Triangle.v1, VertexBase + Triangle.v2);
	}
	return true;
}

FExportedCollisionObject MakeObject(const AActor& Actor, const FString& ComponentName, const FString& Source)
{
	FExportedCollisionObject Object;
	Object.StableId = Actor.GetActorGuid().ToString(EGuidFormats::DigitsWithHyphensLower) + TEXT(":") + ComponentName;
	Object.Label = Actor.GetActorLabel();
	Object.ActorClass = Actor.GetClass()->GetPathName();
	Object.Component = ComponentName;
	Object.CollisionSource = Source;
	return Object;
}

void ExportStaticMeshComponent(AActor& Actor, UStaticMeshComponent& Component,
	TArray<FExportedCollisionObject>& Objects, TArray<FString>& Warnings,
	const bool ForceUnderlyingComplex)
{
	if (!ForceUnderlyingComplex && Component.GetCollisionEnabled() == ECollisionEnabled::NoCollision)
	{
		return;
	}
	UStaticMesh* StaticMesh = Component.GetStaticMesh();
	UBodySetup* BodySetup = StaticMesh != nullptr ? StaticMesh->GetBodySetup() : nullptr;
	if (StaticMesh == nullptr || (!ForceUnderlyingComplex && BodySetup == nullptr))
	{
		Warnings.Add(Component.GetPathName() + (StaticMesh == nullptr
			? TEXT(": no static mesh.") : TEXT(": no static mesh body setup.")));
		return;
	}

	ECollisionTraceFlag TraceFlag = CTF_UseDefault;
	if (BodySetup != nullptr)
	{
		TraceFlag = BodySetup->GetCollisionTraceFlag();
	}
	const bool ForceComplex = ForceUnderlyingComplex || TraceFlag == CTF_UseComplexAsSimple;
	FExportedCollisionObject Object = MakeObject(Actor, Component.GetName(),
		ForceUnderlyingComplex ? TEXT("complex_forced")
			: (ForceComplex ? TEXT("complex_as_simple") : TEXT("simple")));
	bool Exported = false;
	if (ForceComplex)
	{
		Exported = AddComplexCollision(Component.GetComponentTransform(), *StaticMesh, Object);
	}
	else
	{
		Exported = AddSimpleCollision(Component.GetComponentTransform(), Component.GetPathName(),
			*BodySetup, Object, Warnings);
		if (!Exported && TraceFlag != CTF_UseSimpleAsComplex)
		{
			Object.CollisionSource = TEXT("complex_fallback_no_simple");
			Exported = AddComplexCollision(Component.GetComponentTransform(), *StaticMesh, Object);
		}
	}
	if (Exported)
	{
		Objects.Add(MoveTemp(Object));
	}
	else
	{
		Warnings.Add(Component.GetPathName() + TEXT(": no supported collision triangles were exported."));
	}
}

void ExportInstancedStaticMeshComponent(AActor& Actor, UInstancedStaticMeshComponent& Component,
	TArray<FExportedCollisionObject>& Objects, TArray<FString>& Warnings,
	const bool ForceUnderlyingComplex)
{
	UStaticMesh* StaticMesh = Component.GetStaticMesh();
	UBodySetup* BodySetup = StaticMesh != nullptr ? StaticMesh->GetBodySetup() : nullptr;
	if (StaticMesh == nullptr || (!ForceUnderlyingComplex && BodySetup == nullptr))
	{
		Warnings.Add(Component.GetPathName() + (StaticMesh == nullptr
			? TEXT(": no static mesh.") : TEXT(": no static mesh body setup.")));
		return;
	}

	ECollisionTraceFlag TraceFlag = CTF_UseDefault;
	if (BodySetup != nullptr)
	{
		TraceFlag = BodySetup->GetCollisionTraceFlag();
	}
	const bool ForceComplex = ForceUnderlyingComplex || TraceFlag == CTF_UseComplexAsSimple;
	for (int32 InstanceIndex = 0; InstanceIndex < Component.GetInstanceCount(); ++InstanceIndex)
	{
		FTransform InstanceToWorld;
		if (!Component.GetInstanceTransform(InstanceIndex, InstanceToWorld, true))
		{
			Warnings.Add(FString::Printf(TEXT("%s[%d]: world transform was unavailable."),
				*Component.GetPathName(), InstanceIndex));
			continue;
		}
		const FString InstanceName = FString::Printf(TEXT("%s[%d]"), *Component.GetName(), InstanceIndex);
		FExportedCollisionObject Object = MakeObject(Actor, InstanceName,
			ForceUnderlyingComplex ? TEXT("complex_forced_instanced")
				: (ForceComplex ? TEXT("complex_as_simple_instanced") : TEXT("simple_instanced")));
		bool Exported = false;
		if (ForceComplex)
		{
			Exported = AddComplexCollision(InstanceToWorld, *StaticMesh, Object);
		}
		else
		{
			Exported = AddSimpleCollision(InstanceToWorld,
				FString::Printf(TEXT("%s[%d]"), *Component.GetPathName(), InstanceIndex),
				*BodySetup, Object, Warnings);
			if (!Exported && TraceFlag != CTF_UseSimpleAsComplex)
			{
				Object.CollisionSource = TEXT("complex_fallback_no_simple_instanced");
				Exported = AddComplexCollision(InstanceToWorld, *StaticMesh, Object);
			}
		}
		if (Exported)
		{
			Objects.Add(MoveTemp(Object));
		}
		else
		{
			Warnings.Add(FString::Printf(TEXT("%s[%d]: no supported collision triangles were exported."),
				*Component.GetPathName(), InstanceIndex));
		}
	}
}

void ExportLandscape(AActor& Actor, ALandscapeProxy& Landscape,
	TArray<FExportedCollisionObject>& Objects, TArray<FString>& Warnings)
{
	int32 SizeX = 0;
	int32 SizeY = 0;
	TArray<float> Heights;
	Landscape.GetHeightValues(SizeX, SizeY, Heights);
	if (SizeX < 2 || SizeY < 2 || Heights.Num() != SizeX * SizeY)
	{
		Warnings.Add(Landscape.GetPathName() + TEXT(": cooked landscape heightfield was unavailable."));
		return;
	}

	int32 MinX = MAX_int32;
	int32 MinY = MAX_int32;
	for (const ULandscapeComponent* Component : Landscape.LandscapeComponents)
	{
		if (Component == nullptr)
		{
			continue;
		}
		MinX = FMath::Min(MinX, Component->SectionBaseX);
		MinY = FMath::Min(MinY, Component->SectionBaseY);
	}
	if (MinX == MAX_int32 || MinY == MAX_int32)
	{
		Warnings.Add(Landscape.GetPathName() + TEXT(": landscape grid origin was unavailable."));
		return;
	}

	FExportedCollisionObject Object = MakeObject(Actor, TEXT("LandscapeHeightfield"), TEXT("landscape_heightfield"));
	Object.Vertices.Reserve(Heights.Num());
	Object.Indices.Reserve((SizeX - 1) * (SizeY - 1) * 2);
	const FTransform LandscapeToWorld = Landscape.GetActorTransform();
	for (int32 Y = 0; Y < SizeY; ++Y)
	{
		for (int32 X = 0; X < SizeX; ++X)
		{
			FVector Vertex = LandscapeToWorld.TransformPosition(FVector(MinX + X, MinY + Y, 0.0));
			Vertex.Z = Heights[Y * SizeX + X];
			Object.Vertices.Add(Vertex);
		}
	}
	for (int32 Y = 0; Y + 1 < SizeY; ++Y)
	{
		for (int32 X = 0; X + 1 < SizeX; ++X)
		{
			const int32 TopLeft = Y * SizeX + X;
			const int32 TopRight = TopLeft + 1;
			const int32 BottomLeft = TopLeft + SizeX;
			const int32 BottomRight = BottomLeft + 1;
			Object.Indices.Emplace(TopLeft, TopRight, BottomLeft);
			Object.Indices.Emplace(TopRight, BottomRight, BottomLeft);
		}
	}
	Objects.Add(MoveTemp(Object));
	Warnings.Add(Landscape.GetPathName() +
		TEXT(": v1 exports the cooked heightfield surface; landscape hole/material masks are not represented."));
}

void WriteStringArray(const TSharedRef<TJsonWriter<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>>& Writer,
	const TCHAR* Name, const TArray<FString>& Values)
{
	Writer->WriteArrayStart(Name);
	for (const FString& Value : Values)
	{
		Writer->WriteValue(Value);
	}
	Writer->WriteArrayEnd();
}

bool WriteSnapshot(const FString& Path, const FString& MapName, const int32 SelectedActorCount,
	const TArray<FExportedCollisionObject>& Objects, const TArray<FString>& Warnings)
{
	FString Json;
	const TSharedRef<TJsonWriter<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>> Writer =
		TJsonWriterFactory<TCHAR, TPrettyJsonPrintPolicy<TCHAR>>::Create(&Json);
	Writer->WriteObjectStart();
	Writer->WriteValue(TEXT("schema"), TEXT("prophecy.unreal-collision.v1"));
	Writer->WriteValue(TEXT("map"), MapName);
	Writer->WriteValue(TEXT("coordinate_system"), TEXT("prophecy_sim_xyz_meters"));
	Writer->WriteArrayStart(TEXT("objects"));
	int64 TriangleCount = 0;
	for (const FExportedCollisionObject& Object : Objects)
	{
		Writer->WriteObjectStart();
		Writer->WriteValue(TEXT("id"), Object.StableId);
		Writer->WriteValue(TEXT("label"), Object.Label);
		Writer->WriteValue(TEXT("actor_class"), Object.ActorClass);
		Writer->WriteValue(TEXT("component"), Object.Component);
		Writer->WriteValue(TEXT("collision_source"), Object.CollisionSource);
		Writer->WriteArrayStart(TEXT("vertices"));
		for (const FVector& UnrealVertex : Object.Vertices)
		{
			const FVector Meters = UnrealVertex * CentimetersToMeters;
			Writer->WriteArrayStart();
			Writer->WriteValue(Meters.X);
			Writer->WriteValue(Meters.Y);
			Writer->WriteValue(Meters.Z);
			Writer->WriteArrayEnd();
		}
		Writer->WriteArrayEnd();
		Writer->WriteArrayStart(TEXT("indices"));
		for (const FIntVector& Triangle : Object.Indices)
		{
			Writer->WriteArrayStart();
			Writer->WriteValue(Triangle.X);
			Writer->WriteValue(Triangle.Y);
			Writer->WriteValue(Triangle.Z);
			Writer->WriteArrayEnd();
		}
		Writer->WriteArrayEnd();
		Writer->WriteObjectEnd();
		TriangleCount += Object.Indices.Num();
	}
	Writer->WriteArrayEnd();
	Writer->WriteObjectStart(TEXT("summary"));
	Writer->WriteValue(TEXT("selected_actors"), SelectedActorCount);
	Writer->WriteValue(TEXT("exported_objects"), Objects.Num());
	Writer->WriteValue(TEXT("triangles"), TriangleCount);
	Writer->WriteObjectEnd();
	WriteStringArray(Writer, TEXT("warnings"), Warnings);
	Writer->WriteObjectEnd();
	Writer->Close();

	IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path), true);
	return FFileHelper::SaveStringToFile(Json, *Path, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
}

void ExportSelectedSimCollisionInternal(const TArray<FString>& Arguments,
	const bool ForceUnderlyingComplex)
{
	if (GEditor == nullptr || GEditor->GetSelectedActors() == nullptr)
	{
		UE_LOG(LogProphecySimCollisionExport, Error, TEXT("No editor actor selection is available."));
		return;
	}

	const FString DefaultPath = FPaths::Combine(FPaths::ProjectDir(), TEXT("StandaloneSim/data/unreal_collision.json"));
	const FString RequestedPath = Arguments.IsEmpty()
		? DefaultPath
		: FString::Join(Arguments, TEXT(" ")).TrimQuotes();
	const FString OutputPath = FPaths::ConvertRelativePathToFull(RequestedPath);
	TArray<FExportedCollisionObject> Objects;
	TArray<FString> Warnings;
	int32 SelectedActorCount = 0;

	for (FSelectionIterator Iterator(*GEditor->GetSelectedActors()); Iterator; ++Iterator)
	{
		AActor* Actor = Cast<AActor>(*Iterator);
		if (Actor == nullptr)
		{
			continue;
		}
		++SelectedActorCount;
		if (ALandscapeProxy* Landscape = Cast<ALandscapeProxy>(Actor))
		{
			ExportLandscape(*Actor, *Landscape, Objects, Warnings);
			continue;
		}

		TInlineComponentArray<UStaticMeshComponent*> StaticMeshComponents(Actor);
		if (StaticMeshComponents.IsEmpty())
		{
			Warnings.Add(Actor->GetPathName() + TEXT(": no supported static-mesh or landscape collision component."));
		}
		for (UStaticMeshComponent* Component : StaticMeshComponents)
		{
			if (Component != nullptr)
			{
				if (UInstancedStaticMeshComponent* Instanced = Cast<UInstancedStaticMeshComponent>(Component))
				{
					ExportInstancedStaticMeshComponent(*Actor, *Instanced, Objects, Warnings,
						ForceUnderlyingComplex);
				}
				else
				{
					ExportStaticMeshComponent(*Actor, *Component, Objects, Warnings,
						ForceUnderlyingComplex);
				}
			}
		}
	}

	if (SelectedActorCount == 0)
	{
		UE_LOG(LogProphecySimCollisionExport, Warning,
			TEXT("Select one or more level actors before running Prophecy.ExportSelectedSimCollision."));
		return;
	}
	if (!WriteSnapshot(OutputPath,
		GEditor->GetEditorWorldContext().World()->GetOutermost()->GetName(),
		SelectedActorCount, Objects, Warnings))
	{
		UE_LOG(LogProphecySimCollisionExport, Error, TEXT("Failed to write %s"), *OutputPath);
		return;
	}

	int64 TriangleCount = 0;
	for (const FExportedCollisionObject& Object : Objects)
	{
		TriangleCount += Object.Indices.Num();
	}
	UE_LOG(LogProphecySimCollisionExport, Display,
		TEXT("Exported %d collision object(s), %lld triangles, and %d warning(s) to %s"),
		Objects.Num(), TriangleCount, Warnings.Num(), *OutputPath);
	for (const FString& Warning : Warnings)
	{
		UE_LOG(LogProphecySimCollisionExport, Warning, TEXT("%s"), *Warning);
	}
}

void ExportSelectedSimCollision(const TArray<FString>& Arguments)
{
	ExportSelectedSimCollisionInternal(Arguments, false);
}

void ExportSelectedSimComplexCollision(const TArray<FString>& Arguments)
{
	ExportSelectedSimCollisionInternal(Arguments, true);
}

FAutoConsoleCommand ExportSelectedSimCollisionCommand(
	TEXT("Prophecy.ExportSelectedSimCollision"),
	TEXT("Exports selected actors' Unreal collision to a v1 standalone-sim debug snapshot. Optional argument: output path."),
	FConsoleCommandWithArgsDelegate::CreateStatic(&ExportSelectedSimCollision));

FAutoConsoleCommand ExportSelectedSimComplexCollisionCommand(
	TEXT("Prophecy.ExportSelectedSimComplexCollision"),
	TEXT("Exports selected actors' underlying complex static-mesh collision, including disabled and instanced components. Optional argument: output path."),
	FConsoleCommandWithArgsDelegate::CreateStatic(&ExportSelectedSimComplexCollision));

} // namespace
