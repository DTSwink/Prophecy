// Included by ProphecyGhostAttackLibrary.cpp; sparse state, no retained UObject layout changes.
namespace ProphecyAttackControls
{
static TSet<TWeakObjectPtr<const AProphecyAgent>> Blocked,ResetBlocked;
static TSet<TWeakObjectPtr<const AProphecyAgent>> FullAttackHeld;
static TMap<TWeakObjectPtr<const AProphecyAgent>,int64> SinceLowerAttack;
// Explicit user setting, independent of when Initialize Agent Reset was called.
static TMap<TWeakObjectPtr<const AProphecyAgent>,int64> CounterResetTicks;
static FDelegateHandle CounterTick;
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
    RefreshTick();
}
static void RefreshTick()
{
    if(SinceLowerAttack.IsEmpty()) {FWorldDelegates::OnWorldPreActorTick.Remove(CounterTick);CounterTick.Reset();}
    else if(!CounterTick.IsValid())CounterTick=FWorldDelegates::OnWorldPreActorTick.AddStatic(&Tick);
}
bool ArmedBlocked(const AProphecyAgent* A) {return !Blocked.IsEmpty() && Blocked.Contains(A);}
void StartAttackTickCounter(const AProphecyAgent* A)
{
    if(FullAttackHeld.Contains(A) || SinceLowerAttack.Contains(A))return;
    SinceLowerAttack.Add(A,CounterResetTicks.FindRef(A));RefreshTick();
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
void ForgetReset(const AProphecyAgent* A) {ResetBlocked.Remove(A);}
void Remove(const AProphecyAgent* A)
{SinceLowerAttack.Remove(A);CounterResetTicks.Remove(A);FullAttackHeld.Remove(A);RefreshTick();Blocked.Remove(A);ForgetReset(A);}
void CaptureReset(const AProphecyAgent* A)
{
    if(ArmedBlocked(A))ResetBlocked.Add(A);else ResetBlocked.Remove(A);
}
void RestoreReset(const AProphecyAgent* A)
{
    SinceLowerAttack.Remove(A);FullAttackHeld.Remove(A);StartAttackTickCounter(A);
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
bool UProphecyGhostAttackLibrary::SetTicksSinceLastAttack(AProphecyAgent* Agent,int64 Ticks)
{
    using namespace ProphecyAttackControls;
    if(!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld() ||
        Agent->GetWorld()->bIsTearingDown || Ticks<0 || FullAttackHeld.Contains(Agent))return false;
    CounterResetTicks.Add(Agent,Ticks);SinceLowerAttack.Add(Agent,Ticks);RefreshTick();
    return true;
}
#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAttackArmedGateTest,"Prophecy.NN.AttackControls.ArmedGate",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyAttackArmedGateTest::RunTest(const FString&)
{
    using namespace ProphecyAttackControls;
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    TestFalse(TEXT("Armed block defaults off"),ArmedBlocked(A));
    UProphecyGhostAttackLibrary::SetAttackArmedBlocked(A,true);CaptureReset(A);
    UProphecyGhostAttackLibrary::SetAttackArmedBlocked(A,false);
    RestoreReset(A);TestTrue(TEXT("Reset restores block"),ArmedBlocked(A));
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
    if(SinceLowerAttack.IsEmpty())TestFalse(TEXT("No counters leaves no tick delegate"),CounterTick.IsValid());
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
    if(SinceLowerAttack.IsEmpty())TestFalse(TEXT("No counter leaves no callback"),CounterTick.IsValid());
    W->DestroyWorld(false);W->MarkAsGarbage();return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyManualAttackTicksTest,"Prophecy.NN.AttackControls.ManualTicks",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyManualAttackTicksTest::RunTest(const FString&)
{
    using namespace ProphecyAttackControls;
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    auto Count=[&](){return UProphecyGhostAttackLibrary::GetTicksSinceLastAttack(A);};
    CaptureReset(A); // Setter works even after reset initialization.
    TestTrue(TEXT("Manual seed accepted"),UProphecyGhostAttackLibrary::SetTicksSinceLastAttack(A,1000));
    TestEqual(TEXT("Immediately visible"),Count(),int64(1000));
    for(float Dt:{1.f/30,1.f/60,1.f/120})Tick(W,LEVELTICK_All,Dt);
    TestEqual(TEXT("Counts ticks, not seconds"),Count(),int64(1003));
    TestFalse(TEXT("Negative rejected"),UProphecyGhostAttackLibrary::SetTicksSinceLastAttack(A,-1));
    TestEqual(TEXT("Rejected write is atomic"),Count(),int64(1003));
    RestoreReset(A);TestEqual(TEXT("Reset uses explicit seed"),Count(),int64(1000));
    FullAttackStarted(A);TestEqual(TEXT("Full attack still zero"),Count(),int64(0));
    TestFalse(TEXT("Cannot rewrite active full attack"),UProphecyGhostAttackLibrary::SetTicksSinceLastAttack(A,99));
    LowerAttackFinished(A);TestEqual(TEXT("Real release still zero"),Count(),int64(0));
    Tick(W,LEVELTICK_All,.016f);TestEqual(TEXT("Counts after release"),Count(),int64(1));
    RestoreReset(A);TestEqual(TEXT("Real attack retains reset seed"),Count(),int64(1000));
    UProphecyGhostAttackLibrary::SetTicksSinceLastAttack(A,MAX_int64);Tick(W,LEVELTICK_All,.016f);
    TestEqual(TEXT("Saturates without overflow"),Count(),int64(MAX_int64));
    UProphecyGhostAttackLibrary::SetTicksSinceLastAttack(A,0);RestoreReset(A);
    TestEqual(TEXT("Explicit zero restores original reset behavior"),Count(),int64(0));
    Remove(A);TestFalse(TEXT("Removal forgets manual setting"),CounterResetTicks.Contains(A));
    W->DestroyWorld(false);W->MarkAsGarbage();return !HasAnyErrors();
}
#endif
