#pragma once
#include "CoreMinimal.h"
#include "ProphecyJoltRig.h"
#include "ProphecyJoltRobot.h"
class AProphecyAgent;
namespace ProphecyRobot
{
struct FBodySpec
{
    FName Bone;
    TArray<FName> Aliases;
    FTransform BodyFromBone, MassFrame;
    float Mass=0;
    FVector Inertia;
    FProphecyJoltRobotDrag Drag;
    TArray<FProphecyJoltRigShape> Shapes;
};
struct FJointSpec
{
    FName Name;
    int32 Child=0,Parent=0,Action=0;
    FTransform ParentFrame;
    FQuat Rest;
    FVector Bounds;
    FProphecyJoltRobotMotor Motor[2];
};
struct FProfile
{
    TArray<FBodySpec> Bodies;
    TArray<FJointSpec> Joints;
    TArray<FProphecyJoltRigDisabledPair> Disabled;
};
const FProfile* Profile(FString& Error);
struct FBodyState
{
    FTransform World;
    FVector COMVelocity=FVector::ZeroVector,AngularVelocity=FVector::ZeroVector;
};
bool MakeSnapshot(const FProfile& Profile,USkeletalMeshComponent& Mesh,
    TConstArrayView<FBodyState> Entry,FProphecyJoltRigSnapshot& Snapshot,FString& Error);
// Physical observations use the checkpoint's global +90 Z basis, never actor heading.
void Observation(const FProfile& Profile,TConstArrayView<FBodyState> Bodies,bool Clanker,
    float Gait,const FVector& Direction,bool SwordDrawn,const FVector2f& Phase,TArrayView<float> Out);
}
