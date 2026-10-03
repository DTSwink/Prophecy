#pragma once
#include "CoreMinimal.h"
#include "Containers/StaticArray.h"
#include "ProphecyFKReturnData.h"

namespace ProphecyForearmConvention
{
inline const FQuat& IdleLocalUE(int32 Side)
{
    static const TStaticArray<FQuat,2> Reference=[]
    {
        TStaticArray<FQuat,2> Result;
        for(int32 I=0;I<2;++I)for(const auto& Bone:ProphecyFKReturn::Data::Bones)
            if(FCString::Strcmp(Bone.Name,I==0?TEXT("lowerarm_l"):TEXT("lowerarm_r"))==0)
                Result[I]=FQuat(Bone.Q[0],Bone.Q[1],Bone.Q[2],Bone.Q[3]).GetNormalized();
        return Result;
    }();
    return Reference[Side];
}

// All arguments use the same basis. Carry the neutral parent-local frame, then
// swing its anatomical axis to the wrist. Hand orientation never chooses roll.
inline FQuat FromReference(const FVector& LocalAxis,const FVector& ElbowToHand,const FQuat& Reference)
{
    const FVector From=Reference.RotateVector(LocalAxis);
    const FVector To=ElbowToHand.GetSafeNormal(1.e-16,From);
    const double Dot=FMath::Clamp(FVector::DotProduct(From,To),-1.,1.);
    FQuat Swing;
    if(Dot>=-.999999)
    {
        const FVector Cross=FVector::CrossProduct(From,To);
        Swing=FQuat(Cross.X,Cross.Y,Cross.Z,1.+Dot).GetNormalized();
    }
    else
    {
        FVector Axis=FVector::CrossProduct(From,FVector(1,0,0));
        if(Axis.SizeSquared()<1.e-10)Axis=FVector::CrossProduct(From,FVector(0,1,0));
        Swing=FQuat(Axis.GetSafeNormal(),UE_DOUBLE_PI);
    }
    return Swing*Reference;
}
}
