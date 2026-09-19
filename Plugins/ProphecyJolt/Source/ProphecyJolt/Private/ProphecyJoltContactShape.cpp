#include "ProphecyJoltContactShape.h"
#include "PhysicsEngine/BodySetup.h"
THIRD_PARTY_INCLUDES_START
#include <Jolt/Jolt.h>
#include <Jolt/Physics/Collision/Shape/SphereShape.h>
#include <Jolt/Physics/Collision/Shape/BoxShape.h>
#include <Jolt/Physics/Collision/Shape/CapsuleShape.h>
#include <Jolt/Physics/Collision/Shape/ConvexHullShape.h>
#include <Jolt/Physics/Collision/Shape/StaticCompoundShape.h>
#include <Jolt/Physics/Collision/CollideShape.h>
#include <Jolt/Physics/Collision/CollisionDispatch.h>
#include <Jolt/Physics/Collision/CollisionCollectorImpl.h>
THIRD_PARTY_INCLUDES_END

namespace
{
JPH::Vec3 ContactMeters(const FVector& V) { return JPH::Vec3(float(V.X*.01),float(V.Y*.01),float(V.Z*.01)); }
JPH::Quat ContactQuat(const FQuat& Q) { return JPH::Quat(float(Q.X),float(Q.Y),float(Q.Z),float(Q.W)); }
bool ContactEnabled(const FKShapeElem& E)
{ return E.GetCollisionEnabled()==ECollisionEnabled::QueryAndPhysics || E.GetCollisionEnabled()==ECollisionEnabled::PhysicsOnly; }
}
struct FProphecyJoltContactShape::FNative
{
    JPH::RefConst<JPH::Shape> Shape;
    float Radius=0;
};
FProphecyJoltContactShape::FProphecyJoltContactShape()=default;
FProphecyJoltContactShape::~FProphecyJoltContactShape()=default;
bool FProphecyJoltContactShape::Build(const UBodySetup& Setup,const FVector& Scale,FString& Error)
{
    Native.Reset();Error.Reset();
    if (Scale.ContainsNaN() || Scale.GetAbsMin()<=UE_SMALL_NUMBER)
    { Error=TEXT("Invalid collision scale.");return false; }
    const auto& G=Setup.AggGeom;
    if (G.TaperedCapsuleElems.Num() || G.LevelSetElems.Num() || G.SkinnedLevelSetElems.Num())
    { Error=TEXT("Kinematic contact query does not support this authored shape type.");return false; }
    JPH::StaticCompoundShapeSettings Compound;int32 Count=0;
    auto Add=[&](const JPH::Shape::ShapeResult& R,const FVector& P,const FQuat& Q)
    {
        if (R.HasError()) { Error=UTF8_TO_TCHAR(R.GetError().c_str());return false; }
        Compound.AddShape(ContactMeters(P),ContactQuat(Q),R.Get());++Count;return true;
    };
    for (const auto& Source:G.SphereElems) if (ContactEnabled(Source))
    {
        const auto E=Source.GetFinalScaled(Scale,FTransform::Identity);
        if (!Add(JPH::SphereShapeSettings(float(E.Radius*.01)).Create(),E.Center,FQuat::Identity)) return false;
    }
    for (const auto& Source:G.BoxElems) if (ContactEnabled(Source))
    {
        const auto E=Source.GetFinalScaled(Scale,FTransform::Identity);
        if (!Add(JPH::BoxShapeSettings(ContactMeters(FVector(E.X,E.Y,E.Z)*.5),0.f).Create(),E.Center,E.Rotation.Quaternion())) return false;
    }
    for (const auto& Source:G.SphylElems) if (ContactEnabled(Source))
    {
        const auto E=Source.GetFinalScaled(Scale,FTransform::Identity);
        const FQuat Q=E.Rotation.Quaternion()*FQuat(FVector::XAxisVector,UE_HALF_PI);
        if (E.Length<=UE_SMALL_NUMBER)
        { if (!Add(JPH::SphereShapeSettings(float(E.Radius*.01)).Create(),E.Center,Q)) return false; }
        else if (!Add(JPH::CapsuleShapeSettings(float(E.Length*.005),float(E.Radius*.01)).Create(),E.Center,Q)) return false;
    }
    for (const auto& E:G.ConvexElems) if (ContactEnabled(E))
    {
        JPH::ConvexHullShapeSettings S;S.mMaxConvexRadius=0;S.mHullTolerance=0;
        for (const FVector& V:E.VertexData) S.mPoints.push_back(ContactMeters(E.GetTransform().TransformPosition(V)*Scale));
        if (S.mPoints.size()>JPH::ConvexHullShape::cMaxPointsInHull)
        { Error=TEXT("Authored convex exceeds Jolt's hull limit; refusing to simplify contact geometry.");return false; }
        if (!Add(S.Create(),FVector::ZeroVector,FQuat::Identity)) return false;
    }
    if (!Count) { Error=TEXT("No authored simulation collision shapes.");return false; }
    const auto Result=Compound.Create();
    if (Result.HasError()) { Error=UTF8_TO_TCHAR(Result.GetError().c_str());return false; }
    Native=MakeUnique<FNative>();Native->Shape=Result.Get();
    const auto Bounds=Native->Shape->GetLocalBounds();
    Native->Radius=Bounds.GetExtent().Length()+Bounds.GetCenter().Length()+Native->Shape->GetCenterOfMass().Length();
    return true;
}
float FProphecyJoltContactShape::PenetrationCm(const FTransform& A,const FProphecyJoltContactShape& Other,const FTransform& B) const
{
    if (!Native || !Other.Native) return 0.f;
    auto At=[&](const FTransform& T,const FNative& N)
    {
        const auto Q=ContactQuat(T.GetRotation());
        return JPH::Mat44::sRotationTranslation(Q,ContactMeters(T.GetLocation()-A.GetLocation())+Q*N.Shape->GetCenterOfMass());
    };
    JPH::AllHitCollisionCollector<JPH::CollideShapeCollector> Hits;
    JPH::CollideShapeSettings Settings;Settings.mCollisionTolerance=1.e-6f;
    JPH::CollisionDispatch::sCollideShapeVsShape(Native->Shape,Other.Native->Shape,JPH::Vec3::sReplicate(1),JPH::Vec3::sReplicate(1),
        At(A,*Native),At(B,*Other.Native),{},{},Settings,Hits);
    float Depth=0.f;
    for (const auto& Hit:Hits.mHits) Depth=FMath::Max(Depth,Hit.mPenetrationDepth*100.f);
    return Depth;
}
bool FProphecyJoltContactShape::Sweep(const FTransform& A0,const FTransform& A1,const FProphecyJoltContactShape& Other,
    const FTransform& B0,const FTransform& B1,float& Fraction) const
{
    Fraction=0;if (!Native || !Other.Native) return false;
    const FVector R0=B0.GetLocation()-A0.GetLocation(),R1=B1.GetLocation()-A1.GetLocation(),D=R1-R0;
    const double T=D.SizeSquared()>0?FMath::Clamp(-FVector::DotProduct(R0,D)/D.SizeSquared(),0.,1.):0.;
    const float Radius=Native->Radius+Other.Native->Radius;
    if ((R0+D*T).SizeSquared()>FMath::Square(double(Radius)*100.)) return false;
    const float Speed=float(D.Size()*.01+A0.GetRotation().AngularDistance(A1.GetRotation())*Native->Radius
        +B0.GetRotation().AngularDistance(B1.GetRotation())*Other.Native->Radius);
    auto At=[&](const FTransform& From,const FTransform& To,const FNative& N)
    {
        const auto Q=ContactQuat(FQuat::Slerp(From.GetRotation(),To.GetRotation(),Fraction).GetNormalized());
        const auto P=ContactMeters(FMath::Lerp(From.GetLocation(),To.GetLocation(),double(Fraction))-A0.GetLocation());
        return JPH::Mat44::sRotationTranslation(Q,P+Q*N.Shape->GetCenterOfMass());
    };
    JPH::CollideShapeSettings Settings;Settings.mCollisionTolerance=1.e-6f;
    Settings.mMaxSeparationDistance=float(FMath::Max(R0.Size(),R1.Size())*.01)+Radius+.01f;
    // Conservative advancement bounds both translation and rotation. No inflated
    // gameplay margin: 0.001 cm here is only numerical contact convergence.
    for (int32 I=0;I<128;++I)
    {
        JPH::ClosestHitCollisionCollector<JPH::CollideShapeCollector> Hit;
        JPH::CollisionDispatch::sCollideShapeVsShape(Native->Shape,Other.Native->Shape,JPH::Vec3::sReplicate(1),JPH::Vec3::sReplicate(1),
            At(A0,A1,*Native),At(B0,B1,*Other.Native),{},{},Settings,Hit);
        if (!Hit.HadHit()) return false;
        const float Gap=-Hit.mHit.mPenetrationDepth;
        if (Gap<=1.e-5f) return true;
        if (Speed<=1.e-8f) return false;
        Fraction+=Gap/(Speed*1.01f);
        if (Fraction>1.f) return false;
    }
    return false; // An unresolved numerical query is not evidence of contact.
}

#if !UE_BUILD_SHIPPING
#include "Components/SkeletalMeshComponent.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"
// On demand only: measure PHAT overlap at the actually displayed PhysicalMesh poses.
static FAutoConsoleCommandWithWorldAndArgs MeasureHandHead(TEXT("Prophecy.Debug.MeasureHandHead"),
    TEXT("Measure displayed PHAT overlap: attacker actor name, defender actor name."),
    FConsoleCommandWithWorldAndArgsDelegate::CreateLambda([](const TArray<FString>& Args,UWorld* World)
{
    if (!World || Args.Num()!=2) return;
    USkeletalMeshComponent* AM=nullptr;USkeletalMeshComponent* BM=nullptr;
    for (TActorIterator<AActor> It(World);It;++It)
    {
        if (It->GetName()!=Args[0] && It->GetName()!=Args[1]) continue;
        TInlineComponentArray<USkeletalMeshComponent*> Meshes(*It);
        for (auto* Mesh:Meshes) if (Mesh->GetFName()==TEXT("PhysicalMesh"))
        {
            if (It->GetName()==Args[0]) AM=Mesh;
            if (It->GetName()==Args[1]) BM=Mesh;
        }
    }
    if (!AM || !BM || !AM->GetPhysicsAsset() || !BM->GetPhysicsAsset()) return;
    auto Build=[](USkeletalMeshComponent* Mesh,FName Bone,FProphecyJoltContactShape& Shape)
    {
        auto* Asset=Mesh->GetPhysicsAsset();const int32 Index=Asset->FindBodyIndex(Bone);
        FString Error;
        return Asset->SkeletalBodySetups.IsValidIndex(Index) &&
            Shape.Build(*Asset->SkeletalBodySetups[Index],Mesh->GetSocketTransform(Bone).GetScale3D(),Error);
    };
    FProphecyJoltContactShape Head;
    if (!Build(BM,TEXT("head"),Head)) return;
    for (FName Bone:{FName(TEXT("hand_l")),FName(TEXT("hand_r")),FName(TEXT("lowerarm_l")),FName(TEXT("lowerarm_r"))})
    {
        FProphecyJoltContactShape Limb;if (!Build(AM,Bone,Limb)) continue;
        const float Visible=Limb.PenetrationCm(AM->GetSocketTransform(Bone),Head,BM->GetSocketTransform(TEXT("head")));
        UE_LOG(LogTemp,Display,TEXT("PHAT_OVERLAP,%.6f,%s,%s,%s,%.6f"),
            World->GetTimeSeconds(),*Args[0],*Args[1],*Bone.ToString(),Visible);
    }
}));
#endif

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyContactDepthTest,"Prophecy.Jolt.ContactShapes.PenetrationDepth",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyContactDepthTest::RunTest(const FString&)
{
    auto* Capsule=NewObject<UBodySetup>();FKSphylElem C;C.Radius=10;C.Length=20;Capsule->AggGeom.SphylElems.Add(C);
    auto* Sphere=NewObject<UBodySetup>();FKSphereElem S;S.Radius=1;Sphere->AggGeom.SphereElems.Add(S);
    FProphecyJoltContactShape A,B;FString Error;
    if (!A.Build(*Capsule,FVector::OneVector,Error) || !B.Build(*Sphere,FVector::OneVector,Error)) { AddError(Error);return false; }
    TestNearlyEqual(TEXT("Capsule/sphere overlap in cm"),A.PenetrationCm(FTransform::Identity,B,FTransform(FVector(10.5,0,0))),.5f,.001f);
    TestEqual(TEXT("Separated shapes"),A.PenetrationCm(FTransform::Identity,B,FTransform(FVector(12,0,0))),0.f);
    return true;
}
#endif
