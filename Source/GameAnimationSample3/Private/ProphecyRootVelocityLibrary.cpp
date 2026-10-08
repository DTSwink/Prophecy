#include "ProphecyRootVelocityLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "ProphecyRootVelocityDelay.h"
#include "ProphecyBlendClock.h"
#include "Engine/World.h"
#include "EngineUtils.h"

namespace
{
bool SetVelocity(AProphecyAgent* Agent,const FVector& Value,bool Angular,bool Add)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || Value.ContainsNaN() || !Agent->GetWorld() || !Agent->HasValidAgentHandle()) return false;
    for (TActorIterator<AProphecyNNLocomotionManager> It(Agent->GetWorld());It;++It)
        if (It->ResolveAgent(Agent->GetAgentHandle())==Agent)
            return It->SetAgentRootVelocity(Agent->GetAgentHandle(),Value,Angular,Add);
    return false;
}
}
namespace ProphecyRootVelocityDelay
{
struct FRequest
{
    TWeakObjectPtr<AProphecyAgent> Agent;
    FVector Value;
    bool Angular, Add;
    uint64 Remaining, LastFrame;
    int32 SpreadRemaining=0;
    FVector RemainingImpulse=FVector::ZeroVector;
};
using FDue = TArray<FRequest,TInlineAllocator<8>>;
static TArray<FRequest> Pending;
static FDelegateHandle TickHandle, CleanupHandle;
static void Refresh();
static void Collect(UWorld* World,ELevelTick TickType,float Delta,uint64 Frame,FDue& Due)
{
    if (!World || World->IsPaused() || TickType!=LEVELTICK_All || !FMath::IsFinite(Delta) || Delta<=0) return;
    // Stable removal retains call order, including multiple requests due on the same tick.
    Pending.RemoveAll([&](FRequest& R)
    {
        auto* A=R.Agent.Get();
        if (!A || A->IsActorBeingDestroyed()) return true;
        if (A->GetWorld()==World && R.LastFrame!=Frame)
        {
            R.LastFrame=Frame;
            if (--R.Remaining==0)
            {
                auto& Part=Due.Add_GetRef(R);
                if (R.SpreadRemaining>0)
                {
                    // Use the residual on the final tick so division rounding cannot
                    // accumulate into an over/under-sized total requested impulse.
                    if (R.SpreadRemaining==1) Part.Value=R.RemainingImpulse;
                    R.RemainingImpulse-=Part.Value;
                    R.Remaining=1;
                    return --R.SpreadRemaining==0;
                }
                return true;
            }
        }
        return false;
    });
    Refresh();
}
static void Tick(UWorld* World,ELevelTick TickType,float Delta)
{
    FDue Due;
    Collect(World,TickType,Delta,GFrameCounter,Due);
    for (const auto& R:Due)
        SetVelocity(R.Agent.Get(),R.Value,R.Angular,R.Add);
}
static void Cleanup(UWorld* World,bool,bool)
{
    Pending.RemoveAll([&](const FRequest& R){return !R.Agent.IsValid() || R.Agent->GetWorld()==World;});
    Refresh();
}
static void Refresh()
{
    if (Pending.IsEmpty())
    {
        FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle); TickHandle.Reset();
        FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle); CleanupHandle.Reset();
    }
    else
    {
        if (!TickHandle.IsValid()) TickHandle=FWorldDelegates::OnWorldPreActorTick.AddStatic(&Tick);
        if (!CleanupHandle.IsValid()) CleanupHandle=FWorldDelegates::OnWorldCleanup.AddStatic(&Cleanup);
    }
}
static bool Submit(AProphecyAgent* Agent,const FVector& Value,bool Angular,bool Add,float Delay)
{
    if (!FMath::IsFinite(Delay) || Delay<0) return false;
    if (Delay==0) return SetVelocity(Agent,Value,Angular,Add);
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || Value.ContainsNaN()) return false;
    const auto* World=Agent->GetWorld();
    if (!World || !World->IsGameWorld() || World->bIsTearingDown) return false;
    const uint64 Ticks=uint64(FMath::Max(1.,FMath::CeilToDouble(FMath::Min(double(Delay)/ProphecyBlendClock::TickSeconds,9.e15)-1.e-5)));
    Pending.Add({Agent,Value,Angular,Add,Ticks,GFrameCounter});
    Refresh();
    return true;
}
void Cancel(const AProphecyAgent* Agent)
{
    if (Pending.IsEmpty()) return;
    Pending.RemoveAll([&](const FRequest& R){return R.Agent==Agent;});
    Refresh();
}
static void QueueSpread(AProphecyAgent* Agent,const FVector& Total,const FVector& Part,bool Angular,int32 Ticks)
{
    Pending.Add({Agent,Part,Angular,true,1,GFrameCounter,Ticks-1,Total-Part});
    Refresh();
}
static bool Spread(AProphecyAgent* Agent,const FVector& Value,bool Angular,int32 Ticks,float Delay)
{
    if (Ticks<1 || !FMath::IsFinite(Delay) || Delay<0) return false;
    if (Ticks==1) return Submit(Agent,Value,Angular,true,Delay);
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || Value.ContainsNaN()) return false;
    const auto* World=Agent->GetWorld();
    if (!World || !World->IsGameWorld() || World->bIsTearingDown) return false;
    const FVector Part=Value/double(Ticks);
    if (Delay>0)
    {
        const uint64 Wait=uint64(FMath::Max(1.,FMath::CeilToDouble(FMath::Min(double(Delay)/ProphecyBlendClock::TickSeconds,9.e15)-1.e-5)));
        Pending.Add({Agent,Part,Angular,true,Wait,GFrameCounter,Ticks,Value});
        Refresh();return true;
    }
    if (!SetVelocity(Agent,Part,Angular,true)) return false;
    if (!Value.IsZero()) QueueSpread(Agent,Value,Part,Angular,Ticks);
    return true;
}
}
bool UProphecyRootVelocityLibrary::SetRootVelocity(AProphecyAgent* Agent,FVector WorldVelocity,bool bAddToCurrent,float Delay)
{ return ProphecyRootVelocityDelay::Submit(Agent,WorldVelocity,false,bAddToCurrent,Delay); }
bool UProphecyRootVelocityLibrary::SetRootAngVelocity(AProphecyAgent* Agent,FVector WorldAngularVelocityDegrees,bool bAddToCurrent,float Delay)
{ return ProphecyRootVelocityDelay::Submit(Agent,WorldAngularVelocityDegrees,true,bAddToCurrent,Delay); }
bool UProphecyRootVelocityLibrary::AddRootSpreadVelocity(AProphecyAgent* Agent,FVector WorldVelocity,int32 SpreadTicks,float Delay)
{ return ProphecyRootVelocityDelay::Spread(Agent,WorldVelocity,false,SpreadTicks,Delay); }
bool UProphecyRootVelocityLibrary::AddRootSpreadAngVelocity(AProphecyAgent* Agent,FVector WorldAngularVelocityDegrees,int32 SpreadTicks,float Delay)
{ return ProphecyRootVelocityDelay::Spread(Agent,WorldAngularVelocityDegrees,true,SpreadTicks,Delay); }

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include <limits>
#include "ProphecyAgentResetPhysics.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRootVelocitySpreadTest,"Prophecy.Root.VelocitySpread",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyRootVelocitySpreadTest::RunTest(const FString&)
{
    using namespace ProphecyRootVelocityDelay;
    using L=UProphecyRootVelocityLibrary;
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false);
    if (!TestNotNull(TEXT("World"),World)) return false;
    auto* A=World->SpawnActor<AProphecyAgent>();
    auto* B=World->SpawnActor<AProphecyAgent>();
    ON_SCOPE_EXIT { Cancel(A);Cancel(B);World->DestroyWorld(false); };
    if (!A || !B) return false;
    A->bAutoEnsureStandaloneNNManager=false;B->bAutoEnsureStandaloneNNManager=false;
    TestFalse(TEXT("Zero tick count rejected"),L::AddRootSpreadVelocity(A,FVector(1,2,0),0));
    TestFalse(TEXT("One tick retains immediate setter initialization guard"),L::AddRootSpreadVelocity(A,FVector(1,2,0),1));
    TestFalse(TEXT("Unavailable first installment queues nothing"),L::AddRootSpreadAngVelocity(A,FVector(0,0,90),4));
    TestFalse(TEXT("Rejected request absent"),Pending.ContainsByPredicate([&](const FRequest& R){return R.Agent==A;}));
    for(float FPS:{30.f,60.f,120.f}) for(int32 Count:{2,3,60})
    {
        A->CustomTimeDilation=.2f;
        const FVector Total(100,37,0),Turn(0,0,-83),Part=Total/double(Count),AngularPart=Turn/double(Count);
        FVector Sum=Part,AngularSum=AngularPart;
        QueueSpread(A,Total,Part,false,Count);QueueSpread(B,Turn,AngularPart,true,Count);
        FDue Due;const uint64 Start=GFrameCounter;
        Collect(World,LEVELTICK_All,1/FPS,Start,Due);
        TestTrue(TEXT("Enqueue frame cannot consume the second installment"),Due.IsEmpty());
        for(int32 I=1;I<Count;++I)
        {
            Collect(World,LEVELTICK_PauseTick,1/FPS,Start+I,Due);
            Collect(World,LEVELTICK_All,0,Start+I,Due);
            TestTrue(TEXT("Pause/zero delta do not deliver"),Due.IsEmpty());
            Collect(World,LEVELTICK_All,1/FPS,Start+I,Due);
            TestEqual(TEXT("One installment per channel per tick"),Due.Num(),2);
            if(Due.Num()!=2)return false;
            TestTrue(TEXT("FIFO additive channels preserved"),Due[0].Agent==A&&!Due[0].Angular&&Due[0].Add&&Due[1].Agent==B&&Due[1].Angular&&Due[1].Add);
            Sum+=Due[0].Value;AngularSum+=Due[1].Value;Due.Reset();
            Collect(World,LEVELTICK_All,1/FPS,Start+I,Due);
            TestTrue(TEXT("Duplicate frame delivers nothing"),Due.IsEmpty());
        }
        TestTrue(TEXT("Total linear impulse conserved"),Sum.Equals(Total,1.e-10));
        TestTrue(TEXT("Total angular impulse conserved"),AngularSum.Equals(Turn,1.e-10));
        Collect(World,LEVELTICK_All,1/FPS,Start+Count,Due);
        TestTrue(TEXT("Nothing after completion"),Due.IsEmpty());
    }
    QueueSpread(A,FVector(6,0,0),FVector(2,0,0),false,3);
    QueueSpread(A,FVector(0,0,9),FVector(0,0,3),true,3);
    QueueSpread(B,FVector(9,0,0),FVector(3,0,0),false,3);
    ProphecyAgentResetPhysics::CancelBlends(A);
    FDue Due;Collect(World,LEVELTICK_All,.016f,GFrameCounter+1,Due);
    TestTrue(TEXT("Reset removes both channels only for reset agent"),Due.Num()==1&&Due[0].Agent==B);
    Cleanup(World,false,false);
    TestFalse(TEXT("World cleanup removes residual installments"),Pending.ContainsByPredicate([&](const FRequest& R){return R.Agent==A||R.Agent==B;}));
    if(Pending.IsEmpty())TestTrue(TEXT("No idle callbacks"),!TickHandle.IsValid()&&!CleanupHandle.IsValid());
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRootVelocityDelayTest,"Prophecy.Root.VelocityDelay",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyRootVelocityDelayTest::RunTest(const FString&)
{
    using namespace ProphecyRootVelocityDelay;
    using L=UProphecyRootVelocityLibrary;
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false);
    if (!TestNotNull(TEXT("World"),World)) return false;
    auto* A=World->SpawnActor<AProphecyAgent>();
    auto* B=World->SpawnActor<AProphecyAgent>();
    ON_SCOPE_EXIT { Cancel(A);Cancel(B);World->DestroyWorld(false); };
    if (!A || !B) return false;
    A->bAutoEnsureStandaloneNNManager=false;B->bAutoEnsureStandaloneNNManager=false;
    FDue Due;
    for (float FPS:{30.f,60.f,120.f})
    {
        A->CustomTimeDilation=.2f;
        TestTrue(TEXT("Linear delayed request accepted"),L::SetRootVelocity(A,FVector(100,200,0),false,1));
        TestTrue(TEXT("Angular additive request accepted"),L::SetRootAngVelocity(A,FVector(0,0,90),true,1));
        const uint64 Start=GFrameCounter;
        Collect(World,LEVELTICK_All,1/FPS,Start,Due);
        TestTrue(TEXT("Enqueue frame does not consume a tick"),Due.IsEmpty());
        for (uint64 I=1;I<60;++I) Collect(World,LEVELTICK_All,1/FPS,Start+I,Due);
        TestTrue(TEXT("Not due before 60 ticks regardless of FPS/dilation"),Due.IsEmpty());
        Collect(World,LEVELTICK_All,1/FPS,Start+59,Due);
        Collect(World,LEVELTICK_PauseTick,1/FPS,Start+60,Due);
        Collect(World,LEVELTICK_TimeOnly,1/FPS,Start+60,Due);
        Collect(World,LEVELTICK_All,0,Start+60,Due);
        TestTrue(TEXT("Duplicate/paused/non-game/zero-delta calls do not advance"),Due.IsEmpty());
        Collect(World,LEVELTICK_All,1/FPS,Start+60,Due);
        TestEqual(TEXT("Both channels due exactly at 60 ticks"),Due.Num(),2);
        if (Due.Num()==2)
        {
            TestTrue(TEXT("FIFO overwrite retains exact requested vector"),!Due[0].Angular&&!Due[0].Add&&Due[0].Value==FVector(100,200,0));
            TestTrue(TEXT("Additive remains an operation until dispatch, not a captured velocity"),Due[1].Angular&&Due[1].Add&&Due[1].Value==FVector(0,0,90));
        }
        Due.Reset();
    }
    TestFalse(TEXT("Negative delay rejected"),L::SetRootVelocity(A,FVector::ZeroVector,false,-1));
    TestFalse(TEXT("Zero delay retains immediate initialization guard"),L::SetRootVelocity(A,FVector::ZeroVector));
    L::SetRootVelocity(A,FVector(1,0,0),true,.1f);
    for (uint64 I=1;I<=6;++I) Collect(World,LEVELTICK_All,.01f,GFrameCounter+I,Due);
    TestEqual(TEXT("Float .1 seconds rounds to six ticks"),Due.Num(),1);Due.Reset();
    L::SetRootAngVelocity(A,FVector(0,0,1),false,.001f);
    Collect(World,LEVELTICK_All,.1f,GFrameCounter+1,Due);
    TestEqual(TEXT("Positive sub-tick delay uses one tick"),Due.Num(),1);Due.Reset();
    L::SetRootVelocity(A,FVector(1,0,0),false,.001f);
    L::SetRootVelocity(B,FVector(2,0,0),true,.001f);
    ProphecyAgentResetPhysics::CancelBlends(A);
    Collect(World,LEVELTICK_All,.1f,GFrameCounter+1,Due);
    TestTrue(TEXT("Reset cancels only its agent's requests"),Due.Num()==1&&Due[0].Agent==B);Due.Reset();
    L::SetRootVelocity(A,FVector(1,0,0),false,1);
    L::SetRootAngVelocity(B,FVector(0,0,1),true,1);
    Cleanup(World,false,false);
    TestFalse(TEXT("World cleanup removes requests"),Pending.ContainsByPredicate([&](const FRequest& R){return R.Agent==A||R.Agent==B;}));
    if (Pending.IsEmpty()) TestTrue(TEXT("No hooks when queue empty"),!TickHandle.IsValid()&&!CleanupHandle.IsValid());
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRootVelocitySpreadDelayTest,"Prophecy.Root.VelocitySpreadDelay",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyRootVelocitySpreadDelayTest::RunTest(const FString&)
{
    using namespace ProphecyRootVelocityDelay;using L=UProphecyRootVelocityLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Game,false);auto* A=W->SpawnActor<AProphecyAgent>();
    ON_SCOPE_EXIT {Cancel(A);W->DestroyWorld(false);};
    A->bAutoEnsureStandaloneNNManager=false;A->CustomTimeDilation=.2f;
    const FVector Linear(100,37,0),Angular(0,0,-83);
    TestFalse(TEXT("Negative spread delay rejected"),L::AddRootSpreadVelocity(A,Linear,3,-1));
    TestFalse(TEXT("Nonfinite spread delay rejected"),L::AddRootSpreadAngVelocity(A,Angular,3,std::numeric_limits<float>::infinity()));
    for(float FPS:{30.f,60.f,120.f})for(int32 Count:{1,3,60})
    {
        TestTrue(TEXT("Queue delayed linear spread before initialization"),L::AddRootSpreadVelocity(A,Linear,Count,.1f));
        TestTrue(TEXT("Queue delayed angular spread before initialization"),L::AddRootSpreadAngVelocity(A,Angular,Count,.1f));
        FVector Sum=FVector::ZeroVector,Turn=FVector::ZeroVector;FDue Due;const uint64 Start=GFrameCounter;
        Collect(W,LEVELTICK_All,1/FPS,Start,Due);TestTrue(TEXT("No impulse on enqueue frame"),Due.IsEmpty());
        for(int I=1;I<=6+Count;++I)
        {
            Collect(W,LEVELTICK_PauseTick,1/FPS,Start+I,Due);Collect(W,LEVELTICK_All,0,Start+I,Due);
            TestTrue(TEXT("Pause and zero delta preserve delay/spread"),Due.IsEmpty());
            Collect(W,LEVELTICK_All,1/FPS,Start+I,Due);
            const bool Deliver=I>=6 && I<6+Count;
            TestEqual(TEXT("Six tick delay then exactly Count consecutive installments"),Due.Num(),Deliver?2:0);
            if(Deliver && Due.Num()==2)
            {
                TestTrue(TEXT("Both channels remain add-to-current at dispatch"),Due[0].Add&&!Due[0].Angular&&Due[1].Add&&Due[1].Angular);
                Sum+=Due[0].Value;Turn+=Due[1].Value;
            }
            Due.Reset();Collect(W,LEVELTICK_All,1/FPS,Start+I,Due);TestTrue(TEXT("Duplicate frame ignored"),Due.IsEmpty());
        }
        TestTrue(TEXT("Delayed total linear impulse conserved"),Sum.Equals(Linear,1.e-10));
        TestTrue(TEXT("Delayed total angular impulse conserved"),Turn.Equals(Angular,1.e-10));
    }
    L::AddRootSpreadVelocity(A,Linear,3,.001f);L::AddRootSpreadAngVelocity(A,Angular,3,.001f);
    FDue Due;Collect(W,LEVELTICK_All,.016f,GFrameCounter+1,Due);
    TestEqual(TEXT("Positive sub-tick delay delivers first part on next tick"),Due.Num(),2);Due.Reset();
    ProphecyAgentResetPhysics::CancelBlends(A);Collect(W,LEVELTICK_All,.016f,GFrameCounter+2,Due);
    TestTrue(TEXT("Reset cancels remaining delayed spread"),Due.IsEmpty());
    L::AddRootSpreadVelocity(A,Linear,3,1);ProphecyAgentResetPhysics::CancelBlends(A);
    TestFalse(TEXT("Reset cancels before first installment"),Pending.ContainsByPredicate([&](const FRequest& R){return R.Agent==A;}));
    if(Pending.IsEmpty())TestTrue(TEXT("No idle callbacks"),!TickHandle.IsValid()&&!CleanupHandle.IsValid());
    return !HasAnyErrors();
}
#endif
