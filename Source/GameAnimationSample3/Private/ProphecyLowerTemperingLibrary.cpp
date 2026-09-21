#include "ProphecyLowerTemperingLibrary.h"
#include "ProphecyLowerTempering.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"
#include "ProphecyBlendClock.h"

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
        if (Value->IsIdentity())
        { Returns.Remove(Agent);ProphecyBlendClock::Stop(Agent,ProphecyBlendClock::EKind::Tempering); }
    }
    auto SamplePart=[&](auto& Timelines,bool Feet,ProphecyBlendClock::EKind Kind)
    {
        auto* Return=Timelines.IsEmpty() ? nullptr : Timelines.Find(Agent);
        if (!Return) return;
        Return->Elapsed+=ProphecyBlendClock::Consume(Agent,Kind);
        const auto Sample=Return->Sample();
        if (Feet) { Value->FeetTranslation=Sample.FeetTranslation;Value->FeetTranslationZ=Sample.FeetTranslationZ;Value->FeetRotation=Sample.FeetRotation; }
        else { Value->PelvisTranslation=Sample.PelvisTranslation;Value->PelvisTranslationZ=Sample.PelvisTranslationZ;Value->PelvisRotation=Sample.PelvisRotation; }
        const bool Done=Feet ? Value->FeetTranslation==1 && Value->FeetTranslationZ==1 && Value->FeetRotation==1
            : Value->PelvisTranslation==1 && Value->PelvisTranslationZ==1 && Value->PelvisRotation==1;
        if (Done) { Timelines.Remove(Agent);ProphecyBlendClock::Stop(Agent,Kind); }
    };
    SamplePart(FeetReturns,true,ProphecyBlendClock::EKind::FeetTempering);
    SamplePart(PelvisReturns,false,ProphecyBlendClock::EKind::PelvisTempering);
    if (Value->IsIdentity()) { Remove(Agent);return nullptr; }
    return Value;
}
void Remove(const AProphecyAgent* Agent)
{
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
    // Detach only this part from a pre-existing combined return. The other part
    // keeps exactly its old elapsed time, hold, duration and initial values.
    if (auto* Shared=Returns.Find(Agent))
    {
        if (Feet) Shared->Initial.FeetTranslation=Shared->Initial.FeetTranslationZ=Shared->Initial.FeetRotation=1;
        else Shared->Initial.PelvisTranslation=Shared->Initial.PelvisTranslationZ=Shared->Initial.PelvisRotation=1;
        if (Shared->Initial.IsIdentity())
        { Returns.Remove(Agent);ProphecyBlendClock::Stop(Agent,ProphecyBlendClock::EKind::Tempering); }
    }
    auto& Timelines=Feet ? FeetReturns : PelvisReturns;
    const auto Kind=Feet ? ProphecyBlendClock::EKind::FeetTempering : ProphecyBlendClock::EKind::PelvisTempering;
    const bool AlreadyNormal=Feet ? Initial.FeetTranslation==1 && Initial.FeetTranslationZ==1 && Initial.FeetRotation==1
        : Initial.PelvisTranslation==1 && Initial.PelvisTranslationZ==1 && Initial.PelvisRotation==1;
    if (AlreadyNormal || (Duration==0 && Hold==0))
    {
        Timelines.Remove(Agent);ProphecyBlendClock::Stop(Agent,Kind);
        auto& Value=Settings.FindChecked(Agent);
        if (Feet) Value.FeetTranslation=Value.FeetTranslationZ=Value.FeetRotation=1;
        else Value.PelvisTranslation=Value.PelvisTranslationZ=Value.PelvisRotation=1;
        if (Value.IsIdentity()) Remove(Agent);
        return true;
    }
    Timelines.Add(Agent,FReturnTimeline{Initial,Duration,Hold});
    ProphecyBlendClock::Start(Agent,Kind,double(Duration)+Hold);
    return true;
}
}

bool UProphecyLowerTemperingLibrary::SetLocomotionLowerBodyTempering(AProphecyAgent* Agent, bool Enabled,
    float FeetTranslation, float FeetTranslationZ, float FeetRotation,
    float PelvisTranslation, float PelvisTranslationZ, float PelvisRotation)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown) return false;
    using namespace ProphecyLowerTempering;
    if (!Enabled) { Remove(Agent); return true; }
    for (float V : {FeetTranslation, FeetRotation, PelvisTranslation, PelvisRotation, FeetTranslationZ, PelvisTranslationZ})
        if (!FMath::IsFinite(V) || V < 0.f || V > 1.f) return false;
    const FSettings Value{FeetTranslation, FeetRotation, PelvisTranslation, PelvisRotation, FeetTranslationZ, PelvisTranslationZ};
    if (Value.IsIdentity()) { Remove(Agent); return true; }
    if (!Cleanup.IsValid()) Cleanup = FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World, bool, bool)
    {
        for (auto It = Settings.CreateIterator(); It; ++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld() == World) It.RemoveCurrent();
        for (auto It = Returns.CreateIterator(); It; ++It)
            if (!It.Key().IsValid() || It.Key()->GetWorld() == World) It.RemoveCurrent();
        for (auto* Map : {&FeetReturns,&PelvisReturns})
            for (auto It=Map->CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
    });
    CancelReturns(Agent);
    Settings.Add(Agent, Value);
    return true;
}

bool UProphecyLowerTemperingLibrary::BlendLocomotionLowerBodyTemperingToNormal(
    AProphecyAgent* Agent,float DurationSeconds,float HoldDurationSeconds,float PelvisDurationSeconds,float PelvisHoldDurationSeconds)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown
        || !FMath::IsFinite(DurationSeconds) || DurationSeconds<0
        || !FMath::IsFinite(HoldDurationSeconds) || HoldDurationSeconds<0
        || !FMath::IsFinite(PelvisDurationSeconds) || PelvisDurationSeconds<0
        || !FMath::IsFinite(PelvisHoldDurationSeconds) || PelvisHoldDurationSeconds<0) return false;
    using namespace ProphecyLowerTempering;
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
    CancelReturns(Agent);
    Returns.Add(Agent,FReturnTimeline{Initial,DurationSeconds,HoldDurationSeconds});
    ProphecyBlendClock::Start(Agent,ProphecyBlendClock::EKind::Tempering,double(DurationSeconds)+HoldDurationSeconds);
    return true;
}

bool UProphecyLowerTemperingLibrary::BlendLocomotionFeetTemperingToNormal(
    AProphecyAgent* Agent,float DurationSeconds,float HoldDurationSeconds)
{ return ProphecyLowerTempering::BlendPart(Agent,true,DurationSeconds,HoldDurationSeconds); }

bool UProphecyLowerTemperingLibrary::BlendLocomotionPelvisTemperingToNormal(
    AProphecyAgent* Agent,float DurationSeconds,float HoldDurationSeconds)
{ return ProphecyLowerTempering::BlendPart(Agent,false,DurationSeconds,HoldDurationSeconds); }

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
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
    TestEqual(TEXT("Exactly Set and Blend exposed in the Blueprint menu"),VisibleNodes,2);
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
#endif
