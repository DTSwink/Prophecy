#pragma once
#include "ProphecyDefenseFeatures.h"

// On-demand drawing data, never a second sampled pose or retained debug cache.
namespace ProphecyDefenseInputDebug
{
struct FSample
{
    FVector Pelvis,Collider,Corners[8],PelvisAxes[3];
};
inline FVector Vector(const FVector3f& V) { return FVector(V.X,V.Z,V.Y); }
inline FTransform WorldBone(const FVector3f& Position,const ProphecyDefenseFeatures::FRows& Axes,
    const FVector3f& WorldOrigin,const FVector& Offset)
{
    // Same UE boundary as DefenseForearmRoll/DefenseComponentPose: the training
    // second bone axis is the negative Unreal local Y axis.
    return FTransform(FRotationMatrix::MakeFromXY(Vector(Axes.V[0]),-Vector(Axes.V[1])).ToQuat(),
        Vector(Position+WorldOrigin)*100.+Offset);
}
inline FSample Build(const float* Pelvis9,const float* Collider9,const FVector3f& Half,
    const FVector3f& WorldOrigin,const FVector& Offset)
{
    using namespace ProphecyDefenseFeatures;
    FSample S;
    S.Pelvis=Vector(Read(Pelvis9)+WorldOrigin)*100.+Offset;
    S.Collider=Vector(Read(Collider9)+WorldOrigin)*100.+Offset;
    // Retain the actual supplied axes. A UE quaternion roundtrip would silently
    // orthonormalize them and can obscure the input's handedness/box attachment.
    const FVector3f PX=Read(Pelvis9+3),PY=Read(Pelvis9+6);
    S.PelvisAxes[0]=Vector(PX);S.PelvisAxes[1]=Vector(PY);S.PelvisAxes[2]=Vector(FVector3f::CrossProduct(PX,PY));
    const FVector3f X=Read(Collider9+3),Y=Read(Collider9+6),Z=FVector3f::CrossProduct(X,Y);
    for(int32 I=0;I<8;++I)
        S.Corners[I]=S.Collider+Vector(X*((I&1)?Half.X:-Half.X)+Y*((I&2)?Half.Y:-Half.Y)+Z*((I&4)?Half.Z:-Half.Z))*100.;
    return S;
}
}
