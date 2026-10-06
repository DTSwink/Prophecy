#include "ProphecyAgent.h"
#include "Engine/World.h"

namespace ProphecyStunned
{
using FKey=TWeakObjectPtr<AProphecyAgent>;
struct FState { uint64 Remaining=0,Serial=0; };
static TMap<FKey,FState> Active;
static uint64 NextSerial=0;
static FDelegateHandle TickHandle,CleanupHandle;
static void Refresh();

static void Advance(UWorld* World,ELevelTick TickType,float DeltaSeconds)
{
    if(!World || World->IsPaused() || TickType!=LEVELTICK_All || DeltaSeconds<=0)return;
    // Collect first: Blueprint expiry handlers may cancel/restart/destroy agents.
    TArray<TPair<FKey,uint64>,TInlineAllocator<8>> Expired;
    for(auto It=Active.CreateIterator();It;++It)
    {
        auto* Agent=It.Key().Get();
        if(!Agent || Agent->IsActorBeingDestroyed()){It.RemoveCurrent();continue;}
        if(Agent->GetWorld()==World && --It.Value().Remaining==0)
            Expired.Emplace(It.Key(),It.Value().Serial);
    }
    for(const auto& Due:Expired)
    {
        const auto* State=Active.Find(Due.Key);
        if(!State || State->Serial!=Due.Value)continue;
        Active.Remove(Due.Key);
        if(auto* Agent=Due.Key.Get();Agent && !Agent->IsActorBeingDestroyed())Agent->OnStunnedEnded();
    }
    Refresh();
}
static void Cleanup(UWorld* World,bool,bool)
{
    for(auto It=Active.CreateIterator();It;++It)
        if(!It.Key().IsValid() || It.Key()->GetWorld()==World)It.RemoveCurrent();
    Refresh();
}
static void Refresh()
{
    if(Active.IsEmpty())
    {
        FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle);TickHandle.Reset();
        FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);CleanupHandle.Reset();
    }
    else if(!TickHandle.IsValid())
    {
        TickHandle=FWorldDelegates::OnWorldPreActorTick.AddStatic(&Advance);
        CleanupHandle=FWorldDelegates::OnWorldCleanup.AddStatic(&Cleanup);
    }
}
}

bool AProphecyAgent::StartStunned(float DurationSeconds)
{
    if(!IsInGameThread() || IsActorBeingDestroyed() || !GetWorld() || GetWorld()->bIsTearingDown
        || !FMath::IsFinite(DurationSeconds) || DurationSeconds<0)return false;
    if(DurationSeconds==0)
    {
        DisableStunned();
        OnStunnedEnded();
        return true;
    }
    using namespace ProphecyStunned;
    // Match the established 60-tick duration convention and float-boundary tolerance.
    const uint64 Ticks=uint64(FMath::Max(1.,FMath::CeilToDouble(FMath::Min(double(DurationSeconds)*60.,9.e15)-1.e-5)));
    Active.Add(this,FState{Ticks,++NextSerial});Refresh();return true;
}
void AProphecyAgent::DisableStunned()
{
    if(!IsInGameThread())return;
    if(ProphecyStunned::Active.Remove(this))ProphecyStunned::Refresh();
}
bool AProphecyAgent::IsStunned() const
{ return ProphecyStunned::Active.Contains(const_cast<AProphecyAgent*>(this)); }

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Engine/Engine.h"
#include "Misc/ScopeExit.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyStunnedTest,"Prophecy.Agent.Stunned.TickDurationAndCancellation",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyStunnedTest::RunTest(const FString&)
{
    using namespace ProphecyStunned;
    const auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(true).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
        .CreateFXSystem(false).SetTransactional(false);
    auto* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);
    if(!TestNotNull(TEXT("World"),World))return false;
    if(GEngine)GEngine->CreateNewWorldContext(EWorldType::Game).SetCurrentWorld(World);
    auto* A=World->SpawnActor<AProphecyAgent>();
    ON_SCOPE_EXIT{if(A)A->DisableStunned();World->DestroyWorld(false);if(GEngine)GEngine->DestroyWorldContext(World);};
    if(!TestNotNull(TEXT("Agent"),A))return false;
    A->bAutoEnsureStandaloneNNManager=false;
    TestFalse(TEXT("Default off"),A->IsStunned());
    const int32 Before=Active.Num();
    const auto* Event=A->FindFunction(TEXT("OnStunnedEnded"));
    TestTrue(TEXT("Blueprint expiry event"),Event && Event->HasAnyFunctionFlags(FUNC_BlueprintEvent));
    for(float FPS:{30.f,60.f,120.f})
    {
        A->CustomTimeDilation=.25f;
        TestTrue(TEXT("Start accepted"),A->StartStunned(1));
        for(int I=0;I<59;++I)Advance(World,LEVELTICK_All,1/FPS);
        TestTrue(TEXT("Still stunned after59 ticks independent of FPS/dilation"),A->IsStunned());
        Advance(World,LEVELTICK_TimeOnly,1/FPS);Advance(World,LEVELTICK_All,0);
        TestTrue(TEXT("No progress on non-game or zero-delta ticks"),A->IsStunned());
        Advance(World,LEVELTICK_All,1/FPS);
        TestFalse(TEXT("Expires on60th tick"),A->IsStunned());
    }
    A->StartStunned(1);Advance(World,LEVELTICK_All,.01f);
    TestFalse(TEXT("Negative rejected"),A->StartStunned(-1));
    TestEqual(TEXT("Invalid request preserves countdown"),Active.FindChecked(A).Remaining,uint64(59));
    A->StartStunned(.01f);Advance(World,LEVELTICK_All,.1f);
    TestFalse(TEXT("Subtick duration rounds up to one tick and replaces previous"),A->IsStunned());
    A->StartStunned(.1f);for(int I=0;I<3;++I)Advance(World,LEVELTICK_All,.1f);
    A->StartStunned(.1f);for(int I=0;I<5;++I)Advance(World,LEVELTICK_All,.1f);
    TestTrue(TEXT("Restart gets a full new duration"),A->IsStunned());
    Advance(World,LEVELTICK_All,.1f);TestFalse(TEXT("Decimal duration expires at exact tick"),A->IsStunned());
    A->StartStunned(1);A->DisableStunned();Advance(World,LEVELTICK_All,.1f);
    TestFalse(TEXT("Manual cancel stays inactive"),A->IsStunned());
    A->StartStunned(0);TestFalse(TEXT("Zero duration expires immediately"),A->IsStunned());
    TestEqual(TEXT("No retained inactive entry"),Active.Num(),Before);
    if(Before==0)TestFalse(TEXT("No dormant timer callback"),TickHandle.IsValid());
    A->StartStunned(1);Cleanup(World,false,false);
    TestFalse(TEXT("World cleanup cancels stun"),A->IsStunned());
    return !HasAnyErrors();
}
#endif
