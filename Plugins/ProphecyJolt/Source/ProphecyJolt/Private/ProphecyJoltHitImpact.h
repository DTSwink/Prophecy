#pragma once

namespace ProphecyJolt::HitImpact
{
struct FKey
{
    uint32 Body1, Shape1, Body2, Shape2;
    bool operator==(const FKey& Other) const
    { return Body1==Other.Body1 && Shape1==Other.Shape1 && Body2==Other.Body2 && Shape2==Other.Shape2; }
    friend uint32 GetTypeHash(const FKey& Key)
    { return HashCombineFast(HashCombineFast(Key.Body1,Key.Shape1),HashCombineFast(Key.Body2,Key.Shape2)); }
};
inline FKey Key(JPH::BodyID A,JPH::SubShapeID SA,JPH::BodyID B,JPH::SubShapeID SB)
{
    if (A.GetIndexAndSequenceNumber()>B.GetIndexAndSequenceNumber()) { Swap(A,B);Swap(SA,SB); }
    return {A.GetIndexAndSequenceNumber(),SA.GetValue(),B.GetIndexAndSequenceNumber(),SB.GetValue()};
}
struct FSample
{
    FVector RelativeVelocity=FVector::ZeroVector;
    double Speed=0.;
    bool Valid=false;
};
inline FSample Sample(const JPH::Body& A,const JPH::Body& B,const JPH::ContactManifold& Manifold)
{
    FSample Result;
    for (JPH::uint I=0;I<Manifold.mRelativeContactPointsOn1.size();++I)
    {
        const auto Relative=A.GetPointVelocity(Manifold.GetWorldSpaceContactPointOn1(I))
            -B.GetPointVelocity(Manifold.GetWorldSpaceContactPointOn2(I));
        const double Speed=FMath::Max(0.,double(Relative.Dot(Manifold.mWorldSpaceNormal))*100.);
        if (!Result.Valid || Speed>Result.Speed)
        {
            Result.Valid=true;Result.Speed=Speed;
            Result.RelativeVelocity=FVector(Relative.GetX(),Relative.GetY(),Relative.GetZ())*100.;
        }
    }
    // Stored consistently with the canonical native-body key.
    if (A.GetID().GetIndexAndSequenceNumber()>B.GetID().GetIndexAndSequenceNumber()) Result.RelativeVelocity*=-1.;
    return Result;
}
struct FDispatch
{
    UPrimitiveComponent* Mine=nullptr;
    UPrimitiveComponent* Other=nullptr;
    FName MyBone, OtherBone;
    FSample Sample;
};
// Synchronous GT event scope only; no last-hit cache or retained UObject references.
inline const FDispatch* Current=nullptr;
}
