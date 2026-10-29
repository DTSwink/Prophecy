#pragma once
#include "CoreMinimal.h"

// The evaluator stays in the lab's right-handed Y-up metres. Convert only at the UE boundary.
namespace ProphecyThrow
{
using FPose=TArray<FTransform>;
struct FProfile
{
    FString Id,Kind;
    TArray<FName> Names; TArray<int32> Parents;
    TArray<FPose> Locals;
    TMap<int32,FQuat> HandKeys,ForearmKeys;
    TArray<FVector2D> Curve,Forward;
    double FPS=30,End=0,Armed=0,Release=0,Peak=0,Slowdown=0,Amount=1,Twist=0,Mass=1;
    bool Half=false,Aim=false;
    FVector Target=FVector::ZeroVector,Velocity=FVector::ZeroVector,Axis=FVector::UpVector,Scale=FVector::OneVector,COM=FVector::ZeroVector;
    FTransform Bind=FTransform::Identity,Grip=FTransform::Identity;
};
struct FPlan
{
    double Yaw=0,Pitch=0,Heading=0,Armed=0;
    bool Half=false,Valid=false,Entry=false;
    FQuat Rotation=FQuat::Identity;
    FPose Initial,ArmedLocal;
};
struct FCarry { double Frame=0,Duration=0; FVector Angular[3],Offset[3]; };
struct FModel
{
    const FProfile* Profile=nullptr;
    double Amount=1,Trigger=0,Release=0,Finish=0,Speed=1,StartSource=0,EndSource=0;
    FPlan FullPlan,PartialPlan;
    FPose Neutral,Reached;
    TArray<FVector> Rotation,Angular,Translation,Linear;
    FCarry EntryCarry,ExitCarry;
    void Prepare(const FProfile& In,double InAmount,const FVector& Target);
    FPose Raw(double Frame) const;
    FPose Keys(FPose Pose,double Frame) const;
    FPose Full(double Frame) const;
    FPose Body(double Frame) const;
    FPose Motion(double Frame,bool Carry=true) const;
    FPose Sample(double Frame) const;
    FTransform Held(const FPose& Pose) const;
    FTransform Launch(FVector& Velocity,FVector& Omega) const;
};
const FProfile* Profile(bool Small,FString& Error);
FVector ToUnrealPoint(const FVector& P);
FVector FromUnrealPoint(const FVector& P);
FTransform ToUnreal(const FTransform& T);
FQuat Euler(const FVector& Degrees);
}
