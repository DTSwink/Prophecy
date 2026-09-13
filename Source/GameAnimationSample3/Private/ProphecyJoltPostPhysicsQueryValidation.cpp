#include "ProphecyJoltPostPhysicsQueryValidation.h"
#include "UObject/Package.h"

#include "ProphecyJoltRig.h"
#include "Chaos/ImplicitObject.h"
#include "Chaos/ShapeInstance.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "GameFramework/Actor.h"
#include "Physics/PhysicsFiltering.h"
#include "Physics/PhysicsInterfaceCore.h"
#include "Dom/JsonObject.h"
#include "Engine/World.h"
#include "PhysicsEngine/BodyInstance.h"
#include "PhysicsProxy/SingleParticlePhysicsProxy.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Chaos/Sphere.h"
#include "UObject/StrongObjectPtrTemplates.h"
#include "Chaos/ChaosMarshallingManager.h"
#include "Chaos/ISpatialAcceleration.h"
#include "PBDRigidsSolver.h"
#include "ProphecyJoltPoseAnimInstance.h"
#include "ProphecyJoltQueryPose.h"
#include "Engine/Engine.h"
#include "Engine/SkeletalMesh.h"
#include "GameFramework/Pawn.h"
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "Physics/Experimental/PhysScene_Chaos.h"
#endif

namespace ProphecySterileBench::MultiJolt
{
namespace
{
constexpr double PositionToleranceCm = 0.02;
constexpr double AngleToleranceDegrees = 0.02;
constexpr double EdgeClearanceCm = 0.04;

void WriteVector(FJsonObject& Row, const TCHAR* Name, const FVector& Value)
{
    TArray<TSharedPtr<FJsonValue>> Elements;
    for (int32 Axis = 0; Axis != 3; ++Axis) Elements.Add(MakeShared<FJsonValueNumber>(Value[Axis]));
    Row.SetArrayField(Name, Elements);
}

bool ReadVector(const FJsonObject& Row, const TCHAR* Name, FVector& Out)
{
    const TArray<TSharedPtr<FJsonValue>>* Values = nullptr;
    if (!Row.TryGetArrayField(Name, Values) || !Values || Values->Num() != 3) return false;
    for (int32 Axis = 0; Axis != 3; ++Axis)
    {
        double Number;
        if (!(*Values)[Axis] || !(*Values)[Axis]->TryGetNumber(Number) || !FMath::IsFinite(Number)) return false;
        Out[Axis] = Number;
    }
    return true;
}

// All ray calculations use the original, already-scaled Chaos query geometry. The rigid body/bone
// pose supplies only rotation and translation, exactly as the native query publisher does.
bool ExpectedIntersection(const Chaos::FImplicitObject& Geometry, const FTransform& Pose,
    const FVector& Start, const FVector& End, FVector& OutPoint)
{
    const double Length = FVector::Distance(Start, End);
    if (Length <= UE_SMALL_NUMBER) return false;
    const Chaos::FVec3 LocalStart(Pose.InverseTransformPositionNoScale(Start));
    const Chaos::FVec3 LocalDirection(Pose.InverseTransformVectorNoScale((End - Start) / Length));
    Chaos::FReal Time = 0;
    Chaos::FVec3 Point, Normal;
    int32 Face = INDEX_NONE;
    if (!Geometry.Raycast(LocalStart, LocalDirection, Length, 0.0, Time, Point, Normal, Face)
        || !FMath::IsFinite(Time) || Time <= 0.0 || Time >= Length || FVector(Point).ContainsNaN()) return false;
    OutPoint = Pose.TransformPositionNoScale(FVector(Point));
    return !OutPoint.ContainsNaN();
}

struct FAnalyticQueryBody
{
    const Chaos::FImplicitObject* Geometry = nullptr;
    FTransform Pose = FTransform::Identity;
    FName Name;
    TWeakObjectPtr<UCapsuleComponent> OwnerCapsule;
};

// Select candidates entirely from native geometry at COMPLETED bone poses. This function never
// performs a scene query, so a failed UE ray cannot influence which candidates are accepted.
bool SelectAnalyticHeadCandidate(TConstArrayView<FAnalyticQueryBody> Bodies,
    const Chaos::FImplicitObject& HeadGeometry, const FTransform& HeadPose,
    const FVector& Start, const FVector& End, FVector& OutPoint, bool& bOutHeadFirst,
    FName& OutOccluder, FString& OutError, const UCapsuleComponent* IgnoredCapsule = nullptr)
{
    bOutHeadFirst = false;
    OutOccluder = NAME_None;
    OutError.Reset();
    if (!ExpectedIntersection(HeadGeometry, HeadPose, Start, End, OutPoint)) return true;
    const double Length = FVector::Distance(Start, End);
    const double HeadDistance = FVector::Distance(Start, OutPoint);
    const FVector Direction = (End - Start) / Length;
    for (const FAnalyticQueryBody& Body : Bodies)
    {
        if ((!Body.OwnerCapsule.IsValid() && Body.Name == FName(TEXT("head")))
            || (IgnoredCapsule && Body.OwnerCapsule.Get() == IgnoredCapsule)) continue;
        const Chaos::FVec3 LocalStart(Body.Pose.InverseTransformPositionNoScale(Start));
        // A ray beginning inside another body is occluded at time zero, even if that shape's
        // raycast implementation instead reports its exit or no intersection.
        if (Body.Geometry->Overlap(LocalStart, 0.0))
        { OutOccluder = Body.Name; return true; }
        const Chaos::FVec3 LocalDirection(Body.Pose.InverseTransformVectorNoScale(Direction));
        Chaos::FReal Time = 0;
        Chaos::FVec3 Point, Normal;
        int32 Face = INDEX_NONE;
        if (!Body.Geometry->Raycast(LocalStart, LocalDirection, Length, 0.0, Time, Point, Normal, Face)) continue;
        if (!FMath::IsFinite(Time) || Time < 0.0 || Time > Length || FVector(Point).ContainsNaN())
        {
            OutError = FString::Printf(TEXT("Native analytic query for %s returned an invalid ray intersection."), *Body.Name.ToString());
            return false;
        }
        // Reject ambiguous equal-distance contacts too; this fixture is specifically testing the
        // original HEAD receiver. The retained geometry, not the UE scene result, decides occlusion.
        if (Time <= HeadDistance + PositionToleranceCm)
        { OutOccluder = Body.Name; return true; }
    }
    bOutHeadFirst = true;
    return true;
}

// The NN fixture retains its real movement capsule. Use its native, already-scaled simple
// query shape and effective filter; authored radius/scale and the head trace result are not inputs.
bool AppendOwnBlockingCapsule(USkeletalMeshComponent& Mesh,
    TArray<FAnalyticQueryBody, TInlineAllocator<32>>& Bodies, FJsonObject& Row, FString& Error)
{
    // ProphecyAgent is an APawn with a native capsule root, not an ACharacter.
    AActor* Owner = Mesh.GetOwner();
    UCapsuleComponent* Capsule = Owner ? Cast<UCapsuleComponent>(Owner->GetRootComponent()) : nullptr;
    Row.SetStringField(TEXT("own_root_component"), Owner ? GetPathNameSafe(Owner->GetRootComponent()) : TEXT("None"));
    Row.SetBoolField(TEXT("own_root_is_capsule"), Capsule != nullptr);
    Row.SetNumberField(TEXT("own_blocking_capsule_shapes"), 0);
    if (!Capsule || !Capsule->IsRegistered() || !Capsule->IsQueryCollisionEnabled()) return true;
    FBodyInstance* Body = Capsule->GetBodyInstance(NAME_None, false);
    if (!Body || Body->WeldParent || !Body->IsValidBodyInstance() || !Body->GetPhysicsActor()
        || Body->GetPhysicsActor()->GetMarkedDeleted())
    { Error = TEXT("The retained query capsule has no valid unwelded native body."); return false; }
    bool bValid = true;
    const bool bRead = FPhysicsCommand::ExecuteRead(Body->GetPhysicsActor(), [&](const FPhysicsActorHandle& Actor)
    {
        TArray<FPhysicsShapeHandle> Shapes;
        Body->GetAllShapes_AssumesLocked(Shapes);
        // This fixture's actor root capsule has one native primitive. Do not guess at a
        // welded or compound receiver's shape-to-component ownership.
        if (Shapes.Num() != 1 || !Shapes[0].IsValid())
        { Error = TEXT("The retained root capsule is not one valid native shape."); bValid = false; return; }
        const FPhysicsShapeHandle& Shape = Shapes[0];
        const FCollisionFilterData& Filter = Shape.Shape->GetQueryData();
        if (!Shape.Shape->GetQueryEnabled() || !(Filter.Word3 & EPDF_SimpleCollision)
            || ExtractQueryCollisionResponseContainer(Filter).GetResponse(ECC_WorldStatic) != ECR_Block) return;
        const auto& External = Actor->GetGameThreadAPI();
        const FTransform Native(FQuat(External.R()), FVector(External.X()));
        const FTransform Component = Capsule->GetComponentTransform();
        if (Native.ContainsNaN() || Component.ContainsNaN() || !Native.GetRotation().IsNormalized()
            || !Component.GetRotation().IsNormalized())
        { Error = TEXT("The retained query capsule has an invalid native/component pose."); bValid = false; return; }
        const double PositionError = FVector::Distance(Native.GetTranslation(), Component.GetTranslation());
        const double AngleError = FMath::RadiansToDegrees(Native.GetRotation().GetNormalized()
            .AngularDistance(Component.GetRotation().GetNormalized()));
        if (PositionError > PositionToleranceCm || AngleError > AngleToleranceDegrees)
        { Error = TEXT("The retained native capsule pose differs from its current component pose."); bValid = false; return; }
        FAnalyticQueryBody& Entry = Bodies.AddDefaulted_GetRef();
        Entry.Geometry = &Shape.GetGeometry();
        Entry.Pose = FTransform(Component.GetRotation().GetNormalized(), Component.GetTranslation());
        Entry.Name = Capsule->GetFName();
        Entry.OwnerCapsule = Capsule;
        Row.SetNumberField(TEXT("own_blocking_capsule_shapes"), 1);
        Row.SetStringField(TEXT("own_blocking_capsule"), Capsule->GetPathName());
        Row.SetNumberField(TEXT("capsule_native_component_position_error_cm"), PositionError);
        Row.SetNumberField(TEXT("capsule_native_component_angle_error_degrees"), AngleError);
    });
    if (!bRead) { Error = TEXT("Reading the retained query capsule failed."); return false; }
    return bValid;
}

struct FCapsuleFallback
{
    TWeakObjectPtr<UCapsuleComponent> Capsule;
    FVector Start = FVector::ZeroVector, End = FVector::ZeroVector;
    FVector HeadPoint = FVector::ZeroVector, CapsulePoint = FVector::ZeroVector;
    int32 Axis = INDEX_NONE;
    bool bReverse = false, bStartsInsideCapsule = false;
};

// A fallback is eligible only if the independently predicted capsule is strictly before the
// head, and ignoring that exact capsule leaves the head first among every other rig body.
bool FindAnalyticCapsuleFallback(TConstArrayView<FAnalyticQueryBody> Bodies,
    const Chaos::FImplicitObject& HeadGeometry, const FTransform& HeadPose,
    const FVector& Start, const FVector& End, FCapsuleFallback& Out, FString& Error)
{
    Out = FCapsuleFallback();
    for (const FAnalyticQueryBody& Body : Bodies)
    {
        UCapsuleComponent* Capsule = Body.OwnerCapsule.Get();
        if (!Capsule) continue;
        FVector HeadPoint;
        bool bHeadFirst = false;
        FName Occluder;
        if (!SelectAnalyticHeadCandidate(Bodies, HeadGeometry, HeadPose, Start, End,
            HeadPoint, bHeadFirst, Occluder, Error, Capsule)) return false;
        if (!bHeadFirst) continue;
        const Chaos::FVec3 LocalStart(Body.Pose.InverseTransformPositionNoScale(Start));
        const bool bInside = Body.Geometry->Overlap(LocalStart, 0.0);
        FVector CapsulePoint = Start;
        if (!bInside && !ExpectedIntersection(*Body.Geometry, Body.Pose, Start, End, CapsulePoint)) continue;
        if (FVector::Distance(Start, CapsulePoint) >= FVector::Distance(Start, HeadPoint)) continue;
        Out.Capsule = Capsule;
        Out.Start = Start; Out.End = End;
        Out.HeadPoint = HeadPoint; Out.CapsulePoint = CapsulePoint;
        Out.bStartsInsideCapsule = bInside;
        return true;
    }
    return true;
}

bool TraceExpectedCapsule(USkeletalMeshComponent& Mesh, const FCapsuleFallback& Expected,
    FJsonObject& Row, FString& Error)
{
    UCapsuleComponent* Capsule = Expected.Capsule.Get();
    if (!Capsule || !Capsule->IsRegistered() || Capsule->GetOwner() != Mesh.GetOwner())
    { Error = TEXT("The independently predicted own capsule expired before its diagnostic trace."); return false; }
    FCollisionQueryParams Params(SCENE_QUERY_STAT(ProphecyJoltPostPhysicsCapsule), false);
    FHitResult Hit;
    const bool bHit = Mesh.GetWorld()->LineTraceSingleByChannel(Hit, Expected.Start, Expected.End, ECC_WorldStatic, Params);
    const double PositionError = bHit ? FVector::Distance(Hit.ImpactPoint, Expected.CapsulePoint) : -1.0;
    WriteVector(Row, TEXT("start_cm"), Expected.Start);
    WriteVector(Row, TEXT("end_cm"), Expected.End);
    WriteVector(Row, TEXT("expected_impact_cm"), Expected.CapsulePoint);
    if (bHit) WriteVector(Row, TEXT("actual_impact_cm"), Hit.ImpactPoint);
    Row.SetStringField(TEXT("expected_capsule"), Capsule->GetPathName());
    Row.SetStringField(TEXT("hit_component"), GetPathNameSafe(Hit.GetComponent()));
    Row.SetNumberField(TEXT("impact_error_cm"), PositionError);
    Row.SetBoolField(TEXT("analytic_start_inside_capsule"), Expected.bStartsInsideCapsule);
    Row.SetBoolField(TEXT("actual_start_penetrating"), Hit.bStartPenetrating);
    Row.SetBoolField(TEXT("query_filtered"), false);
    const bool bSuccess = bHit && Hit.bBlockingHit && Hit.GetComponent() == Capsule
        && Hit.GetActor() == Mesh.GetOwner() && PositionError <= PositionToleranceCm;
    Row.SetBoolField(TEXT("success"), bSuccess);
    if (!bSuccess)
    {
        Error = FString::Printf(TEXT("Post-EndPhysics capsule blocker trace: hit=%d, receiver=%s, impact error=%.9f cm."),
            bHit, *GetPathNameSafe(Hit.GetComponent()), PositionError);
        return false;
    }
    return true;
}

bool TraceExpectedHead(USkeletalMeshComponent& Mesh, const FVector& Start, const FVector& End,
    const FVector& ExpectedPoint, FJsonObject& Row, FString& Error,
    const UCapsuleComponent* VerifiedIgnoredCapsule = nullptr)
{
    FCollisionQueryParams Params(SCENE_QUERY_STAT(ProphecyJoltPostPhysicsHead), false);
    if (VerifiedIgnoredCapsule)
    {
        if (!VerifiedIgnoredCapsule->IsRegistered() || VerifiedIgnoredCapsule->GetOwner() != Mesh.GetOwner())
        { Error = TEXT("The verified diagnostic capsule no longer belongs to the query mesh's actor."); return false; }
        Params.AddIgnoredComponent(VerifiedIgnoredCapsule);
    }
    Row.SetBoolField(TEXT("validation_only_capsule_filter"), VerifiedIgnoredCapsule != nullptr);
    Row.SetStringField(TEXT("ignored_verified_capsule"), GetPathNameSafe(VerifiedIgnoredCapsule));
    FHitResult Hit;
    const bool bHit = Mesh.GetWorld()->LineTraceSingleByChannel(Hit, Start, End, ECC_WorldStatic, Params);
    const double PositionError = bHit ? FVector::Distance(Hit.ImpactPoint, ExpectedPoint) : -1.0;
    WriteVector(Row, TEXT("start_cm"), Start);
    WriteVector(Row, TEXT("end_cm"), End);
    WriteVector(Row, TEXT("expected_impact_cm"), ExpectedPoint);
    if (bHit) WriteVector(Row, TEXT("actual_impact_cm"), Hit.ImpactPoint);
    Row.SetNumberField(TEXT("impact_error_cm"), PositionError);
    Row.SetStringField(TEXT("hit_component"), GetPathNameSafe(Hit.GetComponent()));
    Row.SetStringField(TEXT("hit_bone"), Hit.BoneName.ToString());
    Row.SetBoolField(TEXT("success"), bHit && Hit.bBlockingHit && !Hit.bStartPenetrating
        && Hit.GetComponent() == &Mesh && Hit.GetActor() == Mesh.GetOwner()
        && Hit.BoneName == FName(TEXT("head")) && PositionError <= PositionToleranceCm);
    if (!Row.GetBoolField(TEXT("success")))
    {
        Error = FString::Printf(TEXT("Post-EndPhysics head trace: hit=%d, receiver=%s, bone=%s, impact error=%.9f cm."),
            bHit, *GetPathNameSafe(Hit.GetComponent()), *Hit.BoneName.ToString(), PositionError);
        return false;
    }
    return true;
}
}

bool ValidatePostPhysicsQueries(USkeletalMeshComponent& Mesh, const FProphecyJoltRigSnapshot& SourceRig,
    const FJsonObject* PreviousAgent, FJsonObject& AgentRow, FString& OutError)
{
    OutError.Reset();
    auto Row = MakeShared<FJsonObject>();
    AgentRow.SetObjectField(TEXT("post_endphysics_queries"), Row);
    Row->SetBoolField(TEXT("success"), false);
    Row->SetBoolField(TEXT("disjoint_previous_aabb_ray"), false);
    auto Fail = [&](const FString& Message) { OutError = Message; Row->SetStringField(TEXT("error"), Message); return false; };
    if (!IsInGameThread() || !Mesh.GetWorld() || Mesh.GetWorld()->TickGroup <= TG_EndPhysics
        || !Mesh.IsRegistered() || !Mesh.IsPhysicsStateCreated() || SourceRig.Bodies.IsEmpty())
        return Fail(TEXT("Current query validation requires a registered retained mesh after EndPhysics."));
    Row->SetNumberField(TEXT("observed_world_tick_group"), int32(Mesh.GetWorld()->TickGroup));
    Row->SetStringField(TEXT("trace_channel"), TEXT("WorldStatic (the captured fixture's blocking response)"));
    double MaxPosition = 0.0, MaxAngle = 0.0;
    TArray<FAnalyticQueryBody, TInlineAllocator<32>> AnalyticBodies;
    AnalyticBodies.Reserve(SourceRig.Bodies.Num());
    for (const FProphecyJoltRigBody& SourceBody : SourceRig.Bodies)
    {
        FBodyInstance* Body = Mesh.GetBodyInstance(SourceBody.BodyName);
        const FPhysicsActorHandle Actor = Body ? Body->GetPhysicsActor() : nullptr;
        if (!Body || !Actor || !Body->IsValidBodyInstance() || Actor->GetMarkedDeleted()
            || !FPhysicsInterface::IsKinematic(Actor) || Body->InstanceBoneIndex != Mesh.GetBoneIndex(SourceBody.BodyName))
            return Fail(FString::Printf(TEXT("Post-EndPhysics query body %s lost its native identity."), *SourceBody.BodyName.ToString()));
        const auto& External = Actor->GetGameThreadAPI();
        const FTransform Native(FQuat(External.R()), FVector(External.X()));
        const FTransform Expected = Mesh.GetBoneTransform(Body->InstanceBoneIndex);
        if (Native.ContainsNaN() || Expected.ContainsNaN() || !Native.GetRotation().IsNormalized()
            || !Expected.GetRotation().IsNormalized() || !External.GetGeometry())
            return Fail(FString::Printf(TEXT("Post-EndPhysics query body %s has an invalid transform or geometry."), *SourceBody.BodyName.ToString()));
        const double Position = FVector::Distance(Native.GetTranslation(), Expected.GetTranslation());
        const double Angle = FMath::RadiansToDegrees(Native.GetRotation().GetNormalized()
            .AngularDistance(Expected.GetRotation().GetNormalized()));
        MaxPosition = FMath::Max(MaxPosition, Position);
        MaxAngle = FMath::Max(MaxAngle, Angle);
        if (Position > PositionToleranceCm || Angle > AngleToleranceDegrees)
            return Fail(FString::Printf(TEXT("Post-EndPhysics query body %s differs from its completed bone: %.9f cm, %.9f degrees."),
                *SourceBody.BodyName.ToString(), Position, Angle));
        FAnalyticQueryBody& Analytic = AnalyticBodies.AddDefaulted_GetRef();
        Analytic.Geometry = External.GetGeometry();
        Analytic.Pose = FTransform(Expected.GetRotation().GetNormalized(), Expected.GetTranslation());
        Analytic.Name = SourceBody.BodyName;
    }
    Row->SetNumberField(TEXT("validated_query_bodies"), SourceRig.Bodies.Num());
    Row->SetNumberField(TEXT("max_query_bone_position_cm"), MaxPosition);
    Row->SetNumberField(TEXT("max_query_bone_angle_degrees"), MaxAngle);
    if (!AppendOwnBlockingCapsule(Mesh, AnalyticBodies, *Row, OutError)) return Fail(OutError);
    Row->SetBoolField(TEXT("normal_unfiltered_head_visibility_exercised"), false);
    Row->SetBoolField(TEXT("validation_only_ignored_own_capsule"), false);

    FBodyInstance* Head = Mesh.GetBodyInstance(TEXT("head"));
    if (!Head || !Head->GetPhysicsActor()) return Fail(TEXT("The retained query head is missing."));
    const auto& External = Head->GetPhysicsActor()->GetGameThreadAPI();
    const Chaos::FImplicitObject* Geometry = External.GetGeometry();
    const FTransform Bone = Mesh.GetBoneTransform(Head->InstanceBoneIndex);
    const FTransform Pose(Bone.GetRotation().GetNormalized(), Bone.GetTranslation());
    const auto NativeBounds = Geometry->BoundingBox();
    const FBox LocalBounds(FVector(NativeBounds.Min()), FVector(NativeBounds.Max()));
    const FBox CurrentBounds = LocalBounds.TransformBy(Pose);
    if (!CurrentBounds.IsValid || CurrentBounds.Min.ContainsNaN() || CurrentBounds.Max.ContainsNaN())
        return Fail(TEXT("The head's expected native query bounds are invalid."));
    WriteVector(*Row, TEXT("head_bounds_min_cm"), CurrentBounds.Min);
    WriteVector(*Row, TEXT("head_bounds_max_cm"), CurrentBounds.Max);

    // Consider both directions on all three head-local axes. The head shape overlaps its neck:
    // select an independently predicted head-first ray before making the one strict UE query.
    bool bCenterRayTested = false;
    FCapsuleFallback CapsuleFallback;
    int32 CenterCandidates = 0, CenterOccludedCandidates = 0;
    for (int32 Axis = 0; Axis != 3 && !bCenterRayTested; ++Axis)
    {
        FVector Offset = FVector::ZeroVector;
        Offset[Axis] = LocalBounds.GetExtent()[Axis] + 2.0;
        const FVector A = Pose.TransformPositionNoScale(LocalBounds.GetCenter() - Offset);
        const FVector B = Pose.TransformPositionNoScale(LocalBounds.GetCenter() + Offset);
        for (int32 Direction = 0; Direction != 2 && !bCenterRayTested; ++Direction)
        {
            ++CenterCandidates;
            const FVector Start = Direction ? B : A, End = Direction ? A : B;
            FVector ExpectedPoint;
            bool bHeadFirst = false;
            FName Occluder;
            if (!SelectAnalyticHeadCandidate(AnalyticBodies, *Geometry, Pose, Start, End,
                ExpectedPoint, bHeadFirst, Occluder, OutError)) return Fail(OutError);
            if (!Occluder.IsNone()) ++CenterOccludedCandidates;
            if (!bHeadFirst)
            {
                // Save a fallback entirely from geometry, but prefer any ordinary head-first
                // direction among all six before making an unfiltered or filtered UE query.
                if (!CapsuleFallback.Capsule.IsValid())
                {
                    if (!FindAnalyticCapsuleFallback(AnalyticBodies, *Geometry, Pose, Start, End,
                        CapsuleFallback, OutError)) return Fail(OutError);
                    CapsuleFallback.Axis = Axis;
                    CapsuleFallback.bReverse = Direction != 0;
                }
                continue;
            }
            auto Ray = MakeShared<FJsonObject>();
            Ray->SetNumberField(TEXT("local_axis"), Axis);
            Ray->SetBoolField(TEXT("reverse_direction"), Direction != 0);
            Ray->SetNumberField(TEXT("analytic_occlusion_bodies"), AnalyticBodies.Num());
            Row->SetObjectField(TEXT("center_ray"), Ray);
            // Never retry another direction after an analytically unoccluded candidate fails in UE.
            if (!TraceExpectedHead(Mesh, Start, End, ExpectedPoint, *Ray, OutError)) return Fail(OutError);
            bCenterRayTested = true;
            Row->SetBoolField(TEXT("normal_unfiltered_head_visibility_exercised"), true);
        }
    }
    if (!bCenterRayTested && CapsuleFallback.Capsule.IsValid())
    {
        auto BlockerRay = MakeShared<FJsonObject>();
        Row->SetObjectField(TEXT("unfiltered_capsule_blocker_ray"), BlockerRay);
        // A mismatch is a test failure, never a reason to try another ray or ignore another object.
        if (!TraceExpectedCapsule(Mesh, CapsuleFallback, *BlockerRay, OutError)) return Fail(OutError);
        auto HeadRay = MakeShared<FJsonObject>();
        Row->SetObjectField(TEXT("center_ray"), HeadRay);
        HeadRay->SetNumberField(TEXT("local_axis"), CapsuleFallback.Axis);
        HeadRay->SetBoolField(TEXT("reverse_direction"), CapsuleFallback.bReverse);
        HeadRay->SetNumberField(TEXT("analytic_occlusion_bodies"), AnalyticBodies.Num());
        Row->SetBoolField(TEXT("validation_only_ignored_own_capsule"), true);
        Row->SetStringField(TEXT("filtered_head_coverage_scope"),
            TEXT("Native query pose/receiver diagnostic after verifying the real unfiltered capsule blocker; no normal head or blood visibility claim."));
        if (!TraceExpectedHead(Mesh, CapsuleFallback.Start, CapsuleFallback.End, CapsuleFallback.HeadPoint,
            *HeadRay, OutError, CapsuleFallback.Capsule.Get())) return Fail(OutError);
        bCenterRayTested = true;
    }
    Row->SetNumberField(TEXT("center_analytic_candidates"), CenterCandidates);
    Row->SetNumberField(TEXT("center_analytically_occluded_candidates"), CenterOccludedCandidates);
    if (!bCenterRayTested) return Fail(TEXT("No head-center ray independently predicted either an unobstructed head or a verifiable own-capsule-only blocker."));

    if (PreviousAgent)
    {
        const TSharedPtr<FJsonObject>* PreviousRow = nullptr;
        FVector PreviousMin, PreviousMax;
        if (!PreviousAgent->TryGetObjectField(TEXT("post_endphysics_queries"), PreviousRow) || !PreviousRow || !*PreviousRow
            || !ReadVector(**PreviousRow, TEXT("head_bounds_min_cm"), PreviousMin)
            || !ReadVector(**PreviousRow, TEXT("head_bounds_max_cm"), PreviousMax)
            || PreviousMin.X > PreviousMax.X || PreviousMin.Y > PreviousMax.Y || PreviousMin.Z > PreviousMax.Z)
            return Fail(TEXT("Previous-frame query bounds are missing or invalid; motion coverage cannot be inferred."));
        const FBox PreviousBounds(PreviousMin, PreviousMax);
        const FBox GuardedPrevious = PreviousBounds.ExpandBy(EdgeClearanceCm);
        bool bDisjointRayTested = false;
        // Candidate segments are perpendicular to a newly exposed side of the CURRENT bounds.
        // Requiring the entire segment to miss the previous AABB (with a small clearance) excludes
        // tiny overlapping center-ray motions. Direct current-geometry raycast rejects empty AABB corners.
        for (int32 SideAxis = 0; SideAxis != 3 && !bDisjointRayTested; ++SideAxis)
            for (int32 Side = 0; Side != 2 && !bDisjointRayTested; ++Side)
            {
                const double OldEdge = Side ? GuardedPrevious.Max[SideAxis] : GuardedPrevious.Min[SideAxis];
                const double NewEdge = Side ? CurrentBounds.Max[SideAxis] : CurrentBounds.Min[SideAxis];
                if ((Side ? NewEdge - OldEdge : OldEdge - NewEdge) <= EdgeClearanceCm) continue;
                FVector Center = CurrentBounds.GetCenter();
                Center[SideAxis] = (OldEdge + NewEdge) * 0.5;
                for (int32 RayAxis = 0; RayAxis != 3 && !bDisjointRayTested; ++RayAxis)
                {
                    if (RayAxis == SideAxis) continue;
                    FVector Start = Center, End = Center;
                    Start[RayAxis] = CurrentBounds.Min[RayAxis] - 2.0;
                    End[RayAxis] = CurrentBounds.Max[RayAxis] + 2.0;
                    if (FMath::LineBoxIntersection(GuardedPrevious, Start, End, End - Start)) continue;
                    for (int32 Direction = 0; Direction != 2 && !bDisjointRayTested; ++Direction)
                    {
                        const FVector RayStart = Direction ? End : Start, RayEnd = Direction ? Start : End;
                        FVector ExpectedPoint;
                        bool bHeadFirst = false;
                        FName Occluder;
                        if (!SelectAnalyticHeadCandidate(AnalyticBodies, *Geometry, Pose, RayStart, RayEnd,
                            ExpectedPoint, bHeadFirst, Occluder, OutError)) return Fail(OutError);
                        if (!bHeadFirst) continue;
                        auto Ray = MakeShared<FJsonObject>();
                        Row->SetObjectField(TEXT("motion_edge_ray"), Ray);
                        WriteVector(*Ray, TEXT("previous_bounds_min_cm"), PreviousMin);
                        WriteVector(*Ray, TEXT("previous_bounds_max_cm"), PreviousMax);
                        Ray->SetNumberField(TEXT("old_bounds_clearance_cm"), EdgeClearanceCm);
                        Ray->SetNumberField(TEXT("analytic_occlusion_bodies"), AnalyticBodies.Num());
                        Ray->SetBoolField(TEXT("reverse_direction"), Direction != 0);
                        Ray->SetBoolField(TEXT("intersects_previous_exact_query_aabb"), false);
                        // Both directions span the same segment outside the previous AABB.
                        if (!TraceExpectedHead(Mesh, RayStart, RayEnd, ExpectedPoint, *Ray, OutError)) return Fail(OutError);
                        bDisjointRayTested = true;
                    }
                }
            }
        Row->SetBoolField(TEXT("disjoint_previous_aabb_ray"), bDisjointRayTested);
    }
    Row->SetBoolField(TEXT("success"), true);
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltHeadRayOcclusionTest,
    "Prophecy.Jolt.QueryPose.AnalyticHeadRayOcclusion",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyJoltHeadRayOcclusionTest::RunTest(const FString&)
{
    const Chaos::TSphere<Chaos::FReal, 3> Head(Chaos::FVec3(0), 2.0);
    const Chaos::TSphere<Chaos::FReal, 3> Neck(Chaos::FVec3(0), 1.5);
    TArray<FAnalyticQueryBody> Bodies;
    Bodies.Add({ &Head, FTransform::Identity, FName(TEXT("head")) });
    Bodies.Add({ &Neck, FTransform(FVector(-3.0, 0.0, 0.0)), FName(TEXT("neck_01")) });
    for (int32 Index = 2; Index < 22; ++Index)
        Bodies.Add({ &Neck, FTransform(FVector(0.0, 100.0 + 5.0 * Index, 0.0)),
            FName(*FString::Printf(TEXT("body_%d"), Index)) });
    FVector Impact;
    bool bHeadFirst = false;
    FName Occluder;
    FString Error;
    const FVector A(-5.0, 0.0, 0.0), B(5.0, 0.0, 0.0);
    TestTrue(TEXT("All 22-body analytic inputs evaluate"), SelectAnalyticHeadCandidate(Bodies, Head,
        FTransform::Identity, A, B, Impact, bHeadFirst, Occluder, Error));
    TestFalse(TEXT("A nearer neck rejects the candidate before any UE query"), bHeadFirst);
    TestEqual(TEXT("Occluding native body is identified"), Occluder, FName(TEXT("neck_01")));
    TestTrue(TEXT("Reverse direction evaluates independently"), SelectAnalyticHeadCandidate(Bodies, Head,
        FTransform::Identity, B, A, Impact, bHeadFirst, Occluder, Error));
    TestTrue(TEXT("Reverse ray reaches the head before the neck"), bHeadFirst && Occluder.IsNone());
    TestTrue(TEXT("Head entry position remains independently predicted"), Impact.Equals(FVector(2.0, 0.0, 0.0), 1.0e-6));
    Bodies.Last().Pose = FTransform(B);
    TestTrue(TEXT("Starting inside another native body evaluates"), SelectAnalyticHeadCandidate(Bodies, Head,
        FTransform::Identity, B, A, Impact, bHeadFirst, Occluder, Error));
    TestFalse(TEXT("Initial overlap is occlusion at time zero"), bHeadFirst);
    TestEqual(TEXT("The body containing the start is reported"), Occluder, Bodies.Last().Name);
    Bodies.Last().Pose = FTransform(FVector(0.0, 200.0, 0.0));

    // Let UE create the native capsule. Constructing Chaos's concrete FCapsule here instantiates
    // template virtuals that are not exported by the Launcher engine's Chaos DLL.
    const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
        .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
    UWorld* CapsuleWorld = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true,
        ERHIFeatureLevel::Num, &Values);
    if (!TestNotNull(TEXT("Native capsule fixture world"), CapsuleWorld)) return false;
    if (GEngine) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(CapsuleWorld);
    ON_SCOPE_EXIT
    {
        CapsuleWorld->DestroyWorld(false);
        if (GEngine) GEngine->DestroyWorldContext(CapsuleWorld);
        CapsuleWorld->MarkAsGarbage();
    };
    APawn* CapsuleActor = CapsuleWorld->SpawnActor<APawn>();
    if (!TestNotNull(TEXT("Native capsule fixture actor"), CapsuleActor)) return false;
    TStrongObjectPtr<UCapsuleComponent> Capsule(NewObject<UCapsuleComponent>(CapsuleActor, TEXT("Capsule")));
    CapsuleActor->AddInstanceComponent(Capsule.Get());
    CapsuleActor->SetRootComponent(Capsule.Get());
    Capsule->SetCapsuleSize(4.0f, 7.0f); // UE halfheight includes radius: native segment endpoints are Z +/-3.
    Capsule->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Capsule->SetCollisionResponseToAllChannels(ECR_Block);
    Capsule->SetMobility(EComponentMobility::Movable);
    Capsule->RegisterComponent();
    Capsule->SetComponentTickEnabled(false);
    FBodyInstance* NativeCapsuleBody = Capsule->GetBodyInstance();
    if (!TestTrue(TEXT("Registered capsule owns actual native geometry"),
        NativeCapsuleBody && NativeCapsuleBody->IsValidBodyInstance() && NativeCapsuleBody->GetPhysicsActor()
        && NativeCapsuleBody->GetPhysicsActor()->GetGameThreadAPI().GetGeometry())) return false;
    // No scene query result can select a candidate or authorize an ignored receiver.
    TStrongObjectPtr<UCapsuleComponent> OtherCapsule(NewObject<UCapsuleComponent>(GetTransientPackage()));
    USkeletalMeshComponent* QueryReceiver = NewObject<USkeletalMeshComponent>(CapsuleActor);
    CapsuleActor->AddInstanceComponent(QueryReceiver);
    TArray<FAnalyticQueryBody, TInlineAllocator<32>> CapturedCapsules;
    FJsonObject CapsuleRow;
    // Exercise the production collector itself. Manually inserting a capsule geometry would
    // miss an owner-class regression and allow all analytic math tests to pass with zero real blockers.
    if (!TestTrue(TEXT("An APawn root capsule is collected through its real receiver owner"),
        AppendOwnBlockingCapsule(*QueryReceiver, CapturedCapsules, CapsuleRow, Error))
        || !TestEqual(TEXT("A native blocking simple capsule is included"), CapturedCapsules.Num(), 1)) return false;
    TestTrue(TEXT("The collected identity is the actual APawn root"), CapturedCapsules[0].OwnerCapsule.Get() == Capsule.Get());
    CapturedCapsules.Reset();
    Capsule->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Ignore);
    if (!TestTrue(TEXT("Native ignored response is inspected"),
        AppendOwnBlockingCapsule(*QueryReceiver, CapturedCapsules, CapsuleRow, Error))) return false;
    TestTrue(TEXT("An ignored native capsule is not invented as a blocker"), CapturedCapsules.IsEmpty());
    Capsule->SetCollisionResponseToChannel(ECC_WorldStatic, ECR_Block);
    if (!TestTrue(TEXT("Restored blocking response is inspected"),
        AppendOwnBlockingCapsule(*QueryReceiver, CapturedCapsules, CapsuleRow, Error))
        || !TestEqual(TEXT("Restoring block restores exactly one capsule"), CapturedCapsules.Num(), 1)) return false;
    Bodies.Add(CapturedCapsules[0]);
    TestTrue(TEXT("An enclosing movement capsule is considered before a UE query"), SelectAnalyticHeadCandidate(Bodies, Head,
        FTransform::Identity, B, A, Impact, bHeadFirst, Occluder, Error));
    TestFalse(TEXT("An unfiltered capsule-occluded ray is never claimed to expose the head"), bHeadFirst);
    TestEqual(TEXT("The native capsule blocker is identified"), Occluder, FName(TEXT("Capsule")));
    FCapsuleFallback Fallback;
    TestTrue(TEXT("Capsule-only fallback analysis succeeds"), FindAnalyticCapsuleFallback(Bodies, Head,
        FTransform::Identity, B, A, Fallback, Error));
    TestTrue(TEXT("Fallback authorizes only the exact independently predicted capsule"), Fallback.Capsule.Get() == Capsule.Get());
    TestTrue(TEXT("Capsule entry precedes the independent head entry"),
        Fallback.CapsulePoint.Equals(FVector(4.0, 0.0, 0.0), 1.0e-6)
        && Fallback.HeadPoint.Equals(FVector(2.0, 0.0, 0.0), 1.0e-6));
    TestTrue(TEXT("Ignoring an unrelated capsule still evaluates"), SelectAnalyticHeadCandidate(Bodies, Head,
        FTransform::Identity, B, A, Impact, bHeadFirst, Occluder, Error, OtherCapsule.Get()));
    TestFalse(TEXT("An unrelated ignored identity cannot hide the real capsule"), bHeadFirst);
    TestTrue(TEXT("Starting inside the capsule is analyzed at time zero"), FindAnalyticCapsuleFallback(Bodies, Head,
        FTransform::Identity, FVector(3.0, 0.0, 0.0), A, Fallback, Error));
    TestTrue(TEXT("An initial-overlap fallback records the actual start as expected blocker impact"),
        Fallback.Capsule.Get() == Capsule.Get() && Fallback.bStartsInsideCapsule
        && Fallback.CapsulePoint.Equals(FVector(3.0, 0.0, 0.0), 1.0e-6));
    TestTrue(TEXT("Capsule fallback also checks every other rig body"), FindAnalyticCapsuleFallback(Bodies, Head,
        FTransform::Identity, A, B, Fallback, Error));
    TestFalse(TEXT("Ignoring a capsule must not bypass an independently closer neck"), Fallback.Capsule.IsValid());
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltPostEndPhysicsQueryTest,
    "Prophecy.Jolt.QueryPose.PostEndPhysicsPreservesNewerExternalPose",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyJoltPostEndPhysicsQueryTest::RunTest(const FString&)
{
    // Own one actual transient game physics scene. No World::Tick, world tick-group assignment,
    // engine private hooks, solver/PT particle writes, or changes to the timed crowd are involved.
    struct FControlledWorld
    {
        UWorld* World = nullptr;
        FControlledWorld()
        {
            const auto Values = UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
                .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(true)
                .EnableTraceCollision(true).CreateFXSystem(false).SetTransactional(false);
            World = UWorld::CreateWorld(EWorldType::Game, false, NAME_None, nullptr, true, ERHIFeatureLevel::Num, &Values);
            if (World && GEngine) GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
        }
        ~FControlledWorld()
        {
            if (!World) return;
            World->DestroyWorld(false);
            if (GEngine) GEngine->DestroyWorldContext(World);
            World->MarkAsGarbage();
        }
    } Fixture;
    if (!TestNotNull(TEXT("Controlled game physics world"), Fixture.World)) return false;
    FPhysScene* Scene = Fixture.World->GetPhysicsScene();
    if (!TestNotNull(TEXT("Public physics scene"), Scene) || !TestNotNull(TEXT("Native Chaos scene solver"), Scene->GetSolver())
        || !TestNotNull(TEXT("External query acceleration structure"), Scene->GetSpacialAcceleration())) return false;
    USkeletalMesh* Asset = LoadObject<USkeletalMesh>(nullptr,
        TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin"));
    if (!TestNotNull(TEXT("Actual project mannequin"), Asset)) return false;
    AActor* Actor = Fixture.World->SpawnActor<AActor>();
    if (!TestNotNull(TEXT("Original receiver actor"), Actor)) return false;
    USkeletalMeshComponent* Mesh = NewObject<USkeletalMeshComponent>(Actor);
    Actor->AddInstanceComponent(Mesh);
    Actor->SetRootComponent(Mesh);
    Mesh->SetSkeletalMeshAsset(Asset);
    Mesh->SetCollisionEnabled(ECollisionEnabled::QueryOnly);
    Mesh->SetCollisionResponseToAllChannels(ECR_Block);
    Mesh->SetMobility(EComponentMobility::Movable);
    Mesh->KinematicBonesUpdateType = EKinematicBonesUpdateToPhysics::SkipAllBones;
    Mesh->bDeferKinematicBoneUpdate = false;
    Mesh->bEnableUpdateRateOptimizations = false;
    Mesh->RegisterComponent();
    Mesh->SetAllBodiesSimulatePhysics(false);
    Mesh->SetSimulatePhysics(false);
    Mesh->SetAllBodiesPhysicsBlendWeight(0.0f);
    Mesh->SetDisablePostProcessBlueprint(true);
    Mesh->SetAnimInstanceClass(UProphecyJoltPoseAnimInstance::StaticClass());
    Mesh->SetComponentTickEnabled(false);
    auto* Anim = Cast<UProphecyJoltPoseAnimInstance>(Mesh->GetAnimInstance());
    if (!TestNotNull(TEXT("Completed pose AnimInstance"), Anim)
        || !TestEqual(TEXT("All native query bodies retained"), Mesh->Bodies.Num(), 22)) return false;
    const FReferenceSkeleton& Skeleton = Asset->GetRefSkeleton();
    TArray<FTransform> Local = Skeleton.GetRefBonePose(), Component, CompletedWorld;
    if (!TestEqual(TEXT("All skeleton bones retained"), Local.Num(), 88)) return false;
    const FVector OldRoot(1000.0, 0.0, 200.0), Translation(150.0, 0.0, 0.0);
    Local[0].SetScale3D(FVector(1.03, 1.11, 0.94));
    const int32 HeadBone = Skeleton.FindBoneIndex(TEXT("head"));
    if (!TestTrue(TEXT("Head bone exists"), HeadBone != INDEX_NONE)) return false;
    Local[HeadBone].SetRotation(FQuat(FVector::UpVector, FMath::DegreesToRadians(17.0)) * Local[HeadBone].GetRotation());
    FString Error;
    FProphecyJoltQueryPose QueryPose;
    if (!QueryPose.Initialize(*Mesh, Error)) { AddError(Error); return false; }
    bool bSceneStarted = false;
    ON_SCOPE_EXIT
    {
        Anim->ClearPostEvaluateQueryCommit();
        if (bSceneStarted) { Scene->WaitPhysScenes(); Scene->EndFrame(); }
    };
    uint64 Revision = 0;
    const auto Publish = [&](bool bMoved)
    {
        Local[0].SetTranslation(OldRoot + (bMoved ? Translation : FVector::ZeroVector));
        Component.SetNum(Local.Num());
        CompletedWorld.SetNum(Local.Num());
        for (int32 Index = 0; Index < Local.Num(); ++Index)
        {
            const int32 Parent = Skeleton.GetParentIndex(Index);
            Component[Index] = Parent == INDEX_NONE ? Local[Index] : Local[Index] * Component[Parent];
            CompletedWorld[Index] = Component[Index] * Mesh->GetComponentTransform();
        }
        ++Revision;
        if (!Anim->PublishCompletedLocalPose(Local, Revision, Error)) return false;
        Mesh->TickAnimation(0.0f, false);
        if (!Anim->ArmPostEvaluateQueryCommit(FProphecyJoltPostEvaluateQueryCommit::CreateLambda(
            [&](FString& QueryError) { return QueryPose.Publish(*Mesh, CompletedWorld, QueryError); }), Revision, Error)) return false;
        Mesh->RefreshBoneTransforms(nullptr);
        Anim->ClearPostEvaluateQueryCommit();
        return Anim->GetPostEvaluateQueryCommitResult(Revision, Error);
    };
    const auto FindHeadRay = [&](FVector& OutStart, FVector& OutEnd, FVector& OutImpact, FBox& OutHeadBounds)
    {
        TArray<FAnalyticQueryBody, TInlineAllocator<32>> Bodies;
        const Chaos::FImplicitObject* HeadGeometry = nullptr;
        FTransform HeadPose = FTransform::Identity;
        for (FBodyInstance* Body : Mesh->Bodies)
        {
            if (!Body || !Body->IsValidBodyInstance() || !Body->GetPhysicsActor())
            { Error = TEXT("Controlled fixture lost a native query body."); return false; }
            const FTransform Bone = Mesh->GetBoneTransform(Body->InstanceBoneIndex);
            FAnalyticQueryBody& Entry = Bodies.AddDefaulted_GetRef();
            Entry.Geometry = Body->GetPhysicsActor()->GetGameThreadAPI().GetGeometry();
            Entry.Pose = FTransform(Bone.GetRotation().GetNormalized(), Bone.GetTranslation());
            Entry.Name = Skeleton.GetBoneName(Body->InstanceBoneIndex);
            if (!Entry.Geometry) { Error = TEXT("Controlled fixture lost native geometry."); return false; }
            if (Entry.Name == FName(TEXT("head"))) { HeadGeometry = Entry.Geometry; HeadPose = Entry.Pose; }
        }
        if (!HeadGeometry) { Error = TEXT("Controlled head geometry is missing."); return false; }
        const auto Bounds = HeadGeometry->BoundingBox();
        const FBox LocalBounds(FVector(Bounds.Min()), FVector(Bounds.Max()));
        OutHeadBounds = LocalBounds.TransformBy(HeadPose);
        for (int32 Axis = 0; Axis != 3; ++Axis)
        {
            FVector Offset = FVector::ZeroVector;
            Offset[Axis] = LocalBounds.GetExtent()[Axis] + 2.0;
            const FVector A = HeadPose.TransformPositionNoScale(LocalBounds.GetCenter() - Offset);
            const FVector B = HeadPose.TransformPositionNoScale(LocalBounds.GetCenter() + Offset);
            for (int32 Direction = 0; Direction != 2; ++Direction)
            {
                const FVector Start = Direction ? B : A, End = Direction ? A : B;
                bool bHeadFirst = false;
                FName Occluder;
                if (!SelectAnalyticHeadCandidate(Bodies, *HeadGeometry, HeadPose, Start, End,
                    OutImpact, bHeadFirst, Occluder, Error)) return false;
                if (bHeadFirst) { OutStart = Start; OutEnd = End; return true; }
            }
        }
        Error = TEXT("Controlled fixture has no independently head-first ray.");
        return false;
    };
    if (!Publish(false)) { AddError(Error); return false; }
    TArray<const Chaos::FImplicitObject*> GeometryIdentities;
    for (FBodyInstance* Body : Mesh->Bodies) GeometryIdentities.Add(Body->GetPhysicsActor()->GetGameThreadAPI().GetGeometry());
    const uint64 InitialScaleUpdates = QueryPose.GetScaleUpdateCalls();
    bool bObservedReturnedOlderTree = false;
    auto& Marshalling = Scene->GetSolver()->GetMarshallingManager();
    const FVector Gravity = FVector::ZeroVector;
    // AABB rebuilding can span physics frames. Every packet below contains the OLD pose, even if
    // the returned tree lags by several frames. Only GT query state receives the +150 cm position.
    for (int32 Attempt = 0; Attempt < 8 && !bObservedReturnedOlderTree; ++Attempt)
    {
        if (!Publish(false)) { AddError(Error); return false; }
        FVector OldStart, OldEnd, OldImpact;
        FBox OldHeadBounds;
        if (!FindHeadRay(OldStart, OldEnd, OldImpact, OldHeadBounds)) { AddError(Error); return false; }
        FJsonObject OldRay;
        if (!TraceExpectedHead(*Mesh, OldStart, OldEnd, OldImpact, OldRay, Error)) { AddError(Error); return false; }
        const int32 BeforeTreeTimestamp = Scene->GetSpacialAcceleration()->GetSyncTimestamp();
        const int32 OldPacketTimestamp = Marshalling.GetExternalTimestamp_External();
        Scene->SetUpForFrame(&Gravity, 1.0f / 60.0f, 0.0f, 1.0f / 60.0f, 1.0f / 60.0f, 1, false);
        Scene->StartFrame();
        bSceneStarted = true;
        const int32 NewWriteTimestamp = Marshalling.GetExternalTimestamp_External();
        if (!TestTrue(TEXT("StartFrame marshalled the old pose before the new GT write"), NewWriteTimestamp > OldPacketTimestamp)) return false;
        if (!Publish(true)) { AddError(Error); return false; }
        if (!TestEqual(TEXT("New pose publication did not advance a solver packet"), Marshalling.GetExternalTimestamp_External(), NewWriteTimestamp)) return false;
        Scene->WaitPhysScenes();
        Scene->EndFrame();
        bSceneStarted = false;
        const int32 AfterTreeTimestamp = Scene->GetSpacialAcceleration()->GetSyncTimestamp();
        if (!TestTrue(TEXT("Returned physics tree cannot have consumed the newer GT pose"), AfterTreeTimestamp < NewWriteTimestamp)) return false;
        bObservedReturnedOlderTree = AfterTreeTimestamp > BeforeTreeTimestamp;
        AddInfo(FString::Printf(TEXT("Controlled query frame %d: prior tree=%d, old PT packet=%d, new GT write=%d, returned tree=%d, translated=150cm"),
            Attempt, BeforeTreeTimestamp, OldPacketTimestamp, NewWriteTimestamp, AfterTreeTimestamp));
        for (int32 Index = 0; Index < Mesh->Bodies.Num(); ++Index)
        {
            FBodyInstance* Body = Mesh->Bodies[Index];
            const auto& External = Body->GetPhysicsActor()->GetGameThreadAPI();
            const FTransform Expected = Mesh->GetBoneTransform(Body->InstanceBoneIndex);
            const double Position = FVector::Distance(FVector(External.X()), Expected.GetTranslation());
            const double Angle = FMath::RadiansToDegrees(FQuat(External.R()).GetNormalized()
                .AngularDistance(Expected.GetRotation().GetNormalized()));
            if (!TestTrue(TEXT("Every native query body retains its newer completed pose after EndFrame"),
                FQuat(External.R()).IsNormalized() && Expected.GetRotation().IsNormalized()
                && Position <= PositionToleranceCm && Angle <= AngleToleranceDegrees
                && External.GetGeometry() == GeometryIdentities[Index])) return false;
        }
        for (int32 Bone = 0; Bone < CompletedWorld.Num(); ++Bone)
        {
            const FTransform Actual = Mesh->GetBoneTransform(Bone);
            if (!TestTrue(TEXT("All 88 completed bones survive EndFrame without scale or pose loss"),
                Actual.GetTranslation().Equals(CompletedWorld[Bone].GetTranslation(), PositionToleranceCm)
                && Actual.GetScale3D().Equals(CompletedWorld[Bone].GetScale3D(), 1.0e-4)
                && FMath::RadiansToDegrees(Actual.GetRotation().GetNormalized()
                    .AngularDistance(CompletedWorld[Bone].GetRotation().GetNormalized())) <= AngleToleranceDegrees)) return false;
        }
        FVector NewStart, NewEnd, NewImpact;
        FBox NewHeadBounds;
        if (!FindHeadRay(NewStart, NewEnd, NewImpact, NewHeadBounds)) { AddError(Error); return false; }
        if (!TestTrue(TEXT("Controlled head moved a full 150 cm"),
            NewHeadBounds.GetCenter().Equals(OldHeadBounds.GetCenter() + Translation, PositionToleranceCm))) return false;
        if (!TestFalse(TEXT("New head ray cannot intersect the old head's broadphase bounds"),
            FMath::LineBoxIntersection(OldHeadBounds.ExpandBy(EdgeClearanceCm), NewStart, NewEnd, NewEnd - NewStart))) return false;
        FJsonObject NewRay;
        if (!TraceExpectedHead(*Mesh, NewStart, NewEnd, NewImpact, NewRay, Error)) { AddError(Error); return false; }
        FHitResult OldAreaHit;
        if (!TestFalse(TEXT("The old head ray is empty after EndFrame"),
            Fixture.World->LineTraceSingleByChannel(OldAreaHit, OldStart, OldEnd, ECC_WorldStatic))) return false;
    }
    TestTrue(TEXT("At least one returned older physics tree was observed after the newer GT pose write"), bObservedReturnedOlderTree);
    TestEqual(TEXT("Moving the completed pose preserves query geometry and scale caching"), QueryPose.GetScaleUpdateCalls(), InitialScaleUpdates);
    return !HasAnyErrors();
}
#endif
}
