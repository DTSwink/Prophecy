#include "ProphecyLowerTemperingLibrary.h"
#include "ProphecyLowerTempering.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"
#include "ProphecyBlendClock.h"

namespace ProphecyLegRecovery
{
struct FConfig { float Duration=1.f,Speed=180.f; };
struct FActive { FConfig Config; double Elapsed=0; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FConfig> Configs;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FActive> Active;
static FDelegateHandle Cleanup;
static void EnsureCleanup()
{
    if(Cleanup.IsValid()) return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for(auto It=Configs.CreateIterator();It;++It)
            if(!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
        for(auto It=Active.CreateIterator();It;++It)
            if(!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
    });
}
void Cancel(const AProphecyAgent* Agent)
{
    if(!Active.IsEmpty() && Active.Remove(Agent))
        ProphecyBlendClock::Stop(Agent,ProphecyBlendClock::EKind::LegReconstruction);
}
void Remove(const AProphecyAgent* Agent) { Cancel(Agent);Configs.Remove(Agent); }
void Begin(const AProphecyAgent* Agent)
{
    Cancel(Agent);
    const auto* Config=Configs.IsEmpty()?nullptr:Configs.Find(Agent);
    const FConfig Value=Config?*Config:FConfig{};
    if(Value.Duration<=0 || !IsValid(Agent) || !ProphecyLegChainDebug::IsEnabled(Agent)) return;
    EnsureCleanup();Active.Add(Agent,FActive{Value});
    ProphecyBlendClock::Start(Agent,ProphecyBlendClock::EKind::LegReconstruction);
}
bool Step(const AProphecyAgent* Agent,FStep& Out)
{
    auto* State=Active.IsEmpty()?nullptr:Active.Find(Agent);
    if(!State) return false;
    const double Dt=ProphecyBlendClock::Consume(Agent,ProphecyBlendClock::EKind::LegReconstruction);
    State->Elapsed+=Dt;
    Out.MaxTurnRadians=FMath::DegreesToRadians(State->Config.Speed*float(Dt));
    Out.Expired=State->Elapsed+1.e-6>=State->Config.Duration;
    return true;
}
void FinishStep(const AProphecyAgent* Agent,bool Limited)
{
    const auto* State=Active.Find(Agent);
    if(State && !Limited && State->Elapsed+1.e-6>=State->Config.Duration) Cancel(Agent);
}
}

bool UProphecyLegChainDebugLibrary::SetLegReconstructionRecovery(AProphecyAgent* Agent,float DurationSeconds,float PoleTurnSpeedDegreesPerSecond)
{
    if(!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown
        || !FMath::IsFinite(DurationSeconds) || DurationSeconds<0
        || !FMath::IsFinite(PoleTurnSpeedDegreesPerSecond) || PoleTurnSpeedDegreesPerSecond<=0) return false;
    using namespace ProphecyLegRecovery;
    EnsureCleanup();const FConfig Config{DurationSeconds,PoleTurnSpeedDegreesPerSecond};
    if(DurationSeconds==1.f && PoleTurnSpeedDegreesPerSecond==180.f) Configs.Remove(Agent);
    else Configs.Add(Agent,Config);
    if(DurationSeconds==0) Cancel(Agent);
    else if(auto* State=Active.Find(Agent)) State->Config=Config; // Retuning never restarts the clock.
    return true;
}

namespace ProphecyLowerTempering
{
static TMap<TWeakObjectPtr<const AProphecyAgent>,float> MinimumReachOverrides;
static FDelegateHandle MinimumReachCleanup;
float MinimumLegReachMultiplier(const AProphecyAgent* Agent)
{
    const float* Value=MinimumReachOverrides.IsEmpty() ? nullptr : MinimumReachOverrides.Find(Agent);
    return Value ? *Value : 1.2f;
}
}

bool UProphecyLegChainDebugLibrary::SetLocomotionMinimumLegReach(AProphecyAgent* Agent,float Multiplier)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown
        || !FMath::IsFinite(Multiplier) || Multiplier<1.f) return false;
    using namespace ProphecyLowerTempering;
    if (Multiplier==1.2f) { MinimumReachOverrides.Remove(Agent);return true; }
    if (!MinimumReachCleanup.IsValid()) MinimumReachCleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for (auto It=MinimumReachOverrides.CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
    });
    MinimumReachOverrides.Add(Agent,Multiplier);
    return true;
}

namespace ProphecyLegChainDebug
{
static TSet<TWeakObjectPtr<const AProphecyAgent>> Disabled;
static FDelegateHandle Cleanup;
bool IsEnabled(const AProphecyAgent* Agent) { return Disabled.IsEmpty() || !Disabled.Contains(Agent); }
void Remove(const AProphecyAgent* Agent) { if (!Disabled.IsEmpty()) Disabled.Remove(Agent); }
}

bool UProphecyLegChainDebugLibrary::SetLegChainReconstruction(AProphecyAgent* Agent,bool Enabled)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown) return false;
    using namespace ProphecyLegChainDebug;
    if (Enabled) { Remove(Agent);return true; }
    ProphecyLegRecovery::Cancel(Agent);
    if (!Cleanup.IsValid()) Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for (auto It=Disabled.CreateIterator();It;++It)
            if (!It->IsValid() || It->Get()->GetWorld()==World) It.RemoveCurrent();
    });
    Disabled.Add(Agent);
    return true;
}

namespace ProphecyLowerTempering
{
static TMap<TWeakObjectPtr<const AProphecyAgent>, FSettings> Settings;
// Configuration is independent of the active values consumed by Blend To Normal.
static TMap<TWeakObjectPtr<const AProphecyAgent>, FSettings> RegularProfiles,KickProfiles;
static TSet<TWeakObjectPtr<const AProphecyAgent>> KickSelected,RightKickSelected;
// Opt-in separation keeps existing shared-return graphs working until the kick
// node is used. Configuration only; no tick work or additional return clock.
static TSet<TWeakObjectPtr<const AProphecyAgent>> SeparateKickReturns;
// Sidecars preserve live settings, return timelines and reset snapshot layouts.
static TMap<TWeakObjectPtr<const AProphecyAgent>,FSettings> NonKickingProfiles,RightValues;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FSettings> ReturnRightInitial,FeetReturnRightInitial;
const FSettings& RightFootSettings(const AProphecyAgent* Agent,const FSettings& Left)
{
    const auto* Right=RightValues.IsEmpty() ? nullptr : RightValues.Find(Agent);
    return Right ? *Right : Left;
}
static bool AllNormal(const AProphecyAgent* Agent,const FSettings& Left)
{ return Left.IsIdentity() && RightFootSettings(Agent,Left).FeetAreIdentity(); }
static bool SameFeet(const FSettings& A,const FSettings& B)
{ return A.FeetTranslation==B.FeetTranslation && A.FeetTranslationZ==B.FeetTranslationZ && A.FeetRotation==B.FeetRotation; }
static void CopyFeet(FSettings& A,const FSettings& B)
{ A.FeetTranslation=B.FeetTranslation;A.FeetTranslationZ=B.FeetTranslationZ;A.FeetRotation=B.FeetRotation; }
void RestoreRightFootSettings(const AProphecyAgent* Agent,const FSettings& Right)
{
    const auto* Left=Settings.Find(Agent);
    if ((!Left && Right.FeetAreIdentity()) || (Left && SameFeet(*Left,Right))) { RightValues.Remove(Agent);return; }
    if (!Left) Settings.Add(Agent,FSettings{});
    RightValues.Add(Agent,Right);
}
struct FReturnTimeline
{
    FSettings Initial;
    float Duration=1.f,Hold=0.f;
    double Elapsed=0,WorldTime=0;
    FSettings Sample() const
    {
        if (Elapsed+1.e-9<Hold) return Initial;
        const float T=Duration>0 ? FMath::Clamp(float((Elapsed-Hold)/Duration),0.f,1.f) : 1.f;
        const float Alpha=T*T*(3.f-2.f*T);
        return {FMath::Lerp(Initial.FeetTranslation,1.f,Alpha),FMath::Lerp(Initial.FeetRotation,1.f,Alpha),
            FMath::Lerp(Initial.PelvisTranslation,1.f,Alpha),FMath::Lerp(Initial.PelvisRotation,1.f,Alpha),
            FMath::Lerp(Initial.FeetTranslationZ,1.f,Alpha),FMath::Lerp(Initial.PelvisTranslationZ,1.f,Alpha)};
    }
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FReturnTimeline> Returns;
// Separate maps preserve existing live timeline layouts and let either part retire
// while the other keeps its original schedule.
static TMap<TWeakObjectPtr<const AProphecyAgent>,FReturnTimeline> FeetReturns,PelvisReturns;
static FDelegateHandle Cleanup;
static void CancelReturns(const AProphecyAgent* Agent)
{
    ReturnRightInitial.Remove(Agent);FeetReturnRightInitial.Remove(Agent);
    if (!Returns.IsEmpty()) Returns.Remove(Agent);
    if (!FeetReturns.IsEmpty()) FeetReturns.Remove(Agent);
    if (!PelvisReturns.IsEmpty()) PelvisReturns.Remove(Agent);
    for (auto Kind : {ProphecyBlendClock::EKind::Tempering,ProphecyBlendClock::EKind::FeetTempering,
        ProphecyBlendClock::EKind::PelvisTempering}) ProphecyBlendClock::Stop(Agent,Kind);
}
const FSettings* Find(const AProphecyAgent* Agent)
{
    auto* Value=Settings.IsEmpty() ? nullptr : Settings.Find(Agent);
    if (!Value) return nullptr;
    if (auto* Return=Returns.IsEmpty() ? nullptr : Returns.Find(Agent))
    {
        Return->Elapsed+=ProphecyBlendClock::Consume(Agent,ProphecyBlendClock::EKind::Tempering);
        *Value=Return->Sample();
        if (const auto* Initial=ReturnRightInitial.Find(Agent))
        { auto Right=*Return;Right.Initial=*Initial;CopyFeet(RightValues.FindOrAdd(Agent),Right.Sample()); }
        if (AllNormal(Agent,*Value))
        { Returns.Remove(Agent);ReturnRightInitial.Remove(Agent);ProphecyBlendClock::Stop(Agent,ProphecyBlendClock::EKind::Tempering); }
    }
    auto SamplePart=[&](auto& Timelines,bool Feet,ProphecyBlendClock::EKind Kind)
    {
        auto* Return=Timelines.IsEmpty() ? nullptr : Timelines.Find(Agent);
        if (!Return) return;
        Return->Elapsed+=ProphecyBlendClock::Consume(Agent,Kind);
        const auto Sample=Return->Sample();
        if (Feet)
        {
            CopyFeet(*Value,Sample);
            if (const auto* Initial=FeetReturnRightInitial.Find(Agent))
            { auto Right=*Return;Right.Initial=*Initial;CopyFeet(RightValues.FindOrAdd(Agent),Right.Sample()); }
        }
        else { Value->PelvisTranslation=Sample.PelvisTranslation;Value->PelvisTranslationZ=Sample.PelvisTranslationZ;Value->PelvisRotation=Sample.PelvisRotation; }
        const bool Done=Feet ? Value->FeetAreIdentity() && RightFootSettings(Agent,*Value).FeetAreIdentity()
            : Value->PelvisTranslation==1 && Value->PelvisTranslationZ==1 && Value->PelvisRotation==1;
        if (Done) { Timelines.Remove(Agent);if (Feet) FeetReturnRightInitial.Remove(Agent);ProphecyBlendClock::Stop(Agent,Kind); }
    };
    SamplePart(FeetReturns,true,ProphecyBlendClock::EKind::FeetTempering);
    SamplePart(PelvisReturns,false,ProphecyBlendClock::EKind::PelvisTempering);
    if (AllNormal(Agent,*Value)) { Remove(Agent);return nullptr; }
    return Value;
}
void Remove(const AProphecyAgent* Agent)
{
    RightValues.Remove(Agent);
    if (!Settings.IsEmpty()) Settings.Remove(Agent);
    CancelReturns(Agent);
}

static bool BlendPart(AProphecyAgent* Agent,bool Feet,float Duration,float Hold)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown
        || !FMath::IsFinite(Duration) || Duration<0 || !FMath::IsFinite(Hold) || Hold<0) return false;
    const auto* Current=Find(Agent);
    if (!Current) return true;
    const FSettings Initial=*Current;
    const FSettings InitialRight=RightFootSettings(Agent,Initial);
    // Detach only this part from a pre-existing combined return. The other part
    // keeps exactly its old elapsed time, hold, duration and initial values.
    if (auto* Shared=Returns.Find(Agent))
    {
        if (Feet) Shared->Initial.FeetTranslation=Shared->Initial.FeetTranslationZ=Shared->Initial.FeetRotation=1;
        else Shared->Initial.PelvisTranslation=Shared->Initial.PelvisTranslationZ=Shared->Initial.PelvisRotation=1;
        auto* SharedRight=ReturnRightInitial.Find(Agent);
        if (Feet && SharedRight) CopyFeet(*SharedRight,FSettings{});
        if (Shared->Initial.IsIdentity() && (!SharedRight || SharedRight->FeetAreIdentity()))
        { Returns.Remove(Agent);ReturnRightInitial.Remove(Agent);ProphecyBlendClock::Stop(Agent,ProphecyBlendClock::EKind::Tempering); }
    }
    auto& Timelines=Feet ? FeetReturns : PelvisReturns;
    const auto Kind=Feet ? ProphecyBlendClock::EKind::FeetTempering : ProphecyBlendClock::EKind::PelvisTempering;
    const bool AlreadyNormal=Feet ? Initial.FeetAreIdentity() && InitialRight.FeetAreIdentity()
        : Initial.PelvisTranslation==1 && Initial.PelvisTranslationZ==1 && Initial.PelvisRotation==1;
    if (AlreadyNormal || (Duration==0 && Hold==0))
    {
        Timelines.Remove(Agent);ProphecyBlendClock::Stop(Agent,Kind);
        auto& Value=Settings.FindChecked(Agent);
        if (Feet)
        { CopyFeet(Value,FSettings{});RightValues.Remove(Agent);FeetReturnRightInitial.Remove(Agent); }
        else Value.PelvisTranslation=Value.PelvisTranslationZ=Value.PelvisRotation=1;
        if (AllNormal(Agent,Value)) Remove(Agent);
        return true;
    }
    Timelines.Add(Agent,FReturnTimeline{Initial,Duration,Hold});
    if (Feet && RightValues.Contains(Agent)) FeetReturnRightInitial.Add(Agent,InitialRight);
    ProphecyBlendClock::Start(Agent,Kind,double(Duration)+Hold);
    return true;
}
}

namespace ProphecyLowerTempering
{
static void EnsureCleanup()
{
    if (Cleanup.IsValid()) return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for (auto* Map:{&Settings,&RegularProfiles,&KickProfiles,&NonKickingProfiles,&RightValues,&ReturnRightInitial,&FeetReturnRightInitial}) for (auto It=Map->CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
        for (auto* Map:{&Returns,&FeetReturns,&PelvisReturns}) for (auto It=Map->CreateIterator();It;++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
        for (auto* Set:{&KickSelected,&RightKickSelected,&SeparateKickReturns}) for (auto It=Set->CreateIterator();It;++It)
            if (!It->IsValid() || It->Get()->GetWorld()==World) It.RemoveCurrent();
    });
}
static void Apply(const AProphecyAgent* Agent,const FSettings& Value)
{
    Remove(Agent);
    if (!Value.IsIdentity()) { EnsureCleanup();Settings.Add(Agent,Value); }
}
void ClearAttackSelection(const AProphecyAgent* Agent) { KickSelected.Remove(Agent);RightKickSelected.Remove(Agent); }
void ForgetProfiles(const AProphecyAgent* Agent)
{ Remove(Agent);ClearAttackSelection(Agent);SeparateKickReturns.Remove(Agent);RegularProfiles.Remove(Agent);KickProfiles.Remove(Agent);NonKickingProfiles.Remove(Agent); }
void SelectAttackProfile(const AProphecyAgent* Agent,FName Attack)
{
    const bool Kick=Attack==TEXT("kickl") || Attack==TEXT("kickr");
    if (Kick) { EnsureCleanup();KickSelected.Add(Agent); } else KickSelected.Remove(Agent);
    if (Attack==TEXT("kickr")) RightKickSelected.Add(Agent);else RightKickSelected.Remove(Agent);
    const auto* Special=KickProfiles.Find(Agent);
    const auto* Regular=RegularProfiles.Find(Agent);
    if (!Kick || !Special) { if (Regular || Special) Apply(Agent,Regular ? *Regular : FSettings{});return; }
    const auto* NonKicking=NonKickingProfiles.Find(Agent);
    FSettings Left=*Special,Right=NonKicking ? *NonKicking : *Special;
    if (Attack==TEXT("kickr")) Swap(Left,Right);
    // Pelvis is independent of which leg kicked.
    Left.PelvisTranslation=Special->PelvisTranslation;Left.PelvisTranslationZ=Special->PelvisTranslationZ;Left.PelvisRotation=Special->PelvisRotation;
    Apply(Agent,Left);RestoreRightFootSettings(Agent,Right);
}
static bool SetProfile(bool Kick,AProphecyAgent* Agent,bool Enabled,
    float FeetXY,float FeetZ,float FeetR,float PelvisXY,float PelvisZ,float PelvisR)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown) return false;
    if (Enabled) for (float V:{FeetXY,FeetZ,FeetR,PelvisXY,PelvisZ,PelvisR})
        if (!FMath::IsFinite(V) || V<0 || V>1) return false;
    const FSettings Value=Enabled ? FSettings{FeetXY,FeetR,PelvisXY,PelvisR,FeetZ,PelvisZ} : FSettings{};
    EnsureCleanup();(Kick ? KickProfiles : RegularProfiles).Add(Agent,Value);
    const bool UsesKick=KickSelected.Contains(Agent) && KickProfiles.Contains(Agent);
    if (Kick==UsesKick) Apply(Agent,Value);
    return true;
}
}

bool UProphecyLowerTemperingLibrary::SetLocomotionLowerBodyTempering(AProphecyAgent* Agent,bool Enabled,
    float FeetTranslation,float FeetTranslationZ,float FeetRotation,
    float PelvisTranslation,float PelvisTranslationZ,float PelvisRotation)
{
    return ProphecyLowerTempering::SetProfile(false,Agent,Enabled,FeetTranslation,FeetTranslationZ,FeetRotation,
        PelvisTranslation,PelvisTranslationZ,PelvisRotation);
}

bool UProphecyLowerTemperingLibrary::SetKickLocomotionLowerBodyTempering(AProphecyAgent* Agent,bool Enabled,
    float FeetTranslation,float FeetTranslationZ,float FeetRotation,
    float NonKickingFootTranslationXY,float NonKickingFootTranslationZ,float NonKickingFootRotation,
    float PelvisTranslation,float PelvisTranslationZ,float PelvisRotation)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown) return false;
    if (Enabled) for (float V:{FeetTranslation,FeetTranslationZ,FeetRotation,NonKickingFootTranslationXY,
        NonKickingFootTranslationZ,NonKickingFootRotation,PelvisTranslation,PelvisTranslationZ,PelvisRotation})
        if (!FMath::IsFinite(V) || V<0 || V>1) return false;
    using namespace ProphecyLowerTempering;
    EnsureCleanup();
    KickProfiles.Add(Agent,Enabled ? FSettings{FeetTranslation,FeetRotation,PelvisTranslation,PelvisRotation,FeetTranslationZ,PelvisTranslationZ} : FSettings{});
    NonKickingProfiles.Add(Agent,Enabled ? FSettings{NonKickingFootTranslationXY,NonKickingFootRotation,1,1,NonKickingFootTranslationZ,1} : FSettings{});
    if (KickSelected.Contains(Agent)) SelectAttackProfile(Agent,RightKickSelected.Contains(Agent) ? TEXT("kickr") : TEXT("kickl"));
    return true;
}

static bool BlendSelectedLowerBodyTemperingToNormal(bool Kick,AProphecyAgent* Agent,
    float DurationSeconds,float HoldDurationSeconds,float PelvisDurationSeconds,float PelvisHoldDurationSeconds)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown
        || !FMath::IsFinite(DurationSeconds) || DurationSeconds<0
        || !FMath::IsFinite(HoldDurationSeconds) || HoldDurationSeconds<0
        || !FMath::IsFinite(PelvisDurationSeconds) || PelvisDurationSeconds<0
        || !FMath::IsFinite(PelvisHoldDurationSeconds) || PelvisHoldDurationSeconds<0) return false;
    using namespace ProphecyLowerTempering;
    if (Kick) { EnsureCleanup();SeparateKickReturns.Add(Agent); }
    if ((Kick && !KickSelected.Contains(Agent))
        || (!Kick && SeparateKickReturns.Contains(Agent) && KickSelected.Contains(Agent))) return true;
    if (DurationSeconds!=PelvisDurationSeconds || HoldDurationSeconds!=PelvisHoldDurationSeconds)
    {
        if (!Find(Agent)) return true;
        CancelReturns(Agent);
        return BlendPart(Agent,true,DurationSeconds,HoldDurationSeconds)
            && BlendPart(Agent,false,PelvisDurationSeconds,PelvisHoldDurationSeconds);
    }
    if (DurationSeconds==0 && HoldDurationSeconds==0) { Remove(Agent);return true; }
    const auto* Current=Find(Agent);
    if (!Current) return true;
    const FSettings Initial=*Current;
    const FSettings InitialRight=RightFootSettings(Agent,Initial);
    CancelReturns(Agent);
    if (RightValues.Contains(Agent)) ReturnRightInitial.Add(Agent,InitialRight);
    Returns.Add(Agent,FReturnTimeline{Initial,DurationSeconds,HoldDurationSeconds});
    ProphecyBlendClock::Start(Agent,ProphecyBlendClock::EKind::Tempering,double(DurationSeconds)+HoldDurationSeconds);
    return true;
}

bool UProphecyLowerTemperingLibrary::BlendLocomotionLowerBodyTemperingToNormal(
    AProphecyAgent* Agent,float DurationSeconds,float HoldDurationSeconds,float PelvisDurationSeconds,float PelvisHoldDurationSeconds)
{ return BlendSelectedLowerBodyTemperingToNormal(false,Agent,DurationSeconds,HoldDurationSeconds,PelvisDurationSeconds,PelvisHoldDurationSeconds); }

bool UProphecyLowerTemperingLibrary::BlendKickLocomotionLowerBodyTemperingToNormal(
    AProphecyAgent* Agent,float DurationSeconds,float HoldDurationSeconds,float PelvisDurationSeconds,float PelvisHoldDurationSeconds)
{ return BlendSelectedLowerBodyTemperingToNormal(true,Agent,DurationSeconds,HoldDurationSeconds,PelvisDurationSeconds,PelvisHoldDurationSeconds); }

bool UProphecyLowerTemperingLibrary::BlendLocomotionFeetTemperingToNormal(
    AProphecyAgent* Agent,float DurationSeconds,float HoldDurationSeconds)
{ return ProphecyLowerTempering::BlendPart(Agent,true,DurationSeconds,HoldDurationSeconds); }

bool UProphecyLowerTemperingLibrary::BlendLocomotionPelvisTemperingToNormal(
    AProphecyAgent* Agent,float DurationSeconds,float HoldDurationSeconds)
{ return ProphecyLowerTempering::BlendPart(Agent,false,DurationSeconds,HoldDurationSeconds); }

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyLegRecoveryClockTest,"Prophecy.NN.LowerTempering.IndependentRecoveryClock",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyLegRecoveryClockTest::RunTest(const FString&)
{
    using namespace ProphecyLegRecovery;
    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* Agent=World?World->SpawnActor<AProphecyAgent>():nullptr;
    if(!Agent) return false;
    for(float FPS:{30.f,60.f,120.f})
    {
        TestTrue(TEXT("Configure independent duration and speed"),UProphecyLegChainDebugLibrary::SetLegReconstructionRecovery(Agent,1.f,180.f));
        Begin(Agent);FStep S;float Budget=0;
        for(int32 I=1;I<=60;++I)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/FPS);
            if(I==15) ProphecyLowerTempering::Remove(Agent);
            if(I%2==0)
            {
                TestTrue(TEXT("Recovery survives its independent window"),Step(Agent,S));Budget+=S.MaxTurnRadians;
                if(I<60) TestFalse(TEXT("Timer cannot expire early"),S.Expired);
                FStep Duplicate;Step(Agent,Duplicate);TestEqual(TEXT("Duplicate sample adds no turn budget"),Duplicate.MaxTurnRadians,0.f);
            }
        }
        TestTrue(TEXT("Sixty ticks allows exactly 180 degrees at every FPS"),FMath::IsNearlyEqual(Budget,PI,2.e-6f));
        TestTrue(TEXT("Duration expires at sixty ticks"),S.Expired);
        FinishStep(Agent,true);TestTrue(TEXT("Remaining correction is not dropped at expiry"),Step(Agent,S));
        FinishStep(Agent,false);TestFalse(TEXT("Convergence removes all active pose work"),Step(Agent,S));
        TestFalse(TEXT("Convergence retires active entry"),Active.Contains(Agent));
    }
    UProphecyLegChainDebugLibrary::SetLegReconstructionRecovery(Agent,0,180);Begin(Agent);FStep S;
    TestFalse(TEXT("Zero extra duration creates no state or clock"),Step(Agent,S));
    TestFalse(TEXT("Zero speed rejected"),UProphecyLegChainDebugLibrary::SetLegReconstructionRecovery(Agent,1,0));
    UProphecyLegChainDebugLibrary::SetLegReconstructionRecovery(Agent,1,90);Begin(Agent);Cancel(Agent);
    TestFalse(TEXT("New special/reset cancellation removes active work"),Step(Agent,S));
    TestTrue(TEXT("Cancellation preserves tuning for future exits"),Configs.Contains(Agent));
    Begin(Agent);UProphecyLegChainDebugLibrary::SetLegChainReconstruction(Agent,false);
    TestFalse(TEXT("Disabling leg reconstruction cancels timer"),Step(Agent,S));
    UProphecyLegChainDebugLibrary::SetLegChainReconstruction(Agent,true);
    Remove(Agent);TestFalse(TEXT("Lifetime cleanup removes settings"),Configs.Contains(Agent));
    World->DestroyWorld(false);return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyTemperingReturnTest,"Prophecy.NN.LowerTempering.ReturnTimeline",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyTemperingReturnTest::RunTest(const FString&)
{
    using namespace ProphecyLowerTempering;
    FReturnTimeline T{{0,.2f,.4f,.6f,.8f,.1f},2,1};
    T.Elapsed=.9;TestEqual(TEXT("Hold retains initial feet"),T.Sample().FeetTranslation,0.f);
    T.Elapsed=1;TestEqual(TEXT("Blend starts at hold endpoint"),T.Sample().PelvisRotation,.6f);
    T.Elapsed=2;auto Mid=T.Sample();
    TestTrue(TEXT("All four controls return independently"),FMath::IsNearlyEqual(Mid.FeetTranslation,.5f,1.e-6f)
        && FMath::IsNearlyEqual(Mid.FeetRotation,.6f,1.e-6f) && FMath::IsNearlyEqual(Mid.PelvisTranslation,.7f,1.e-6f)
        && FMath::IsNearlyEqual(Mid.PelvisRotation,.8f,1.e-6f));
    T.Elapsed=3;TestTrue(TEXT("Exact normal endpoint"),T.Sample().IsIdentity());
    TestTrue(TEXT("Z values blend independently with same schedule"),FMath::IsNearlyEqual(Mid.FeetTranslationZ,.9f)
        && FMath::IsNearlyEqual(Mid.PelvisTranslationZ,.55f));
    T.Duration=0;T.Elapsed=.5;TestFalse(TEXT("Zero blend still holds"),T.Sample().IsIdentity());
    T.Elapsed=1;TestTrue(TEXT("Zero blend snaps after hold"),T.Sample().IsIdentity());
    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
    if (!World) return false;
    auto* Agent=World->SpawnActor<AProphecyAgent>();
    if (!Agent) { World->DestroyWorld(false);return false; }
    using L=UProphecyLowerTemperingLibrary;
    TestTrue(TEXT("Set initial"),L::SetLocomotionLowerBodyTempering(Agent,true,0,1.f,0,0,1.f,0));
    TestTrue(TEXT("Start return"),L::BlendLocomotionLowerBodyTemperingToNormal(Agent,1,1,1,1));
    Returns.FindChecked(Agent).Elapsed=3;
    TestNull(TEXT("Completion bypasses pose work"),Find(Agent));
    TestFalse(TEXT("Completion retires timeline"),Returns.Contains(Agent));
    L::SetLocomotionLowerBodyTempering(Agent,true,0,1.f,0,0,1.f,0);
    L::BlendLocomotionLowerBodyTemperingToNormal(Agent,2,1,2,1);
    L::SetLocomotionLowerBodyTempering(Agent,true,.4f,1.f,.4f,.4f,1.f,.4f);
    TestFalse(TEXT("Explicit setter cancels return"),Returns.Contains(Agent));
    TestEqual(TEXT("Explicit setter wins"),Find(Agent)->FeetTranslation,.4f);
    Remove(Agent);World->DestroyWorld(false);
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyTemperingSeparateReturnsTest,"Prophecy.NN.LowerTempering.SeparateReturns",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyTemperingSeparateReturnsTest::RunTest(const FString&)
{
    using namespace ProphecyLowerTempering;
    using L=UProphecyLowerTemperingLibrary;
#if WITH_EDITOR
    int32 VisibleNodes=0;
    for (TFieldIterator<UFunction> It(L::StaticClass(),EFieldIteratorFlags::ExcludeSuper);It;++It)
        if (It->HasAnyFunctionFlags(FUNC_BlueprintCallable) && !It->GetBoolMetaData(TEXT("BlueprintInternalUseOnly"))) ++VisibleNodes;
    TestEqual(TEXT("Regular and kick Set/Blend exposed"),VisibleNodes,4);
#endif
    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* Agent=World ? World->SpawnActor<AProphecyAgent>() : nullptr;
    if (!Agent) { if (World) World->DestroyWorld(false);return false; }
    auto Tick=[&](int32 Count)
    {
        for (int32 I=0;I<Count;++I)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/120.f);
            Find(Agent);
        }
    };
    auto Values=[&]() { const auto* V=Find(Agent);return V ? *V : FSettings{}; };
    L::SetLocomotionLowerBodyTempering(Agent,true,0,.2f,0,0,.4f,0);
    TestTrue(TEXT("One node schedules feet and pelvis independently"),L::BlendLocomotionLowerBodyTemperingToNormal(Agent,1,.5f,.5f,0));
    Tick(15);
    TestEqual(TEXT("Feet still held while pelvis blends"),Values().FeetTranslation,0.f);
    TestEqual(TEXT("Feet Z uses feet hold"),Values().FeetTranslationZ,.2f);
    TestTrue(TEXT("Pelvis Z uses pelvis duration"),FMath::IsNearlyEqual(Values().PelvisTranslationZ,.7f,1.e-6f));
    TestTrue(TEXT("Pelvis halfway at 15 ticks"),FMath::IsNearlyEqual(Values().PelvisRotation,.5f,1.e-6f));
    Tick(15);
    TestEqual(TEXT("Pelvis completes at 30 ticks"),Values().PelvisTranslation,1.f);
    TestFalse(TEXT("Completed pelvis timeline retired independently"),PelvisReturns.Contains(Agent));
    TestTrue(TEXT("Feet timeline remains active"),FeetReturns.Contains(Agent));
    Tick(30);
    TestTrue(TEXT("Feet halfway after its own hold"),FMath::IsNearlyEqual(Values().FeetRotation,.5f,1.e-6f));
    TestEqual(TEXT("Completed pelvis stays normal"),Values().PelvisRotation,1.f);
    Tick(30);
    TestNull(TEXT("Both finished bypass all tempering"),Find(Agent));
    TestFalse(TEXT("No remaining feet timeline"),FeetReturns.Contains(Agent));

    L::SetLocomotionLowerBodyTempering(Agent,true,0,1.f,0,0,1.f,0);
    L::BlendLocomotionFeetTemperingToNormal(Agent,2,0);
    L::BlendLocomotionPelvisTemperingToNormal(Agent,1,0);
    Tick(30);
    const float PelvisBefore=Values().PelvisTranslation;
    L::BlendLocomotionPelvisTemperingToNormal(Agent,.5f,0);
    TestEqual(TEXT("Retarget pelvis has no jump"),Values().PelvisTranslation,PelvisBefore);
    Tick(30);
    TestTrue(TEXT("Retargeting pelvis did not restart feet"),FMath::IsNearlyEqual(Values().FeetTranslation,.5f,1.e-6f));
    TestEqual(TEXT("Retargeted pelvis reaches normal"),Values().PelvisTranslation,1.f);
    L::SetLocomotionLowerBodyTempering(Agent,true,0,1.f,0,0,1.f,0);
    TestFalse(TEXT("Explicit Set cancels feet"),FeetReturns.Contains(Agent));
    TestFalse(TEXT("Explicit Set cancels pelvis"),PelvisReturns.Contains(Agent));

    L::BlendLocomotionLowerBodyTemperingToNormal(Agent,2,0,2,0);
    Tick(30);
    L::BlendLocomotionFeetTemperingToNormal(Agent,0,0);
    TestEqual(TEXT("Zero feet duration snaps feet only"),Values().FeetTranslation,1.f);
    Tick(30);
    TestTrue(TEXT("Combined pelvis schedule survives feet override"),FMath::IsNearlyEqual(Values().PelvisTranslation,.5f,1.e-6f));
    TestEqual(TEXT("Old shared timeline cannot undo completed feet"),Values().FeetRotation,1.f);
    Tick(60);
    TestNull(TEXT("Shared remainder retires"),Find(Agent));

    L::SetLocomotionLowerBodyTempering(Agent,true,0,1.f,0,.4f,1.f,.6f);
    L::BlendLocomotionFeetTemperingToNormal(Agent,0,.5f);
    Tick(30);
    TestEqual(TEXT("Zero duration snaps after feet hold"),Values().FeetTranslation,1.f);
    TestEqual(TEXT("Unscheduled pelvis remains unchanged"),Values().PelvisTranslation,.4f);
    TestFalse(TEXT("No completed feet timer"),FeetReturns.Contains(Agent));
    L::BlendLocomotionPelvisTemperingToNormal(Agent,2,0);
    L::BlendLocomotionLowerBodyTemperingToNormal(Agent,.5f,0,.5f,0);
    TestFalse(TEXT("Combined node replaces independent return"),PelvisReturns.Contains(Agent));
    Tick(30);
    TestNull(TEXT("Combined replacement completes"),Find(Agent));
    Remove(Agent);World->DestroyWorld(false);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyKickTemperingTest,"Prophecy.NN.LowerTempering.KickProfiles",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyKickTemperingTest::RunTest(const FString&)
{
    using namespace ProphecyLowerTempering;
    using L=UProphecyLowerTemperingLibrary;
    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* Agent=World ? World->SpawnActor<AProphecyAgent>() : nullptr;
    if (!Agent) { if (World) World->DestroyWorld(false);return false; }
    auto Value=[&]() { const auto* V=Find(Agent);return V ? *V : FSettings{}; };
    L::SetLocomotionLowerBodyTempering(Agent,true,.2f,.3f,.4f,.5f,.6f,.7f);
    L::SetKickLocomotionLowerBodyTempering(Agent,true,.8f,.7f,.6f,.8f,.7f,.6f,.4f,.3f,.2f);
    TestEqual(TEXT("Configuring kick does not change ordinary locomotion"),Value().FeetTranslation,.2f);
    for (FName Family:{FName(TEXT("kickL")),FName(TEXT("kickR"))})
    {
        SelectAttackProfile(Agent,Family);
        L::SetLocomotionLowerBodyTempering(Agent,true,.2f,.3f,.4f,.5f,.6f,.7f);
        TestEqual(TEXT("Regular end-event setter cannot overwrite kick feet XY"),Value().FeetTranslation,.8f);
        TestEqual(TEXT("Kick pelvis Z selected independently"),Value().PelvisTranslationZ,.3f);
        L::BlendLocomotionLowerBodyTemperingToNormal(Agent,1,0,.5f,0);
        for (int I=0;I<30;++I) { FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/120);Find(Agent); }
        TestTrue(TEXT("Kick feet blend from selected profile at 30 ticks"),FMath::IsNearlyEqual(Value().FeetTranslation,.9f));
        TestEqual(TEXT("Kick pelvis finishes independently"),Value().PelvisTranslationZ,1.f);
        for (int I=0;I<30;++I) { FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/30);Find(Agent); }
        TestNull(TEXT("Kick completion removes active pose work"),Find(Agent));
        TestFalse(TEXT("Kick completion removes timeline"),FeetReturns.Contains(Agent));
    }
    SelectAttackProfile(Agent,TEXT("overL"));
    TestEqual(TEXT("Next ordinary attack restores regular profile"),Value().FeetTranslation,.2f);
    L::SetKickLocomotionLowerBodyTempering(Agent,false);
    SelectAttackProfile(Agent,TEXT("kickL"));
    TestNull(TEXT("Disabled kick overrides nonidentity regular profile"),Find(Agent));
    SelectAttackProfile(Agent,TEXT("hookL"));
    TestEqual(TEXT("Disabled kick did not erase regular profile"),Value().FeetTranslation,.2f);
    ClearAttackSelection(Agent);Remove(Agent);
    L::SetLocomotionLowerBodyTempering(Agent);
    TestNull(TEXT("Reset/normal cancels active tempering"),Find(Agent));
    ForgetProfiles(Agent);World->DestroyWorld(false);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyTemperingFootRolesTest,"Prophecy.NN.LowerTempering.FootRoles",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyTemperingFootRolesTest::RunTest(const FString&)
{
    using namespace ProphecyLowerTempering;
    using L=UProphecyLowerTemperingLibrary;
    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* Agent=World ? World->SpawnActor<AProphecyAgent>() : nullptr;
    if (!Agent) { if (World) World->DestroyWorld(false);return false; }
    auto Left=[&]() { const auto* S=Find(Agent);return S ? *S : FSettings{}; };
    auto Right=[&]() { const auto S=Left();return FSettings(RightFootSettings(Agent,S)); };
    auto Tick=[&](int Count) { for (int I=0;I<Count;++I) { FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/120);Find(Agent); } };
    L::SetLocomotionLowerBodyTempering(Agent,true,.25f,.5f,.75f,.2f,.4f,.6f);
    // Frozen kicking foot, untouched non-kicking foot; independent pelvis channels.
    L::SetKickLocomotionLowerBodyTempering(Agent,true,0,.2f,.4f,1,1,1,.3f,.5f,.7f);
    for (FName Family:{FName(TEXT("kickL")),FName(TEXT("kickR")),FName(TEXT("kickL"))})
    {
        SelectAttackProfile(Agent,Family);
        const bool R=Family==TEXT("kickR");
        auto Kick=[&]() { return R ? Right() : Left(); };
        auto Other=[&]() { return R ? Left() : Right(); };
        TestEqual(TEXT("Kicking XY maps to selected leg"),Kick().FeetTranslation,0.f);
        TestEqual(TEXT("Kicking Z maps to selected leg"),Kick().FeetTranslationZ,.2f);
        TestEqual(TEXT("Kicking rotation maps to selected leg"),Kick().FeetRotation,.4f);
        TestTrue(TEXT("Non-kicking foot remains untempered"),Other().FeetAreIdentity());
        TestEqual(TEXT("Pelvis remains independent of kick side"),Left().PelvisTranslation,.3f);
        L::BlendLocomotionLowerBodyTemperingToNormal(Agent,1,.5f,.5f,0);
        Tick(30);
        TestEqual(TEXT("Each kicking foot honors existing feet hold"),Kick().FeetTranslation,0.f);
        TestEqual(TEXT("Pelvis completes while kicking foot held"),Left().PelvisTranslation,1.f);
        Tick(30);
        TestTrue(TEXT("Kicking XY blends independently"),FMath::IsNearlyEqual(Kick().FeetTranslation,.5f));
        TestTrue(TEXT("Kicking Z blends independently"),FMath::IsNearlyEqual(Kick().FeetTranslationZ,.6f));
        // Lerp(.4f,1,.5f) differs from the .7f literal by one float ULP.
        TestEqual(TEXT("Kicking rotation blends independently"),Kick().FeetRotation,.7f,1.e-6f);
        TestTrue(TEXT("Non-kicking foot was not frozen by other's blend"),Other().FeetAreIdentity());
        Tick(30);
        TestNull(TEXT("All normal removes primary entry"),Find(Agent));
        TestFalse(TEXT("All normal removes right sidecar"),RightValues.Contains(Agent));
        TestFalse(TEXT("All normal removes right timeline initial"),FeetReturnRightInitial.Contains(Agent));
    }
    // Right-only tempering must survive an identity left/pelvis through a shared timeline.
    L::SetKickLocomotionLowerBodyTempering(Agent,true,0,0,0,1,1,1,1,1,1);
    SelectAttackProfile(Agent,TEXT("kickR"));
    TestNotNull(TEXT("Identity left cannot retire active right"),Find(Agent));
    L::BlendLocomotionLowerBodyTemperingToNormal(Agent,1,0,1,0);
    L::BlendLocomotionPelvisTemperingToNormal(Agent,0,0);
    Tick(30);
    TestTrue(TEXT("Pelvis-only change preserves right shared schedule"),FMath::IsNearlyEqual(Right().FeetTranslation,.5f));
    L::BlendLocomotionFeetTemperingToNormal(Agent,.5f,0);
    Tick(15);
    TestTrue(TEXT("Retarget right feet return starts from current value"),FMath::IsNearlyEqual(Right().FeetTranslation,.75f));
    Tick(15);TestNull(TEXT("Retargeted right-only return retires"),Find(Agent));
    SelectAttackProfile(Agent,TEXT("kickL"));
    L::BlendLocomotionLowerBodyTemperingToNormal(Agent,0,0,0,0);
    TestNull(TEXT("Zero return bypasses both feet"),Find(Agent));
    SelectAttackProfile(Agent,TEXT("hookL"));
    TestTrue(TEXT("Non-kick selects regular symmetric settings"),Left().FeetTranslation==.25f && Right().FeetTranslation==.25f);
    ForgetProfiles(Agent);World->DestroyWorld(false);return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySeparatedKickReturnsTest,"Prophecy.NN.LowerTempering.SeparatedKickReturns",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecySeparatedKickReturnsTest::RunTest(const FString&)
{
    using namespace ProphecyLowerTempering;
    using L=UProphecyLowerTemperingLibrary;
    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* Agent=World ? World->SpawnActor<AProphecyAgent>() : nullptr;
    if (!Agent) { if(World) World->DestroyWorld(false);return false; }
    auto Left=[&]() { const auto* V=Find(Agent);return V ? *V : FSettings{}; };
    auto Right=[&]() { const auto V=Left();return FSettings(RightFootSettings(Agent,V)); };
    for (float FPS:{30.f,60.f,120.f}) for (FName Family:{FName(TEXT("kickL")),FName(TEXT("kickR"))})
    {
        ForgetProfiles(Agent);
        auto Tick=[&](int Count) { for(int I=0;I<Count;++I)
            { FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/FPS);Find(Agent); } };
        L::SetLocomotionLowerBodyTempering(Agent,true,.2f,.3f,.4f,.5f,.6f,.7f);
        L::SetKickLocomotionLowerBodyTempering(Agent,true,0,.2f,.4f,.6f,.7f,.8f,.3f,.4f,.5f);
        SelectAttackProfile(Agent,Family);
        // Both call orders: legacy regular call may precede initial opt-in, but
        // only the explicit kick schedule wins; later regular calls do nothing.
        L::BlendLocomotionLowerBodyTemperingToNormal(Agent,2,0,2,0);
        L::BlendKickLocomotionLowerBodyTemperingToNormal(Agent,.5f,.25f,.25f,0);
        L::BlendLocomotionLowerBodyTemperingToNormal(Agent,0,0,0,0);
        Tick(15);
        auto Kick=[&]() { return Family==TEXT("kickR") ? Right() : Left(); };
        TestEqual(TEXT("Kick retains its own hold despite regular zero return"),Kick().FeetTranslation,0.f);
        TestEqual(TEXT("Kick pelvis has independent duration"),Left().PelvisTranslation,1.f);
        Tick(15);TestEqual(TEXT("Kick blend uses its own duration at every FPS"),Kick().FeetTranslation,.5f,1.e-6f);
        Tick(15);TestNull(TEXT("Kick finishes at45 ticks and removes pose work"),Find(Agent));
        TestFalse(TEXT("Kick completion removes feet timeline"),FeetReturns.Contains(Agent));
        TestFalse(TEXT("Kick completion removes pelvis timeline"),PelvisReturns.Contains(Agent));
        SelectAttackProfile(Agent,TEXT("hookL"));
        L::BlendLocomotionLowerBodyTemperingToNormal(Agent,1,.25f,1,.25f);
        L::BlendKickLocomotionLowerBodyTemperingToNormal(Agent,0,0,0,0);
        Tick(15);TestEqual(TEXT("Kick node cannot erase regular hold"),Left().FeetTranslation,.2f);
        Tick(60);TestNull(TEXT("Regular schedule still completes"),Find(Agent));
        SelectAttackProfile(Agent,Family);
        L::BlendKickLocomotionLowerBodyTemperingToNormal(Agent,0,0,0,0);
        TestNull(TEXT("Zero kick duration restores both feet immediately"),Find(Agent));
        TestFalse(TEXT("Zero kick duration retains no timeline"),Returns.Contains(Agent)||FeetReturns.Contains(Agent)||PelvisReturns.Contains(Agent));
    }
    ForgetProfiles(Agent);TestFalse(TEXT("Cleanup removes opt-in configuration"),SeparateKickReturns.Contains(Agent));
    World->DestroyWorld(false);return !HasAnyErrors();
}
#endif
