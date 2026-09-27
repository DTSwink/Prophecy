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
inline FQuat AimFromPivot(const FVector& Pivot,const FVector& VirtualTarget,const FVector& RealTarget)
{
    FVector From=VirtualTarget-Pivot,To=RealTarget-Pivot;
    if(From.ContainsNaN() || To.ContainsNaN() || !From.Normalize(1.e-8) || !To.Normalize(1.e-8)
        || From.Equals(To,1.e-10)) return FQuat::Identity;
    return FQuat::FindBetweenNormals(From,To).GetNormalized();
}
inline void CompensateSpinePosition(FTransform& Spine,const FTransform& GhostSpine,
    const FVector& GhostTarget,const FVector& RealTarget)
{
    // Transport the *target*, not the hand: preserve the learned wind-up/swing
    // relative to its aim ray. Only the ray's parallax changes with translation.
    const FVector VirtualTarget=Spine.TransformPosition(GhostSpine.InverseTransformPosition(GhostTarget));
    const FQuat Aim=AimFromPivot(Spine.GetLocation(),VirtualTarget,RealTarget);
    Spine.SetRotation((Aim*Spine.GetRotation()).GetNormalized());
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
inline bool MountDistributed(TConstArrayView<FTransform> Ghost,TArrayView<FTransform> Pose,
    TConstArrayView<int32> Parents,TConstArrayView<int32> Spines,const FTransform& RealPelvis,
    const FTransform& GhostAnchor,const FTransform& RealCarrier,const FVector* TargetWorld=nullptr)
{
    if(Spines.Num()!=5 || Ghost.Num()!=Pose.Num() || Parents.Num()!=Ghost.Num()) return false;
    for(int32 Bone:Spines) if(!Ghost.IsValidIndex(Bone)) return false;
    FQuat Counter=PelvisCounterRotation(Ghost[0],RealPelvis,GhostAnchor,RealCarrier);
    FTransform Corrected[5];
    BuildDistributedSpines(Ghost,Spines,RealPelvis,Counter,Corrected);
    if(TargetWorld)
    {
        const FVector RealTarget=RealCarrier.InverseTransformPosition(*TargetWorld);
        const FVector ChestLocalTarget=Ghost[Spines[4]].InverseTransformPosition(GhostAnchor.InverseTransformPosition(*TargetWorld));
        FVector VirtualTarget=Corrected[4].TransformPosition(ChestLocalTarget);
        double Error=FVector::DistSquared(VirtualTarget,RealTarget);
        // A distributed turn also moves the chest. At most two bounded five-link
        // evaluations account for that movement; accept only improvements. No
        // iterative convergence loop, allocations, history or extra inference.
        for(int32 Pass=0;Pass<2 && Error>1.e-8;++Pass)
        {
            const FQuat CandidateCounter=(AimFromPivot(Corrected[0].GetLocation(),VirtualTarget,RealTarget)*Counter).GetNormalized();
            FTransform Candidate[5];
            BuildDistributedSpines(Ghost,Spines,RealPelvis,CandidateCounter,Candidate);
            const FVector CandidateTarget=Candidate[4].TransformPosition(ChestLocalTarget);
            const double CandidateError=FVector::DistSquared(CandidateTarget,RealTarget);
            if(!FMath::IsFinite(CandidateError) || CandidateError>=Error) break;
            for(int32 I=0;I<5;++I) Corrected[I]=Candidate[I];
            Counter=CandidateCounter;VirtualTarget=CandidateTarget;Error=CandidateError;
        }
    }
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
