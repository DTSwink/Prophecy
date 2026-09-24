#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyWalkPinning
{
struct FBackwardBound
{
    float MinCm=20,MaxCm=60;
    int32 RootIndex=0;
    float Cap(double BackwardCm) const
    {
        if (BackwardCm<=MinCm) return 1.f;
        if (BackwardCm>=MaxCm) return 0.f;
        return float((double(MaxCm)-BackwardCm)/(double(MaxCm)-MinCm));
    }
};
const FBackwardBound* FindBackwardBound(const AProphecyAgent* Agent);
const FBackwardBound* FindCircleBound(const AProphecyAgent* Agent);
float BackwardTransferMultiplier(const AProphecyAgent* Agent);
inline void TransferBackwardPins(float Multiplier,const FVector2f& BackwardCaps,const FVector2f& OwnCaps,float& Left,float& Right)
{
    if (Multiplier<=0) return;
    // Both requests come from immutable geometry, never from each other's newly
    // modified pin weight. No order dependence or feedback between the feet.
    const float ToLeft=FMath::Clamp((1.f-BackwardCaps.Y)*Multiplier,0.f,1.f);
    const float ToRight=FMath::Clamp((1.f-BackwardCaps.X)*Multiplier,0.f,1.f);
    Left=FMath::Min(OwnCaps.X,FMath::Max(Left,ToLeft));
    Right=FMath::Min(OwnCaps.Y,FMath::Max(Right,ToRight));
}
// Root-window yaw zero faces local +Y in Unreal (training +Z), not actor +X.
inline FVector BoundHeading(const FTransform& Root)
{ return Root.GetUnitAxis(EAxis::Y).GetSafeNormal2D(); }
// Shared gameplay/debug reference: future samples provide heading only.
inline void BackwardReference(const FTransform& CurrentRoot,const FTransform& HeadingRoot,FVector& Origin,FVector& Heading)
{ Origin=CurrentRoot.GetLocation();Heading=BoundHeading(HeadingRoot); }
// Angle interpolation remains well defined even for opposing headings.
inline FVector BlendBackwardHeading(const FVector& Heading,const FVector& Target,float Alpha)
{
    if (Alpha<=0 || Target.ContainsNaN()) return Heading;
    const FVector Goal=Target.GetSafeNormal2D();
    if (Goal.IsNearlyZero()) return Heading;
    if (Alpha>=1) return Goal;
    const double Start=FMath::Atan2(Heading.Y,Heading.X);
    const double Delta=FMath::FindDeltaAngleRadians(Start,FMath::Atan2(Goal.Y,Goal.X));
    const double Angle=Start+double(Alpha)*Delta;
    return FVector(FMath::Cos(Angle),FMath::Sin(Angle),0);
}
// Shared by gameplay and debug arrows. Zero skips target lookup and angle math.
void ApplyBackwardTargetHeading(const AProphecyAgent* Agent,FVector& Heading);
inline double BackwardDistance(const FVector& Foot,const FVector& Root,const FVector& Heading)
{ return FVector::DotProduct(Root-Foot,Heading); }
inline float BoundPin(float Pin,const FBackwardBound& Bound,const FVector& Foot,const FVector& Root,const FVector& Heading)
{ return FMath::Min(Pin,Bound.Cap(BackwardDistance(Foot,Root,Heading))); }
inline float CircleBoundPin(float Pin,const FBackwardBound& Bound,const FVector& Foot,const FVector& Root)
{ return FMath::Min(Pin,Bound.Cap(FVector::Dist2D(Foot,Root))); }
struct FSmoothing
{
    int32 InFrames=3,OutFrames=3;
    float Current[2]={0,0},Target[2]={0,0};
    float Start[2]={0,0};
    uint32 Elapsed[2]={0,0};
    bool Active() const { return Current[0]!=Target[0] || Current[1]!=Target[1]; }
};
FSmoothing* FindSmoothing(const AProphecyAgent* Agent);
void SmoothPins(FSmoothing& State,float& Left,float& Right);
void ClearSmoothedFoot(FSmoothing& State,int32 Side);
void ResetSmoothing(const AProphecyAgent* Agent);
struct FReachGuard
{
    int32 Frames=6;
    int32 Remaining[2]={0,0};
    bool HasCooldown() const { return Remaining[0]>0 || Remaining[1]>0; }
};
FReachGuard* FindReachGuard(const AProphecyAgent* Agent);
// Called only for an actually selected visible Walk/mixed foot, after policy mixing.
bool RejectPin(FReachGuard& Guard,int32 Side,const FVector3f& Hip,const FVector3f& PinnedFoot,float Reach);
void ClearReachCooldown(const AProphecyAgent* Agent);

struct FSettings
{
    float Tolerance=0,Fallback=0;
    bool Apply(float Left,float Right,float PinScale,float& LeftPin,float& RightPin) const
    {
        if (Tolerance<=0 || Left<=0 || Right<=0 || !FMath::IsFinite(Left) || !FMath::IsFinite(Right)
            || FMath::Abs(Left-Right)>Tolerance) return false;
        LeftPin=RightPin=0;
        if (Fallback>0)
        {
            LeftPin=Fallback/(1.f+FMath::Exp(Left*PinScale));
            RightPin=Fallback/(1.f+FMath::Exp(Right*PinScale));
        }
        return true;
    }
};
bool Apply(const AProphecyAgent* Agent,float Left,float Right,float PinScale,float& LeftPin,float& RightPin);
}
