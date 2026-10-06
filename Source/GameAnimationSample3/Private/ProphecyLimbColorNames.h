#pragma once
#include "CoreMinimal.h"
#include "ReferenceSkeleton.h"
namespace ProphecyLimbColors
{
inline constexpr int32 PaletteSize=32, UVChannel=2;
inline constexpr const TCHAR* MeshPath=TEXT("/Game/_mygame/SKM_UEFN_Mannequin.SKM_UEFN_Mannequin");
inline const TArray<FName>& Bones()
{
    static const TArray<FName> Names={TEXT("pelvis"),TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),
        TEXT("neck_01"),TEXT("neck_02"),TEXT("head"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),
        TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),
        TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r")};
    return Names;
}
inline int32 Region(const FReferenceSkeleton& Ref,int32 Bone)
{
    while(Bone!=INDEX_NONE)
    {
        const int32 Index=Bones().Find(Ref.GetBoneName(Bone));
        if(Index!=INDEX_NONE)return Index+1;
        Bone=Ref.GetParentIndex(Bone);
    }
    return 0;
}
}
