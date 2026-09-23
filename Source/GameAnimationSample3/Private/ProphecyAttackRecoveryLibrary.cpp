#include "ProphecyAttackRecoveryLibrary.h"
#include "ProphecyAttackRecovery.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"
#include "ProphecyBlendClock.h"
#include "ProphecyLowerTempering.h"
#include "ProphecyHandRecovery.h"
#include "ProphecyCoreTempering.h"
#include "ProphecySlashReturn.h"
#include "ProphecyUpperBodyInertia.h"
#include "ProphecySpecialRecoveryEvents.h"

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
static TMap<TWeakObjectPtr<const AProphecyAgent>,FSettings> KickSettings;
static TSet<TWeakObjectPtr<const AProphecyAgent>> KickActive;
static TSet<TWeakObjectPtr<const AProphecyAgent>> RightKickActive;
static bool EndEventKick=false,EndEventRightKick=false;
static FSettings ResolveKickRoles(FSettings Value,bool RightKick)
{
    if (RightKick) Swap(Value.Left,Value.Right);
    return Value;
}
static bool IsKick(FName Attack) { return Attack==TEXT("kickl") || Attack==TEXT("kickr"); }
static FDelegateHandle Cleanup;
// Stack-scoped only while invoking the Blueprint event; no idle entry/tick.
static const AProphecyAgent* EndEventAgent=nullptr;
static FName EndAttack;
static void EnsureCleanup()
{
    if (Cleanup.IsValid()) return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for (auto* Map:{&Settings,&KickSettings}) for (auto It=Map->CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
        for (auto* Set:{&KickActive,&RightKickActive}) for (auto It=Set->CreateIterator();It;++It)
            if (!It->IsValid() || It->Get()->GetWorld()==World) It.RemoveCurrent();
        for (auto It=Active.CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
    });
}
void Cancel(const AProphecyAgent* Agent)
{
    if (EndEventAgent==Agent) EndEventAgent=nullptr; // New attack/reset inside the event wins.
    if (!Active.IsEmpty()) Active.Remove(Agent);
    KickActive.Remove(Agent);RightKickActive.Remove(Agent);
    ProphecyBlendClock::Stop(Agent,ProphecyBlendClock::EKind::Recovery);
}
void Begin(const AProphecyAgent* Agent,FName Attack)
{
    if (!IsValid(Agent)) return;
    Cancel(Agent);
    const auto* Config=IsKick(Attack) ? KickSettings.Find(Agent) : nullptr;
    const bool HasKickProfile=Config!=nullptr;
    if (!Config) Config=Settings.Find(Agent);
    const FSettings Value=ResolveKickRoles(Config ? *Config : FSettings{},HasKickProfile && Attack==TEXT("kickr"));
    if (Value.End()<=0) return;
    EnsureCleanup();Active.Add(Agent,FRecovery{Value});
    if (IsKick(Attack)) KickActive.Add(Agent);
    if (Attack==TEXT("kickr")) RightKickActive.Add(Agent);
}
void Remove(const AProphecyAgent* Agent) { Cancel(Agent);Settings.Remove(Agent);KickSettings.Remove(Agent); }
void EnterSpecial(const AProphecyAgent* Agent)
{
    Cancel(Agent);ProphecyLowerTempering::Remove(Agent);
    ProphecyHandRecovery::CancelMotion(Agent);ProphecyCoreTempering::CancelMotion(Agent);
    ProphecySlashReturn::Cancel(Agent);ProphecyUpperBodyInertia::Cancel(Agent);
}
void NotifyEnded(AProphecyAgent* Agent,FName Attack,bool Half,bool ReturningToLocomotion,EProphecyAgentState Special)
{
    TGuardValue<const AProphecyAgent*> Scope(EndEventAgent,ReturningToLocomotion ? Agent : nullptr);
    TGuardValue<bool> KickScope(EndEventKick,IsKick(Attack));
    TGuardValue<bool> SideScope(EndEventRightKick,Attack==TEXT("kickr"));
    TGuardValue<FName> AttackScope(EndAttack,Attack);
    if (ReturningToLocomotion) ProphecyLowerTempering::SelectAttackProfile(Agent,Attack);
    if (ReturningToLocomotion) ProphecyHandRecovery::Begin(Agent);
    if (ReturningToLocomotion) ProphecyCoreTempering::Begin(Agent);
    if (ReturningToLocomotion) ProphecySlashReturn::Begin(Agent,Attack);
    if (Special==EProphecyAgentState::Attacking) Agent->OnNNAttackEnded(Attack,Half);
    // A handler may replace this return with another special/reset. Do not
    // dispatch a second recovery chain over the newly selected action.
    if (IsValid(Agent) && !Agent->IsActorBeingDestroyed() && (!ReturningToLocomotion || EndEventAgent==Agent)
        && Agent->GetClass()->ImplementsInterface(UProphecySpecialRecoveryEvents::StaticClass()))
        IProphecySpecialRecoveryEvents::Execute_OnNNSpecialEnded(Agent,Special,Attack,Half,ReturningToLocomotion);
}
bool IsEndEvent(const AProphecyAgent* Agent) { return EndEventAgent==Agent; }
FName EndEventAttack(const AProphecyAgent* Agent) { return IsEndEvent(Agent)?EndAttack:NAME_None; }
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

static bool SetRecoveryProfile(bool Kick,AProphecyAgent* Agent,
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
    FSettings Value{{PelvisSource,DurationSeconds,HoldDurationSeconds},
        {LeftLegSource,LeftLegDurationSeconds,LeftLegHoldDurationSeconds},
        {RightLegSource,RightLegDurationSeconds,RightLegHoldDurationSeconds}};
    EnsureCleanup();(Kick ? KickSettings : Settings).Add(Agent,Value);
    const bool KickHandoff=KickActive.Contains(Agent) || (EndEventAgent==Agent && EndEventKick);
    const bool UsesKick=KickHandoff && KickSettings.Contains(Agent);
    if (Kick!=UsesKick) return true; // Configuring the other profile cannot overwrite this handoff.
    const bool RightKick=RightKickActive.Contains(Agent) || (EndEventAgent==Agent && EndEventRightKick);
    if (Kick) Value=ResolveKickRoles(Value,RightKick);
    if (EndEventAgent==Agent && !Active.Contains(Agent) && Value.End()>0)
    {
        Active.Add(Agent,FRecovery{Value});
        if (KickHandoff) KickActive.Add(Agent);
        if (RightKick) RightKickActive.Add(Agent);
    }
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

bool UProphecyAttackRecoveryLibrary::SetAttackToLocomotionBlend(AProphecyAgent* Agent,
    EProphecyRecoverySource PelvisSource,float HoldDurationSeconds,float DurationSeconds,
    EProphecyRecoverySource LeftLegSource,float LeftLegHoldDurationSeconds,float LeftLegDurationSeconds,
    EProphecyRecoverySource RightLegSource,float RightLegHoldDurationSeconds,float RightLegDurationSeconds)
{
    return SetRecoveryProfile(false,Agent,PelvisSource,HoldDurationSeconds,DurationSeconds,
        LeftLegSource,LeftLegHoldDurationSeconds,LeftLegDurationSeconds,
        RightLegSource,RightLegHoldDurationSeconds,RightLegDurationSeconds);
}

bool UProphecyAttackRecoveryLibrary::SetKickToLocomotionBlend(AProphecyAgent* Agent,
    EProphecyRecoverySource PelvisSource,float HoldDurationSeconds,float DurationSeconds,
    EProphecyRecoverySource LeftLegSource,float LeftLegHoldDurationSeconds,float LeftLegDurationSeconds,
    EProphecyRecoverySource RightLegSource,float RightLegHoldDurationSeconds,float RightLegDurationSeconds)
{
    return SetRecoveryProfile(true,Agent,PelvisSource,HoldDurationSeconds,DurationSeconds,
        LeftLegSource,LeftLegHoldDurationSeconds,LeftLegDurationSeconds,
        RightLegSource,RightLegHoldDurationSeconds,RightLegDurationSeconds);
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "ProphecyLowerTemperingLibrary.h"
#include "ProphecyHandRecoveryLibrary.h"
#include "ProphecyCoreTemperingLibrary.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySpecialRecoveryTest,"Prophecy.NN.SpecialRecovery.AllExitsAndRetirement",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecySpecialRecoveryTest::RunTest(const FString&)
{
    using namespace ProphecyAttackRecovery;
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    UProphecyLowerTemperingLibrary::SetLocomotionLowerBodyTempering(A,true,.2,.3,.4,.5,.6,.7);
    UProphecyHandRecoveryLibrary::SetLocomotionHandTempering(A,true,.2,.3,.4,.5,.6,.7);
    UProphecyCoreTemperingLibrary::SetLocomotionFKCoreTempering(A,true,.3);
    UProphecyHandRecoveryLibrary::SetAttackToLocomotionHandBlend(A,EProphecyRecoverySource::Walk,0,.5,EProphecyRecoverySource::Run,0,.5);
    UProphecyAttackRecoveryLibrary::SetAttackToLocomotionBlend(A,EProphecyRecoverySource::Walk,0,.5,EProphecyRecoverySource::Run,0,.5,EProphecyRecoverySource::Walk,0,.5);
    for(auto Kind:{EProphecyAgentState::Attacking,EProphecyAgentState::Parrying,EProphecyAgentState::Dodging})
    {
        EnterSpecial(A);
        TestTrue(TEXT("Every special clears prior locomotion control motion"),!ProphecyLowerTempering::Find(A)
            && !ProphecyHandRecovery::Tempering(A) && !ProphecyHandRecovery::Frame(A) && ProphecyCoreTempering::Rotation(A)==1);
        Begin(A);NotifyEnded(A,NAME_None,false,true,Kind);
        const auto* L=ProphecyLowerTempering::Find(A);
        TestTrue(TEXT("All exits restore the regular lower profile without a kick override"),L && L->FeetTranslation==.2f && L->PelvisTranslation==.5f);
        TestTrue(TEXT("All exits restore hands and core"),ProphecyHandRecovery::Tempering(A) && ProphecyCoreTempering::Rotation(A)==.3f);
        UProphecyLowerTemperingLibrary::BlendLocomotionLowerBodyTemperingToNormal(A,.5,0,.5,0);
        UProphecyHandRecoveryLibrary::BlendLocomotionHandTemperingToNormal(A,0,.5,0,.5);
        UProphecyCoreTemperingLibrary::BlendLocomotionFKCoreTemperingToNormal(A,0,.5);
        FWeights Weights;Step(A,1,Weights);ProphecyHandRecovery::Step(A);
        for(int32 I=0;I<30;++I)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/120);
            Step(A,1,Weights);ProphecyHandRecovery::Step(A);ProphecyLowerTempering::Find(A);
            ProphecyHandRecovery::Tempering(A);ProphecyCoreTempering::Rotation(A);
        }
        TestTrue(TEXT("All exits retire all recovery motion after 30 ticks"),!Active.Contains(A) && !ProphecyLowerTempering::Find(A)
            && !ProphecyHandRecovery::Tempering(A) && !ProphecyHandRecovery::Frame(A) && ProphecyCoreTempering::Rotation(A)==1);
        EnterSpecial(A);NotifyEnded(A,NAME_None,false,false,Kind);
        TestTrue(TEXT("Special-to-special interruption does not reactivate locomotion recovery"),!ProphecyLowerTempering::Find(A) && !ProphecyHandRecovery::Frame(A));
    }
    Remove(A);ProphecyLowerTempering::ForgetProfiles(A);ProphecyHandRecovery::Remove(A);ProphecyCoreTempering::Remove(A);
    W->DestroyWorld(false);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAttackRecoveryTest,"Prophecy.NN.PolicyBlend.AttackRecovery",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyAttackRecoveryTest::RunTest(const FString&)
{
    using namespace ProphecyAttackRecovery;
    using E=EProphecyRecoverySource;
    const FSettings Roles{{E::Walk,.5f,.1f},{E::Walk,2,.25f},{E::Run,1,.5f}};
    const auto Mirrored=ResolveKickRoles(Roles,true);
    TestTrue(TEXT("Kicking role maps source, hold and duration together to right"),Mirrored.Right.Source==E::Walk && Mirrored.Right.Duration==2 && Mirrored.Right.Hold==.25f);
    TestTrue(TEXT("Non-kicking role maps source, hold and duration together to left"),Mirrored.Left.Source==E::Run && Mirrored.Left.Duration==1 && Mirrored.Left.Hold==.5f);
    TestTrue(TEXT("Mapping never swaps pelvis settings"),Mirrored.Pelvis.Source==Roles.Pelvis.Source && Mirrored.Pelvis.Duration==Roles.Pelvis.Duration && Mirrored.Pelvis.Hold==Roles.Pelvis.Hold);
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
    using L=UProphecyAttackRecoveryLibrary;
    L::SetAttackToLocomotionBlend(Agent,E::Walk,0,1,E::Walk,0,1,E::Walk,0,1);
    L::SetKickToLocomotionBlend(Agent,E::Run,0,1,E::Run,0,1,E::Walk,0,1);
    for (FName Family:{FName(TEXT("kickl")),FName(TEXT("kickr"))})
    {
        Begin(Agent,Family);
        L::SetAttackToLocomotionBlend(Agent,E::Walk,0,2,E::Walk,0,2,E::Walk,0,2);
        Step(Agent,1,W);
        TestTrue(TEXT("Both kicks select independent profile despite regular event setter"),W.Pelvis==0 && W.Left==(Family==TEXT("kickr") ? 1.f : 0.f) && W.Right==(Family==TEXT("kickr") ? 0.f : 1.f));
    }
    Begin(Agent,TEXT("overl"));Step(Agent,0,W);
    TestTrue(TEXT("Next non-kick restores regular regional settings"),W.Pelvis==1 && W.Left==1 && W.Right==1);
    L::SetKickToLocomotionBlend(Agent,E::Run,0,0,E::Run,0,0,E::Run,0,0);
    Begin(Agent,TEXT("kickr"));TestFalse(TEXT("Disabled kick creates no clock/active recovery"),Active.Contains(Agent));
    { TGuardValue<const AProphecyAgent*> Event(EndEventAgent,Agent);TGuardValue<bool> Kick(EndEventKick,true);
      L::SetAttackToLocomotionBlend(Agent);
      TestFalse(TEXT("Regular event setter cannot enable disabled kick profile"),Active.Contains(Agent));
      L::SetKickToLocomotionBlend(Agent);
      TestTrue(TEXT("Kick event setter can enable current zero handoff"),Active.Contains(Agent)); }
    Remove(Agent);World->DestroyWorld(false);return !HasAnyErrors();
}
#endif
