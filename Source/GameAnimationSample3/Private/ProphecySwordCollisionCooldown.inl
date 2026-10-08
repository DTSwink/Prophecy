// Included by the sword implementation: event-driven configuration/qualification,
// with a world callback only while at least one cooldown is counting down.
namespace ProphecySwordCooldown
{
using FKey=TWeakObjectPtr<const AProphecyAgent>;
struct FCountdown { int32 Remaining=4; uint64 LastFrame=0; };
static TMap<FKey,int32> Config;
static TMap<FKey,int32> MeleeGapThresholds;
static TMap<FKey,FCountdown> Active;
static TSet<FKey> Slash,Qualified;
static FDelegateHandle TickHandle,CleanupHandle;
static void RefreshSubscription();
static int32 Duration(const AProphecyAgent* A)
{ const auto* T=Config.Find(A);return T?*T:4; }
static int32 MeleeGapThreshold(const AProphecyAgent* A)
{ const auto* T=MeleeGapThresholds.Find(A);return T?*T:2; }
static void Advance(UWorld* World,uint64 Frame)
{
    TArray<TWeakObjectPtr<AProphecyAgent>,TInlineAllocator<8>> Expired;
    for(auto It=Active.CreateIterator();It;++It)
    {
        auto* A=It.Key().Get();
        if(!A || A->IsActorBeingDestroyed()){It.RemoveCurrent();continue;}
        auto& C=It.Value();
        if(A->GetWorld()!=World || C.LastFrame==Frame)continue;
        C.LastFrame=Frame;
        if(--C.Remaining==0){Expired.Add(const_cast<AProphecyAgent*>(A));It.RemoveCurrent();}
    }
    for(const auto& A:Expired)if(A.IsValid())ProphecySwordAttackCollision::Refresh(A.Get());
    RefreshSubscription();
}
static void Tick(UWorld* World,ELevelTick Type,float Dt)
{
    if(World && !World->IsPaused() && Type==LEVELTICK_All && Dt>0)Advance(World,GFrameCounter);
}
static void Cleanup(UWorld* World,bool,bool)
{
    for(auto It=Config.CreateIterator();It;++It)if(!It.Key().IsValid() || It.Key()->GetWorld()==World)It.RemoveCurrent();
    for(auto It=MeleeGapThresholds.CreateIterator();It;++It)if(!It.Key().IsValid() || It.Key()->GetWorld()==World)It.RemoveCurrent();
    for(auto It=Active.CreateIterator();It;++It)if(!It.Key().IsValid() || It.Key()->GetWorld()==World)It.RemoveCurrent();
    for(auto It=Slash.CreateIterator();It;++It)if(!It->IsValid() || It->Get()->GetWorld()==World)It.RemoveCurrent();
    for(auto It=Qualified.CreateIterator();It;++It)if(!It->IsValid() || It->Get()->GetWorld()==World)It.RemoveCurrent();
    RefreshSubscription();
}
static void RefreshSubscription()
{
    if(Active.IsEmpty()){FWorldDelegates::OnWorldPostActorTick.Remove(TickHandle);TickHandle.Reset();}
    else if(!TickHandle.IsValid())TickHandle=FWorldDelegates::OnWorldPostActorTick.AddStatic(&Tick);
    const bool Any=!Config.IsEmpty() || !MeleeGapThresholds.IsEmpty() || !Active.IsEmpty() || !Slash.IsEmpty() || !Qualified.IsEmpty();
    if(Any && !CleanupHandle.IsValid())CleanupHandle=FWorldDelegates::OnWorldCleanup.AddStatic(&Cleanup);
    else if(!Any){FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);CleanupHandle.Reset();}
}
static void Family(AProphecyAgent* A,FName Name,bool Armed)
{
    if(Name.ToString().StartsWith(TEXT("slash"),ESearchCase::IgnoreCase))
    { Slash.Add(A);if(Armed)Qualified.Add(A); }
    else Slash.Remove(A);
    RefreshSubscription();
}
static void Armed(AProphecyAgent* A)
{ if(Slash.Contains(A))Qualified.Add(A); }
static void Start(AProphecyAgent* A)
{
    const int32 Ticks=Duration(A);
    if(Ticks>0)Active.Add(A,FCountdown{Ticks,GFrameCounter});
    RefreshSubscription();
}
static void End(AProphecyAgent* A)
{
    Slash.Remove(A);
    if(Qualified.Remove(A) && IsValid(A) && !A->IsActorBeingDestroyed() && A->GetHeldSword())Start(A);
    else RefreshSubscription();
}
static void Cancel(AProphecyAgent* A)
{ Active.Remove(A);Slash.Remove(A);Qualified.Remove(A);RefreshSubscription(); }
static void Remove(AProphecyAgent* A)
{ Config.Remove(A);MeleeGapThresholds.Remove(A);Cancel(A); }
}

bool UProphecySwordPhysicsLibrary::SetSwordCollisionMeleeGapThreshold(AProphecyAgent* Agent,int32 Ticks)
{
    if(!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld()
        || Agent->GetWorld()->bIsTearingDown || Ticks<0)return false;
    using namespace ProphecySwordCooldown;
    if(Ticks==2)MeleeGapThresholds.Remove(Agent);else MeleeGapThresholds.Add(Agent,Ticks);
    RefreshSubscription();return true;
}

bool UProphecySwordPhysicsLibrary::SetSwordCollisionCooldown(AProphecyAgent* Agent,int32 Ticks)
{
    if(!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld()
        || Agent->GetWorld()->bIsTearingDown || Ticks<0)return false;
    using namespace ProphecySwordCooldown;
    if(Ticks==4)Config.Remove(Agent);else Config.Add(Agent,Ticks);
    if(Ticks==0){Active.Remove(Agent);ProphecySwordAttackCollision::Refresh(Agent);}
    RefreshSubscription();return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySwordCooldownTest,"Prophecy.Jolt.Sword.CooldownTicks",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecySwordCooldownTest::RunTest(const FString&)
{
    using namespace ProphecySwordCooldown;
    auto* World=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=World?World->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    auto* B=World->SpawnActor<AProphecyAgent>();
    using L=UProphecySwordPhysicsLibrary;
    TestEqual(TEXT("Default melee gap threshold is two ticks"),MeleeGapThreshold(A),2);
    TestTrue(TEXT("Gap threshold configurable before equip"),L::SetSwordCollisionMeleeGapThreshold(A,7));
    TestFalse(TEXT("Negative gap threshold rejected"),L::SetSwordCollisionMeleeGapThreshold(A,-1));
    TestEqual(TEXT("Invalid threshold retains prior setting"),MeleeGapThreshold(A),7);
    Cancel(A);TestEqual(TEXT("Reset/drop retain configured threshold"),MeleeGapThreshold(A),7);
    TestEqual(TEXT("Gap threshold is per agent"),MeleeGapThreshold(B),2);
    TestEqual(TEXT("Default four ticks"),Duration(A),4);
    Family(A,TEXT("slashL"),false);TestFalse(TEXT("Unarmed slash not qualified"),Qualified.Contains(A));
    Armed(A);TestTrue(TEXT("Armed slash qualifies"),Qualified.Contains(A));
    Cancel(A);Family(A,TEXT("pike"),true);Armed(A);TestFalse(TEXT("Pike excluded"),Qualified.Contains(A));
    Cancel(A);Start(A);const uint64 First=Active.FindChecked(A).LastFrame;
    Advance(World,First);TestEqual(TEXT("End frame not charged"),Active.FindChecked(A).Remaining,4);
    Tick(World,LEVELTICK_TimeOnly,.01f);Tick(World,LEVELTICK_All,0);
    TestEqual(TEXT("Non-game and zero-delta ticks ignored"),Active.FindChecked(A).Remaining,4);
    for(int32 I=1;I<=3;++I){Advance(World,First+I);Advance(World,First+I);}
    TestEqual(TEXT("Three distinct ticks leave one; duplicate calls ignored"),Active.FindChecked(A).Remaining,1);
    TestFalse(TEXT("Other agent isolated"),Active.Contains(B));
    Advance(World,First+4);TestFalse(TEXT("Expires after four complete ticks"),Active.Contains(A));
    TestFalse(TEXT("No dormant callback"),TickHandle.IsValid());
    Start(A);L::SetSwordCollisionCooldown(A,12);
    TestEqual(TEXT("Positive edit leaves running budget"),Active.FindChecked(A).Remaining,4);
    TestFalse(TEXT("Negative rejected"),L::SetSwordCollisionCooldown(A,-1));
    TestEqual(TEXT("Invalid edit retains setting"),Duration(A),12);
    L::SetSwordCollisionCooldown(A,0);TestFalse(TEXT("Zero cancels immediately"),Active.Contains(A));
    Start(A);TestFalse(TEXT("Zero disables future cooldown"),Active.Contains(A));
    L::SetSwordCollisionCooldown(A,4);Start(A);Advance(World,First+1);Start(A);
    TestEqual(TEXT("New qualified end refreshes full budget"),Active.FindChecked(A).Remaining,4);
    Family(A,TEXT("slashRD"),true);Cancel(A);
    TestTrue(TEXT("Drop/reset clears cooldown and qualification"),!Active.Contains(A)&&!Qualified.Contains(A)&&!Slash.Contains(A));
    Start(A);Cleanup(World,false,false);
    TestFalse(TEXT("World cleanup clears threshold overrides"),MeleeGapThresholds.Contains(A));
    TestTrue(TEXT("Cleanup removes sparse state and callback"),!Active.Contains(A)&&!Config.Contains(A)&&!TickHandle.IsValid());
    World->DestroyWorld(false);return !HasAnyErrors();
}
#endif
