#pragma once
#include "ProphecyParryRuntime.h"

namespace ProphecyDefense
{
struct FDodgeControls
{
    FVector2f PelvisHorizontal,RootHorizontal;
    FVector3f Foot[2],PelvisRotation;
    float RootYaw=0,Drop=0,Remaining[6]={},RequestedDistance[6]={},DropRequested=0;
    bool bEnabled=false;
};
// Six path budgets: pelvis XY, left foot XYZ, right foot XYZ, pelvis rotation,
// root XY, root yaw. Values are metres/radians, not rates. Geometry cannot refund.
FDodgeControls DodgeControls(const float* Raw22,const float* Remaining6,float PelvisWorldHeight);
FVector3f DodgeHorizontal(const FVector2f& Offset,const FRows& RootAxes);
FRows DodgeYaw(float Angle);
FVector3f DodgeCommand(const FVector3f& InitialDelta,float YawOffset);
FRootFrame DodgeNextRoot(const FRootFrame& Current,const FVector3f& InitialDelta,float InitialYaw,
    const FVector2f& Horizontal,float YawShift,float YawOffset);
}
