#pragma once
#include "CoreMinimal.h"

namespace ProphecyHalfAttackMount
{
inline bool IsUpper(int32 Bone,int32 Spine01,TConstArrayView<int32> Parents)
{
    if (Spine01==INDEX_NONE) return false;
    for (int32 Remaining=Parents.Num();Parents.IsValidIndex(Bone) && Remaining-->0;Bone=Parents[Bone])
        if (Bone==Spine01) return true;
    return false;
}
inline FTransform Mount(const FTransform& GhostBone,const FTransform& GhostPelvis,const FTransform& RealPelvis)
{ return GhostBone.GetRelativeTransform(GhostPelvis)*RealPelvis; }
inline FVector Target(const FVector& RealTarget,const FTransform& RealPelvis,const FTransform& GhostPelvis)
{ return GhostPelvis.TransformPosition(RealPelvis.InverseTransformPosition(RealTarget)); }
}
