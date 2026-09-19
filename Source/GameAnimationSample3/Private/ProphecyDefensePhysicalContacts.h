#pragma once
#include "CoreMinimal.h"
#include "ProphecyDefenseContacts.h"
class AProphecyAgent;
class AActor;
class FProphecyJoltContactShape;

// Optional kinematic contact-stop geometry, separate from training conditioning.
struct FProphecyDefensePhysicalContacts
{
    struct FBody
    {
        FName Name;
        int32 Bone=INDEX_NONE;
        FTransform Local=FTransform::Identity;
        TSharedPtr<FProphecyJoltContactShape> Shape;
        TWeakObjectPtr<AActor> Sword;
        TWeakObjectPtr<AProphecyAgent> SwordOwner;
        bool bBlade=false;
    };
    TArray<FBody> Defender,Attacker;
    bool Build(AProphecyAgent& Owner,AProphecyAgent& Source,FName AttackBone,TConstArrayView<FName> Names,
        FString& Error);
    void Sweep(const FTransform* D0,const FTransform* D1,const FTransform* A0,const FTransform* A1,
        ProphecyDefense::FFirstContact& Order,int32 Step) const;
};
