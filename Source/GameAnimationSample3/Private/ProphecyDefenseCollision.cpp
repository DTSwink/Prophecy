#include "ProphecyDefenseCollision.h"
#include "ProphecySwordAttackCollision.h"
#include "ProphecyAgent.h"
#include "ProphecyAttackControls.h"
#include "ProphecyJoltCharacterComponent.h"
#include "ProphecyJoltBodyComponent.h"
#include "ProphecyJoltWorldSubsystem.h"
#include "Components/SkeletalMeshComponent.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "Engine/World.h"
#include "UObject/UnrealType.h"
#include "HAL/IConsoleManager.h"

namespace ProphecyDefenseCollision
{
struct FBinding
{
    TWeakObjectPtr<AProphecyAgent> Defender,Attacker;
    TWeakObjectPtr<UProphecyJoltWorldSubsystem> World;
    TArray<FName> AttackBones,DefenseBones;
    FProphecyJoltBodyHandle DefenderRig,AttackerRig,AttackSword,DefenseSword;
    bool Dodge=false,Sword=false,Applied=false;
};
static TMap<const AProphecyAgent*,FBinding> Bindings;
static TMap<const AProphecyAgent*,TSet<const AProphecyAgent*>> Dependents;
bool BlocksSlashSwordNoReaction(const AProphecyAgent* Attacker)
{
    if(!Attacker)return false;
    if(const auto* Victim=Attacker->GetNNAttackVictim())return Bindings.Contains(Victim);
    for(const auto& Entry:Bindings)if(Entry.Value.Attacker.Get()==Attacker)return true;
    return false;
}
#if !UE_BUILD_SHIPPING
static TAutoConsoleVariable<int32> Audit(TEXT("Prophecy.DefenseContacts.Audit"),0,TEXT("Log event-only pair-specific defense rules."));
#endif
static bool Same(const FProphecyJoltBodyHandle& A,const FProphecyJoltBodyHandle& B)
{return A.WorldLifetime==B.WorldLifetime && A.Slot==B.Slot && A.Generation==B.Generation;}
static FProphecyJoltBodyHandle SwordBody(AProphecyAgent* A)
{
    FProphecyJoltBodyHandle H;
    if(auto* Sword=A->GetHeldSword())if(auto* Body=Sword->FindComponentByClass<UProphecyJoltBodyComponent>())Body->GetBodyHandle(H);
    return H;
}
static void Apply(FBinding& B)
{
    auto* D=B.Defender.Get();auto* A=B.Attacker.Get();if(!D || !A)return;
    auto* DC=D->GetJoltCharacterComponent();auto* AC=A->GetJoltCharacterComponent();
    FProphecyJoltBodyHandle DR,AR,AS,DS;
    if(DC)DC->GetRigIdentityBody(DR);if(AC)AC->GetRigIdentityBody(AR);
    if(B.Sword)AS=SwordBody(A);if(B.Dodge)DS=SwordBody(D);
    if(B.Applied && Same(DR,B.DefenderRig) && Same(AR,B.AttackerRig) && Same(AS,B.AttackSword) && Same(DS,B.DefenseSword))return;
    auto* World=D->GetWorld()->GetSubsystem<UProphecyJoltWorldSubsystem>();if(!World)return;
    TArray<FProphecyJoltBodyHandle,TInlineAllocator<32>> DH,AH;
    FProphecyJoltBodyHandle H;
    if(DR.IsSet())for(FName Bone:B.DefenseBones)if(DC->GetBodyHandle(Bone,H))DH.Add(H);
    if(AR.IsSet())for(FName Bone:B.AttackBones)if(AC->GetBodyHandle(Bone,H))AH.Add(H);
    if(AS.IsSet())AH.Add(AS);if(DS.IsSet())DH.Add(DS);
    TArray<FProphecyJoltBodyPair,TInlineAllocator<96>> Pairs;
    for(const auto& Defender:DH)for(const auto& Attacker:AH)Pairs.Add({Defender,Attacker});
    const TConstArrayView<FProphecyJoltBodyPair> View(Pairs);
    const auto Result=World->UpdateScopedContactRules(D,B.Dodge?View:TConstArrayView<FProphecyJoltBodyPair>(),B.Dodge?TConstArrayView<FProphecyJoltBodyPair>():View);
    if(!Result.IsSuccess())return; // Admission can be pending; retry on the existing rig update.
#if !UE_BUILD_SHIPPING
    if(Audit.GetValueOnGameThread())
    {
        FString Bones;for(FName N:B.DefenseBones)Bones+=N.ToString()+TEXT(",");
        UE_LOG(LogTemp,Display,TEXT("DefenseContacts defender=%s attacker=%s dodge=%d pairs=%d defenderBodies=%d attackBodies=%d bones=%s"),*D->GetName(),*A->GetName(),B.Dodge,Pairs.Num(),DH.Num(),AH.Num(),*Bones);
    }
#endif
    B.World=World;B.DefenderRig=DR;B.AttackerRig=AR;B.AttackSword=AS;B.DefenseSword=DS;B.Applied=true;
}
void Stop(const AProphecyAgent* D)
{
    auto* B=Bindings.Find(D);if(!B)return;
    if(auto* W=B->World.Get())W->UpdateScopedContactRules(D,{},{});
    const AProphecyAgent* Sources[]={D,B->Attacker.Get()};
    for(const AProphecyAgent* Agent:Sources)if(auto* Set=Dependents.Find(Agent))
    {Set->Remove(D);if(Set->IsEmpty())Dependents.Remove(Agent);}
    Bindings.Remove(D);
    ProphecySwordNoReaction::DefenseChanged();
}
void Start(AProphecyAgent* D,AProphecyAgent* A,FName Family,bool Dodge)
{
    Stop(D);if(!IsValid(D) || !IsValid(A) || D==A)return;
    FBinding B;B.Defender=D;B.Attacker=A;B.Dodge=Dodge;
    ProphecyAttackControls::ColliderRoles(Family,B.AttackBones,B.Sword);
    if(Dodge)
    {
        auto* Mesh=D->GetPoseReferenceMesh();auto* Asset=Mesh?Mesh->GetPhysicsAsset():nullptr;
        if(Asset)for(const USkeletalBodySetup* Body:Asset->SkeletalBodySetups)if(Body)B.DefenseBones.AddUnique(Body->BoneName);
    }
    else
    {
        // Capture the user's actual Blueprint list once at defense entry.
        auto* Property=FindFProperty<FArrayProperty>(D->GetClass(),TEXT("trunk"));
        if(Property && CastField<FNameProperty>(Property->Inner))
        {
            FScriptArrayHelper Array(Property,Property->ContainerPtrToValuePtr<void>(D));
            for(int32 I=0;I<Array.Num();++I)B.DefenseBones.AddUnique(*reinterpret_cast<const FName*>(Array.GetRawPtr(I)));
        }
        else for(const TCHAR* Bone:{TEXT("pelvis"),TEXT("spine_01"),TEXT("spine_02"),TEXT("spine_03"),TEXT("spine_04"),TEXT("spine_05"),TEXT("clavicle_l"),TEXT("clavicle_r"),TEXT("neck_01"),TEXT("neck_02"),TEXT("head")})B.DefenseBones.Add(FName(Bone));
        for(const TCHAR* Bone:{TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")})B.DefenseBones.AddUnique(FName(Bone));
    }
    Dependents.FindOrAdd(D).Add(D);Dependents.FindOrAdd(A).Add(D);
    Apply(B);Bindings.Add(D,MoveTemp(B));
    ProphecySwordNoReaction::DefenseChanged();
}
void Remove(const AProphecyAgent* Agent)
{
    if(const auto* Set=Dependents.Find(Agent))
    {const auto Owners=Set->Array();for(const auto* D:Owners)Stop(D);}
    // EndPlay/GC may already invalidate the weak attacker pointer used by Stop.
    // Remove its raw dependency key explicitly so idle updates remain a no-op.
    Dependents.Remove(Agent);
    Stop(Agent);
}
void Refresh(AProphecyAgent* Agent)
{
    if(Dependents.IsEmpty())return;
    if(const auto* Set=Dependents.Find(Agent))for(const auto* D:*Set)if(auto* B=Bindings.Find(D))Apply(*B);
}
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDefenseContactLifetimeTest,"Prophecy.NN.Defense.ContactLifetime",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDefenseContactLifetimeTest::RunTest(const FString&)
{
    using namespace ProphecyDefenseCollision;
    const int32 InitialBindings=Bindings.Num(),InitialDependencies=Dependents.Num();
    auto* W=UWorld::CreateWorld(EWorldType::Game,false);if(!W)return false;
    auto* A=W->SpawnActor<AProphecyAgent>();auto* B=W->SpawnActor<AProphecyAgent>();
    auto* C=W->SpawnActor<AProphecyAgent>();auto* D=W->SpawnActor<AProphecyAgent>();
    if(!A || !B || !C || !D){W->DestroyWorld(false);return false;}
    Start(B,A,TEXT("slashL"),false);Start(D,C,TEXT("jabR"),true);
    TestEqual(TEXT("Two independent defenses"),Bindings.Num(),InitialBindings+2);
    TestTrue(TEXT("Both arms protected"),Bindings.FindChecked(B).DefenseBones.Contains(TEXT("hand_l")) && Bindings.FindChecked(B).DefenseBones.Contains(TEXT("upperarm_r")));
    TestTrue(TEXT("Slash hand and sword attack roles"),Bindings.FindChecked(B).Sword && Bindings.FindChecked(B).AttackBones.Contains(TEXT("hand_r")));
    // Model cleanup after the weak attacker becomes invalid, without using a
    // dangling UObject or changing the live world's actors.
    Bindings.FindChecked(B).Attacker.Reset();
    Remove(A);
    TestFalse(TEXT("Invalid attacker dependency removed"),Dependents.Contains(A));
    TestFalse(TEXT("Dependent defense removed"),Bindings.Contains(B));
    TestTrue(TEXT("Unrelated defense retained"),Bindings.Contains(D));
    Remove(C);Remove(A);Remove(B);Remove(D);
    TestEqual(TEXT("All bindings released"),Bindings.Num(),InitialBindings);
    TestEqual(TEXT("No idle dependency residue"),Dependents.Num(),InitialDependencies);
    W->DestroyWorld(false);W->MarkAsGarbage();return !HasAnyErrors();
}
#endif
