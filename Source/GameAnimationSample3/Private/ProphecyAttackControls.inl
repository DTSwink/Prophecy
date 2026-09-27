// Included by ProphecyGhostAttackLibrary.cpp; sparse state, no retained UObject layout changes.
namespace ProphecyAttackControls
{
struct FBoost { float Hold=0,Blend=0,Value=0; double Duration() const {return double(Hold)+Blend;} };
struct FReturn { FBoost Config; double Elapsed=0; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FBoost> Boosts,ResetBoosts;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FReturn> Returns;
static TSet<TWeakObjectPtr<const AProphecyAgent>> Blocked,ResetBlocked;
static TSet<TWeakObjectPtr<const AProphecyAgent>> FullAttackHeld;
static TMap<TWeakObjectPtr<const AProphecyAgent>,int64> SinceLowerAttack;
static FDelegateHandle ReturnTick;
static void RefreshTick();
static void Tick(UWorld* World,ELevelTick Type,float Dt)
{
    if(!World || World->IsPaused() || Type!=LEVELTICK_All || Dt<=0)return;
    for(auto It=SinceLowerAttack.CreateIterator();It;++It)
    {
        const auto* A=It.Key().Get();
        if(!A || A->IsActorBeingDestroyed()) {It.RemoveCurrent();continue;}
        if(A->GetWorld()==World && It.Value()<MAX_int64)++It.Value();
    }
    for(auto It=Returns.CreateIterator();It;++It)
    {
        const auto* A=It.Key().Get();
        if(!A || A->IsActorBeingDestroyed()) {It.RemoveCurrent();continue;}
        if(A->GetWorld()!=World)continue;
        auto& R=It.Value();R.Elapsed+=1./60.;
        if(R.Elapsed+1.e-6>=R.Config.Duration())It.RemoveCurrent();
    }
    RefreshTick();
}
static void RefreshTick()
{
    if(Returns.IsEmpty() && SinceLowerAttack.IsEmpty()) {FWorldDelegates::OnWorldPreActorTick.Remove(ReturnTick);ReturnTick.Reset();}
    else if(!ReturnTick.IsValid())ReturnTick=FWorldDelegates::OnWorldPreActorTick.AddStatic(&Tick);
}
bool ArmedBlocked(const AProphecyAgent* A) {return !Blocked.IsEmpty() && Blocked.Contains(A);}
void StartAttackTickCounter(const AProphecyAgent* A)
{
    if(FullAttackHeld.Contains(A) || SinceLowerAttack.Contains(A))return;
    SinceLowerAttack.Add(A,0);RefreshTick();
}
void FullAttackStarted(AProphecyAgent* A)
{
    UProphecyRootPhysicsLibrary::SetRootMagicVelocity(A,FVector::ZeroVector,false);
    UProphecyRootPhysicsLibrary::SetRootMagicAngVelocity(A,FVector::ZeroVector,false);
    UProphecyRootPhysicsLibrary::SetRootMagicVelocity2(A,FVector::ZeroVector,false);
    UProphecyRootPhysicsLibrary::SetRootMagicAngVelocity2(A,FVector::ZeroVector,false);
    SinceLowerAttack.Remove(A);FullAttackHeld.Add(A);RefreshTick();
}
void LowerAttackFinished(const AProphecyAgent* A)
{
    if(!FullAttackHeld.Remove(A))return;
    SinceLowerAttack.Add(A,0);RefreshTick();
}
void CancelLowerReturn(const AProphecyAgent* A)
{if(!Returns.IsEmpty() && Returns.Remove(A))RefreshTick();}
void BeginLowerReturn(const AProphecyAgent* A)
{
    const auto* Config=Boosts.IsEmpty()?nullptr:Boosts.Find(A);
    if(!Config)return;
    Returns.Add(A,FReturn{*Config});RefreshTick();
}
float RunBoost(const AProphecyAgent* A,float Normal)
{
    const auto* R=Returns.IsEmpty()?nullptr:Returns.Find(A);
    if(!R)return Normal;
    const float Alpha=R->Config.Blend>0 ? FMath::Clamp(float((R->Elapsed-R->Config.Hold)/R->Config.Blend),0.f,1.f) : 0.f;
    return FMath::Lerp(R->Config.Value,Normal,Alpha);
}
void ForgetReset(const AProphecyAgent* A) {ResetBoosts.Remove(A);ResetBlocked.Remove(A);}
void Remove(const AProphecyAgent* A)
{SinceLowerAttack.Remove(A);FullAttackHeld.Remove(A);CancelLowerReturn(A);RefreshTick();Boosts.Remove(A);Blocked.Remove(A);ForgetReset(A);}
void CaptureReset(const AProphecyAgent* A)
{
    if(const auto* B=Boosts.Find(A))ResetBoosts.Add(A,*B);else ResetBoosts.Remove(A);
    if(ArmedBlocked(A))ResetBlocked.Add(A);else ResetBlocked.Remove(A);
}
void RestoreReset(const AProphecyAgent* A)
{
    SinceLowerAttack.Remove(A);FullAttackHeld.Remove(A);StartAttackTickCounter(A);
    CancelLowerReturn(A);
    if(const auto* B=ResetBoosts.Find(A))Boosts.Add(A,*B);else Boosts.Remove(A);
    if(ResetBlocked.Contains(A))Blocked.Add(A);else Blocked.Remove(A);
}
}
int64 UProphecyGhostAttackLibrary::GetTicksSinceLastAttack(AProphecyAgent* Agent)
{
    if(!IsInGameThread() || !IsValid(Agent))return 0;
    const auto* T=ProphecyAttackControls::SinceLowerAttack.IsEmpty()?nullptr:ProphecyAttackControls::SinceLowerAttack.Find(Agent);
    // Existing actors may predate the BeginPlay hook after a Live Coding update.
    if(!T && Agent->HasActorBegunPlay() && !Agent->IsActorBeingDestroyed())
        ProphecyAttackControls::StartAttackTickCounter(Agent);
    return T?*T:0;
}
bool UProphecyGhostAttackLibrary::SetAttackArmedBlocked(AProphecyAgent* Agent,bool Blocked)
{
    if(!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown)return false;
    if(Blocked)ProphecyAttackControls::Blocked.Add(Agent);else ProphecyAttackControls::Blocked.Remove(Agent);
    return true;
}
bool UProphecyWalkPinningLibrary::SetAttackRecoveryRunPinningBoost(AProphecyAgent* Agent,bool Enabled,float HoldDurationSeconds,float BlendDurationSeconds,float Boost)
{
    using namespace ProphecyAttackControls;
    if(!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld() || Agent->GetWorld()->bIsTearingDown)return false;
    if(Enabled && (!FMath::IsFinite(HoldDurationSeconds) || HoldDurationSeconds<0 || !FMath::IsFinite(BlendDurationSeconds) || BlendDurationSeconds<0 || !FMath::IsFinite(Boost) || Boost<0 || Boost>1))return false;
    CancelLowerReturn(Agent);
    if(Enabled && (HoldDurationSeconds>0 || BlendDurationSeconds>0))Boosts.Add(Agent,FBoost{HoldDurationSeconds,BlendDurationSeconds,Boost});
    else Boosts.Remove(Agent);
    // The lower callback configures this handoff, even on its first invocation.
    // Outside that callback the node remains configuration for the next release.
    if(ProphecyAttackRecovery::IsLowerAttackEndEvent(Agent))BeginLowerReturn(Agent);
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyAttackRecovery.h"
#include "ProphecyWalkPinning.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAttackRecoveryBoostGateTest,"Prophecy.NN.AttackControls.RecoveryAndArmedGate",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyAttackRecoveryBoostGateTest::RunTest(const FString&)
{
    using namespace ProphecyAttackControls;
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    const int32 Before=Returns.Num();
    TestFalse(TEXT("Armed block defaults off"),ArmedBlocked(A));
    TestEqual(TEXT("Recovery defaults to ordinary boost"),RunBoost(A,.25f),.25f);
    UProphecyWalkPinningLibrary::SetAttackRecoveryRunPinningBoost(A,true,.5f,1.f,1.f);
    ProphecyAttackRecovery::EnterSpecial(A,true);
    ProphecyAttackRecovery::NotifyEnded(A,TEXT("pike"),true,true);
    TestEqual(TEXT("Pure half does not start boost"),RunBoost(A,.25f),.25f);
    for(float Dt:{1.f/30,1.f/60,1.f/120})
    {
        ProphecyAttackRecovery::EnterSpecial(A,false);
        ProphecyAttackRecovery::NotifyLowerEnded(A,TEXT("pike"),true,true);
        TestEqual(TEXT("Full to half immediately boosts Run"),RunBoost(A,.25f),1.f);
        for(int32 I=0;I<30;++I)Tick(W,LEVELTICK_All,Dt);
        TestEqual(TEXT("30 tick hold"),RunBoost(A,.25f),1.f);
        ProphecyAttackRecovery::NotifyEnded(A,TEXT("pike"),true,true);
        for(int32 I=0;I<30;++I)Tick(W,LEVELTICK_All,Dt);
        TestTrue(TEXT("Upper end did not restart lower blend"),FMath::IsNearlyEqual(RunBoost(A,.25f),.625f));
        TestTrue(TEXT("Blend follows latest normal setting"),FMath::IsNearlyEqual(RunBoost(A,.5f),.75f));
        UProphecyWalkPinningLibrary::SetRunPinningBoost(A,.5f);
        float L=.2f,R=.6f;ProphecyWalkPinning::BoostRunPin(A,L,R);
        TestTrue(TEXT("Actual Run pin uses recovery override"),L==.2f && FMath::IsNearlyEqual(R,.9f));
        for(int32 I=0;I<30;++I)Tick(W,LEVELTICK_All,Dt);
        TestEqual(TEXT("Completion restores ordinary boost"),RunBoost(A,.25f),.25f);
        TestEqual(TEXT("Completed records retired without a Run consumer"),Returns.Num(),Before);
    }
    UProphecyWalkPinningLibrary::SetAttackRecoveryRunPinningBoost(A,true,1.f,0.f,.8f);
    ProphecyAttackRecovery::NotifyEnded(A,TEXT("pike"),false,true);
    for(int32 I=0;I<59;++I)Tick(W,LEVELTICK_All,.01f);
    TestEqual(TEXT("Hold-only remains at boost"),RunBoost(A,0),.8f);
    Tick(W,LEVELTICK_All,.01f);TestEqual(TEXT("Hold-only returns immediately at end"),RunBoost(A,0),0.f);
    BeginLowerReturn(A);ProphecyAttackRecovery::EnterLowerSpecial(A);
    TestEqual(TEXT("Full reacquisition cancels boost"),RunBoost(A,.2f),.2f);
    ProphecyAttackRecovery::NotifyEnded(A,NAME_None,false,true,EProphecyAgentState::Parrying);
    TestEqual(TEXT("Defense does not trigger attack boost"),RunBoost(A,.2f),.2f);
    UProphecyGhostAttackLibrary::SetAttackArmedBlocked(A,true);CaptureReset(A);
    UProphecyGhostAttackLibrary::SetAttackArmedBlocked(A,false);
    UProphecyWalkPinningLibrary::SetAttackRecoveryRunPinningBoost(A,false,0,0,0);
    RestoreReset(A);TestTrue(TEXT("Reset restores block"),ArmedBlocked(A));
    BeginLowerReturn(A);TestEqual(TEXT("Reset restores boost config"),RunBoost(A,0),.8f);
    RestoreReset(A);TestEqual(TEXT("Reset cancels running boost"),RunBoost(A,.2f),.2f);
    UProphecyWalkPinningLibrary::SetAttackRecoveryRunPinningBoost(A,true,0,0,1);
    BeginLowerReturn(A);TestEqual(TEXT("Both zero bypass"),RunBoost(A,.2f),.2f);
    TestFalse(TEXT("Invalid boost rejected"),UProphecyWalkPinningLibrary::SetAttackRecoveryRunPinningBoost(A,true,1,1,2));
    for(bool Legacy:{false,true})
    {
        float Armed=0,Hit=0;
        for(int32 I=0;I<120;++I)PhaseLatches(true,Legacy,Armed,Hit,1,1,.6f,Armed,Hit);
        TestTrue(TEXT("Block prevents Armed; existing Hit rule requires prior Armed"),Armed==0 && Hit==0);
        PhaseLatches(false,Legacy,Armed,Hit,1,1,.6f,Armed,Hit);
        TestTrue(TEXT("Release arms without same-step hit"),Armed==1 && Hit==0);
        PhaseLatches(false,Legacy,Armed,Hit,1,1,.6f,Armed,Hit);
        TestTrue(TEXT("Next step can hit"),Armed==1 && Hit==1);
        PhaseLatches(true,Legacy,Armed,Hit,0,0,.6f,Armed,Hit);
        TestTrue(TEXT("Late block never rewinds a committed attack"),Armed==1 && Hit==1);
        PhaseLatches(true,Legacy,1,0,0,1,.6f,Armed,Hit);
        TestTrue(TEXT("Block does not suppress Hit on an already Armed attack"),Armed==1 && Hit==1);
    }
    Remove(A);TestFalse(TEXT("Remove clears block"),ArmedBlocked(A));
    if(Before==0 && SinceLowerAttack.IsEmpty())TestFalse(TEXT("No active returns/counters leaves no tick delegate"),ReturnTick.IsValid());
    ProphecyAttackRecovery::Remove(A);UProphecyWalkPinningLibrary::SetRunPinningBoost(A,0);
    W->DestroyWorld(false);W->MarkAsGarbage();return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAttackEntryMagicClockTest,"Prophecy.NN.AttackControls.EntryMagicAndTicks",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyAttackEntryMagicClockTest::RunTest(const FString&)
{
    using namespace ProphecyAttackControls;
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    auto Count=[&](){return UProphecyGhostAttackLibrary::GetTicksSinceLastAttack(A);};
    TestEqual(TEXT("Before first full attack"),Count(),int64(0));
    LowerAttackFinished(A);Tick(W,LEVELTICK_All,.016f);
    TestEqual(TEXT("No full ownership means no counter start"),Count(),int64(0));
    for(float Dt:{1.f/30,1.f/60,1.f/120})
    {
        UProphecyRootPhysicsLibrary::SetRootMagicVelocity(A,FVector(100,200,300));
        UProphecyRootPhysicsLibrary::SetRootMagicVelocity2(A,FVector(-100,50,30));
        UProphecyRootPhysicsLibrary::SetRootMagicAngVelocity(A,FVector(0,0,90));
        UProphecyRootPhysicsLibrary::SetRootMagicAngVelocity2(A,FVector(0,0,-45));
        FullAttackStarted(A);
        TestTrue(TEXT("First linear cleared"),UProphecyRootPhysicsLibrary::GetRootMagicVelocity(A).IsZero());
        TestTrue(TEXT("Second linear cleared"),UProphecyRootPhysicsLibrary::GetRootMagicVelocity2(A).IsZero());
        TestTrue(TEXT("First angular cleared"),UProphecyRootPhysicsLibrary::GetRootMagicAngVelocity(A).IsZero());
        TestTrue(TEXT("Second angular cleared"),UProphecyRootPhysicsLibrary::GetRootMagicAngVelocity2(A).IsZero());
        for(int32 I=0;I<10;++I)Tick(W,LEVELTICK_All,Dt);
        TestEqual(TEXT("Full attack holds zero"),Count(),int64(0));
        LowerAttackFinished(A);
        TestEqual(TEXT("Release tick starts at zero"),Count(),int64(0));
        for(int32 I=0;I<60;++I)Tick(W,LEVELTICK_All,Dt);
        TestEqual(TEXT("60 engine ticks independent of FPS"),Count(),int64(60));
        TestEqual(TEXT("Repeated reads do not advance"),Count(),int64(60));
        Tick(W,LEVELTICK_All,0);Tick(W,LEVELTICK_TimeOnly,Dt);
        TestEqual(TEXT("Non-simulation ticks ignored"),Count(),int64(60));
        LowerAttackFinished(A); // A duplicate/later upper release must not restart.
        Tick(W,LEVELTICK_All,Dt);TestEqual(TEXT("Repeated release does not restart"),Count(),int64(61));
        FullAttackStarted(A);TestEqual(TEXT("Reacquisition resets"),Count(),int64(0));
    }
    LowerAttackFinished(A);Tick(W,LEVELTICK_All,.016f);RestoreReset(A);
    TestEqual(TEXT("Initial reset clears elapsed ticks"),Count(),int64(0));
    TestFalse(TEXT("Reset removes held marker"),FullAttackHeld.Contains(A));
    FullAttackStarted(A);LowerAttackFinished(A);Remove(A);
    TestFalse(TEXT("Removal retires count"),SinceLowerAttack.Contains(A));
    if(Returns.IsEmpty() && SinceLowerAttack.IsEmpty())TestFalse(TEXT("No counter leaves no callback"),ReturnTick.IsValid());
    W->DestroyWorld(false);W->MarkAsGarbage();return !HasAnyErrors();
}
#endif
