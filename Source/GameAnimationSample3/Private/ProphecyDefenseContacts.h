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
    bool Load(const FString& Filename,FString& Error,bool bAttacker=false);
    // Training attacker boxes attach directly to the authored bone basis.
    // Defender forearm/end-effector reconstruction must not affect this input.
    FDefenseBox BuildAttachedBox(const FVector3f& Position,const FRows& Rotation,int32 Index) const;
    void Build(const FPose& Pose,FDefenseBox* Out) const;
    FDefenseBox BuildBox(const FPose& Pose,int32 Index) const;
    uint32 PresentMask(bool bDrawn) const;
};

struct FContactPair
{
    float Fraction=0,Gap=0;
    int32 Iterations=0;
    bool bPossible=false,bConfirmed=false,bResolved=true;
};
float BoxGap(const FDefenseBox& A,const FVector3f& HalfA,const FDefenseBox& B,const FVector3f& HalfB);
// Conservative advancement: exhausted searches do not confirm a contact.
// Time is a fraction of this completed policy interval.
FContactPair SweepBoxes(const FDefenseBox& A0,const FDefenseBox& A1,const FVector3f& HalfA,const FVector3f& OffsetA,
    const FDefenseBox& B0,const FDefenseBox& B1,const FVector3f& HalfB,const FVector3f& OffsetB,int32 MaxIterations=96);

// Earliest confirmed contact, without gameplay success/damage classification.
struct FFirstContact
{
    double Time=std::numeric_limits<double>::infinity();
    int32 Collider=INDEX_NONE,Unresolved=0;
    void Include(const FContactPair& Pair,int32 Body,double Start,double End);
};
}
