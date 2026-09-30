#pragma once
#include "CoreMinimal.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "PhysicsEngine/ConstraintInstance.h"

namespace ProphecyFixedArmPhysics
{
// Mode/rig-entry only. Angular motion is independent of attachment length.
inline void AttachWrists(USkeletalMeshComponent* Mesh)
{
    if(!Mesh || !Mesh->GetSkeletalMeshAsset())return;
    const auto& Ref=Mesh->GetSkeletalMeshAsset()->GetRefSkeleton();
    static const FName Hands[]={TEXT("hand_l"),TEXT("hand_r")};
    static const FName Forearms[]={TEXT("lowerarm_l"),TEXT("lowerarm_r")};
    for(FConstraintInstance* Joint:Mesh->Constraints)if(Joint)for(int32 S=0;S<2;++S)
    {
        const bool HandFirst=Joint->ConstraintBone1==Hands[S] && Joint->ConstraintBone2==Forearms[S];
        const bool HandSecond=Joint->ConstraintBone2==Hands[S] && Joint->ConstraintBone1==Forearms[S];
        if(!HandFirst && !HandSecond)continue;
        const int32 H=Ref.FindBoneIndex(Hands[S]);
        if(H==INDEX_NONE || Ref.GetParentIndex(H)==INDEX_NONE || Ref.GetBoneName(Ref.GetParentIndex(H))!=Forearms[S])continue;
        Joint->SetLinearXLimit(LCM_Locked,0);Joint->SetLinearYLimit(LCM_Locked,0);Joint->SetLinearZLimit(LCM_Locked,0);
        Joint->SetLinearBreakable(false,0);
        Joint->SetRefPosition(HandFirst?EConstraintFrame::Frame1:EConstraintFrame::Frame2,FVector::ZeroVector);
        Joint->SetRefPosition(HandFirst?EConstraintFrame::Frame2:EConstraintFrame::Frame1,Ref.GetRefBonePose()[H].GetLocation());
    }
}
}
