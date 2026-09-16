#pragma once
#include "ProphecyDefenseGeometry.h"

namespace ProphecyDefense
{
struct FRootFrame
{
    FVector3f P;
    FRows R;
    static FRootFrame Read12(const float* Values) { return {Read(Values),Rows(Values+3)}; }
};
struct FParryState
{
    float PreviousLower[41],PreviousUpper[90],CurrentLower[41],CurrentUpper[90],CurrentBaseline[90];
    FRootFrame PreviousRoot,CurrentRoot;
    FVector3f InitialWorldDelta;
    float InitialYawDelta;
    uint64 CompletedSteps=0;
    bool bInitialized=false;

    // Primers are two consecutive completed samples, each in its own root.
    void Initialize(const float* Lower0,const float* Upper0,const float* Root0,
        const float* Lower1,const float* Upper1,const float* Root1,const float* Baseline1);
};
struct FParryWork
{
    float HeldLower[41],HeldBaseline[90];
    uint64 StateStep=MAX_uint64;
};
// Prepare/Complete are split so all active agents share one batched network
// call. The manager must finish attacker inference and lower locomotion first.
bool PrepareParry(const FParryState& State,const float* NextLower,const float* NextBaseline,
    const FRootFrame& NextRoot,FContext Context,float Drawn,FParryWork& Work,float* Input258);
bool CompleteParry(FParryState& State,const FParryWork& Work,const float* Delta90,const float* NextLower,
    const float* NextBaseline,const FRootFrame& NextRoot,const FPose& Frozen,const FGeometry& Geometry,FPose& Out);
}
