#pragma once
#include "ProphecyFKReturnData.h"

namespace ProphecyFKReturn
{
// Canonical upper hierarchy. All work here is at entry or when gaze changes.
inline void GazeIdle(const FVector2f& Normalized,FTransform (&Local)[BoneCount])
{
    constexpr int32 Parent[]={-1,0,1,2,3,4,5,6,7,4,9,10,11,4,13,14};
    FTransform World[BoneCount];
    for(int32 J=0;J<BoneCount;++J)
    {
        const auto& B=Data::Bones[J];
        Local[J]=FTransform(FQuat(B.Q[0],B.Q[1],B.Q[2],B.Q[3]),FVector(B.P[0],B.P[1],B.P[2]));
        World[J]=Parent[J]<0?Local[J]:Local[J]*World[Parent[J]];
    }
    if(Normalized.IsZero())return;
    auto Turn=[&](int32 Root,const FQuat& Rotation,const FVector& Pivot)
    {
        for(int32 J=Root;J<BoneCount;++J)
        {
            int32 K=J;while(K>=0 && K!=Root)K=Parent[K];if(K<0)continue;
            // Training rotates descendant offsets; the subtree root stays put.
            if(J!=Root)World[J].SetLocation(Pivot+Rotation.RotateVector(World[J].GetLocation()-Pivot));
            World[J].SetRotation((Rotation*World[J].GetRotation()).GetNormalized());
        }
    };
    constexpr int32 Chain[]={0,1,2,3,4,13,14,15};
    // Training local coordinates reflect Y on export: axial X/Z rotations reverse sign.
    const double Yaw=-FMath::DegreesToRadians(170.*Normalized.X),Pitch=-FMath::DegreesToRadians(85.*Normalized.Y);
    for(int32 K=0;K<8;++K)
    {
        const int32 J=Chain[K];const FVector Pivot=World[J==15?14:J].GetLocation();
        Turn(J,FQuat(World[J].GetRotation().GetAxisX(),Yaw*(K+1)/36.),Pivot);
    }
    const FQuat SpineYaw=World[4].GetRotation();
    for(int32 J=0;J<4;++J)Turn(J,FQuat(World[J].GetRotation().GetAxisZ(),Pitch*(J+1)/36.),World[J].GetLocation());
    Turn(4,(SpineYaw*World[4].GetRotation().Inverse()).GetNormalized(),World[4].GetLocation());
    for(int32 K=0;K<2;++K){const int32 J=13+K;Turn(J,FQuat(World[J].GetRotation().GetAxisZ(),Pitch*.6*(6+K)/13.),World[J].GetLocation());}
    Turn(15,FQuat(World[15].GetRotation().GetAxisZ(),Pitch*.4),World[14].GetLocation());
    for(int32 J:Chain)Local[J]=Parent[J]<0?World[J]:World[J].GetRelativeTransform(World[Parent[J]]);
}
inline void RetargetGaze(FCurve& Curve,const FTransform (&Target)[BoneCount])
{
    // Preserve the continuous arc through 180 degrees, including selected slash winding.
    for(int32 J=0;J<BoneCount;++J)
    {
        auto& B=Curve.Bones[J];const FVector3f Before=B.Return.Axis*B.Return.HalfAngle;
        B.Return.Set(B.Start.Inverse()*FQuat4f(Target[J].GetRotation()));
        if(B.Return.HalfAngle==0 && !Before.IsNearlyZero())B.Return.Axis=Before.GetSafeNormal();
        B.Return.HalfAngle+=PI*FMath::RoundToFloat((FVector3f::DotProduct(Before,B.Return.Axis)-B.Return.HalfAngle)/PI);
        B.OffsetReturn.Set(Swing(B.Offset,FVector3f(Target[J].GetTranslation())));
    }
}
}
