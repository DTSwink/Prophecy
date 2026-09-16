#pragma once
#include "ProphecyDefenseGeometry.h"
#include <limits>

namespace ProphecyDefense
{
struct FDefenseBox { FVector3f Center; FRows Axes; };
// Loaded once with the model, never rebuilt per agent or physics/render tick.
struct FContactGeometry
{
    static constexpr int32 MaxBoxes=20;
    struct FAttachment
    {
        FName Name;
        FVector3f Half,CenterOffset,BoneOffset;
        FRows LocalAxes;
        int32 Bone=INDEX_NONE;
    };
    FAttachment Boxes[MaxBoxes];
    int32 Count=0,BaseCount=0;
    bool Load(const FString& Filename,FString& Error);
    void Build(const FPose& Pose,FDefenseBox* Out) const;
    FDefenseBox BuildBox(const FPose& Pose,int32 Index) const;
    // Eligibility is supplied by gameplay, never appended to the NN input.
    uint32 BlockingMask(int32 TrainingLabel,bool bDrawn) const;
    uint32 PresentMask(bool bDrawn) const;
};

struct FContactPair
{
    float Fraction=0,Gap=0;
    int32 Iterations=0;
    bool bPossible=false,bConfirmed=false,bResolved=true;
};
float BoxGap(const FDefenseBox& A,const FVector3f& HalfA,const FDefenseBox& B,const FVector3f& HalfB);
// Strict conservative advancement: exhausted searches may be harmful, but
// never certify a block. Time is a fraction of this completed policy interval.
FContactPair SweepBoxes(const FDefenseBox& A0,const FDefenseBox& A1,const FVector3f& HalfA,const FVector3f& OffsetA,
    const FDefenseBox& B0,const FDefenseBox& B1,const FVector3f& HalfB,const FVector3f& OffsetB,int32 MaxIterations=96);

struct FContactOrder
{
    double BlockTime=std::numeric_limits<double>::infinity(),HarmTime=std::numeric_limits<double>::infinity();
    int32 BlockCollider=INDEX_NONE,HarmCollider=INDEX_NONE,Unresolved=0;
    float BlockFraction=0,HarmFraction=0;
    bool bProtected=false,bHarmful=false;
    // Source-frame times, matching training's 2/8192 tie margin. Calling code
    // accumulates only real intervals, and stops the episode at the first hit.
    void Include(const FContactPair& Pair,int32 Collider,bool bBlocking,double Start,double End);
};
}
