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
inline FQuat PelvisCounterRotation(const FTransform& GhostPelvis,const FTransform& RealPelvis,
    const FTransform& GhostAnchor,const FTransform& RealCarrier)
{
    // Compare in one frame: the ghost anchor and the real carrier can turn
    // independently. Counter-rotate at the spine attachment, not at the pelvis.
    const FQuat GhostPelvisInCarrier=(RealCarrier.GetRotation().Inverse()*GhostAnchor.GetRotation()*GhostPelvis.GetRotation()).GetNormalized();
    return GhostPelvisInCarrier*RealPelvis.GetRotation().Inverse();
}
inline FTransform CompensatedSpine(const FTransform& GhostSpine,const FTransform& GhostPelvis,
    const FTransform& RealPelvis,const FTransform& GhostAnchor,const FTransform& RealCarrier)
{
    FTransform Spine=Mount(GhostSpine,GhostPelvis,RealPelvis);
    const FQuat InversePelvisDifference=PelvisCounterRotation(GhostPelvis,RealPelvis,GhostAnchor,RealCarrier);
    Spine.SetRotation((InversePelvisDifference*Spine.GetRotation()).GetNormalized());
    return Spine;
}
inline void BuildDistributedSpines(TConstArrayView<FTransform> Ghost,TConstArrayView<int32> Spines,
    const FTransform& RealPelvis,const FQuat& Counter,FTransform (&Corrected)[5])
{
    const FQuat Step=FQuat::Slerp(FQuat::Identity,Counter,.2).GetNormalized();
    for(int32 I=0;I<5;++I)
    {
        const FTransform& GhostParent=Ghost[I==0 ? 0 : Spines[I-1]];
        const FTransform& RealParent=I==0 ? RealPelvis : Corrected[I-1];
        Corrected[I]=Ghost[Spines[I]].GetRelativeTransform(GhostParent)*RealParent;
        Corrected[I].SetRotation((Step*Corrected[I].GetRotation()).GetNormalized());
    }
}
// Inverse of the upper mount: the NN must see the actual torso-to-target
// distance as well as direction. Ghost and real transforms share one frame.
inline FVector ReachTarget(const FTransform (&Ghost)[6],const FTransform& RealPelvis,
    const FVector& RealTarget,bool bDistributed)
{
    if(bDistributed)
    {
        const int32 Spines[]={1,2,3,4,5};
        FTransform Corrected[5];
        BuildDistributedSpines(MakeArrayView(Ghost),MakeArrayView(Spines),RealPelvis,
            (Ghost[0].GetRotation()*RealPelvis.GetRotation().Inverse()).GetNormalized(),Corrected);
        return Ghost[5].TransformPosition(Corrected[4].InverseTransformPosition(RealTarget));
    }
    const FTransform Spine=CompensatedSpine(Ghost[1],Ghost[0],RealPelvis,FTransform::Identity,FTransform::Identity);
    return Ghost[1].TransformPosition(Spine.InverseTransformPosition(RealTarget));
}
inline bool MountDistributed(TConstArrayView<FTransform> Ghost,TArrayView<FTransform> Pose,
    TConstArrayView<int32> Parents,TConstArrayView<int32> Spines,const FTransform& RealPelvis,
    const FTransform& GhostAnchor,const FTransform& RealCarrier)
{
    if(Spines.Num()!=5 || Ghost.Num()!=Pose.Num() || Parents.Num()!=Ghost.Num()) return false;
    for(int32 Bone:Spines) if(!Ghost.IsValidIndex(Bone)) return false;
    FQuat Counter=PelvisCounterRotation(Ghost[0],RealPelvis,GhostAnchor,RealCarrier);
    FTransform Corrected[5];
    BuildDistributedSpines(Ghost,Spines,RealPelvis,Counter,Corrected);
    // Each subtree follows its nearest spine joint. This keeps attachment
    // translations/bone lengths and works independently of bone array ordering.
    for(int32 Bone=0;Bone<Ghost.Num();++Bone)
    {
        int32 Slot=INDEX_NONE;
        for(int32 Parent=Bone,Remaining=Parents.Num();Parents.IsValidIndex(Parent) && Remaining-->0;Parent=Parents[Parent])
        {
            for(int32 I=0;I<5;++I) if(Parent==Spines[I]) { Slot=I;break; }
            if(Slot!=INDEX_NONE)break;
        }
        if(Slot!=INDEX_NONE) Pose[Bone]=Bone==Spines[Slot] ? Corrected[Slot]
            : Ghost[Bone].GetRelativeTransform(Ghost[Spines[Slot]])*Corrected[Slot];
    }
    return true;
}
inline FVector Target(const FVector& RealTarget,const FTransform& RealPelvis,const FTransform& GhostPelvis)
{ return GhostPelvis.TransformPosition(RealPelvis.InverseTransformPosition(RealTarget)); }
}
