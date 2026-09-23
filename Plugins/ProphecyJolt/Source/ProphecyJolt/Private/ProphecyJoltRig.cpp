#include "ProphecyJoltRig.h"
#include "ProphecyJoltMaterial.h"
#include "ProphecyJoltBodyConversion.h"

#include "Chaos/Box.h"
#include "Chaos/Capsule.h"
#include "Chaos/ImplicitObjectTransformed.h"
#include "Chaos/ShapeInstance.h"
#include "Chaos/Sphere.h"
#include "Chaos/MassConditioning.h"
#include "HAL/IConsoleManager.h"
#include "Components/SkeletalMeshComponent.h"
#include "CoreGlobals.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "HAL/ThreadSafeCounter.h"
#include "PhysicalMaterials/PhysicalMaterial.h"
#include "Physics/PhysicsFiltering.h"
#include "Physics/PhysicsInterfaceCore.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/PhysicsSettings.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "ProphecyJoltConversions.h"

THIRD_PARTY_INCLUDES_START
#include <Jolt/Jolt.h>
#include <Jolt/Core/Factory.h>
#include <Jolt/Physics/Body/MassProperties.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/CapsuleShape.h>
#include <Jolt/Physics/Collision/Shape/ConvexHullShape.h>
#include <Jolt/Geometry/ConvexHullBuilder.h>
#include <Jolt/Physics/Collision/Shape/OffsetCenterOfMassShape.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Collision/Shape/StaticCompoundShape.h>
#include <Jolt/RegisterTypes.h>
THIRD_PARTY_INCLUDES_END

namespace ProphecyJolt::Rig
{
namespace
{
FThreadSafeCounter LivePreparedRigs;
constexpr double UnitScaleTolerance = 1.0e-4;

bool Fail(FString& OutError, const FString& Message) { OutError = Message; return false; }
bool Finite(const FVector& V) { return FMath::IsFinite(V.X) && FMath::IsFinite(V.Y) && FMath::IsFinite(V.Z); }
bool NativeFinite(double V) { return FMath::IsFinite(V) && FMath::IsFinite(static_cast<float>(V)); }
bool UnitScale(const FVector& Scale) { return Finite(Scale) && Scale.Equals(FVector::OneVector, UnitScaleTolerance); }
bool ValidFrame(const FTransform& Frame)
{
    return !Frame.ContainsNaN() && Frame.GetRotation().IsNormalized() && Finite(Frame.GetTranslation()) && UnitScale(Frame.GetScale3D());
}
bool PositiveNative(double V) { return NativeFinite(V) && V > 0.0 && static_cast<float>(V) > 0.0f; }
bool PositiveNativeVector(const FVector& V) { return PositiveNative(V.X) && PositiveNative(V.Y) && PositiveNative(V.Z); }
JPH::Vec3 LocalMeters(const FVector& V) { return static_cast<JPH::Vec3>(Conversions::ToJoltPosition(V)); }
FVector LocalCentimeters(JPH::Vec3Arg V) { return Conversions::FromJoltPosition(JPH::RVec3(V)); }

bool ValidateShape(const FProphecyJoltRigShape& Shape, FString& Error)
{
    if (Shape.SourceElementIndex < 0 || !ValidFrame(Shape.LocalToBodyOrigin) || !NativeFinite(Shape.RestOffsetCm))
        return Fail(Error, TEXT("Shape index/frame/rest offset is invalid; scaled shapes are unsupported."));
    if (Shape.bGeometryCapturedFromNative && (Shape.SourceNativeShapeIndex < 0
        || !NativeFinite(Shape.NativeCollisionMarginCm) || Shape.NativeCollisionMarginCm < 0.0))
        return Fail(Error, TEXT("Native shape index or captured collision margin is invalid."));
    if (!Finite(Shape.LocalToBodyOrigin.GetTranslation() * 0.01)
        || !NativeFinite(Shape.LocalToBodyOrigin.GetTranslation().X * 0.01)
        || !NativeFinite(Shape.LocalToBodyOrigin.GetTranslation().Y * 0.01)
        || !NativeFinite(Shape.LocalToBodyOrigin.GetTranslation().Z * 0.01))
        return Fail(Error, TEXT("Shape local position is outside native float precision range."));
    switch (Shape.Kind)
    {
    case EProphecyJoltRigShape::Sphere:
        return PositiveNative(Shape.RadiusCm * 0.01) || Fail(Error, TEXT("Sphere radius must be positive and finite."));
    case EProphecyJoltRigShape::Box:
        return PositiveNativeVector(Shape.BoxHalfExtentCm * 0.01) || Fail(Error, TEXT("Box half extents must be positive and finite."));
    case EProphecyJoltRigShape::Capsule:
        return (PositiveNative(Shape.RadiusCm * 0.01) && NativeFinite(Shape.CapsuleCylinderLengthCm * 0.005)
            && Shape.CapsuleCylinderLengthCm >= 0.0) || Fail(Error, TEXT("Capsule radius/straight cylinder length is invalid."));
    case EProphecyJoltRigShape::Convex:
        if (Shape.ConvexVerticesCm.Num() < 4)
            return Fail(Error, TEXT("Convex requires at least four retained input points."));
        for (const FVector& V : Shape.ConvexVerticesCm)
            if (!Finite(V) || !NativeFinite(V.X * 0.01) || !NativeFinite(V.Y * 0.01) || !NativeFinite(V.Z * 0.01))
                return Fail(Error, TEXT("Convex contains an invalid vertex."));
        return true;
    default:
        return Fail(Error, TEXT("Unsupported shape kind."));
    }
}

void AddDisabledPair(FProphecyJoltRigSnapshot& Snapshot, int32 A, int32 B, bool FromAsset)
{
    if (A > B) Swap(A, B);
    FProphecyJoltRigDisabledPair* Existing = Snapshot.DisabledPairs.FindByPredicate(
        [A, B](const FProphecyJoltRigDisabledPair& Pair) { return Pair.Body1Index == A && Pair.Body2Index == B; });
    if (!Existing)
    {
        Existing = &Snapshot.DisabledPairs.AddDefaulted_GetRef();
        Existing->Body1Index = A;
        Existing->Body2Index = B;
    }
    Existing->bFromPhysicsAsset |= FromAsset;
    Existing->bFromCurrentJoint |= !FromAsset;
}

bool CaptureNativePrimitive(const FPhysicsShapeHandle& Handle, FProphecyJoltRigShape& Out, FString& Error)
{
    if (!BodyConversion::CaptureGeometry(Handle.GetGeometry(), Out, Error)) return false;
    Out.SourceNativeShapeIndex = Handle.Shape->GetShapeIndex();
    Out.NativeCollisionMarginCm = Handle.GetGeometry().GetMarginf();
    Out.bNativeSimulationEnabled = Handle.Shape->GetSimEnabled();
    Out.bNativeQueryEnabled = Handle.Shape->GetQueryEnabled();
    Out.CurrentCollisionEnabled = CollisionEnabledFromFlags(Out.bNativeQueryEnabled,
        Out.bNativeSimulationEnabled, Handle.Shape->GetIsProbe());
    // Read the per-shape data used by Chaos::DoCollide, after body/component overrides.
    // Use the distinct official decoders: simulation Word2 is NOT an overlap mask.
    const FCollisionFilterData& SimFilter = Handle.Shape->GetSimData();
    const FCollisionFilterData& QueryFilter = Handle.Shape->GetQueryData();
    auto StoreWords = [](const FCollisionFilterData& Filter, uint32 (&Words)[4])
    { Words[0] = Filter.Word0; Words[1] = Filter.Word1; Words[2] = Filter.Word2; Words[3] = Filter.Word3; };
    StoreWords(SimFilter, Out.NativeSimulationFilterWords);
    StoreWords(QueryFilter, Out.NativeQueryFilterWords);
    if (Out.bNativeSimulationEnabled && !(SimFilter.Word0 || SimFilter.Word1 || SimFilter.Word2 || SimFilter.Word3))
        return Fail(Error, TEXT("An enabled native shape has the all-zero/no-filter simulation policy; this fixture requires an explicit channel filter."));
    Out.NativeSimulationObjectType = GetCollisionChannel(SimFilter.Word3);
    Out.NativeSimulationResponses = ExtractSimCollisionResponseContainer(SimFilter);
    Out.NativeQueryObjectType = GetCollisionChannel(QueryFilter.Word3);
    Out.NativeQueryResponses = ExtractQueryCollisionResponseContainer(QueryFilter);
    Out.bGeometryCapturedFromNative = true;
    return ValidateShape(Out, Error);
}

bool CaptureShapes(const FBodyInstance& Body, const UBodySetup& Setup, FProphecyJoltRigBody& Out, FString& Error)
{
    const FKAggregateGeom& Agg = Setup.AggGeom;
    // These scales are provenance only. Native geometry already includes all UE scaling decisions.
    Out.SourceBuildScale3D = Setup.BuildScale3D;
    Out.SourceBodyScale3D = Body.Scale3D;
    if (!PositiveNativeVector(Setup.BuildScale3D) || !PositiveNativeVector(Body.Scale3D))
        return Fail(Error, FString::Printf(TEXT("Primitive capture requires finite positive source scales; negative/invalid scales remain unsupported. BuildScale=(%.9g,%.9g,%.9g), BodyScale=(%.9g,%.9g,%.9g)."),
            Setup.BuildScale3D.X, Setup.BuildScale3D.Y, Setup.BuildScale3D.Z, Body.Scale3D.X, Body.Scale3D.Y, Body.Scale3D.Z));
    if (Agg.ConvexElems.Num())
        return Fail(Error, FString::Printf(TEXT("Native convex capture is unsupported; cooked hull vertices/wrappers need an explicit conversion. BuildScale=(%.9g,%.9g,%.9g), BodyScale=(%.9g,%.9g,%.9g)."),
            Setup.BuildScale3D.X, Setup.BuildScale3D.Y, Setup.BuildScale3D.Z, Body.Scale3D.X, Body.Scale3D.Y, Body.Scale3D.Z));
    if (Agg.TaperedCapsuleElems.Num() || Agg.LevelSetElems.Num() || Agg.SkinnedLevelSetElems.Num()
        || Agg.MLLevelSetElems.Num() || Agg.SkinnedTriangleMeshElems.Num() || Setup.TriMeshGeometries.Num()
        || Setup.GetCollisionTraceFlag() == CTF_UseComplexAsSimple)
        return Fail(Error, TEXT("Tapered capsules, level sets, skinned/triangle meshes and complex-as-simple bodies are unsupported."));
    if (Agg.GetElementCount() == 0)
        return Fail(Error, TEXT("Body has no authored simple collision geometry."));
    TArray<FPhysicsShapeHandle> NativeShapes;
    Body.GetAllShapes_AssumesLocked(NativeShapes);
    if (NativeShapes.Num() != Agg.GetElementCount())
        return Fail(Error, FString::Printf(TEXT("Native shape count %d does not match authored simple element count %d."),
            NativeShapes.Num(), Agg.GetElementCount()));
    TMap<const FKShapeElem*, int32> ElementToNativeIndex;
    for (int32 NativeIndex = 0; NativeIndex < NativeShapes.Num(); ++NativeIndex)
    {
        const FPhysicsShapeHandle& Handle = NativeShapes[NativeIndex];
        if (!Handle.IsValid() || Handle.Shape->GetShapeIndex() != NativeIndex)
            return Fail(Error, TEXT("Native shape handle or native shape-array index is invalid."));
        const FKShapeElem* Element = FChaosUserData::Get<FKShapeElem>(FPhysicsInterface::GetUserData(Handle));
        if (!Element || ElementToNativeIndex.Contains(Element))
            return Fail(Error, TEXT("Native shape lacks unique authored FKShapeElem user-data identity."));
        ElementToNativeIndex.Add(Element, NativeIndex);
    }
    int32 ElementIndex = 0;
    TArray<const FKShapeElem*> AuthoredElements;
    auto Add = [&](const FKShapeElem& Elem, EProphecyJoltRigShape Kind) -> FProphecyJoltRigShape&
    {
        FProphecyJoltRigShape& Shape = Out.Shapes.AddDefaulted_GetRef();
        Shape.Kind = Kind;
        Shape.SourceElementIndex = ElementIndex++;
        AuthoredElements.Add(&Elem);
        Shape.ElementName = Elem.GetName();
        Shape.LocalToBodyOrigin = Elem.GetTransform();
        Shape.AuthoredLocalToBodyOrigin = Elem.GetTransform();
        Shape.AuthoredCollisionEnabled = Elem.GetCollisionEnabled();
        Shape.bContributesToAuthoredMass = Elem.GetContributeToMass();
        Shape.RestOffsetCm = Elem.RestOffset;
        return Shape;
    };
    // Preserve FKAggregateGeom element order/identity independently of native shape-array order.
    // Dimensions below are source provenance; effective geometry is read from the native shape.
    for (const FKSphereElem& Elem : Agg.SphereElems)
    {
        FProphecyJoltRigShape& Shape = Add(Elem, EProphecyJoltRigShape::Sphere);
        Shape.AuthoredRadiusCm = Elem.Radius;
    }
    for (const FKBoxElem& Elem : Agg.BoxElems)
    {
        FProphecyJoltRigShape& Shape = Add(Elem, EProphecyJoltRigShape::Box);
        Shape.AuthoredBoxHalfExtentCm = FVector(Elem.X, Elem.Y, Elem.Z) * 0.5;
    }
    for (const FKSphylElem& Elem : Agg.SphylElems)
    {
        FProphecyJoltRigShape& Shape = Add(Elem, EProphecyJoltRigShape::Capsule);
        Shape.AuthoredRadiusCm = Elem.Radius;
        Shape.AuthoredCapsuleCylinderLengthCm = Elem.Length;
    }
    for (int32 Index = 0; Index < Out.Shapes.Num(); ++Index)
    {
        const int32* NativeIndex = ElementToNativeIndex.Find(AuthoredElements[Index]);
        if (!NativeIndex) return Fail(Error, FString::Printf(TEXT("Authored shape %d has no corresponding live native shape."), Index));
        if (!CaptureNativePrimitive(NativeShapes[*NativeIndex], Out.Shapes[Index], Error))
        {
            Error = FString::Printf(TEXT("Shape %d/native %d: %s"), Index, *NativeIndex, *Error);
            return false;
        }
    }
    bool bHaveSimulationFilter = false;
    for (const FProphecyJoltRigShape& Shape : Out.Shapes)
    {
        if (!Shape.bNativeSimulationEnabled) continue;
        if (!bHaveSimulationFilter)
        {
            Out.ObjectType = Shape.NativeSimulationObjectType;
            Out.CollisionResponses = Shape.NativeSimulationResponses;
            bHaveSimulationFilter = true;
        }
        else if (Out.ObjectType != Shape.NativeSimulationObjectType || Out.CollisionResponses != Shape.NativeSimulationResponses)
        {
            return Fail(Error, FString::Printf(TEXT("Native simulated shape %d has a different object channel/block response policy; per-shape simulation filters are unsupported by this rig fixture."),
                Shape.SourceNativeShapeIndex));
        }
    }
    if (!bHaveSimulationFilter) return Fail(Error, TEXT("Body has no native simulation-enabled primitive from which to capture its fixture collision policy."));
    return true;
}

bool CaptureLocked(USkeletalMeshComponent& Component, UPhysicsAsset& Asset, FProphecyJoltRigSnapshot& Snapshot, FString& Error)
{
    TMap<FName, int32> NameToBody;
    for (int32 Index = 0; Index < Asset.SkeletalBodySetups.Num(); ++Index)
    {
        const USkeletalBodySetup* Setup = Asset.SkeletalBodySetups[Index];
        const FBodyInstance* Body = Component.Bodies[Index];
        if (!Setup || !Body || !Body->IsValidBodyInstance() || Body->GetBodySetup() != Setup || Body->WeldParent)
            return Fail(Error, FString::Printf(TEXT("Body %d is missing, invalid, welded or uses another setup."), Index));
        if (Setup->BoneName.IsNone() || NameToBody.Contains(Setup->BoneName))
            return Fail(Error, FString::Printf(TEXT("Body %d has an empty/duplicate stable bone name."), Index));
        FProphecyJoltRigBody& Captured = Snapshot.Bodies.AddDefaulted_GetRef();
        Captured.SourceBodyIndex = Index;
        Captured.BodyName = Setup->BoneName;
        Captured.BoneIndex = Component.GetBoneIndex(Setup->BoneName);
        if (Captured.BoneIndex == INDEX_NONE) return Fail(Error, TEXT("Physics body bone is absent from the live mesh."));
        const FPhysicsActorHandle Actor = Body->GetPhysicsActor();
        // Read raw global body origin, with no custom visual projection or kinematic target substitution.
        Captured.BodyOriginToWorld = Body->GetUnrealWorldTransform_AssumesLocked(false, true);
        Captured.MassFrameToBodyOrigin = FPhysicsInterface::GetComTransformLocal_AssumesLocked(Actor);
        Captured.MassKg = FPhysicsInterface::GetMass_AssumesLocked(Actor);
        Captured.PrincipalInertiaKgCmSquared = FPhysicsInterface::GetLocalInertiaTensor_AssumesLocked(Actor);
        Captured.CenterOfMassVelocityCmPerSecond = FPhysicsInterface::GetLinearVelocity_AssumesLocked(Actor);
        Captured.AngularVelocityRadiansPerSecond = FPhysicsInterface::GetAngularVelocity_AssumesLocked(Actor);
        Captured.MaxLinearVelocityCmPerSecond = FPhysicsInterface::GetMaxLinearVelocity_AssumesLocked(Actor);
        Captured.MaxAngularVelocityRadiansPerSecond = FPhysicsInterface::GetMaxAngularVelocity_AssumesLocked(Actor);
        Captured.bSimulating = Body->IsInstanceSimulatingPhysics();
        Captured.bAwake = !FPhysicsInterface::IsSleeping(Actor);
        Captured.bGravityEnabled = FPhysicsInterface::IsGravityEnabled_AssumesLocked(Actor);
        Captured.bCCD = Body->bUseCCD;
        Captured.bMACD = Body->IsUsingMACD();
        Captured.bInertiaConditioning = Body->IsInertiaConditioningEnabled();
        Captured.LinearDamping = Body->LinearDamping;
        Captured.AngularDamping = Body->AngularDamping;
        Captured.bOverrideMaxDepenetrationVelocity = Body->GetOverrideMaxDepenetrationVelocity();
        Captured.MaxDepenetrationVelocityCmPerSecond = Body->GetMaxDepenetrationVelocity();
        Captured.PositionSolverIterations = Body->GetPositionSolverIterationCount();
        Captured.VelocitySolverIterations = Body->GetVelocitySolverIterationCount();
        Captured.ProjectionSolverIterations = Body->GetProjectionSolverIterationCount();
        Captured.CollisionEnabled = Body->GetCollisionEnabled();
        Captured.SourceBodyObjectType = Body->GetObjectType();
        Captured.SourceBodyCollisionResponses = Body->GetResponseToChannels();
        const UPhysicalMaterial* Material = Body->GetSimplePhysicalMaterial();
        if (!Material) return Fail(Error, TEXT("Live body has no resolvable simple physical material."));
        Captured.PhysicalMaterialPath = Material->GetPathName();
        Captured.Friction = Material->Friction;
        Captured.StaticFriction = Material->StaticFriction;
        Captured.Restitution = Material->Restitution;
        Captured.EffectiveFrictionCombineMode = static_cast<uint8>(Material->bOverrideFrictionCombineMode
            ? Material->FrictionCombineMode.GetValue() : UPhysicsSettings::Get()->FrictionCombineMode.GetValue());
        Captured.EffectiveRestitutionCombineMode = static_cast<uint8>(Material->bOverrideRestitutionCombineMode
            ? Material->RestitutionCombineMode.GetValue() : UPhysicsSettings::Get()->RestitutionCombineMode.GetValue());
        Captured.SurfaceType = static_cast<uint8>(Material->SurfaceType.GetValue());
        if (!CaptureShapes(*Body, *Setup, Captured, Error))
        {
            Error = FString::Printf(TEXT("Body %s: %s"), *Captured.BodyName.ToString(), *Error);
            return false;
        }
        NameToBody.Add(Captured.BodyName, Index);
        Snapshot.CoverageNotes.AddUnique(TEXT("Primitive dimensions/placements come from live Chaos geometry, including UE's nonuniform-scale decisions and dimension floors. Source scales and authored AggGeom values are provenance only and are not reapplied."));
        Snapshot.CoverageNotes.AddUnique(TEXT("Native primitive collision margins are recorded; matching Chaos/Jolt contact-generation margin semantics is not claimed."));
        Snapshot.CoverageNotes.AddUnique(TEXT("Body object channel/block responses come from agreed live native simulation filters, including skeletal-component overrides. Raw BodyInstance settings and per-shape simulation/query filter words/responses are retained as provenance."));
        if (Captured.bInertiaConditioning)
            Snapshot.CoverageNotes.AddUnique(TEXT("Body inertia conditioning is enabled. Captured actor principal I remains raw provenance; rig preparation derives effective native inertia from current engine policy, geometry bounds and joint arms."));
        if (Captured.bOverrideMaxDepenetrationVelocity)
            Snapshot.CoverageNotes.AddUnique(TEXT("A body initial-overlap depenetration override is recorded; no Jolt equivalent is selected by shape preparation."));
        if (Captured.bCCD || Captured.bMACD)
            Snapshot.CoverageNotes.AddUnique(TEXT("CCD/MACD is enabled in the source; shape preparation does not implement that collision mode."));
    }
    TSet<FName> JointNames;
    for (int32 Index = 0; Index < Component.Constraints.Num(); ++Index)
    {
        const FConstraintInstance* Joint = Component.Constraints[Index];
        if (!Joint || !Joint->IsValidConstraintInstance())
            return Fail(Error, FString::Printf(TEXT("Constraint %d is missing or has no valid live constraint."), Index));
        const int32* Body1 = NameToBody.Find(Joint->ConstraintBone1);
        const int32* Body2 = NameToBody.Find(Joint->ConstraintBone2);
        if (!Body1 || !Body2 || *Body1 == *Body2 || Joint->JointName.IsNone() || JointNames.Contains(Joint->JointName))
            return Fail(Error, FString::Printf(TEXT("Constraint %d has invalid/duplicate identity or unmapped bodies."), Index));
        FProphecyJoltRigJoint& Captured = Snapshot.Joints.AddDefaulted_GetRef();
        Captured.SourceConstraintIndex = Index;
        Captured.JointName = Joint->JointName;
        Captured.Bone1 = Joint->ConstraintBone1;
        Captured.Bone2 = Joint->ConstraintBone2;
        Captured.Body1Index = *Body1;
        Captured.Body2Index = *Body2;
        // GetRefFrame omits LastKnownScale and later native connector updates. GetLocalPose returns
        // JointTransforms[0/1], whose world pose is local * particle(R,X): body-origin, not COM, space.
        Captured.Frame1 = FPhysicsInterface::GetLocalPose(Joint->GetPhysicsConstraintRef(), EConstraintFrame::Frame1);
        Captured.Frame2 = FPhysicsInterface::GetLocalPose(Joint->GetPhysicsConstraintRef(), EConstraintFrame::Frame2);
        Captured.AngularRotationOffsetDegrees = Joint->AngularRotationOffset;
        Captured.CurrentProfile = Joint->ProfileInstance;
        JointNames.Add(Captured.JointName);
        if (Captured.CurrentProfile.bDisableCollision) AddDisabledPair(Snapshot, *Body1, *Body2, false);
    }
    // UE inserts value 0 for disabled pairs. Presence, not the bool value, disables collision.
    for (const TPair<FRigidBodyIndexPair, bool>& Entry : Asset.CollisionDisableTable)
    {
        const int32 A = Entry.Key.Indices[0];
        const int32 B = Entry.Key.Indices[1];
        if (!Snapshot.Bodies.IsValidIndex(A) || !Snapshot.Bodies.IsValidIndex(B) || A == B)
            return Fail(Error, TEXT("Physics asset disabled pair contains invalid body indices."));
        AddDisabledPair(Snapshot, A, B, true);
    }
    Snapshot.DisabledPairs.Sort([](const FProphecyJoltRigDisabledPair& A, const FProphecyJoltRigDisabledPair& B)
    { return A.Body1Index != B.Body1Index ? A.Body1Index < B.Body1Index : A.Body2Index < B.Body2Index; });
    return true;
}
}

bool ValidateSnapshot(const FProphecyJoltRigSnapshot& Snapshot, FString& OutError)
{
    OutError.Reset();
    if (!Snapshot.CaptureId.IsValid() || Snapshot.Bodies.IsEmpty()) return Fail(OutError, TEXT("Rig capture identity/bodies are missing."));
    TSet<FName> BodyNames;
    for (int32 Index = 0; Index < Snapshot.Bodies.Num(); ++Index)
    {
        const FProphecyJoltRigBody& Body = Snapshot.Bodies[Index];
        if (Body.SourceBodyIndex != Index || Body.BoneIndex < 0 || Body.BodyName.IsNone() || BodyNames.Contains(Body.BodyName)
            || !ValidFrame(Body.BodyOriginToWorld) || !ValidFrame(Body.MassFrameToBodyOrigin)
            || !PositiveNative(Body.MassKg) || !PositiveNativeVector(Body.PrincipalInertiaKgCmSquared * 0.0001)
            || !Finite(Body.CenterOfMassVelocityCmPerSecond) || !Finite(Body.AngularVelocityRadiansPerSecond)
            || !NativeFinite(Body.LinearDamping) || Body.LinearDamping < 0.0
            || !NativeFinite(Body.AngularDamping) || Body.AngularDamping < 0.0
            || !PositiveNative(Body.MaxLinearVelocityCmPerSecond * 0.01) || !PositiveNative(Body.MaxAngularVelocityRadiansPerSecond)
            || !NativeFinite(Body.Friction) || Body.Friction < 0.0 || !NativeFinite(Body.StaticFriction) || Body.StaticFriction < 0.0
            || !Material::ValidModes(Body.EffectiveFrictionCombineMode, Body.EffectiveRestitutionCombineMode)
            || !NativeFinite(Body.Restitution) || Body.Restitution < 0.0 || Body.Restitution > 1.0 || Body.Shapes.IsEmpty())
            return Fail(OutError, FString::Printf(TEXT("Body %d (%s) has invalid identity, unscaled frame, mass/inertia, velocity, material or damping data."), Index, *Body.BodyName.ToString()));
        BodyNames.Add(Body.BodyName);
        TSet<int32> ShapeIndices;
        for (const FProphecyJoltRigShape& Shape : Body.Shapes)
        {
            if (ShapeIndices.Contains(Shape.SourceElementIndex) || !ValidateShape(Shape, OutError))
                return Fail(OutError, FString::Printf(TEXT("Body %s shape %d is invalid or duplicated: %s"), *Body.BodyName.ToString(), Shape.SourceElementIndex, *OutError));
            ShapeIndices.Add(Shape.SourceElementIndex);
        }
    }
    TSet<FName> JointNames;
    for (const FProphecyJoltRigJoint& Joint : Snapshot.Joints)
    {
        if (Joint.SourceConstraintIndex < 0 || Joint.JointName.IsNone() || JointNames.Contains(Joint.JointName)
            || !Snapshot.Bodies.IsValidIndex(Joint.Body1Index) || !Snapshot.Bodies.IsValidIndex(Joint.Body2Index)
            || Joint.Body1Index == Joint.Body2Index || !ValidFrame(Joint.Frame1) || !ValidFrame(Joint.Frame2)
            || Snapshot.Bodies[Joint.Body1Index].BodyName != Joint.Bone1 || Snapshot.Bodies[Joint.Body2Index].BodyName != Joint.Bone2)
            return Fail(OutError, FString::Printf(TEXT("Joint %s has invalid identity, body mapping or frame."), *Joint.JointName.ToString()));
        JointNames.Add(Joint.JointName);
    }
    for (const FProphecyJoltRigDisabledPair& Pair : Snapshot.DisabledPairs)
        if (!Snapshot.Bodies.IsValidIndex(Pair.Body1Index) || !Snapshot.Bodies.IsValidIndex(Pair.Body2Index)
            || Pair.Body1Index >= Pair.Body2Index || (!Pair.bFromPhysicsAsset && !Pair.bFromCurrentJoint))
            return Fail(OutError, TEXT("Invalid disabled collision pair."));
    return true;
}

bool CaptureLiveRig(USkeletalMeshComponent& Component, FProphecyJoltRigSnapshot& OutSnapshot, FString& OutError)
{
    OutSnapshot = FProphecyJoltRigSnapshot();
    OutError.Reset();
    if (!IsInGameThread()) return Fail(OutError, TEXT("Live rig capture must run on the game thread."));
    UWorld* World = Component.GetWorld();
    UPhysicsAsset* Asset = Component.GetPhysicsAsset();
    USkeletalMesh* Mesh = Component.GetSkeletalMeshAsset();
    if (!World || !World->IsGameWorld() || !Component.IsRegistered() || !Component.IsPhysicsStateCreated() || !Asset || !Mesh)
        return Fail(OutError, TEXT("Capture requires a registered Game/PIE skeletal component with a live physics state, mesh and physics asset."));
    if (UPhysicsSettings::Get()->bTickPhysicsAsync)
        return Fail(OutError, TEXT("Async Chaos capture is not supported; this reader requires the current synchronous fixture cadence."));
    const FTransform Carrier=Component.GetComponentTransform();
    if (Carrier.ContainsNaN() || !Carrier.GetRotation().IsNormalized() || Carrier.GetScale3D().GetMin()<=0)
        return Fail(OutError, TEXT("Component transform must be finite, normalized and have positive scale."));
    // Body geometry/mass and joint connectors are read from live Chaos actors below;
    // component scale is already baked there. Do not apply it a second time.
    if (Asset->SkeletalBodySetups.IsEmpty() || Component.Bodies.Num() != Asset->SkeletalBodySetups.Num()
        || Component.Constraints.Num() != Asset->ConstraintSetup.Num())
        return Fail(OutError, TEXT("Live body/constraint arrays do not completely match the physics asset."));
    FProphecyJoltRigSnapshot Captured;
    Captured.CaptureId = FGuid::NewGuid();
    Captured.SourceComponent = &Component;
    Captured.SourceWorld = World;
    Captured.ComponentPath = Component.GetPathName();
    Captured.SkeletalMeshPath = Mesh->GetPathName();
    Captured.PhysicsAssetPath = Asset->GetPathName();
    Captured.EngineFrame = GFrameCounter;
    Captured.WorldTimeSeconds = World->GetTimeSeconds();
    Captured.CoverageNotes.Add(TEXT("Live sphere/box/capsule geometry and shape flags are captured under the mesh physics read lock, with unique authored element user-data matching. Only rigid transform wrappers are accepted; other wrappers/geometry fail explicitly."));
    Captured.CoverageNotes.Add(TEXT("Material coefficients/combine modes are captured per simple body material; preparation does not implement UE contact/filter/combine policy."));
    Captured.CoverageNotes.Add(TEXT("Disabled pairs combine physics-asset key presence and current anatomical joint collision-disable flags; arbitrary scene ignore-pair mutations are not introspected."));
    Captured.CoverageNotes.Add(TEXT("Joint CurrentProfile retains softness, drives, projection, conditioning and breakage/plasticity for explicit hard-fixture conversion; shape preparation does not implement them."));
    Captured.CoverageNotes.Add(TEXT("MaxDepenetrationVelocity records the configured initial-overlap override and enable flag; it is not a general solver velocity cap."));
    bool bCaptured = false;
    const bool bRead = FPhysicsCommand::ExecuteRead(&Component, [&]() { bCaptured = CaptureLocked(Component, *Asset, Captured, OutError); });
    if (!bRead || !bCaptured) return OutError.IsEmpty() ? Fail(OutError, TEXT("Mesh physics read failed.")) : false;
    if (!ValidateSnapshot(Captured, OutError)) return false;
    OutSnapshot = MoveTemp(Captured);
    return true;
}
}


namespace ProphecyJolt::BodyConversion
{
bool CaptureNativeShape(const FPhysicsShapeHandle& Handle, FProphecyJoltRigShape& OutShape, FString& OutError)
{
    return Rig::CaptureNativePrimitive(Handle, OutShape, OutError);
}

bool ValidateShapes(TConstArrayView<FProphecyJoltRigShape> Shapes, FString& OutError)
{
    if (Shapes.IsEmpty()) return Rig::Fail(OutError, TEXT("No simulation shapes were supplied."));
    TSet<int32> ShapeIndices;
    for (const FProphecyJoltRigShape& Shape : Shapes)
    {
        if (ShapeIndices.Contains(Shape.SourceElementIndex) || !Rig::ValidateShape(Shape, OutError))
            return OutError.IsEmpty() ? Rig::Fail(OutError, TEXT("Duplicate simulation shape identity.")) : false;
        ShapeIndices.Add(Shape.SourceElementIndex);
    }
    return true;
}

bool ValidateBodyData(const FProphecyJoltBodyData& Body, FString& OutError)
{
    using namespace Rig;
    if (!ValidFrame(Body.BodyOriginToWorld) || !ValidFrame(Body.MassFrameToBodyOrigin)
        || !PositiveNative(Body.MassKg) || !PositiveNativeVector(Body.PrincipalInertiaKgCmSquared * 0.0001)
        || !Finite(Body.CenterOfMassVelocityCmPerSecond) || !Finite(Body.AngularVelocityRadiansPerSecond)
        || !NativeFinite(Body.LinearDamping) || Body.LinearDamping < 0.0
        || !NativeFinite(Body.AngularDamping) || Body.AngularDamping < 0.0
        || !PositiveNative(Body.MaxLinearVelocityCmPerSecond * 0.01) || !PositiveNative(Body.MaxAngularVelocityRadiansPerSecond)
        || !NativeFinite(Body.Friction) || Body.Friction < 0.0 || !NativeFinite(Body.StaticFriction) || Body.StaticFriction < 0.0
        || !Material::ValidModes(Body.EffectiveFrictionCombineMode, Body.EffectiveRestitutionCombineMode)
        || !NativeFinite(Body.Restitution) || Body.Restitution < 0.0 || Body.Restitution > 1.0 || Body.Shapes.IsEmpty())
        return Fail(OutError, TEXT("Invalid rigid body frame, mass/inertia, velocity, damping, material or simulation shape data."));
    return ValidateShapes(Body.Shapes, OutError);
}

bool PrepareShapes(TConstArrayView<FProphecyJoltRigShape> Shapes, JPH::RefConst<JPH::Shape>& OutShape, FString& OutError)
{
    using namespace Rig;
    using namespace Conversions;
    OutError.Reset();
    if (!ValidateShapes(Shapes, OutError)) return false;
    JPH::StaticCompoundShapeSettings Compound;
    for (const FProphecyJoltRigShape& Shape : Shapes)
    {
        if (Shape.RestOffsetCm != 0.0)
            return Fail(OutError, FString::Printf(TEXT("Body %s shape %d has unsupported nonzero RestOffset."), TEXT("StandaloneBody"), Shape.SourceElementIndex));
        if (Shape.CurrentCollisionEnabled != ECollisionEnabled::QueryAndPhysics && Shape.CurrentCollisionEnabled != ECollisionEnabled::PhysicsOnly)
            return Fail(OutError, FString::Printf(TEXT("Body %s shape %d requires unsupported per-shape query/probe/disabled filtering."), TEXT("StandaloneBody"), Shape.SourceElementIndex));
        JPH::Shape::ShapeResult Result;
        JPH::Quat Rotation = ToJoltRotation(Shape.LocalToBodyOrigin.GetRotation());
        switch (Shape.Kind)
        {
        case EProphecyJoltRigShape::Sphere:
        {
            JPH::SphereShapeSettings Settings(static_cast<float>(Shape.RadiusCm * 0.01));
            Settings.mUserData = static_cast<uint64>(Shape.SourceElementIndex + 1);
            Result = Settings.Create();
            break;
        }
        case EProphecyJoltRigShape::Box:
        {
            // Zero convex radius preserves the authored outer box, with no implicit default bevel.
            JPH::BoxShapeSettings Settings(LocalMeters(Shape.BoxHalfExtentCm), 0.0f);
            Settings.mUserData = static_cast<uint64>(Shape.SourceElementIndex + 1);
            Result = Settings.Create();
            break;
        }
        case EProphecyJoltRigShape::Capsule:
        {
            JPH::CapsuleShapeSettings Settings(static_cast<float>(Shape.CapsuleCylinderLengthCm * 0.005), static_cast<float>(Shape.RadiusCm * 0.01));
            Settings.mUserData = static_cast<uint64>(Shape.SourceElementIndex + 1);
            Result = Settings.Create();
            // Jolt capsule Y -> UE sphyl Z, then the authored element rotation.
            Rotation = Rotation * JPH::Quat::sRotation(JPH::Vec3::sAxisX(), JPH::DegreesToRadians(90.0f));
            break;
        }
        case EProphecyJoltRigShape::Convex:
        {
            JPH::ConvexHullShapeSettings Settings;
            Settings.mHullTolerance = 0.0f;
            Settings.mMaxConvexRadius = 0.0f;
            Settings.mUserData = static_cast<uint64>(Shape.SourceElementIndex + 1);
            Settings.mPoints.reserve(Shape.ConvexVerticesCm.Num());
            for (const FVector& Point : Shape.ConvexVerticesCm) Settings.mPoints.push_back(LocalMeters(Point));
            if (Settings.mPoints.size() > JPH::ConvexHullShape::cMaxPointsInHull)
            {
                // ConvexHullShape accepts MaxVerticesReached and omits its consistency check
                // for that result. Refuse that implicit simplification, while allowing redundant
                // input points when the complete hull fits the native representation.
                JPH::ConvexHullBuilder Builder(Settings.mPoints);
                const char* BuilderError = nullptr;
                const auto BuildResult = Builder.Initialize(JPH::ConvexHullShape::cMaxPointsInHull, 0.0f, BuilderError);
                if (BuildResult == JPH::ConvexHullBuilder::EResult::MaxVerticesReached)
                {
                    JPH::ConvexHullBuilder::Face* ErrorFace = nullptr;
                    float MaxErrorMeters = 0.0f, CoplanarMeters = 0.0f;
                    int ErrorPoint = -1;
                    Builder.DetermineMaxError(ErrorFace, MaxErrorMeters, ErrorPoint, CoplanarMeters);
                    JPH::ConvexHullBuilder CompleteBuilder(Settings.mPoints);
                    const auto CompleteResult = CompleteBuilder.Initialize(MAX_int32, 0.0f, BuilderError);
                    const int32 Required = CompleteResult == JPH::ConvexHullBuilder::EResult::Success
                        ? CompleteBuilder.GetNumVerticesUsed() : INDEX_NONE;
                    return Fail(OutError, FString::Printf(TEXT("Convex has %d input points and requires %d final hull vertices; Jolt supports 256. Capped builder maximum error: %.9g mm (point %d); numeric coplanar distance: %.9g mm. No automatic simplification was applied."),
                        Shape.ConvexVerticesCm.Num(), Required, double(MaxErrorMeters) * 1000.0, ErrorPoint,
                        double(CoplanarMeters) * 1000.0));
                }
                if (BuildResult != JPH::ConvexHullBuilder::EResult::Success)
                    return Fail(OutError, FString::Printf(TEXT("Complete convex hull preflight failed: %s"),
                        BuilderError ? UTF8_TO_TCHAR(BuilderError) : TEXT("unknown builder error")));
            }
            Result = Settings.Create();
            break;
        }
        default: return Fail(OutError, TEXT("Unsupported native shape kind."));
        }
        if (Result.HasError()) return Fail(OutError, FString::Printf(TEXT("Body %s shape %d: %s"), TEXT("StandaloneBody"), Shape.SourceElementIndex, UTF8_TO_TCHAR(Result.GetError().c_str())));
        Compound.AddShape(LocalMeters(Shape.LocalToBodyOrigin.GetTranslation()), Rotation, Result.Get(), static_cast<JPH::uint32>(Shape.SourceElementIndex + 1));
    }
    const JPH::Shape::ShapeResult CompoundResult = Compound.Create();
    if (CompoundResult.HasError()) return Fail(OutError, FString::Printf(TEXT("Body %s compound: %s"), TEXT("StandaloneBody"), UTF8_TO_TCHAR(CompoundResult.GetError().c_str())));
    OutShape = CompoundResult.Get();
    return true;
}

bool PrepareShapeAndMass(const FProphecyJoltBodyData& Body, JPH::RefConst<JPH::Shape>& OutShape,
    JPH::MassProperties& OutMass, FString& OutError)
{
    using namespace Rig;
    using namespace Conversions;
    OutError.Reset();
    if (!ValidateBodyData(Body, OutError)) return false;
    JPH::RefConst<JPH::Shape> CompoundShape;
    if (!PrepareShapes(Body.Shapes, CompoundShape, OutError)) return false;
    JPH::RefConst<JPH::Shape> BuiltShape;
    JPH::MassProperties BuiltMass;
    const JPH::Vec3 DesiredCOM = LocalMeters(Body.MassFrameToBodyOrigin.GetTranslation());
    BuiltShape = new JPH::OffsetCenterOfMassShape(CompoundShape.GetPtr(), DesiredCOM - CompoundShape->GetCenterOfMass());
    BuiltMass.mMass = ToJoltMass(Body.MassKg);
    BuiltMass.mInertia = JPH::Mat44::sScale(ToJoltInertiaDiagonal(Body.PrincipalInertiaKgCmSquared));
    BuiltMass.Rotate(JPH::Mat44::sRotation(ToJoltRotation(Body.MassFrameToBodyOrigin.GetRotation())));
    // The input inertia is already about the actual COM. Do not add another parallel-axis translation.
    JPH::Mat44 PrincipalRotation;
    JPH::Vec3 PrincipalDiagonal;
    if (!BuiltMass.DecomposePrincipalMomentsOfInertia(PrincipalRotation, PrincipalDiagonal)
        || PrincipalDiagonal.GetX() <= 0.0f || PrincipalDiagonal.GetY() <= 0.0f || PrincipalDiagonal.GetZ() <= 0.0f)
        return Fail(OutError, FString::Printf(TEXT("Body %s native inertia decomposition failed."), TEXT("StandaloneBody")));
    if (!LocalCentimeters(BuiltShape->GetCenterOfMass()).Equals(Body.MassFrameToBodyOrigin.GetTranslation(), 1.0e-3))
        return Fail(OutError, FString::Printf(TEXT("Body %s native COM round-trip exceeds 0.001 cm."), TEXT("StandaloneBody")));
    OutShape = MoveTemp(BuiltShape);
    OutMass = BuiltMass;
    return true;
}
}

struct FImportedInertiaConditioning
{
    bool bEnabled = false;
    bool bExcludeFreeJoints = true;
    float DistanceCm = 20;
    float RotationRatio = 2.5f;
    float MaxComponentRatio = 0;
    Chaos::FInertiaConditioningTolerances Tolerances;

    bool Capture(const FProphecyJoltRigSnapshot& Snapshot, FString& Error)
    {
        if (!Snapshot.Bodies.ContainsByPredicate([](const auto& Body) { return Body.bInertiaConditioning; })) return true;
        auto Read = [](const TCHAR* Name, float Default) {
            const auto* Var = IConsoleManager::Get().FindConsoleVariable(Name);
            return Var ? Var->GetFloat() : Default;
        };
        bEnabled = Read(TEXT("p.Chaos.Solver.InertiaConditioning.Enabled"), 1) != 0;
        if (!bEnabled) return true;
        bExcludeFreeJoints = Read(TEXT("p.Chaos.ExcludeFreeJointForInertiaConditioning"),1) != 0;
        DistanceCm = Read(TEXT("p.Chaos.Solver.InertiaConditioning.Distance"),20);
        RotationRatio = Read(TEXT("p.Chaos.Solver.InertiaConditioning.RotationRatio"),2.5f);
        MaxComponentRatio = Read(TEXT("p.Chaos.Solver.InertiaConditioning.MaxInvInertiaComponentRatio"),0);
        Tolerances.InvMassTolerance = Read(TEXT("p.Chaos.InertiaConditioning.InvMassTolerance"), Tolerances.InvMassTolerance);
        Tolerances.InvInertiaTolerance = Read(TEXT("p.Chaos.InertiaConditioning.InvInertiaTolerance"), Tolerances.InvInertiaTolerance);
        Tolerances.ExtentTolerance = Read(TEXT("p.Chaos.InertiaConditioning.ExtentTolerance"), Tolerances.ExtentTolerance);
        for (float Value : {DistanceCm, RotationRatio, MaxComponentRatio, Tolerances.InvMassTolerance,
            Tolerances.InvInertiaTolerance, Tolerances.ExtentTolerance})
            if (!FMath::IsFinite(Value) || Value < 0)
                return ProphecyJolt::Rig::Fail(Error, TEXT("Invalid inertia-conditioning setting; expected finite nonnegative values."));
        if (RotationRatio <= 0)
            return ProphecyJolt::Rig::Fail(Error, TEXT("Inertia-conditioning rotation ratio must be positive."));
        return true;
    }
};

// Admission-only: derive effective native inertia from the body opt-in, current
// engine policy, geometry bounds and attached joint arms. No live Chaos solver
// state is read, no mass is redistributed, and no per-step conditioning is added.
static bool ApplyImportedInertiaConditioning(const FProphecyJoltRigSnapshot& Snapshot, int32 Index,
    const FImportedInertiaConditioning& Policy, const JPH::Shape& Shape, JPH::MassProperties& Mass, FString& Error)
{
    const auto& Body = Snapshot.Bodies[Index];
    if (!Policy.bEnabled || !Body.bInertiaConditioning) return true;
    const JPH::AABox Bounds = Shape.GetLocalBounds();
    FBox PrincipalBounds(ForceInit);
    const FQuat PrincipalRotation = Body.MassFrameToBodyOrigin.GetRotation();
    for (int32 Corner = 0; Corner < 8; ++Corner)
    {
        const FVector Point(Corner & 1 ? Bounds.mMax.GetX() : Bounds.mMin.GetX(),
            Corner & 2 ? Bounds.mMax.GetY() : Bounds.mMin.GetY(),
            Corner & 4 ? Bounds.mMax.GetZ() : Bounds.mMin.GetZ());
        PrincipalBounds += PrincipalRotation.UnrotateVector(Point * 100.0);
    }
    FVector Extent = PrincipalBounds.GetExtent();
    for (const auto& Joint : Snapshot.Joints)
    {
        const auto& P = Joint.CurrentProfile;
        if (P.LinearLimit.XMotion == LCM_Free && P.LinearLimit.YMotion == LCM_Free && P.LinearLimit.ZMotion == LCM_Free
            && !P.LinearDrive.IsPositionDriveEnabled() && Policy.bExcludeFreeJoints) continue;
        const FTransform* Frame = Joint.Body1Index == Index ? &Joint.Frame1 : Joint.Body2Index == Index ? &Joint.Frame2 : nullptr;
        if (Frame) Extent = Extent.ComponentMax(Body.MassFrameToBodyOrigin.InverseTransformPosition(Frame->GetTranslation()).GetAbs());
    }
    const FVector I = Body.PrincipalInertiaKgCmSquared;
    const Chaos::FVec3f Scale = Chaos::CalculateInertiaConditioning(float(1.0 / Body.MassKg),
        Chaos::FVec3f(1.0/I.X, 1.0/I.Y, 1.0/I.Z), Chaos::FVec3f(Extent),
        Policy.DistanceCm, Policy.RotationRatio, Policy.MaxComponentRatio, Policy.Tolerances);
    if (Scale.GetMin() <= 0 || !FMath::IsFinite(Scale.X) || !FMath::IsFinite(Scale.Y) || !FMath::IsFinite(Scale.Z)
        || !ProphecyJolt::Rig::PositiveNativeVector((I / FVector(Scale)) * 0.0001))
        return ProphecyJolt::Rig::Fail(Error, TEXT("Conditioned inertia exceeds the finite positive native range."));
    Mass.mInertia = JPH::Mat44::sScale(ProphecyJolt::Conversions::ToJoltInertiaDiagonal(I / FVector(Scale)));
    Mass.Rotate(JPH::Mat44::sRotation(ProphecyJolt::Conversions::ToJoltRotation(PrincipalRotation)));
    JPH::Mat44 Rotation;
    JPH::Vec3 Diagonal;
    if (!Mass.DecomposePrincipalMomentsOfInertia(Rotation, Diagonal)
        || !ProphecyJolt::Rig::PositiveNativeVector(ProphecyJolt::Conversions::FromJoltDirection(Diagonal)))
        return ProphecyJolt::Rig::Fail(Error, TEXT("Conditioned inertia cannot be decomposed into positive native principal moments."));
    return true;
}

class FProphecyJoltPreparedRigState
{
public:
    struct FBody
    {
        JPH::RefConst<JPH::Shape> Shape;
        JPH::MassProperties Mass;
    };
    FProphecyJoltPreparedRigState() { ProphecyJolt::Rig::LivePreparedRigs.Increment(); }
    ~FProphecyJoltPreparedRigState() { Bodies.Empty(); ProphecyJolt::Rig::LivePreparedRigs.Decrement(); }
    FGuid CaptureId;
    TArray<FBody> Bodies;
};

FProphecyJoltPreparedRig::FProphecyJoltPreparedRig() = default;
FProphecyJoltPreparedRig::~FProphecyJoltPreparedRig() = default;
FProphecyJoltPreparedRig::FProphecyJoltPreparedRig(FProphecyJoltPreparedRig&& Other) noexcept = default;
FProphecyJoltPreparedRig& FProphecyJoltPreparedRig::operator=(FProphecyJoltPreparedRig&& Other) noexcept = default;
void FProphecyJoltPreparedRig::Reset() { Native.Reset(); }
int32 FProphecyJoltPreparedRig::GetBodyCount() const { return Native ? Native->Bodies.Num() : 0; }
FGuid FProphecyJoltPreparedRig::GetCaptureId() const { return Native ? Native->CaptureId : FGuid(); }
int32 FProphecyJoltPreparedRig::GetLivePreparedRigCount() { return ProphecyJolt::Rig::LivePreparedRigs.GetValue(); }

bool FProphecyJoltPreparedRig::Build(const FProphecyJoltRigSnapshot& Snapshot, FString& OutError)
{
    using namespace ProphecyJolt::Rig;
    using namespace ProphecyJolt::Conversions;
    OutError.Reset();
    if (!IsInGameThread()) return Fail(OutError, TEXT("Prepared rig construction must run on the game thread."));
    if (!JPH::VerifyJoltVersionID() || !JPH::Factory::sInstance)
        return Fail(OutError, TEXT("Jolt runtime/ABI is unavailable."));
    if (!ValidateSnapshot(Snapshot, OutError)) return false;
    FImportedInertiaConditioning Conditioning;
    if (!Conditioning.Capture(Snapshot, OutError)) return false;
    TUniquePtr<FProphecyJoltPreparedRigState> Built = MakeUnique<FProphecyJoltPreparedRigState>();
    Built->CaptureId = Snapshot.CaptureId;
    for (const FProphecyJoltRigBody& Body : Snapshot.Bodies)
    {
        FProphecyJoltPreparedRigState::FBody& Prepared = Built->Bodies.AddDefaulted_GetRef();
        if (!ProphecyJolt::BodyConversion::PrepareShapeAndMass(Body, Prepared.Shape, Prepared.Mass, OutError))
        {
            OutError = FString::Printf(TEXT("Body %s: %s"), *Body.BodyName.ToString(), *OutError);
            return false;
        }
        if (!ApplyImportedInertiaConditioning(Snapshot, Built->Bodies.Num()-1, Conditioning, *Prepared.Shape, Prepared.Mass, OutError))
        {
            OutError = FString::Printf(TEXT("Body %s: %s"), *Body.BodyName.ToString(), *OutError);
            return false;
        }
    }
    Native = MoveTemp(Built);
    return true;
}

const JPH::Shape* FProphecyJoltPreparedRig::GetNativeBodyShape(int32 BodyIndex) const
{
    return Native && Native->Bodies.IsValidIndex(BodyIndex) ? Native->Bodies[BodyIndex].Shape.GetPtr() : nullptr;
}
bool FProphecyJoltPreparedRig::GetNativeBodyMassProperties(int32 BodyIndex, JPH::MassProperties& OutProperties) const
{
    if (!Native || !Native->Bodies.IsValidIndex(BodyIndex)) return false;
    OutProperties = Native->Bodies[BodyIndex].Mass;
    return true;
}
bool FProphecyJoltPreparedRig::GetBodyGeometrySummary(int32 BodyIndex, FVector& OutCenterOfMassCm, FBox& OutBoundsInBodyOriginCm, FString& OutError) const
{
    using namespace ProphecyJolt::Rig;
    OutError.Reset();
    OutCenterOfMassCm = FVector::ZeroVector;
    OutBoundsInBodyOriginCm = FBox(ForceInit);
    const JPH::Shape* Shape = GetNativeBodyShape(BodyIndex);
    if (!Shape) return Fail(OutError, TEXT("Prepared body index is invalid."));
    const JPH::Vec3 COM = Shape->GetCenterOfMass();
    const JPH::AABox Bounds = Shape->GetLocalBounds();
    OutCenterOfMassCm = LocalCentimeters(COM);
    OutBoundsInBodyOriginCm = FBox(LocalCentimeters(Bounds.mMin + COM), LocalCentimeters(Bounds.mMax + COM));
    return true;
}
