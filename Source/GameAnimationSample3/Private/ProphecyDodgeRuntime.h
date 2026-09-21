#pragma once
#include "ProphecyDodgeBanks.h"

namespace ProphecyDefense
{
struct FDodgeState
{
    float PreviousLower[41],PreviousUpper[90],CurrentLower[41],CurrentUpper[90];
    FRootFrame PreviousRoot,CurrentRoot;
    FVector3f InitialWorldDelta,RootShift;
    float InitialYawDelta=0,YawOffset=0,Remaining[6]={};
    uint64 CompletedSteps=0;
    bool bInitialized=false;
    void Initialize(const float* Lower0,const float* Upper0,const float* Root0,
        const float* Lower1,const float* Upper1,const float* Root1,const float* Limits6);
};
struct FDodgeWork { uint64 StateStep=MAX_uint64; };
// FrozenLower must be the just-completed accepted lower network step under
// this state's causal root command, including its checkpoint's pin projection.
bool PrepareDodge(const FDodgeState& State,const float* FrozenLower,FContext Context,FDodgeWork& Work,float* Input362,
    const FRootFrame* PlannedRoot=nullptr);
bool CompleteDodge(FDodgeState& State,const FDodgeWork& Work,const float* FrozenLower,const float* Output112,
    const FGeometry& Geometry,FPose& Pose,float* ModifiedLower=nullptr,float* UnrebasedUpper=nullptr,
    const FRootFrame* PlannedRoot=nullptr,bool bReconstructLegs=true);
}
