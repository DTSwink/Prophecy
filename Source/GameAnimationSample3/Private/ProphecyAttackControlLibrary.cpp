#include "ProphecyAttackControlLibrary.h"
#include "ProphecyAttackControls.h"
#include "ProphecyAgent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/World.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "ProphecyRootBalance.h"
#include "ProphecyAttackTargetReach.inl"
#include <cmath>

namespace ProphecyAttackTargetReach
{
static TMap<TWeakObjectPtr<const AProphecyAgent>,float> ExtraReach;
// Preserve the existing scalar storage's live layout; nonuniform profiles use
// separate storage. Entry order follows the baked GT table, not the node layout.
struct FFamilyExtraReach { float Values[UE_ARRAY_COUNT(Entries)]; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FFamilyExtraReach> FamilyExtraReach;
static FDelegateHandle Cleanup;
static double Radius(FName Attack,double Extra)
{
    for (const auto& Entry:Entries) if (Entry.Attack==Attack) return Entry.RadiusCm+Extra;
    return 0.; // No fabricated reach for unknown attack families.
}
static FVector Clamp(const FVector& Center,const FVector& Wanted,double RadiusCm,double* DistanceToLimit=nullptr)
{
    const FVector Delta=Wanted-Center;
    const double Distance=std::hypot(Delta.X,Delta.Y);
    if (DistanceToLimit) *DistanceToLimit=FMath::Max(0.,RadiusCm-Distance);
    if (Distance<=RadiusCm) return Wanted;
    const double Scale=RadiusCm/Distance;
    return FVector(Center.X+Delta.X*Scale,Center.Y+Delta.Y*Scale,Wanted.Z);
}
}

void UProphecyAttackControlLibrary::GetValidAttackTarget(AProphecyAgent* Agent,FName Attack,FVector Target,
    FVector& EffectiveTarget,FVector& Difference,FVector& WantedTarget,double& DistanceToLimit)
{
    WantedTarget=EffectiveTarget=Target;Difference=FVector::ZeroVector;DistanceToLimit=0.;
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || Target.ContainsNaN()) return;
    FVector Center;
    if (!ProphecyRootBalance::GetFlatFeetTarget(Agent,Center)) Center=Agent->GetRootLowPoint();
    if (Center.ContainsNaN()) return;
    using namespace ProphecyAttackTargetReach;
    const float* Extra=ExtraReach.IsEmpty()?nullptr:ExtraReach.Find(Agent);
    const auto* Family=FamilyExtraReach.IsEmpty()?nullptr:FamilyExtraReach.Find(Agent);
    double Reach=0.;
    for (int32 I=0;I<UE_ARRAY_COUNT(Entries);++I) if (Entries[I].Attack==Attack)
    { Reach=Entries[I].RadiusCm+(Family?Family->Values[I]:(Extra?*Extra:50.f));break; }
    EffectiveTarget=Clamp(Center,Target,Reach,&DistanceToLimit);
    Difference=EffectiveTarget-WantedTarget;
}

bool UProphecyAttackControlLibrary::SetAttackTargetExtraReach(AProphecyAgent* Agent,float ExtraReachCm,
    float SlashR,float SlashLD,float SlashRD,float SlashLU,float SlashRU,float Pike,
    float JabL,float JabR,float HookL,float HookR,float OverL,float OverR,float Headbutt,float KickL,float KickR)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() ||
        !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown) return false;
    using namespace ProphecyAttackTargetReach;
    const FFamilyExtraReach Profile{{JabL,JabR,HookL,HookR,OverL,OverR,Headbutt,KickL,KickR,
        ExtraReachCm,SlashR,SlashLD,SlashRD,SlashLU,SlashRU,Pike}};
    bool Uniform=true;
    for (float Value:Profile.Values)
    { if (!FMath::IsFinite(Value) || Value<0.f) return false;Uniform&=Value==ExtraReachCm; }
    if (Uniform && ExtraReachCm==50.f) { ExtraReach.Remove(Agent);FamilyExtraReach.Remove(Agent);return true; }
    if (!Cleanup.IsValid()) Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for (auto It=ExtraReach.CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
        for (auto It=FamilyExtraReach.CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
    });
    for (auto It=ExtraReach.CreateIterator();It;++It) if (!It.Key().IsValid()) It.RemoveCurrent();
    for (auto It=FamilyExtraReach.CreateIterator();It;++It) if (!It.Key().IsValid()) It.RemoveCurrent();
    if (Uniform) { ExtraReach.Add(Agent,ExtraReachCm);FamilyExtraReach.Remove(Agent); }
    else { ExtraReach.Remove(Agent);FamilyExtraReach.Add(Agent,Profile); }
    return true;
}

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
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAttackTargetReachTest,"Prophecy.Attack.TargetReach",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyAttackTargetReachTest::RunTest(const FString&)
{
    using namespace ProphecyAttackTargetReach;
    TestEqual(TEXT("All 16 runtime attacks have GT reach"),int32(UE_ARRAY_COUNT(Entries)),16);
    const FVector Center(123.,-456.,987.);
    for (const auto& Entry:Entries)
    {
        const double R=Radius(Entry.Attack,50.);
        TestTrue(TEXT("Positive GT distance with default margin"),R>50.);
        const FVector Wanted=Center+FVector(3.*R,4.*R,10000.);
        const FVector Effective=Clamp(Center,Wanted,R);
        TestTrue(TEXT("Horizontal projection lands on cylinder, independent of height"),FMath::IsNearlyEqual(FVector::Dist2D(Effective,Center),R,1.e-8));
        TestEqual(TEXT("Height remains exact"),Effective.Z,Wanted.Z);
        TestTrue(TEXT("Nearest radial point, not axiswise square clamp"),Effective.Equals(Center+FVector(.6*R,.8*R,10000.),1.e-8));
        const FVector Difference=Effective-Wanted;
        TestTrue(TEXT("Signed difference reconstructs effective target"),(Wanted+Difference).Equals(Effective,1.e-8));
        const FVector Inside=Center+FVector(.3*R,.4*R,-10000.);
        TestEqual(TEXT("Interior passes through unchanged"),Clamp(Center,Inside,R),Inside);
        double Margin=-1.;
        Clamp(Center,Inside,R,&Margin);
        TestTrue(TEXT("Interior margin is radial distance to boundary, ignoring height"),FMath::IsNearlyEqual(Margin,.5*R,1.e-8));
        Clamp(Center,Wanted,R,&Margin);
        TestEqual(TEXT("Outside margin is zero"),Margin,0.);
        Clamp(Center,Center+FVector(R,0,500),R,&Margin);
        TestTrue(TEXT("Boundary margin is zero"),FMath::IsNearlyZero(Margin,1.e-8));
        Clamp(Center,Center+FVector(0,0,500),R,&Margin);
        TestEqual(TEXT("Cylinder axis has full radius remaining"),Margin,R);
        TestEqual(TEXT("Zero planar distance preserves arbitrary height"),Clamp(Center,Center+FVector(0,0,20.),R),Center+FVector(0,0,20.));
        TestTrue(TEXT("Removing extra reach changes radius by 50cm"),FMath::IsNearlyEqual(R-Radius(Entry.Attack,0.),50.,1.e-8));
    }
    TestEqual(TEXT("Family names are case insensitive"),Radius(TEXT("KICKL"),0.),Radius(TEXT("kickL"),0.));
    TestEqual(TEXT("Unknown family cannot invent reach"),Radius(TEXT("bad_attack"),50.),0.);
    TestEqual(TEXT("Zero radius safely projects onto axis"),Clamp(Center,Center+FVector(10,20,30),0.),Center+FVector(0,0,30));
    FVector Effective,Difference,Wanted;
    double Margin=123.;
    UProphecyAttackControlLibrary::GetValidAttackTarget(nullptr,TEXT("jabL"),Center,Effective,Difference,Wanted,Margin);
    TestEqual(TEXT("Invalid agent clears distance to limit"),Margin,0.);
    TestEqual(TEXT("Invalid agent returns original target"),Effective,Center);
    TestEqual(TEXT("Wanted output always echoes input"),Wanted,Center);
    TestTrue(TEXT("Invalid agent difference is zero"),Difference.IsZero());
    return true;
}
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
