#include "ProphecyDefensePhysicalContacts.h"
#include "ProphecyAgent.h"
#include "ProphecySwordAttackCollision.h"
#include "ProphecyJoltContactShape.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/SkeletalMeshSocket.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"

namespace
{
bool AttackBody(FName Name,FName Selected)
{
    if (Name==Selected) return true;
    if (Selected==TEXT("lowerarm_l")) return Name==TEXT("hand_l");
    if (Selected==TEXT("lowerarm_r")) return Name==TEXT("hand_r");
    if (Selected==TEXT("calf_l")) return Name==TEXT("foot_l") || Name==TEXT("ball_l");
    if (Selected==TEXT("calf_r")) return Name==TEXT("foot_r") || Name==TEXT("ball_r");
    return false;
}
bool AttachBone(USkeletalMeshComponent& Mesh,FName Name,TConstArrayView<FName> Names,int32& Bone,FTransform& Local)
{
    const auto& Ref=Mesh.GetSkeletalMeshAsset()->GetRefSkeleton();
    int32 Index=Ref.FindBoneIndex(Name);
    while (Index!=INDEX_NONE)
    {
        Bone=Names.IndexOfByKey(Ref.GetBoneName(Index));if (Bone!=INDEX_NONE) return true;
        Local=Local*Ref.GetRefBonePose()[Index];Index=Ref.GetParentIndex(Index);
    }
    return false;
}
bool AddBodies(AProphecyAgent& Agent,TConstArrayView<FName> Names,FName Attack,
    TArray<FProphecyDefensePhysicalContacts::FBody>& Out,FString& Error)
{
    auto* Mesh=Agent.GetPoseReferenceMesh();auto* Asset=Mesh?Mesh->GetPhysicsAsset():nullptr;
    if (!Asset || !Mesh->GetSkeletalMeshAsset()) { Error=TEXT("Kinematic contact stop requires the agent's PHAT asset.");return false; }
    for (const auto& Setup:Asset->SkeletalBodySetups)
    {
        if (!Setup || (!Attack.IsNone() && !AttackBody(Setup->BoneName,Attack))) continue;
        FProphecyDefensePhysicalContacts::FBody B;B.Name=Setup->BoneName;
        if (!AttachBone(*Mesh,B.Name,Names,B.Bone,B.Local))
        { Error=FString::Printf(TEXT("Cannot attach PHAT body %s to the NN pose."),*B.Name.ToString());return false; }
        B.Shape=MakeShared<FProphecyJoltContactShape>();
        if (!B.Shape->Build(*Setup,Mesh->GetSocketTransform(B.Name).GetScale3D(),Error))
        { if (Error==TEXT("No authored simulation collision shapes.")) { Error.Reset();continue; } return false; }
        Out.Add(MoveTemp(B));
    }
    if (Attack.IsNone() || Attack==TEXT("blade")) if (AActor* Sword=Agent.GetHeldSword())
    {
        auto* Blade=Cast<UStaticMeshComponent>(Sword->GetRootComponent());
        if (!Blade || !Blade->GetBodySetup()) { Error=TEXT("Held sword has no collision body setup.");return false; }
        FProphecyDefensePhysicalContacts::FBody B;B.Name=TEXT("blade");B.bBlade=true;B.Sword=Sword;B.SwordOwner=&Agent;
        FName Bone=Agent.SwordHandSocket;B.Local=Agent.SwordGripTransform;
        if (const auto* Socket=Mesh->GetSocketByName(Bone)) { Bone=Socket->BoneName;B.Local=B.Local*Socket->GetSocketLocalTransform(); }
        if (!AttachBone(*Mesh,Bone,Names,B.Bone,B.Local)) { Error=TEXT("Cannot attach held sword to the NN pose.");return false; }
        B.Shape=MakeShared<FProphecyJoltContactShape>();
        if (!B.Shape->Build(*Blade->GetBodySetup(),Blade->GetComponentScale(),Error)) return false;
        B.Local.SetScale3D(FVector::OneVector);Out.Add(MoveTemp(B));
    }
    if (Out.IsEmpty()) { Error=TEXT("No authored contact shapes for this attack/defender.");return false; }
    return true;
}
}
bool FProphecyDefensePhysicalContacts::Build(AProphecyAgent& Owner,AProphecyAgent& Source,FName AttackBone,
    TConstArrayView<FName> Names,FString& Error)
{
    Defender.Reset();Attacker.Reset();
    return AddBodies(Owner,Names,NAME_None,Defender,Error) && AddBodies(Source,Names,AttackBone,Attacker,Error);
}
void FProphecyDefensePhysicalContacts::Sweep(const FTransform* D0,const FTransform* D1,const FTransform* A0,const FTransform* A1,
    ProphecyDefense::FFirstContact& Order,int32 Step) const
{
    for (int32 I=0;I<Defender.Num();++I)
    {
        const auto& D=Defender[I];if (D.bBlade && (!D.Sword.IsValid() || !D.SwordOwner.IsValid() || D.SwordOwner->GetHeldSword()!=D.Sword.Get()
            || !ProphecySwordAttackCollision::IsAllowed(D.SwordOwner.Get()))) continue;
        const FTransform From=D.Local*D0[D.Bone],To=D.Local*D1[D.Bone];
        for (const auto& A:Attacker)
        {
            if (A.bBlade && (!A.Sword.IsValid() || !A.SwordOwner.IsValid() || A.SwordOwner->GetHeldSword()!=A.Sword.Get()
                || !ProphecySwordAttackCollision::IsAllowed(A.SwordOwner.Get()))) continue;
            float Fraction;
            if (D.Shape->Sweep(From,To,*A.Shape,A.Local*A0[A.Bone],A.Local*A1[A.Bone],Fraction))
            {
                ProphecyDefense::FContactPair Pair;Pair.Fraction=Fraction;Pair.bPossible=Pair.bConfirmed=true;
                Order.Include(Pair,I,Step,Step+1);
            }
        }
    }
}
