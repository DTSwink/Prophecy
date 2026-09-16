#include "ProphecyJoltStaticBody.h"
#include "ProphecyJoltBodyConversion.h"
#include "ProphecyJoltConversions.h"
#include "ProphecyJoltMaterial.h"

#include "Chaos/Collision/CollisionFilter.h"
#include "Chaos/ImplicitObjectScaled.h"
#include "Chaos/ImplicitObjectTransformed.h"
#include "Chaos/ShapeInstance.h"
#include "Chaos/TriangleMeshImplicitObject.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "Math/ScaleMatrix.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "Physics/PhysicsFiltering.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/BodySetup.h"
#include "PhysicsEngine/PhysicsSettings.h"

THIRD_PARTY_INCLUDES_START
#include <Jolt/Core/Factory.h>
#include <Jolt/Physics/Collision/Shape/MeshShape.h>
#include <Jolt/Physics/Collision/Shape/StaticCompoundShape.h>
#include <Jolt/RegisterTypes.h>
THIRD_PARTY_INCLUDES_END

namespace ProphecyJolt::StaticBody
{
namespace
{
bool Fail(FString& Error, const FString& Message) { Error = Message; return false; }
bool Finite(const FVector& V) { return FMath::IsFinite(V.X) && FMath::IsFinite(V.Y) && FMath::IsFinite(V.Z); }
bool NativeFinite(double V) { return FMath::IsFinite(V) && FMath::IsFinite(static_cast<float>(V)); }
bool NonzeroScale(const FVector& V) { return Finite(V) && V.X != 0.0 && V.Y != 0.0 && V.Z != 0.0; }
bool Rigid(const FTransform& T)
{
    return !T.ContainsNaN() && Finite(T.GetTranslation()) && T.GetRotation().IsNormalized()
        && T.GetScale3D().Equals(FVector::OneVector, 1.0e-6);
}
void StoreWords(const FCollisionFilterData& Filter, uint32 (&Words)[4])
{
    Words[0] = Filter.Word0; Words[1] = Filter.Word1; Words[2] = Filter.Word2; Words[3] = Filter.Word3;
}
JPH::Vec3 LocalMeters(const FVector& V) { return static_cast<JPH::Vec3>(Conversions::ToJoltPosition(V)); }

bool CaptureMesh(const FPhysicsShapeHandle& Handle, FProphecyJoltStaticMeshShape& Out, FString& Error)
{
    const Chaos::FImplicitObject* Geometry = &Handle.GetGeometry();
    FMatrix VertexToBody = FMatrix::Identity;
    int32 WrapperCount = 0;
    while (Geometry)
    {
        Out.NativeGeometryTypeChain.Add(uint32(Geometry->GetType()));
        if (const auto* Transformed = Geometry->GetObject<Chaos::FImplicitObjectTransformed>())
        {
            if (++WrapperCount > 32 || !Rigid(Transformed->GetTransform()))
                return Fail(Error, TEXT("Static mesh has too many wrappers or a non-rigid native transform."));
            VertexToBody = Transformed->GetTransform().ToMatrixWithScale() * VertexToBody;
            Geometry = Transformed->GetTransformedObject();
            continue;
        }
        if (const auto* Scaled = Geometry->AsA<Chaos::FImplicitObjectScaled>())
        {
            const FVector Scale(Scaled->GetScale());
            if (++WrapperCount > 32 || !NonzeroScale(Scale))
                return Fail(Error, TEXT("Static mesh native scale is zero/nonfinite or wrappers exceed the limit."));
            VertexToBody = FScaleMatrix(Scale) * VertexToBody;
            Geometry = Scaled->GetInnerObject().Get();
            continue;
        }
        if (const auto* Instanced = Geometry->AsA<Chaos::FImplicitObjectInstanced>())
        {
            if (++WrapperCount > 32) return Fail(Error, TEXT("Static mesh exceeds 32 native wrappers."));
            Geometry = Instanced->GetInnerObject().Get();
            continue;
        }
        break;
    }
    const auto* Mesh = Geometry ? Geometry->GetObject<Chaos::FTriangleMeshImplicitObject>() : nullptr;
    if (!Mesh) return Fail(Error, TEXT("Effective static triangle shape does not contain a cooked triangle mesh."));
    const double Determinant = VertexToBody.Determinant();
    if (!FMath::IsFinite(Determinant) || Determinant == 0.0)
        return Fail(Error, TEXT("Static mesh native wrapper matrix is singular or nonfinite."));
    Out.bReversedWindingForNegativeScale = Determinant < 0.0;
    Out.NativeShapeIndex = Handle.Shape->GetShapeIndex();
    Out.bQueryEnabled = Handle.Shape->GetQueryEnabled();
    StoreWords(Handle.Shape->GetSimData(), Out.SimulationFilterWords);
    StoreWords(Handle.Shape->GetQueryData(), Out.QueryFilterWords);
    const auto& Particles = Mesh->Particles();
    if (Particles.Size() > uint32(MAX_int32))
        return Fail(Error, TEXT("Static mesh vertex count exceeds the capture array limit."));
    const int32 VertexCount = int32(Particles.Size());
    Out.VerticesCm.Reserve(VertexCount);
    for (int32 Index = 0; Index < VertexCount; ++Index)
        Out.VerticesCm.Add(FVector(VertexToBody.TransformPosition(FVector(Particles.GetX(Index)))));
    auto CopyTriangles = [&](const auto& Indices)
    {
        for (int32 Index = 0; Index < Indices.Num(); ++Index)
        {
            const auto& Triangle = Indices[Index];
            FIntVector Result{int32(Triangle[0]), int32(Triangle[1]), int32(Triangle[2])};
            // Chaos applies the scale determinant to oriented mesh normals. Baking signed scale
            // into vertices requires the matching index reversal to retain its outward face.
            if (Out.bReversedWindingForNegativeScale) Swap(Result.Y, Result.Z);
            Out.Triangles.Add(Result);
            Out.ExternalFaceIndices.Add(Mesh->GetExternalFaceIndexFromInternal(Index));
            Out.MaterialIndices.Add(Mesh->GetMaterialIndex(Index));
        }
    };
    const auto& Elements = Mesh->Elements();
    if (Elements.RequiresLargeIndices()) CopyTriangles(Elements.GetLargeIndexBuffer());
    else CopyTriangles(Elements.GetSmallIndexBuffer());
    return true;
}

bool CaptureLocked(const FBodyInstance& Instance, const UBodySetup& Setup, FProphecyJoltStaticBodySnapshot& Out, FString& Error)
{
    const FPhysicsActorHandle Actor = Instance.GetPhysicsActor();
    if (!Actor || Instance.WeldParent || (!FPhysicsInterface::IsStatic(Actor)
        && !(Out.bKinematic && FPhysicsInterface::IsKinematic(Actor))) || Instance.IsInstanceSimulatingPhysics())
        return Fail(Error, TEXT("Static capture requires one independent native static body; moving/kinematic/dynamic and welded bodies are unsupported."));
    Out.BodyOriginToWorld = Instance.GetUnrealWorldTransform_AssumesLocked(false, true);
    Out.SourceBodyScale3D = Instance.Scale3D;
    Out.SourceBuildScale3D = Setup.BuildScale3D;
    Out.CollisionEnabled = Instance.GetCollisionEnabled();
    const UPhysicalMaterial* Material = Instance.GetSimplePhysicalMaterial();
    if (!Material) return Fail(Error, TEXT("Static body has no resolved physical material."));
    Out.PhysicalMaterialPath = Material->GetPathName();
    Out.Friction = Material->Friction; Out.Restitution = Material->Restitution;
    Out.EffectiveFrictionCombineMode = uint8(Material->bOverrideFrictionCombineMode
        ? Material->FrictionCombineMode.GetValue() : UPhysicsSettings::Get()->FrictionCombineMode.GetValue());
    Out.EffectiveRestitutionCombineMode = uint8(Material->bOverrideRestitutionCombineMode
        ? Material->RestitutionCombineMode.GetValue() : UPhysicsSettings::Get()->RestitutionCombineMode.GetValue());
    for (const UPhysicalMaterial* Complex : Instance.GetComplexPhysicalMaterials())
        Out.ComplexPhysicalMaterialPaths.Add(GetPathNameSafe(Complex));

    TMap<const FKShapeElem*, FProphecyJoltRigShape> Authored;
    int32 ElementIndex = 0;
    auto Add = [&](const FKShapeElem& Element, EProphecyJoltRigShape Kind)
    {
        auto& Shape = Authored.Add(&Element);
        Shape.Kind = Kind; Shape.SourceElementIndex = ElementIndex++;
        Shape.ElementName = Element.GetName(); Shape.AuthoredLocalToBodyOrigin = Element.GetTransform();
        Shape.AuthoredCollisionEnabled = Element.GetCollisionEnabled();
        Shape.RestOffsetCm = Element.RestOffset;
        Shape.bContributesToAuthoredMass = Element.GetContributeToMass();
    };
    for (const auto& Element : Setup.AggGeom.SphereElems) Add(Element, EProphecyJoltRigShape::Sphere);
    for (const auto& Element : Setup.AggGeom.BoxElems) Add(Element, EProphecyJoltRigShape::Box);
    for (const auto& Element : Setup.AggGeom.SphylElems) Add(Element, EProphecyJoltRigShape::Capsule);
    for (const auto& Element : Setup.AggGeom.ConvexElems) Add(Element, EProphecyJoltRigShape::Convex);
    TArray<FPhysicsShapeHandle> Shapes;
    Instance.GetAllShapes_AssumesLocked(Shapes);
    Out.NativeShapeCount = Shapes.Num();
    TSet<int32> Seen;
    TSet<const FKShapeElem*> SeenAuthored;
    bool bHavePolicy = false;
    for (const auto& Handle : Shapes)
    {
        if (!Handle.IsValid() || Handle.Shape->GetShapeIndex() < 0 || Seen.Contains(Handle.Shape->GetShapeIndex()))
            return Fail(Error, TEXT("Static body contains an invalid or duplicate native shape identity."));
        Seen.Add(Handle.Shape->GetShapeIndex());
        const Chaos::FImplicitObject* Leaf = Handle.Shape->GetLeafGeometry();
        const auto Type = Leaf ? Chaos::GetInnerType(Leaf->GetCollisionType()) : Chaos::ImplicitObjectType::Unknown;
        if (Handle.Shape->GetIsProbe()) return Fail(Error, TEXT("Static probe shapes require an event adapter and cannot become solid collision."));
        const bool bEffective = Handle.Shape->GetSimEnabled() && Chaos::DoCollide(Type, Handle.Shape);
        if (!bEffective)
        {
            auto& Query = Out.NonSimulationShapes.AddDefaulted_GetRef();
            Query.NativeShapeIndex = Handle.Shape->GetShapeIndex(); Query.NativeGeometryType = uint32(Handle.GetGeometry().GetType());
            Query.bQueryEnabled = Handle.Shape->GetQueryEnabled(); Query.bSimulationEnabled = Handle.Shape->GetSimEnabled();
            StoreWords(Handle.Shape->GetSimData(), Query.SimulationFilterWords);
            StoreWords(Handle.Shape->GetQueryData(), Query.QueryFilterWords);
            const auto Bounds = Handle.GetGeometry().BoundingBox();
            Query.BoundsInBodyOriginCm = FBox(FVector(Bounds.Min()), FVector(Bounds.Max()));
            continue;
        }
        if (Type == Chaos::ImplicitObjectType::Unknown || Type == Chaos::ImplicitObjectType::LevelSet)
            return Fail(Error, TEXT("Static collision has an unsupported particle-dependent geometry type."));
        const auto& Filter = Handle.Shape->GetSimData();
        const ECollisionChannel Channel = GetCollisionChannel(Filter.Word3);
        const FCollisionResponseContainer Responses = ExtractSimCollisionResponseContainer(Filter);
        if (!bHavePolicy) { Out.ObjectType = Channel; Out.CollisionResponses = Responses; bHavePolicy = true; }
        else if (Out.ObjectType != Channel || Out.CollisionResponses != Responses)
            return Fail(Error, TEXT("Static simulation shapes have different effective collision policies; split ownership is required."));
        if (Type == Chaos::ImplicitObjectType::TriangleMesh)
        {
            if (!CaptureMesh(Handle, Out.MeshShapes.AddDefaulted_GetRef(), Error)) return false;
        }
        else
        {
            if (Out.SourceBodyScale3D.GetMin() <= 0.0 || Out.SourceBuildScale3D.GetMin() <= 0.0)
                return Fail(Error, TEXT("Mirrored simple static shapes remain outside the strict primitive/convex converter."));
            const FKShapeElem* Element = FChaosUserData::Get<FKShapeElem>(FPhysicsInterface::GetUserData(Handle));
            const auto* Found = Authored.Find(Element);
            if (!Found || SeenAuthored.Contains(Element))
                return Fail(Error, TEXT("Static simulation shape lacks unique supported authored simple-shape identity; landscape/other geometry is unsupported."));
            SeenAuthored.Add(Element);
            auto& Shape = Out.SimpleShapes.Add_GetRef(*Found);
            if (!BodyConversion::CaptureNativeShape(Handle, Shape, Error)) return false;
        }
    }
    if (!bHavePolicy) return Fail(Error, TEXT("Static body has no effective simulation shapes; query-only collision is not imported as a solid."));
    return true;
}
}

bool ValidateSnapshot(const FProphecyJoltStaticBodySnapshot& Snapshot, FString& Error)
{
    Error.Reset();
    if (!Snapshot.CaptureId.IsValid() || Snapshot.InstanceIndex < INDEX_NONE || !Rigid(Snapshot.BodyOriginToWorld)
        || Snapshot.ComponentToWorld.ContainsNaN() || !Snapshot.ComponentToWorld.GetRotation().IsNormalized()
        || Snapshot.InstanceToWorld.ContainsNaN() || !Snapshot.InstanceToWorld.GetRotation().IsNormalized()
        || !NonzeroScale(Snapshot.ComponentToWorld.GetScale3D()) || !NonzeroScale(Snapshot.InstanceToWorld.GetScale3D())
        || !NonzeroScale(Snapshot.SourceBodyScale3D) || !NonzeroScale(Snapshot.SourceBuildScale3D)
        || (Snapshot.CollisionEnabled != ECollisionEnabled::QueryAndPhysics && Snapshot.CollisionEnabled != ECollisionEnabled::PhysicsOnly)
        || !NativeFinite(Snapshot.Friction) || Snapshot.Friction < 0.0
        || !Material::ValidModes(Snapshot.EffectiveFrictionCombineMode, Snapshot.EffectiveRestitutionCombineMode)
        || !NativeFinite(Snapshot.Restitution) || Snapshot.Restitution < 0.0 || Snapshot.Restitution > 1.0
        || (Snapshot.SimpleShapes.IsEmpty() && Snapshot.MeshShapes.IsEmpty()))
        return Fail(Error, TEXT("Static capture has invalid identity, rigid frame, scale, simulation mode, material or empty geometry."));
    if (!Snapshot.SimpleShapes.IsEmpty() && !BodyConversion::ValidateShapes(Snapshot.SimpleShapes, Error)) return false;
    TSet<int32> NativeIndices;
    for (const auto& Shape : Snapshot.SimpleShapes)
    {
        if (Shape.SourceNativeShapeIndex < 0 || NativeIndices.Contains(Shape.SourceNativeShapeIndex))
            return Fail(Error, TEXT("Static simple shape identity is absent or duplicated."));
        NativeIndices.Add(Shape.SourceNativeShapeIndex);
    }
    for (const auto& Mesh : Snapshot.MeshShapes)
    {
        if (Mesh.NativeShapeIndex < 0 || NativeIndices.Contains(Mesh.NativeShapeIndex) || Mesh.VerticesCm.IsEmpty()
            || Mesh.Triangles.IsEmpty() || Mesh.ExternalFaceIndices.Num() != Mesh.Triangles.Num() || Mesh.MaterialIndices.Num() != Mesh.Triangles.Num())
            return Fail(Error, TEXT("Static mesh identity, vertices, triangles or parallel provenance are invalid."));
        NativeIndices.Add(Mesh.NativeShapeIndex);
        for (const FVector& V : Mesh.VerticesCm)
            if (!Finite(V) || !NativeFinite(V.X * 0.01) || !NativeFinite(V.Y * 0.01) || !NativeFinite(V.Z * 0.01))
                return Fail(Error, TEXT("Static mesh vertex exceeds finite native local precision."));
        for (const FIntVector& T : Mesh.Triangles)
        {
            if (!Mesh.VerticesCm.IsValidIndex(T.X) || !Mesh.VerticesCm.IsValidIndex(T.Y) || !Mesh.VerticesCm.IsValidIndex(T.Z)
                || T.X == T.Y || T.Y == T.Z || T.Z == T.X)
                return Fail(Error, TEXT("Static mesh has an invalid or collapsed triangle index."));
            const JPH::Vec3 A = LocalMeters(Mesh.VerticesCm[T.X]);
            const JPH::Vec3 B = LocalMeters(Mesh.VerticesCm[T.Y]);
            const JPH::Vec3 C = LocalMeters(Mesh.VerticesCm[T.Z]);
            const float AreaSquared = (B - A).Cross(C - A).LengthSq();
            if (!FMath::IsFinite(AreaSquared) || AreaSquared <= 0.0f)
                return Fail(Error, TEXT("Static mesh triangle collapses or overflows in native local precision."));
        }
    }
    return true;
}

bool CaptureStaticBody(UPrimitiveComponent& Component, int32 InstanceIndex, FProphecyJoltStaticBodySnapshot& OutSnapshot, FString& Error, bool bAllowKinematic)
{
    OutSnapshot = {}; Error.Reset();
    if (!IsInGameThread()) return Fail(Error, TEXT("Static capture requires the game thread at a completed synchronous Chaos step."));
    UWorld* World = Component.GetWorld();
    if (!World || !World->IsGameWorld() || !Component.IsRegistered() || !Component.IsPhysicsStateCreated()
        || (!bAllowKinematic && Component.GetMobility() != EComponentMobility::Static) || Cast<USkeletalMeshComponent>(&Component))
        return Fail(Error, TEXT("Capture requires a registered static-mobility Game/PIE primitive with native physics; moving/skeletal components are unsupported."));
    if (UPhysicsSettings::Get()->bTickPhysicsAsync) return Fail(Error, TEXT("Async Chaos static capture is unsupported."));
    auto* ISM = Cast<UInstancedStaticMeshComponent>(&Component);
    if ((ISM && (InstanceIndex < 0 || InstanceIndex >= ISM->GetInstanceCount())) || (!ISM && InstanceIndex != INDEX_NONE))
        return Fail(Error, TEXT("Static instance index must address one live ISM/HISM instance, or be INDEX_NONE for an ordinary primitive."));
    if (ISM && (!ISM->InstanceBodies.IsValidIndex(InstanceIndex) || !ISM->InstanceBodies[InstanceIndex]))
        return Fail(Error, TEXT("Requested static instance has no native body; the ISM base BodyInstance is never substituted."));
    FBodyInstance* Instance = Component.GetBodyInstance(NAME_None, false, InstanceIndex);
    if (ISM && Instance != ISM->InstanceBodies[InstanceIndex])
        return Fail(Error, TEXT("Static instance lookup returned a different body than the exact requested native slot."));
    const UBodySetup* Setup = Instance ? Instance->GetBodySetup() : nullptr;
    if (!Instance || !Instance->IsValidBodyInstance() || Instance->WeldParent || !Setup)
        return Fail(Error, TEXT("Static component/instance has no valid independent native body/setup."));
    FProphecyJoltStaticBodySnapshot Captured;
    Captured.bKinematic = Component.GetMobility() != EComponentMobility::Static;
    Captured.CaptureId = FGuid::NewGuid(); Captured.SourceComponent = &Component; Captured.SourceWorld = World;
    Captured.InstanceIndex = InstanceIndex; Captured.ComponentPath = Component.GetPathName();
    Captured.BodySetupPath = Setup->GetPathName(); Captured.EngineFrame = GFrameCounter;
    Captured.ComponentToWorld = Component.GetComponentTransform(); Captured.InstanceToWorld = Captured.ComponentToWorld;
    if (ISM && !ISM->GetInstanceTransform(InstanceIndex, Captured.InstanceToWorld, true))
        return Fail(Error, TEXT("Static instance world transform could not be captured."));
    if (const auto* Mesh = Cast<UStaticMeshComponent>(&Component)) Captured.StaticMeshPath = GetPathNameSafe(Mesh->GetStaticMesh());
    bool bCaptured = false;
    const bool bRead = FPhysicsCommand::ExecuteRead(Instance->GetPhysicsActor(), [&](const FPhysicsActorHandle&)
        { bCaptured = CaptureLocked(*Instance, *Setup, Captured, Error); });
    if (!bRead || !bCaptured) return Error.IsEmpty() ? Fail(Error, TEXT("Static native read failed.")) : false;
    if (!ValidateSnapshot(Captured, Error)) return false;
    Captured.CoverageNotes.Add(TEXT("Only effective native static simulation shapes are imported. Actual simple collision remains analytic/convex; complex-as-simple uses cooked triangles, including native wrappers once and signed-scale winding correction. No render collision fallback, hull simplification or invented mass is used."));
    Captured.CoverageNotes.Add(TEXT("Original UE component, instance index, native source faces, material indices and query geometry remain provenance. Jolt mesh triangles are single-sided for simulation and internally reordered; per-triangle user data retains the captured local triangle index, not a UE FaceIndex."));
    Captured.CoverageNotes.Add(TEXT("The existing body-level Jolt friction/restitution and bilateral Block policy apply. Complex material coefficients/combine modes, overlaps, probes, scene lifecycle, landscape and moving bodies are not implemented by this static foundation. Retained UE queries provide blood/UV identity."));
    OutSnapshot = MoveTemp(Captured);
    return true;
}
}

class FProphecyJoltPreparedStaticBodyState
{
public:
    FGuid CaptureId;
    JPH::RefConst<JPH::Shape> Shape;
};

FProphecyJoltPreparedStaticBody::FProphecyJoltPreparedStaticBody() = default;
FProphecyJoltPreparedStaticBody::~FProphecyJoltPreparedStaticBody() = default;
FProphecyJoltPreparedStaticBody::FProphecyJoltPreparedStaticBody(FProphecyJoltPreparedStaticBody&& Other) noexcept = default;
FProphecyJoltPreparedStaticBody& FProphecyJoltPreparedStaticBody::operator=(FProphecyJoltPreparedStaticBody&& Other) noexcept = default;
void FProphecyJoltPreparedStaticBody::Reset() { Native.Reset(); }
bool FProphecyJoltPreparedStaticBody::IsValid() const { return Native && Native->Shape; }
FGuid FProphecyJoltPreparedStaticBody::GetCaptureId() const { return Native ? Native->CaptureId : FGuid(); }
const JPH::Shape* FProphecyJoltPreparedStaticBody::GetNativeShape() const { return Native ? Native->Shape.GetPtr() : nullptr; }

bool FProphecyJoltPreparedStaticBody::Build(const FProphecyJoltStaticBodySnapshot& Snapshot, FString& Error)
{
    using namespace ProphecyJolt;
    Error.Reset();
    if (!IsInGameThread()) return StaticBody::Fail(Error, TEXT("Static shape preparation requires the game thread."));
    if (!JPH::VerifyJoltVersionID() || !JPH::Factory::sInstance) return StaticBody::Fail(Error, TEXT("Jolt runtime/ABI is unavailable."));
    if (!StaticBody::ValidateSnapshot(Snapshot, Error)) return false;
    auto Built = MakeUnique<FProphecyJoltPreparedStaticBodyState>();
    Built->CaptureId = Snapshot.CaptureId;
    JPH::StaticCompoundShapeSettings Compound;
    if (!Snapshot.SimpleShapes.IsEmpty())
    {
        JPH::RefConst<JPH::Shape> Simple;
        if (!BodyConversion::PrepareShapes(Snapshot.SimpleShapes, Simple, Error)) return false;
        Compound.AddShape(JPH::Vec3::sZero(), JPH::Quat::sIdentity(), Simple);
    }
    for (const auto& Mesh : Snapshot.MeshShapes)
    {
        JPH::VertexList Vertices; Vertices.reserve(Mesh.VerticesCm.Num());
        for (const auto& V : Mesh.VerticesCm) Vertices.emplace_back(float(V.X * 0.01), float(V.Y * 0.01), float(V.Z * 0.01));
        JPH::IndexedTriangleList Triangles; Triangles.reserve(Mesh.Triangles.Num());
        for (int32 Index = 0; Index < Mesh.Triangles.Num(); ++Index)
        {
            const auto& T = Mesh.Triangles[Index];
            Triangles.emplace_back(uint32(T.X), uint32(T.Y), uint32(T.Z), 0, uint32(Index));
        }
        JPH::MeshShapeSettings Settings(MoveTemp(Vertices), MoveTemp(Triangles));
        if (Settings.mIndexedTriangles.size() != size_t(Mesh.Triangles.Num()))
            return StaticBody::Fail(Error, TEXT("Jolt sanitation would remove captured duplicate/degenerate triangles; static mesh preparation refused."));
        Settings.mPerTriangleUserData = true;
        Settings.mUserData = uint64(Mesh.NativeShapeIndex) + 1;
        const auto Result = Settings.Create();
        if (Result.HasError()) return StaticBody::Fail(Error, UTF8_TO_TCHAR(Result.GetError().c_str()));
        Compound.AddShape(JPH::Vec3::sZero(), JPH::Quat::sIdentity(), Result.Get(), uint32(Mesh.NativeShapeIndex) + 1);
    }
    const auto Result = Compound.Create();
    if (Result.HasError()) return StaticBody::Fail(Error, UTF8_TO_TCHAR(Result.GetError().c_str()));
    Built->Shape = Result.Get();
    Native = MoveTemp(Built);
    return true;
}

bool FProphecyJoltPreparedStaticBody::GetBoundsInBodyOriginCm(FBox& OutBounds, FString& Error) const
{
    Error.Reset(); OutBounds = FBox(ForceInit);
    if (!IsValid()) return ProphecyJolt::StaticBody::Fail(Error, TEXT("Static geometry is not prepared."));
    const JPH::Vec3 COM = Native->Shape->GetCenterOfMass();
    const auto Bounds = Native->Shape->GetLocalBounds();
    OutBounds = FBox(ProphecyJolt::Conversions::FromJoltPosition(JPH::RVec3(Bounds.mMin + COM)),
        ProphecyJolt::Conversions::FromJoltPosition(JPH::RVec3(Bounds.mMax + COM)));
    return true;
}
