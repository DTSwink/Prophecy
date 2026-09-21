#include "ProphecyBlendClock.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"

namespace ProphecyBlendClock
{
struct FKey
{
    TWeakObjectPtr<const AProphecyAgent> Agent;
    EKind Kind;
    bool operator==(const FKey& Other) const { return Agent==Other.Agent && Kind==Other.Kind; }
    friend uint32 GetTypeHash(const FKey& Key) { return HashCombine(GetTypeHash(Key.Agent),uint32(Key.Kind)); }
};
struct FClock { uint64 PendingTicks=0,TotalTicks=0,LimitTicks=0; };
static TMap<FKey,FClock> Active;
// Finished, unread values have no ticking work (e.g. tempering during an attack).
static TMap<FKey,uint64> Finished;
static FDelegateHandle TickHandle,CleanupHandle;
static void Refresh();
static void Advance(UWorld* World,ELevelTick TickType,float DeltaSeconds)
{
    if (!World || World->IsPaused() || TickType!=LEVELTICK_All || DeltaSeconds<=0) return;
    for (auto It=Active.CreateIterator();It;++It)
    {
        const auto* Agent=It.Key().Agent.Get();
        if (!Agent || Agent->IsActorBeingDestroyed()) { It.RemoveCurrent();continue; }
        if (Agent->GetWorld()==World)
        {
            auto& Clock=It.Value();++Clock.PendingTicks;++Clock.TotalTicks;
            if (Clock.LimitTicks && Clock.TotalTicks>=Clock.LimitTicks)
            { Finished.Add(It.Key(),Clock.PendingTicks);It.RemoveCurrent(); }
        }
    }
    if (Active.IsEmpty()) Refresh();
}
static void Refresh()
{
    if (Active.IsEmpty())
    {
        FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle);TickHandle.Reset();
    }
    else if (!TickHandle.IsValid())
    {
        TickHandle=FWorldDelegates::OnWorldPreActorTick.AddStatic(&Advance);
    }
    if (Active.IsEmpty() && Finished.IsEmpty())
    { FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);CleanupHandle.Reset(); }
    else if (!CleanupHandle.IsValid())
        CleanupHandle=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
        {
            for (auto It=Active.CreateIterator();It;++It)
                if (!It.Key().Agent.IsValid() || It.Key().Agent->GetWorld()==World) It.RemoveCurrent();
            for (auto It=Finished.CreateIterator();It;++It)
                if (!It.Key().Agent.IsValid() || It.Key().Agent->GetWorld()==World) It.RemoveCurrent();
            Refresh();
        });
}
void Start(const AProphecyAgent* Agent,EKind Kind,double DurationSeconds)
{
    Finished.Remove({Agent,Kind});
    FClock Clock;
    if (DurationSeconds>0)
        Clock.LimitTicks=uint64(FMath::Max(1.,FMath::CeilToDouble(FMath::Min(DurationSeconds*60.,9.e15)-1.e-5)));
    Active.Add({Agent,Kind},Clock);Refresh();
}
void Ensure(const AProphecyAgent* Agent,EKind Kind)
{ if (Finished.IsEmpty() || !Finished.Contains({Agent,Kind})) Active.FindOrAdd({Agent,Kind});Refresh(); }
double Consume(const AProphecyAgent* Agent,EKind Kind)
{
    auto* Clock=Active.IsEmpty() ? nullptr : Active.Find({Agent,Kind});
    if (!Clock)
    {
        uint64 Ticks=0;
        if (!Finished.IsEmpty() && Finished.RemoveAndCopyValue({Agent,Kind},Ticks)) Refresh();
        return double(Ticks)*TickSeconds;
    }
    const uint64 Ticks=Clock->PendingTicks;Clock->PendingTicks=0;
    return double(Ticks)*TickSeconds;
}
void Stop(const AProphecyAgent* Agent,EKind Kind)
{
    const bool RemovedActive=!Active.IsEmpty() && Active.Remove({Agent,Kind});
    const bool RemovedFinished=!Finished.IsEmpty() && Finished.Remove({Agent,Kind});
    if (RemovedActive || RemovedFinished) Refresh();
}
void Remove(const AProphecyAgent* Agent)
{
    if (Active.IsEmpty() && Finished.IsEmpty()) return;
    for (auto It=Active.CreateIterator();It;++It) if (It.Key().Agent==Agent) It.RemoveCurrent();
    for (auto It=Finished.CreateIterator();It;++It) if (It.Key().Agent==Agent) It.RemoveCurrent();
    Refresh();
}
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "ProphecyLowerTemperingLibrary.h"
#include "ProphecyLowerTempering.h"
#include "ProphecyAttackRecoveryLibrary.h"
#include "ProphecyAttackRecovery.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBlendTickClockTest,"Prophecy.Blends.SixtyTickClock",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBlendTickClockTest::RunTest(const FString&)
{
    using namespace ProphecyBlendClock;
    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* Agent=World ? World->SpawnActor<AProphecyAgent>() : nullptr;
    if (!Agent) return false;
    const int32 Before=Active.Num();
    for (float FPS : {30.f,60.f,120.f})
    {
        Agent->CustomTimeDilation=.25f;
        Start(Agent,EKind::KickBalance,1);
        for (int32 Tick=0;Tick<60;++Tick) Advance(World,LEVELTICK_All,1.f/FPS);
        TestEqual(TEXT("Kick balance clock uses 60 ticks regardless of FPS/dilation"),Consume(Agent,EKind::KickBalance),1.);
        Stop(Agent,EKind::KickBalance);
        Start(Agent,EKind::Tempering);
        double Total=0;
        for (int32 Tick=1;Tick<=60;++Tick)
        {
            Advance(World,LEVELTICK_All,1.f/FPS);
            // Emulate NN reads every second engine tick, including duplicate reads.
            if (Tick%2==0)
            {
                Total+=Consume(Agent,EKind::Tempering);
                TestEqual(TEXT("Repeated reads cannot advance time"),Consume(Agent,EKind::Tempering),0.);
            }
        }
        TestTrue(TEXT("Exactly one authored second per 60 ticks at every FPS"),FMath::IsNearlyEqual(Total,1.,1.e-12));
        Stop(Agent,EKind::Tempering);
        Start(Agent,EKind::Tempering,1);
        for (int32 Tick=0;Tick<60;++Tick) Advance(World,LEVELTICK_All,1.f/FPS);
        if (Before==0) TestFalse(TEXT("Elapsed timer stops even before consumer reads again"),TickHandle.IsValid());
        TestEqual(TEXT("Deferred final read keeps all 60 ticks"),Consume(Agent,EKind::Tempering),1.);

        UProphecyLowerTemperingLibrary::SetLocomotionLowerBodyTempering(Agent,true,0,1.f,0,0,1.f,0);
        UProphecyLowerTemperingLibrary::BlendLocomotionLowerBodyTemperingToNormal(Agent,1,.5f,1,.5f);
        UProphecyAttackRecoveryLibrary::SetAttackToLocomotionBlend(Agent,EProphecyRecoverySource::Run,.5f,1);
        ProphecyAttackRecovery::Begin(Agent);
        ProphecyAttackRecovery::FWeights Weights;
        ProphecyAttackRecovery::Step(Agent,1.f,Weights);
        for (int32 Tick=1;Tick<=90;++Tick)
        {
            Advance(World,LEVELTICK_All,1.f/FPS);
            ProphecyAttackRecovery::Step(Agent,1.f,Weights);
            const auto* Tempering=ProphecyLowerTempering::Find(Agent);
            if (Tick==30)
            {
                TestTrue(TEXT("30-tick tempering hold"),Tempering && Tempering->FeetTranslation==0);
                TestEqual(TEXT("30-tick recovery hold"),Weights.Pelvis,0.f);
            }
            if (Tick==60)
            {
                TestTrue(TEXT("Tempering halfway after 30 hold + 30 blend ticks"),Tempering && FMath::IsNearlyEqual(Tempering->FeetTranslation,.5f,1.e-5f));
                TestTrue(TEXT("Recovery halfway after 30 hold + 30 blend ticks"),FMath::IsNearlyEqual(Weights.Pelvis,.5f,1.e-5f));
            }
        }
        TestNull(TEXT("Tempering normal after 90 ticks"),ProphecyLowerTempering::Find(Agent));
        TestTrue(TEXT("Recovery normal after 90 ticks"),Weights.Pelvis==1 && Weights.Left==1 && Weights.Right==1);
        TestEqual(TEXT("Completed features retire their clocks"),Active.Num(),Before);
        ProphecyAttackRecovery::Remove(Agent);
    }
    TestEqual(TEXT("No retained inactive timer"),Active.Num(),Before);
    if (Before==0) TestFalse(TEXT("No dormant tick callback"),TickHandle.IsValid());
    World->DestroyWorld(false);
    return !HasAnyErrors();
}
#endif
