#include "ProphecyJoltBody.h"
#include "ProphecyJoltBodyConversion.h"
#include "ProphecyJoltConversions.h"

#include "Chaos/Box.h"
#include "Chaos/Capsule.h"
#include "Chaos/Convex.h"
#include "Chaos/Collision/CollisionFilter.h"
#include "Chaos/ImplicitObjectScaled.h"
#include "Chaos/ImplicitObjectTransformed.h"
#include "Chaos/ShapeInstance.h"
#include "Chaos/Sphere.h"
#include "Components/PrimitiveComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "HAL/ThreadSafeCounter.h"
#include "Math/ScaleMatrix.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "Physics/PhysicsFiltering.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/BodySetup.h"
#include "PhysicsEngine/PhysicsSettings.h"

THIRD_PARTY_INCLUDES_START
#include <Jolt/Core/Factory.h>
#include <Jolt/Physics/Collision/Shape/ConvexHullShape.h>
#include <Jolt/RegisterTypes.h>
THIRD_PARTY_INCLUDES_END

namespace ProphecyJolt::BodyConversion
{
namespace
{
bool Reject(FString& Error, const FString& Message) { Error = Message; return false; }
bool FiniteVector(const FVector& V) { return FMath::IsFinite(V.X) && FMath::IsFinite(V.Y) && FMath::IsFinite(V.Z); }
bool Rigid(const FTransform& T)
{
    return !T.ContainsNaN() && T.GetRotation().IsNormalized() && T.GetScale3D().Equals(FVector::OneVector, 1.0e-6);
}
}

bool CaptureGeometry(const Chaos::FImplicitObject& Root, FProphecyJoltRigShape& OutShape, FString& OutError)
{
    OutError.Reset();
    const Chaos::FImplicitObject* Geometry = &Root;
    OutShape.NativeGeometryTypeChain.Reset();
    FTransform RigidToBody = FTransform::Identity;
    FMatrix VertexToBody = FMatrix::Identity;
    bool bHasScaleWrapper = false;
    int32 WrapperCount = 0;
    while (Geometry)
    {
        OutShape.NativeGeometryTypeChain.Add(uint32(Geometry->GetType()));
        if (const auto* Transformed = Geometry->GetObject<Chaos::FImplicitObjectTransformed>())
        {
            if (++WrapperCount > 32) return Reject(OutError, TEXT("Native geometry exceeds 32 wrappers."));
            const FTransform Local = Transformed->GetTransform();
            if (!Rigid(Local)) return Reject(OutError, TEXT("Native transform wrapper is not finite and rigid."));
            VertexToBody = Local.ToMatrixWithScale() * VertexToBody;
            RigidToBody = Local * RigidToBody;
            Geometry = Transformed->GetTransformedObject();
            continue;
        }
        if (const auto* Scaled = Geometry->AsA<Chaos::FImplicitObjectScaled>())
        {
            if (++WrapperCount > 32) return Reject(OutError, TEXT("Native geometry exceeds 32 wrappers."));
            const FVector Scale(Scaled->GetScale());
            if (!FiniteVector(Scale) || Scale.GetMin() <= 0.0)
                return Reject(OutError, TEXT("Native scaled geometry requires finite positive scale; reflected/zero scale is unsupported."));
            VertexToBody = FScaleMatrix(Scale) * VertexToBody;
            bHasScaleWrapper = true;
            Geometry = Scaled->GetInnerObject().Get();
            continue;
        }
        if (const auto* Instanced = Geometry->AsA<Chaos::FImplicitObjectInstanced>())
        {
            if (++WrapperCount > 32) return Reject(OutError, TEXT("Native geometry exceeds 32 wrappers."));
            Geometry = Instanced->GetInnerObject().Get();
            continue;
        }
        break;
    }
    if (!Geometry) return Reject(OutError, TEXT("Native wrapper has no inner geometry."));
    OutShape.NativeCollisionMarginCm = Root.GetMarginf();
    if (!FMath::IsFinite(OutShape.NativeCollisionMarginCm) || OutShape.NativeCollisionMarginCm < 0.0)
        return Reject(OutError, TEXT("Native collision margin is invalid."));
    if (const auto* Convex = Geometry->GetObject<Chaos::FConvex>())
    {
        if (OutShape.Kind != EProphecyJoltRigShape::Convex)
            return Reject(OutError, TEXT("Native convex does not match its authored simulation-shape identity."));
        const int32 VertexCount = Convex->NumVertices();
        if (VertexCount < 4)
            return Reject(OutError, TEXT("Cooked native convex requires at least four points."));
        // Jolt limits the finished hull, not its input points. Preserve the complete capture;
        // preparation checks the builder result before allowing any native shape creation.
        OutShape.ConvexVerticesCm.Reset(VertexCount);
        for (int32 VertexIndex = 0; VertexIndex < VertexCount; ++VertexIndex)
        {
            const FVector Vertex(VertexToBody.TransformPosition(FVector(Convex->GetVertex(VertexIndex))));
            if (!FiniteVector(Vertex)) return Reject(OutError, TEXT("Transformed cooked hull contains a nonfinite vertex."));
            OutShape.ConvexVerticesCm.Add(Vertex);
        }
        // Matrix multiplication preserves rotation/nonuniform-scale order without decomposing shear.
        // Neither Body.Scale3D, BodySetup.BuildScale3D nor FKConvexElem transform is applied again.
        OutShape.LocalToBodyOrigin = FTransform::Identity;
        return true;
    }
    if (bHasScaleWrapper)
        return Reject(OutError, TEXT("Scaled non-convex primitive wrappers are unsupported; no ellipsoid/capsule approximation is selected."));
    FTransform PrimitiveToGeometry = FTransform::Identity;
    if (const auto* Sphere = Geometry->GetObject<Chaos::FSphere>())
    {
        if (OutShape.Kind != EProphecyJoltRigShape::Sphere && OutShape.Kind != EProphecyJoltRigShape::Capsule)
            return Reject(OutError, TEXT("Native sphere does not match its authored sphere/sphyl identity."));
        OutShape.Kind = EProphecyJoltRigShape::Sphere;
        OutShape.RadiusCm = Sphere->GetRadiusf();
        PrimitiveToGeometry.SetTranslation(FVector(Sphere->GetCenterf()));
    }
    else if (const auto* Box = Geometry->GetObject<Chaos::TBox<Chaos::FReal, 3>>())
    {
        if (OutShape.Kind != EProphecyJoltRigShape::Box)
            return Reject(OutError, TEXT("Native box does not match its authored box identity."));
        OutShape.BoxHalfExtentCm = FVector(Box->Extents()) * 0.5;
        PrimitiveToGeometry.SetTranslation(FVector(Box->Center()));
    }
    else if (const auto* Capsule = Geometry->GetObject<Chaos::FCapsule>())
    {
        if (OutShape.Kind != EProphecyJoltRigShape::Capsule)
            return Reject(OutError, TEXT("Native capsule does not match its authored sphyl identity."));
        OutShape.RadiusCm = Capsule->GetRadiusf();
        OutShape.CapsuleCylinderLengthCm = Capsule->GetHeightf();
        PrimitiveToGeometry = FTransform(Capsule->GetRotationOfMass(), FVector(Capsule->GetCenterf()));
    }
    else return Reject(OutError, FString::Printf(TEXT("Native simulation geometry type %u is unsupported; mesh, heightfield and other types are never replaced by a proxy primitive."), uint32(Geometry->GetType())));
    OutShape.LocalToBodyOrigin = PrimitiveToGeometry * RigidToBody;
    return Rigid(OutShape.LocalToBodyOrigin) || Reject(OutError, TEXT("Captured primitive frame is invalid."));
}
}

namespace ProphecyJolt::Body
{
namespace
{
FThreadSafeCounter LivePreparedBodies;
bool Fail(FString& Error, const FString& Message) { Error = Message; return false; }

bool CaptureLocked(const FBodyInstance& Instance, const UBodySetup& Setup, FProphecyJoltBodySnapshot& Snapshot, FString& Error)
{
    FProphecyJoltBodyData& Captured = Snapshot.Body;
    const FPhysicsActorHandle Actor = Instance.GetPhysicsActor();
    if (!Actor || Instance.WeldParent || !Instance.IsInstanceSimulatingPhysics()
        || !FPhysicsInterface::IsDynamic(Actor) || FPhysicsInterface::IsKinematic_AssumesLocked(Actor))
        return Fail(Error, TEXT("Standalone capture requires a live, non-welded native dynamic body."));
    Captured.BodyOriginToWorld = Instance.GetUnrealWorldTransform_AssumesLocked(false, true);
    Captured.MassFrameToBodyOrigin = FPhysicsInterface::GetComTransformLocal_AssumesLocked(Actor);
    Captured.MassKg = FPhysicsInterface::GetMass_AssumesLocked(Actor);
    Captured.PrincipalInertiaKgCmSquared = FPhysicsInterface::GetLocalInertiaTensor_AssumesLocked(Actor);
    Captured.CenterOfMassVelocityCmPerSecond = FPhysicsInterface::GetLinearVelocity_AssumesLocked(Actor);
    Captured.AngularVelocityRadiansPerSecond = FPhysicsInterface::GetAngularVelocity_AssumesLocked(Actor);
    Captured.MaxLinearVelocityCmPerSecond = FPhysicsInterface::GetMaxLinearVelocity_AssumesLocked(Actor);
    Captured.MaxAngularVelocityRadiansPerSecond = FPhysicsInterface::GetMaxAngularVelocity_AssumesLocked(Actor);
    Captured.bSimulating = true;
    Captured.bAwake = !FPhysicsInterface::IsSleeping(Actor);
    Captured.bGravityEnabled = FPhysicsInterface::IsGravityEnabled_AssumesLocked(Actor);
    Captured.bCCD = Instance.bUseCCD;
    Captured.bMACD = Instance.IsUsingMACD();
    Captured.bInertiaConditioning = Instance.IsInertiaConditioningEnabled();
    Captured.LinearDamping = Instance.LinearDamping;
    Captured.AngularDamping = Instance.AngularDamping;
    Captured.bOverrideMaxDepenetrationVelocity = Instance.GetOverrideMaxDepenetrationVelocity();
    Captured.MaxDepenetrationVelocityCmPerSecond = Instance.GetMaxDepenetrationVelocity();
    Captured.PositionSolverIterations = Instance.GetPositionSolverIterationCount();
    Captured.VelocitySolverIterations = Instance.GetVelocitySolverIterationCount();
    Captured.ProjectionSolverIterations = Instance.GetProjectionSolverIterationCount();
    Captured.CollisionEnabled = Instance.GetCollisionEnabled();
    Captured.SourceBodyObjectType = Instance.GetObjectType();
    Captured.SourceBodyCollisionResponses = Instance.GetResponseToChannels();
    Captured.SourceBodyScale3D = Instance.Scale3D;
    Captured.SourceBuildScale3D = Setup.BuildScale3D;
    if (Captured.SourceBodyScale3D.ContainsNaN() || Captured.SourceBodyScale3D.GetMin() <= 0.0
        || Captured.SourceBuildScale3D.ContainsNaN() || Captured.SourceBuildScale3D.GetMin() <= 0.0)
        return Fail(Error, TEXT("Standalone source scale is nonpositive or nonfinite; mirrored/zero-scale bodies are unsupported."));
    const UPhysicalMaterial* Material = Instance.GetSimplePhysicalMaterial();
    if (!Material) return Fail(Error, TEXT("Standalone body has no resolved simple physical material."));
    Captured.PhysicalMaterialPath = Material->GetPathName();
    Captured.Friction = Material->Friction;
    Captured.StaticFriction = Material->StaticFriction;
    Captured.Restitution = Material->Restitution;
    Captured.EffectiveFrictionCombineMode = uint8(Material->bOverrideFrictionCombineMode
        ? Material->FrictionCombineMode.GetValue() : UPhysicsSettings::Get()->FrictionCombineMode.GetValue());
    Captured.EffectiveRestitutionCombineMode = uint8(Material->bOverrideRestitutionCombineMode
        ? Material->RestitutionCombineMode.GetValue() : UPhysicsSettings::Get()->RestitutionCombineMode.GetValue());
    Captured.SurfaceType = uint8(Material->SurfaceType.GetValue());

    TMap<const FKShapeElem*, FProphecyJoltRigShape> Authored;
    int32 ElementIndex = 0;
    auto Add = [&](const FKShapeElem& Element, EProphecyJoltRigShape Kind) -> FProphecyJoltRigShape&
    {
        auto& Shape = Authored.Add(&Element);
        Shape.Kind = Kind;
        Shape.SourceElementIndex = ElementIndex++;
        Shape.ElementName = Element.GetName();
        Shape.AuthoredLocalToBodyOrigin = Element.GetTransform();
        Shape.AuthoredCollisionEnabled = Element.GetCollisionEnabled();
        Shape.bContributesToAuthoredMass = Element.GetContributeToMass();
        Shape.RestOffsetCm = Element.RestOffset;
        return Shape;
    };
    const FKAggregateGeom& Agg = Setup.AggGeom;
    Snapshot.AuthoredSimpleShapeCount = Agg.GetElementCount();
    for (const FKSphereElem& Element : Agg.SphereElems)
        Add(Element, EProphecyJoltRigShape::Sphere).AuthoredRadiusCm = Element.Radius;
    for (const FKBoxElem& Element : Agg.BoxElems)
        Add(Element, EProphecyJoltRigShape::Box).AuthoredBoxHalfExtentCm = FVector(Element.X, Element.Y, Element.Z) * 0.5;
    for (const FKSphylElem& Element : Agg.SphylElems)
    {
        auto& Shape = Add(Element, EProphecyJoltRigShape::Capsule);
        Shape.AuthoredRadiusCm = Element.Radius;
        Shape.AuthoredCapsuleCylinderLengthCm = Element.Length;
    }
    for (const FKConvexElem& Element : Agg.ConvexElems)
    {
        Add(Element, EProphecyJoltRigShape::Convex);
        Snapshot.AuthoredConvexInputVertexCount += Element.VertexData.Num();
    }
    TArray<FPhysicsShapeHandle> Shapes;
    Instance.GetAllShapes_AssumesLocked(Shapes);
    Snapshot.NativeShapeCount = Shapes.Num();
    TSet<int32> SeenNativeIndices;
    TSet<const FKShapeElem*> SeenAuthored;
    bool bHaveFilter = false;
    for (const FPhysicsShapeHandle& Handle : Shapes)
    {
        if (!Handle.IsValid() || Handle.Shape->GetShapeIndex() < 0 || SeenNativeIndices.Contains(Handle.Shape->GetShapeIndex()))
            return Fail(Error, TEXT("Invalid or duplicate native standalone shape identity."));
        SeenNativeIndices.Add(Handle.Shape->GetShapeIndex());
        bool bEffectiveSimulation = Handle.Shape->GetSimEnabled();
        if (bEffectiveSimulation)
        {
            // Match Chaos's shape-pair filter: the raw sim flag is also set on the
            // query triangle mesh of ordinary SimpleAndComplex static-mesh bodies.
            const Chaos::FImplicitObject* Leaf = Handle.Shape->GetLeafGeometry();
            const auto CollisionType = Leaf ? Chaos::GetInnerType(Leaf->GetCollisionType()) : Chaos::ImplicitObjectType::Unknown;
            if (CollisionType == Chaos::ImplicitObjectType::Unknown || CollisionType == Chaos::ImplicitObjectType::LevelSet)
                return Fail(Error, TEXT("Standalone shape requires an unsupported particle-dependent collision type."));
            bEffectiveSimulation = Chaos::DoCollide(CollisionType, Handle.Shape);
        }
        if (!bEffectiveSimulation)
        {
            auto& Query = Snapshot.NonSimulationShapes.AddDefaulted_GetRef();
            Query.NativeShapeIndex = Handle.Shape->GetShapeIndex();
            Query.NativeGeometryType = uint32(Handle.GetGeometry().GetType());
            Query.bQueryEnabled = Handle.Shape->GetQueryEnabled();
            Query.bSimulationEnabled = Handle.Shape->GetSimEnabled(); // Raw flag; effective solver filtering excluded this shape.
            Query.bProbe = Handle.Shape->GetIsProbe();
            const FCollisionFilterData& Sim = Handle.Shape->GetSimData();
            const FCollisionFilterData& Queries = Handle.Shape->GetQueryData();
            Query.SimulationFilterWords[0] = Sim.Word0; Query.SimulationFilterWords[1] = Sim.Word1;
            Query.SimulationFilterWords[2] = Sim.Word2; Query.SimulationFilterWords[3] = Sim.Word3;
            Query.QueryFilterWords[0] = Queries.Word0; Query.QueryFilterWords[1] = Queries.Word1;
            Query.QueryFilterWords[2] = Queries.Word2; Query.QueryFilterWords[3] = Queries.Word3;
            const auto Bounds = Handle.GetGeometry().BoundingBox();
            Query.BoundsInBodyOriginCm = FBox(FVector(Bounds.Min()), FVector(Bounds.Max()));
            if (Query.bProbe) return Fail(Error, TEXT("Native probe shape requires contact/event behavior outside the standalone simulation-shape contract."));
            continue; // Query triangle mesh stays on the retained UE receiver; it is never a Jolt simulation hull.
        }
        if (Handle.Shape->GetIsProbe()) return Fail(Error, TEXT("Native simulation probes are unsupported."));
        const FKShapeElem* Element = FChaosUserData::Get<FKShapeElem>(FPhysicsInterface::GetUserData(Handle));
        const FProphecyJoltRigShape* Source = Authored.Find(Element);
        if (!Source || SeenAuthored.Contains(Element))
            return Fail(Error, FString::Printf(TEXT("Native simulation shape %d (geometry type %u) lacks unique supported sphere/box/capsule/convex authored identity; simulation triangle meshes and unsupported shapes are refused."),
                Handle.Shape->GetShapeIndex(), uint32(Handle.GetGeometry().GetType())));
        SeenAuthored.Add(Element);
        auto& Shape = Captured.Shapes.Add_GetRef(*Source);
        if (!BodyConversion::CaptureNativeShape(Handle, Shape, Error)) return false;
        if (!bHaveFilter)
        {
            Captured.ObjectType = Shape.NativeSimulationObjectType;
            Captured.CollisionResponses = Shape.NativeSimulationResponses;
            bHaveFilter = true;
        }
        else if (Captured.ObjectType != Shape.NativeSimulationObjectType || Captured.CollisionResponses != Shape.NativeSimulationResponses)
            return Fail(Error, TEXT("Simulated shapes disagree on object channel/block policy; per-shape simulation policies are not implemented by this body adapter."));
    }
    if (!bHaveFilter) return Fail(Error, TEXT("Standalone body has no simulation-enabled supported native shapes."));
    Captured.Shapes.Sort([](const FProphecyJoltRigShape& A, const FProphecyJoltRigShape& B)
        { return A.SourceElementIndex < B.SourceElementIndex; });
    return BodyConversion::ValidateBodyData(Captured, Error);
}
}

bool ValidateSnapshot(const FProphecyJoltBodySnapshot& Snapshot, FString& OutError)
{
    OutError.Reset();
    if (!Snapshot.CaptureId.IsValid() || !Snapshot.Body.bSimulating)
        return Fail(OutError, TEXT("Standalone capture identity or dynamic state is missing."));
    if (Snapshot.Body.bMACD)
        return Fail(OutError, TEXT("MACD is recorded but unsupported. Ordinary CCD may use the authorized Jolt linear-cast mode."));
    if (Snapshot.ComponentToWorld.ContainsNaN() || !Snapshot.ComponentToWorld.GetRotation().IsNormalized()
        || Snapshot.ComponentToWorld.GetScale3D().GetMin() <= 0.0 || !BodyConversion::Rigid(Snapshot.BodyOriginToComponent))
        return Fail(OutError, TEXT("Standalone visual component/body-origin mapping is invalid."));
    return BodyConversion::ValidateBodyData(Snapshot.Body, OutError);
}

bool CaptureLiveBody(UPrimitiveComponent& Component, FProphecyJoltBodySnapshot& OutSnapshot, FString& OutError)
{
    OutSnapshot = FProphecyJoltBodySnapshot();
    OutError.Reset();
    if (!IsInGameThread()) return Fail(OutError, TEXT("Standalone capture requires the game thread at a completed synchronous Chaos step."));
    UWorld* World = Component.GetWorld();
    if (!World || !World->IsGameWorld() || !Component.IsRegistered() || !Component.IsPhysicsStateCreated()
        || Cast<USkeletalMeshComponent>(&Component))
        return Fail(OutError, TEXT("Capture requires a registered single-body Game/PIE primitive; skeletal components use CaptureLiveRig."));
    if (UPhysicsSettings::Get()->bTickPhysicsAsync)
        return Fail(OutError, TEXT("Async Chaos standalone capture is unsupported."));
    FBodyInstance* Instance = Component.GetBodyInstance(NAME_None, false);
    const UBodySetup* Setup = Instance ? Instance->GetBodySetup() : nullptr;
    if (!Instance || !Instance->IsValidBodyInstance() || !Setup || Instance->WeldParent)
        return Fail(OutError, TEXT("Standalone component has no valid independent body/setup; welded bodies require a compound ownership adapter."));
    FProphecyJoltBodySnapshot Captured;
    Captured.CaptureId = FGuid::NewGuid();
    Captured.SourceComponent = &Component;
    Captured.SourceWorld = World;
    Captured.ComponentPath = Component.GetPathName();
    Captured.BodySetupPath = Setup->GetPathName();
    Captured.EngineFrame = GFrameCounter;
    Captured.WorldTimeSeconds = World->GetTimeSeconds();
    Captured.ComponentToWorld = Component.GetComponentTransform();
    if (const auto* Static = Cast<UStaticMeshComponent>(&Component))
        Captured.StaticMeshPath = GetPathNameSafe(Static->GetStaticMesh());
    bool bCaptured = false;
    const bool bRead = FPhysicsCommand::ExecuteRead(Instance->GetPhysicsActor(), [&](const FPhysicsActorHandle&)
        { bCaptured = CaptureLocked(*Instance, *Setup, Captured, OutError); });
    if (!bRead || !bCaptured) return OutError.IsEmpty() ? Fail(OutError, TEXT("Standalone native read failed.")) : false;
    const FTransform ComponentRigid(Captured.ComponentToWorld.GetRotation(), Captured.ComponentToWorld.GetLocation());
    Captured.BodyOriginToComponent = Captured.Body.BodyOriginToWorld.GetRelativeTransform(ComponentRigid);
    Captured.CoverageNotes.Add(TEXT("Only actual native simulation shapes are imported. Cooked convex vertices include their native transform/scale wrappers once; raw render/AggGeom input is not treated as the cooked hull."));
    Captured.CoverageNotes.Add(TEXT("Native non-simulation/query shape indices, types, bounds and filter words remain provenance. The original UE receiver retains complex query/paint geometry; native shape IDs are not UE FaceIndex values."));
    Captured.CoverageNotes.Add(TEXT("Mass, COM, principal inertia, body-origin pose, COM V/W, damping, speed caps, gravity and effective filter/material data are captured. Shape preparation does not apply dynamics or collision policy."));
    Captured.CoverageNotes.Add(TEXT("CCD=true is eligible for the authorized stock Jolt linear-cast mode at body creation; rotation-only tunneling and Chaos CCD response equivalence are not claimed. MACD is unsupported."));
    Captured.CoverageNotes.Add(TEXT("Native collision margins are provenance; Jolt convex hull uses zero bevel/hull tolerance to retain cooked outer vertices. UE contact offsets, friction-combine policy, inertia conditioning and solver-iteration semantics are not silently retuned."));
    if (!ValidateSnapshot(Captured, OutError)) return false;
    OutSnapshot = MoveTemp(Captured);
    return true;
}
}

class FProphecyJoltPreparedBodyState
{
public:
    FProphecyJoltPreparedBodyState() { ProphecyJolt::Body::LivePreparedBodies.Increment(); }
    ~FProphecyJoltPreparedBodyState() { Shape = nullptr; ProphecyJolt::Body::LivePreparedBodies.Decrement(); }
    FGuid CaptureId;
    JPH::RefConst<JPH::Shape> Shape;
    JPH::MassProperties Mass;
};

FProphecyJoltPreparedBody::FProphecyJoltPreparedBody() = default;
FProphecyJoltPreparedBody::~FProphecyJoltPreparedBody() = default;
FProphecyJoltPreparedBody::FProphecyJoltPreparedBody(FProphecyJoltPreparedBody&& Other) noexcept = default;
FProphecyJoltPreparedBody& FProphecyJoltPreparedBody::operator=(FProphecyJoltPreparedBody&& Other) noexcept = default;
void FProphecyJoltPreparedBody::Reset() { Native.Reset(); }
bool FProphecyJoltPreparedBody::IsValid() const { return Native && Native->Shape; }
FGuid FProphecyJoltPreparedBody::GetCaptureId() const { return Native ? Native->CaptureId : FGuid(); }
int32 FProphecyJoltPreparedBody::GetLivePreparedBodyCount() { return ProphecyJolt::Body::LivePreparedBodies.GetValue(); }
const JPH::Shape* FProphecyJoltPreparedBody::GetNativeShape() const { return Native ? Native->Shape.GetPtr() : nullptr; }
bool FProphecyJoltPreparedBody::GetNativeMassProperties(JPH::MassProperties& OutProperties) const
{
    if (!Native) return false;
    OutProperties = Native->Mass;
    return true;
}

bool FProphecyJoltPreparedBody::Build(const FProphecyJoltBodySnapshot& Snapshot, FString& OutError)
{
    OutError.Reset();
    if (!IsInGameThread()) { OutError = TEXT("Standalone shape preparation requires the game thread."); return false; }
    if (!JPH::VerifyJoltVersionID() || !JPH::Factory::sInstance)
    { OutError = TEXT("Jolt runtime/ABI is unavailable."); return false; }
    if (!ProphecyJolt::Body::ValidateSnapshot(Snapshot, OutError)) return false;
    auto Built = MakeUnique<FProphecyJoltPreparedBodyState>();
    Built->CaptureId = Snapshot.CaptureId;
    if (!ProphecyJolt::BodyConversion::PrepareShapeAndMass(Snapshot.Body, Built->Shape, Built->Mass, OutError)) return false;
    Native = MoveTemp(Built);
    return true;
}

bool FProphecyJoltPreparedBody::GetGeometrySummary(FVector& OutCOMCm, FBox& OutBoundsInBodyOriginCm, FString& OutError) const
{
    OutError.Reset();
    OutCOMCm = FVector::ZeroVector;
    OutBoundsInBodyOriginCm = FBox(ForceInit);
    if (!Native || !Native->Shape) { OutError = TEXT("Standalone geometry is not prepared."); return false; }
    const JPH::Vec3 COM = Native->Shape->GetCenterOfMass();
    const JPH::AABox Bounds = Native->Shape->GetLocalBounds();
    OutCOMCm = ProphecyJolt::Conversions::FromJoltPosition(JPH::RVec3(COM));
    OutBoundsInBodyOriginCm = FBox(ProphecyJolt::Conversions::FromJoltPosition(JPH::RVec3(Bounds.mMin + COM)),
        ProphecyJolt::Conversions::FromJoltPosition(JPH::RVec3(Bounds.mMax + COM)));
    return true;
}
