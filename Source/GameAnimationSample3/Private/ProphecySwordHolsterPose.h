#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
class USceneComponent;
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
    double Duration=1,Easing=1,Inertia=1,Hold=0,Decay=1,AngleTime=.29,TwistRemoval=0,StartFraction=.9;
    double HandRotationFKAlpha=1;
    bool ArmIKEnabled=false;double ArmIKStart=0,ArmIKEnd=.25;
    double SwordPointSpeed=0,SwordPointExponent=1.5,SwordPointCutoff=.5;
    FCurve Timing;
    double Weights[8]={1,1,1,1,1,1,1,1}; // Last group: drawing hand at release.
};
struct FBodyProfile
{
    bool Authored=false,SwordPole=false,HasSpeeds=false;
    FQuat Targets[2][3]; // Clear/seated: spine relative pelvis, clavicles relative spine05.
    double Pole[2]={0,0},PoleSpeed=180,Compensation=1,Speed=90;
    double Reach=100,Rotation=180,Sliding=60;
};
struct FProfile
{
    double AngleLimit=45,BodySpeed=90,HeadAlpha=1,HeadInSpeed=180,HeadOutSpeed=180;
    double HeadInExponent=1,HeadOutExponent=1,DrawHeadOut=.3,SheatheHeadOut=.5;
    double RotationTolerance=15,RotationCorrection=.1,HeadTargetAlpha=1,HeadSpeedAlpha=1,HeadInMaxGaze=180,HeadOutMaxGaze=180;
    double HeadMaxTilt=70;
    double EntryInertia=0,EntryDuration=.2,Shrink=10,Unshrink=.25;
    double ShrinkDuration=.25,AttachedSpeed=100,AttachedRotation=180,Stabilization=0,HolsterReturnDuration=.25,TipTolerance=2;
    bool LeewayPhase=true;
    FQuat BodyReference[3]={FQuat::Identity,FQuat::Identity,FQuat::Identity};
    FQuat WristReference=FQuat::Identity;
    bool HasWristReference=false;
    FBodyProfile Body[2];
    FCurve Reach[2],Slide[2]; // Draw, sheathe.
    FReturn Return[2];
    FVector2D ReturnBlend[2]={{1,1},{1,1}}; // Draw, sheathe: start/end of linear NN weight. (1,1) keeps the full lab return.
};
struct FStatus
{
    bool Ready=false,ReachDone=false,Finished=false,Returning=false,Blocked=false,Aligning=false;
    int32 Tick=0,ReachTicks=0,SlideTicks=0;
    double Progress=0,SlideProgress=0,Insertion=0,HandError=0,HeadStep=0;
};
struct FGeometry
{
    TWeakObjectPtr<USceneComponent> Holster;
    FTransform Seated,Grip;
    FVector BaseLocal=FVector::ZeroVector,TipLocal=FVector::ZeroVector,AssetScale=FVector::OneVector;
    double Retained=1,GripStabilization=0,HolsterReturnDuration=.25;
    double ShrinkDuration=.25,AttachedSpeed=100,AttachedRotation=180,TipTolerance=2;
    bool LeewayPhase=true;
    bool Valid=false;
};
struct FEntryPose { TArray<FName> Names;TArray<FTransform> Pose; };
bool CaptureEntryPose(AProphecyAgent* Agent,FEntryPose& Out);
float UnshrinkAlpha(float& ElapsedTicks,float Duration);
bool LoadProfile(const FString& Path,FProfile& Out,FString& Error);
void Configure(const AProphecyAgent* Agent,const FProfile& Profile);
void ConfigureReturnBlend(const AProphecyAgent* Agent,FVector2D DrawRange,FVector2D SheatheRange);
bool ActionSpeeds(const AProphecyAgent* Agent,bool Sheathe,float& Reach,float& Rotation,float& Slide);
bool Begin(AProphecyAgent* Agent,bool Sheathe,double ReachSpeed,double RotationSpeed,double SlideSpeed,
    double SlideLength,const FTransform& Clear,const FTransform& Seat,const FVector& Mouth,const FGeometry& Geometry=FGeometry(),const FEntryPose* Previous=nullptr);
void Update(AProphecyAgent* Agent,int32 PoseId);
bool Status(const AProphecyAgent* Agent,FStatus& Out);
void SetSliding(const AProphecyAgent* Agent,bool Sliding);
void UpdateHolsterMount(const AProphecyAgent* Agent);
void RestoreHolsterMount(const AProphecyAgent* Agent);
bool TrySheathe(const AProphecyAgent* Agent,const FTransform& ActualBlade);
bool SwordTarget(const AProphecyAgent* Agent,FTransform& Hand,double& Scale);
bool PhysicsSwordTarget(const AProphecyAgent* Agent,FTransform& Blade);
void SetTargets(const AProphecyAgent* Agent,const FTransform& Clear,const FTransform& Seat,const FVector& Mouth);
void Apply(int32 PoseId,TConstArrayView<FName> Names,TArrayView<FTransform> Pose,
    const FTransform& SpaceToWorld=FTransform::Identity);
void Remove(const AProphecyAgent* Agent,bool RemoveProfile=false);
}
