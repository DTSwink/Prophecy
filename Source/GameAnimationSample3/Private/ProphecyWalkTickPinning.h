#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyWalkPinning
{
// Experimental presentation cache; no changes to the NN clock or retained agent layouts.
struct FTickPinFrame
{
    FVector3f Delta[2]={FVector3f::ZeroVector,FVector3f::ZeroVector};
    FVector2f Applied=FVector2f::ZeroVector,Cap=FVector2f(1,1),Minimum=FVector2f::ZeroVector;
    FVector2f WalkWeight=FVector2f::ZeroVector,OtherPin=FVector2f::ZeroVector;
    bool Valid=false;
    float Effective(int32 Side,float Smoothed) const
    { return FMath::Min(Cap[Side],FMath::Max(Smoothed,Minimum[Side])); }
    FVector3f Shift(int32 Side,float Smoothed) const
    { return Valid ? Delta[Side]*((Effective(Side,Smoothed)-Applied[Side])*WalkWeight[Side]) : FVector3f::ZeroVector; }
};
struct FTickPinning
{
    FTickPinFrame Previous,Current;
    int32 PoseId=INDEX_NONE;
    int32 Bones[8]={};
    FTransform BasePrevious[8],BaseCurrent[8];
    FVector2f Last=FVector2f(-1,-1),Effective=FVector2f::ZeroVector;
    double SampleTime=-1;
    bool HasBase=false,Dirty=false;
};
struct FTickPinOffsets {FVector WorldOffset[2]={FVector::ZeroVector,FVector::ZeroVector};};
FTickPinOffsets& TickOffsets(const AProphecyAgent* Agent);
FTickPinning* FindTickPinning(const AProphecyAgent* Agent);
bool AnyTickPinning();
void ResetTickPinning(const AProphecyAgent* Agent);
}
