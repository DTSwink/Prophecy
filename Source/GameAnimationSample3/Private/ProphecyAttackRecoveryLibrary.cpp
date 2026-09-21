#include "ProphecyAttackRecoveryLibrary.h"
#include "ProphecyAttackRecovery.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"
#include "ProphecyBlendClock.h"

namespace ProphecyAttackRecovery
{
struct FPart
{
    EProphecyRecoverySource Source=EProphecyRecoverySource::Run;
    float Duration=1.f,Hold=0.f;
    bool Enabled() const { return Source!=EProphecyRecoverySource::Normal && Duration>0; }
    double End() const { return Enabled() ? double(Duration)+Hold : 0.; }
    float Sample(double Elapsed,float Normal) const
    {
        if (!Enabled() || Elapsed+1.e-6>=End()) return Normal;
        const float T=FMath::Clamp(float((Elapsed-Hold)/Duration),0.f,1.f);
        return FMath::Lerp(Source==EProphecyRecoverySource::Walk ? 1.f : 0.f,Normal,T*T*(3-2*T));
    }
};
struct FSettings
{
    FPart Pelvis,Left,Right;
    double End() const { return FMath::Max3(Pelvis.End(),Left.End(),Right.End()); }
};
struct FRecovery
{
    FSettings Settings;
    double Elapsed=0;
    bool First=true;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FSettings> Settings;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FRecovery> Active;
static FDelegateHandle Cleanup;
// Stack-scoped only while invoking the Blueprint event; no idle entry/tick.
static const AProphecyAgent* EndEventAgent=nullptr;
static void EnsureCleanup()
{
    if (Cleanup.IsValid()) return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for (auto It=Settings.CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
        for (auto It=Active.CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
    });
}
void Cancel(const AProphecyAgent* Agent)
{
    if (EndEventAgent==Agent) EndEventAgent=nullptr; // New attack/reset inside the event wins.
    if (!Active.IsEmpty()) Active.Remove(Agent);
    ProphecyBlendClock::Stop(Agent,ProphecyBlendClock::EKind::Recovery);
}
void Begin(const AProphecyAgent* Agent)
{
    if (!IsValid(Agent)) return;
    Cancel(Agent);
    const auto* Config=Settings.Find(Agent);
    const FSettings Value=Config ? *Config : FSettings{};
    if (Value.End()<=0) return;
    EnsureCleanup();Active.Add(Agent,FRecovery{Value});
}
void Remove(const AProphecyAgent* Agent) { Cancel(Agent);Settings.Remove(Agent); }
void NotifyEnded(AProphecyAgent* Agent,FName Attack,bool Half,bool ReturningToLocomotion)
{
    TGuardValue<const AProphecyAgent*> Scope(EndEventAgent,ReturningToLocomotion ? Agent : nullptr);
    Agent->OnNNAttackEnded(Attack,Half);
}
void Step(const AProphecyAgent* Agent,float Normal,FWeights& Out)
{
    Out=FWeights(Normal);
    auto* R=Active.IsEmpty() ? nullptr : Active.Find(Agent);
    if (!R) return;
    if (R->First)
    {
        R->First=false;
        ProphecyBlendClock::Start(Agent,ProphecyBlendClock::EKind::Recovery,R->Settings.End());
    }
    else R->Elapsed+=ProphecyBlendClock::Consume(Agent,ProphecyBlendClock::EKind::Recovery);
    Out.Pelvis=R->Settings.Pelvis.Sample(R->Elapsed,Normal);
    Out.Left=R->Settings.Left.Sample(R->Elapsed,Normal);
    Out.Right=R->Settings.Right.Sample(R->Elapsed,Normal);
    if (R->Elapsed+1.e-6>=R->Settings.End()) Cancel(Agent);
}
}

bool UProphecyAttackRecoveryLibrary::SetAttackToLocomotionBlend(AProphecyAgent* Agent,
    EProphecyRecoverySource PelvisSource,float HoldDurationSeconds,float DurationSeconds,
    EProphecyRecoverySource LeftLegSource,float LeftLegHoldDurationSeconds,float LeftLegDurationSeconds,
    EProphecyRecoverySource RightLegSource,float RightLegHoldDurationSeconds,float RightLegDurationSeconds)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown) return false;
    for (float V : {DurationSeconds,HoldDurationSeconds,LeftLegDurationSeconds,LeftLegHoldDurationSeconds,
        RightLegDurationSeconds,RightLegHoldDurationSeconds}) if (!FMath::IsFinite(V) || V<0) return false;
    for (auto S : {PelvisSource,LeftLegSource,RightLegSource})
        if (uint8(S)>uint8(EProphecyRecoverySource::Run)) return false;
    using namespace ProphecyAttackRecovery;
    const FSettings Value{{PelvisSource,DurationSeconds,HoldDurationSeconds},
        {LeftLegSource,LeftLegDurationSeconds,LeftLegHoldDurationSeconds},
        {RightLegSource,RightLegDurationSeconds,RightLegHoldDurationSeconds}};
    EnsureCleanup();Settings.Add(Agent,Value);
    if (EndEventAgent==Agent && !Active.Contains(Agent) && Value.End()>0) Begin(Agent);
    // Disabling applies immediately; positive edits configure the next handoff.
    if (auto* R=Active.Find(Agent))
    {
        // On Attack Ended runs after Begin but before the first locomotion step.
        // Let that event choose this handoff's regions without resetting a running blend.
        if (R->First) R->Settings=Value;
        if (!Value.Pelvis.Enabled()) R->Settings.Pelvis=Value.Pelvis;
        if (!Value.Left.Enabled()) R->Settings.Left=Value.Left;
        if (!Value.Right.Enabled()) R->Settings.Right=Value.Right;
        if (R->Settings.End()<=0) Cancel(Agent);
    }
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAttackRecoveryTest,"Prophecy.NN.PolicyBlend.AttackRecovery",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyAttackRecoveryTest::RunTest(const FString&)
{
    using namespace ProphecyAttackRecovery;
    using E=EProphecyRecoverySource;
    const FPart Run{E::Run,1,.5f},Walk{E::Walk,2,0},Off{E::Run,0,10};
    TestEqual(TEXT("Run source held"),Run.Sample(.5,1),0.f);
    TestEqual(TEXT("Run halfway toward normal walk"),Run.Sample(1,1),.5f);
    TestEqual(TEXT("Run normal remains run at endpoint"),Run.Sample(1.5,0),0.f);
    TestEqual(TEXT("Walk halfway toward normal run"),Walk.Sample(1,0),.5f);
    TestEqual(TEXT("Disabled ignores hold and uses normal blend"),Off.Sample(0,.3f),.3f);
    TestEqual(TEXT("Right foot physical profile uses right policy"),ProphecyBodyPolicyWalkWeight(TEXT("foot_r"),0,FVector2f(0,1)),1.f);
    TestEqual(TEXT("Left calf physical profile uses left policy"),ProphecyBodyPolicyWalkWeight(TEXT("calf_l"),1,FVector2f(0,1)),0.f);
    TestEqual(TEXT("Upper profile follows pelvis"),ProphecyBodyPolicyWalkWeight(TEXT("hand_r"),.25f,FVector2f(0,1)),.25f);
    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* Agent=World ? World->SpawnActor<AProphecyAgent>() : nullptr;
    if (!Agent) return false;
    UProphecyAttackRecoveryLibrary::SetAttackToLocomotionBlend(Agent,E::Run,.5f,1,E::Run,0,.5f,E::Walk,0,2);
    Begin(Agent);FWeights W;Step(Agent,0,W);
    TestTrue(TEXT("kickR starts right walk and left/pelvis run"),W.Right==1 && W.Left==0 && W.Pelvis==0 && W.NeedsBoth());
    for (int I=0;I<60;++I) { FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/120);Step(Agent,0,W); }
    TestTrue(TEXT("Independent durations at 60 ticks"),W.Left==0 && W.Pelvis==0 && FMath::IsNearlyEqual(W.Right,.5f));
    Step(Agent,1,W);
    TestTrue(TEXT("Finished left follows changed normal immediately"),W.Left==1 && FMath::IsNearlyEqual(W.Pelvis,.5f) && W.Right==1);
    for (int I=0;I<60;++I) { FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/30);Step(Agent,1,W); }
    TestTrue(TEXT("Recovery fully retires"),!Active.Contains(Agent) && !W.NeedsRun());
    Begin(Agent);
    UProphecyAttackRecoveryLibrary::SetAttackToLocomotionBlend(Agent,E::Walk,0,1,E::Walk,0,1,E::Run,0,1);
    Step(Agent,1,W);
    TestTrue(TEXT("End event selects current handoff before its first prediction"),W.Pelvis==1 && W.Left==1 && W.Right==0);
    UProphecyAttackRecoveryLibrary::SetAttackToLocomotionBlend(Agent,E::Run,0,0,E::Run,0,0,E::Run,0,0);
    Begin(Agent);TestFalse(TEXT("All-zero creates no recovery"),Active.Contains(Agent));
    Remove(Agent);World->DestroyWorld(false);return !HasAnyErrors();
}
#endif
