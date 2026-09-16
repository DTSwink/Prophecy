#pragma once
#include "ProphecyDefenseFeatures.h"

// Fixed saved-checkpoint skeleton in training coordinates. Loaded once per
// checkpoint, then shared by agents. All pose work uses fixed-size storage.
namespace ProphecyDefense
{
using namespace ProphecyDefenseFeatures;
struct FDodgeControls;
struct FPose { FVector3f P[25]; FRows R[25]; };
struct FGeometry
{
    struct FLimb
    {
        FVector3f Pole[2],ToeOffset,ToeAxis;
        float Length[2];
    };
    FVector3f LowerOffsets[25],FullOffsets[25];
    FVector3f ProjectionToeOffsets[2],ProjectionToeAxes[2];
    FLimb LowerLegs[2],FullLimbs[4]; // arms L/R, legs L/R
    bool bSignedLegHinge=false;

    bool Load(const FString& Filename,bool bDodge,FString& Error);
    void LowerPose(const float* Lower,const FVector3f& RootP,const FRows& RootR,FPose& Out,bool bIncludeLegs=true) const;
    static void EncodeUpper(const FPose& Pose,const FVector3f& RootP,const FRows& RootR,float* Upper);
    void RawPose(const float* Lower,const float* Upper,const FVector3f& RootP,const FRows& RootR,FPose& Out,bool bIncludeLegs=true) const;
    void Finish(const float* Lower,const float* Upper,const FVector3f& RootP,const FRows& RootR,
        const FPose& Frozen,const float* BaselineUpper,FPose& Out) const;
    bool SolveDodgeLower(const float* Baseline,const FDodgeControls& Controls,const FVector3f& RootP,
        const FRows& RootR,float* Out,bool bFootFloor=true) const;
};
}
