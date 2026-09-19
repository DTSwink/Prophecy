#include "ProphecyAttackControlLibrary.h"
#include "ProphecyAttackControls.h"
#include "ProphecyAgent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "PhysicsEngine/PhysicsAsset.h"

namespace ProphecyAttackControls
{
static TSet<TWeakObjectPtr<const AProphecyAgent>> StaticAgents;
static FDelegateHandle Cleanup;
static TSet<TWeakObjectPtr<const AProphecyAgent>> PelvisReturnAgents;
static FDelegateHandle ReturnCleanup;
bool IsStatic(const AProphecyAgent* Agent)
{ return !StaticAgents.IsEmpty() && StaticAgents.Contains(Agent); }
bool UsesRootBalancingTarget(const AProphecyAgent* Agent)
{ return PelvisReturnAgents.IsEmpty() || !PelvisReturnAgents.Contains(Agent); }

bool ColliderRoles(FName Attack, TArray<FName>& Bones, bool& Sword)
{
    Bones.Reset(); Sword = false;
    if (Attack == TEXT("headbutt")) { Bones.Add(TEXT("head")); return true; }
    if (Attack == TEXT("jabl") || Attack == TEXT("hookl") || Attack == TEXT("overl"))
    { Bones = {TEXT("hand_l"), TEXT("lowerarm_l")}; return true; }
    if (Attack == TEXT("jabr") || Attack == TEXT("hookr") || Attack == TEXT("overr"))
    { Bones = {TEXT("hand_r"), TEXT("lowerarm_r")}; return true; }
    if (Attack == TEXT("kickl")) { Bones = {TEXT("calf_l"), TEXT("foot_l"), TEXT("ball_l")}; return true; }
    if (Attack == TEXT("kickr")) { Bones = {TEXT("calf_r"), TEXT("foot_r"), TEXT("ball_r")}; return true; }
    Sword = Attack == TEXT("pike") || Attack == TEXT("slashl") || Attack == TEXT("slashr")
        || Attack == TEXT("slashld") || Attack == TEXT("slashrd") || Attack == TEXT("slashlu") || Attack == TEXT("slashru");
    return Sword;
}
}

bool UProphecyAttackControlLibrary::SetAttackReturnToRootBalancing(AProphecyAgent* Agent,bool UseRootBalancingTarget)
{
    using namespace ProphecyAttackControls;
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown) return false;
    if (UseRootBalancingTarget) { PelvisReturnAgents.Remove(Agent);return true; }
    if (!ReturnCleanup.IsValid()) ReturnCleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for (auto It=PelvisReturnAgents.CreateIterator();It;++It)
            if (!It->IsValid() || It->Get()->GetWorld()==World) It.RemoveCurrent();
    });
    for (auto It=PelvisReturnAgents.CreateIterator();It;++It) if (!It->IsValid()) It.RemoveCurrent();
    PelvisReturnAgents.Add(Agent);
    return true;
}

bool UProphecyAttackControlLibrary::GetNNAttackColliders(AProphecyAgent* Agent, FName& Attack,
    TArray<FName>& BoneNames, UStaticMeshComponent*& SwordCollider)
{
    Attack = NAME_None; BoneNames.Reset(); SwordCollider = nullptr;
    bool Half = false, Armed = false, Hit = false; int32 Frame = 0;
    if (!IsValid(Agent) || !Agent->GetNNAttackState(Attack, Half, Armed, Hit, Frame))
    { Attack = NAME_None; return false; }
    bool Sword = false;
    if (!ProphecyAttackControls::ColliderRoles(Attack, BoneNames, Sword)) return true;
    if (Sword)
    {
        if (AActor* Held = Agent->GetHeldSword()) SwordCollider = Cast<UStaticMeshComponent>(Held->GetRootComponent());
    }
    else
    {
        const auto* Mesh = Agent->GetPoseReferenceMesh();
        const auto* Asset = Mesh ? Mesh->GetPhysicsAsset() : nullptr;
        // ball_* is returned only when it is a separate PHAT body, just like contact detection.
        BoneNames.RemoveAll([Asset](FName Bone) { return !Asset || Asset->FindBodyIndex(Bone) == INDEX_NONE; });
    }
    return true;
}

bool UProphecyAttackControlLibrary::SetAttackInitializationMode(AProphecyAgent* Agent, EProphecyAttackInitializationMode Mode)
{
    using namespace ProphecyAttackControls;
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown
        || (Mode != EProphecyAttackInitializationMode::Dynamic && Mode != EProphecyAttackInitializationMode::Static)) return false;
    if (Mode == EProphecyAttackInitializationMode::Dynamic) { StaticAgents.Remove(Agent); return true; }
    if (!Cleanup.IsValid()) Cleanup = FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World, bool, bool)
    {
        for (auto It = StaticAgents.CreateIterator(); It; ++It)
            if (!It->IsValid() || It->Get()->GetWorld() == World) It.RemoveCurrent();
    });
    for (auto It = StaticAgents.CreateIterator(); It; ++It) if (!It->IsValid()) It.RemoveCurrent();
    StaticAgents.Add(Agent); return true;
}

EProphecyAttackInitializationMode UProphecyAttackControlLibrary::GetAttackInitializationMode(AProphecyAgent* Agent)
{
    return IsValid(Agent) && ProphecyAttackControls::IsStatic(Agent)
        ? EProphecyAttackInitializationMode::Static : EProphecyAttackInitializationMode::Dynamic;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAttackControlsTest, "Prophecy.Attack.Controls.HistoryAndColliders",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyAttackControlsTest::RunTest(const FString&)
{
    TArray<float> State; for (int32 I = 0; I < 272; ++I) State.Add(float(I));
    const auto Before = State;
    ProphecyAttackControls::MakeHistoryStatic(State);
    for (int32 I = 0; I < 41; ++I) TestEqual(TEXT("Lower previous equals current"), State[I], Before[I + 41]);
    for (int32 I = 0; I < 90; ++I) TestEqual(TEXT("Upper previous equals current"), State[82 + I], Before[172 + I]);
    for (int32 I = 41; I < 82; ++I) TestEqual(TEXT("Lower current preserved"), State[I], Before[I]);
    for (int32 I = 172; I < 272; ++I) TestEqual(TEXT("Current upper, target, labels and latches preserved"), State[I], Before[I]);
    TArray<FName> Bones; bool Sword = false;
    for (FName Attack : {FName(TEXT("jabl")), FName(TEXT("hookl")), FName(TEXT("overl"))})
    {
        TestTrue(TEXT("Left punch known"), ProphecyAttackControls::ColliderRoles(Attack, Bones, Sword));
        TestTrue(TEXT("Left punch bodies"), !Sword && Bones == TArray<FName>{TEXT("hand_l"), TEXT("lowerarm_l")});
    }
    for (FName Attack : {FName(TEXT("jabr")), FName(TEXT("hookr")), FName(TEXT("overr"))})
    {
        ProphecyAttackControls::ColliderRoles(Attack, Bones, Sword);
        TestTrue(TEXT("Right punch bodies"), !Sword && Bones == TArray<FName>{TEXT("hand_r"), TEXT("lowerarm_r")});
    }
    for (FName Attack : {FName(TEXT("pike")), FName(TEXT("slashl")), FName(TEXT("slashr")), FName(TEXT("slashld")), FName(TEXT("slashrd")), FName(TEXT("slashlu")), FName(TEXT("slashru"))})
    {
        ProphecyAttackControls::ColliderRoles(Attack, Bones, Sword);
        TestTrue(TEXT("Sword attacks exclude arm bodies"), Sword && Bones.IsEmpty());
    }
    ProphecyAttackControls::ColliderRoles(TEXT("kickl"), Bones, Sword);
    TestTrue(TEXT("Left kick bodies"), Bones == TArray<FName>{TEXT("calf_l"), TEXT("foot_l"), TEXT("ball_l")});
    ProphecyAttackControls::ColliderRoles(TEXT("kickr"), Bones, Sword);
    TestTrue(TEXT("Right kick bodies"), Bones == TArray<FName>{TEXT("calf_r"), TEXT("foot_r"), TEXT("ball_r")});
    ProphecyAttackControls::ColliderRoles(TEXT("headbutt"), Bones, Sword);
    TestTrue(TEXT("Headbutt body"), Bones == TArray<FName>{TEXT("head")});
    TestFalse(TEXT("No null override"), ProphecyAttackControls::IsStatic(nullptr));
    return true;
}
#endif
