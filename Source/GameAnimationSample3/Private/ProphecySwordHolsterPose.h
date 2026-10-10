#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecySwordHolsterPose
{
struct FCurve
{
    FVector2D Points[6]={{0,0},{.2,.2},{.4,.4},{.6,.6},{.8,.8},{1,1}};
    double Slopes[6]={1,1,1,1,1,1};
    void Prepare();
    double Sample(double X) const;
};
struct FReturn
{
    bool Enabled=true,World=false,Spring=false;
    double Duration=1,Easing=1,Inertia=1,Hold=0,Decay=1,AngleTime=.29,TwistRemoval=0;
    double Weights[7]={1,1,1,1,1,1,1};
};
struct FProfile
{
    double AngleLimit=45,BodySpeed=90,HeadAlpha=1,HeadInSpeed=180,HeadOutSpeed=180;
    double HeadInExponent=1,HeadOutExponent=1,DrawHeadOut=.3,SheatheHeadOut=.5;
    FCurve Reach[2],Slide[2]; // Draw, sheathe.
    FReturn Return[2];
};
struct FStatus
{
    bool Ready=false,ReachDone=false,Finished=false,Returning=false,Blocked=false;
    int32 Tick=0,ReachTicks=0,SlideTicks=0;
    double Progress=0,SlideProgress=0,HandError=0,HeadStep=0;
};
float UnshrinkAlpha(float& ElapsedTicks,float Duration);
bool LoadProfile(const FString& Path,FProfile& Out,FString& Error);
void Configure(const AProphecyAgent* Agent,const FProfile& Profile);
bool Begin(AProphecyAgent* Agent,bool Sheathe,double ReachSpeed,double RotationSpeed,double SlideSpeed,
    double SlideLength,const FTransform& Clear,const FTransform& Seat,const FVector& Mouth);
void Update(AProphecyAgent* Agent,int32 PoseId);
bool Status(const AProphecyAgent* Agent,FStatus& Out);
void SetSliding(const AProphecyAgent* Agent,bool Sliding);
void SetTargets(const AProphecyAgent* Agent,const FTransform& Clear,const FTransform& Seat,const FVector& Mouth);
void Apply(int32 PoseId,TConstArrayView<FName> Names,TArrayView<FTransform> Pose,
    const FTransform& SpaceToWorld=FTransform::Identity);
void Remove(const AProphecyAgent* Agent,bool RemoveProfile=false);
}
