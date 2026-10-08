// Included by ProphecyRootPhysicsLibrary.cpp; uses its cached-channel storage.
namespace ProphecyRootMagic3
{
struct FRequest
{
    TWeakObjectPtr<AProphecyAgent> Agent;
    FVector Value, Start=FVector::ZeroVector, Target=FVector::ZeroVector;
    bool Angular=false, Add=false, Started=false;
    int32 Count=1, Delivered=0;
    uint64 Remaining=1, LastFrame=0;
};
static TArray<FRequest> Pending;
// New storage keeps the existing retained FRequest allocation layout unchanged.
struct FBrake { double Step; uint64 LastFrame; bool Active; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FBrake> Brakes;
static FDelegateHandle TickHandle,CleanupHandle;
static void Refresh();
static FVector Read(const AProphecyAgent* A,bool Angular)
{
    const auto* V=IsInGameThread() && IsValid(A) ? ProphecyRootMagic::FindChannel(A,2) : nullptr;
    if (!V) return FVector::ZeroVector;
    return Angular ? FVector(0,0,-FMath::RadiansToDegrees(V->Yaw)) : FVector(V->Linear.X,V->Linear.Z,V->Linear.Y)*100.;
}
static bool Write(AProphecyAgent* A,FVector V,bool Angular,bool Add)
{ return Angular ? ProphecyRootMagic::SetAngular(A,V,Add,2) : ProphecyRootMagic::SetLinear(A,V,Add,2); }
static bool Deliver(FRequest& R,bool Braking=false)
{
    if (!R.Started)
    {
        R.Start=Read(R.Agent.Get(),R.Angular);
        R.Target=R.Add ? R.Start+R.Value : R.Value;
        R.Started=true;
        if (R.Target.ContainsNaN()) return false;
    }
    FVector Next=R.Delivered+1==R.Count ? R.Target : FMath::Lerp(R.Start,R.Target,double(R.Delivered+1)/R.Count);
    if (Braking)
    {
        // Deliver only this installment; an absolute ramp would restore velocity
        // already removed by braking on the previous tick.
        const FVector Previous=R.Delivered==0 ? R.Start : FMath::Lerp(R.Start,R.Target,double(R.Delivered)/R.Count);
        Next=Read(R.Agent.Get(),false)+(Next-Previous);
    }
    if (!Write(R.Agent.Get(),Next,R.Angular,false)) return false;
    ++R.Delivered;return true;
}
static void Advance(UWorld* W,ELevelTick Type,float Dt,uint64 Frame)
{
    if (!W || W->IsPaused() || Type!=LEVELTICK_All || !FMath::IsFinite(Dt) || Dt<=0) return;
    Pending.RemoveAll([&](FRequest& R)
    {
        auto* A=R.Agent.Get();
        if (!A || A->IsActorBeingDestroyed()) return true;
        if (A->GetWorld()!=W || R.LastFrame==Frame) return false;
        R.LastFrame=Frame;
        if (--R.Remaining>0) return false;
        auto* Brake=!R.Angular && !Brakes.IsEmpty() ? Brakes.Find(A) : nullptr;
        if (!Deliver(R,Brake!=nullptr)) return true;
        if (Brake) Brake->Active=true;
        if (R.Delivered==R.Count) return true;
        R.Remaining=1;return false;
    });
    // Only agents explicitly using positive deceleration are present here.
    if (!Brakes.IsEmpty()) for (auto It=Brakes.CreateIterator();It;++It)
    {
        auto* A=It.Key().Get();auto& B=It.Value();
        if (!A || A->IsActorBeingDestroyed()) {It.RemoveCurrent();continue;}
        if (!B.Active || A->GetWorld()!=W || B.LastFrame==Frame) continue;
        B.LastFrame=Frame;
        const FVector V=Read(A,false);const double Speed=V.Size();
        const FVector Next=Speed<=B.Step ? FVector::ZeroVector : V*(1.-B.Step/Speed);
        if (!Write(const_cast<AProphecyAgent*>(A),Next,false,false)) {It.RemoveCurrent();continue;}
        if (Next.IsZero() && !Pending.ContainsByPredicate([&](const FRequest& R){return R.Agent==A&&!R.Angular;})) It.RemoveCurrent();
    }
    Refresh();
}
static void Tick(UWorld* W,ELevelTick Type,float Dt) { Advance(W,Type,Dt,GFrameCounter); }
static void Cleanup(UWorld* W,bool,bool)
{
    Pending.RemoveAll([&](const FRequest& R){return !R.Agent.IsValid() || R.Agent->GetWorld()==W;});
    for (auto It=Brakes.CreateIterator();It;++It)
        if (!It.Key().IsValid() || It.Key()->GetWorld()==W) It.RemoveCurrent();
    Refresh();
}
static void Refresh()
{
    if (Pending.IsEmpty() && Brakes.IsEmpty())
    {
        FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle);TickHandle.Reset();
        FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);CleanupHandle.Reset();
    }
    else
    {
        if (!TickHandle.IsValid()) TickHandle=FWorldDelegates::OnWorldPreActorTick.AddStatic(&Tick);
        if (!CleanupHandle.IsValid()) CleanupHandle=FWorldDelegates::OnWorldCleanup.AddStatic(&Cleanup);
    }
}
void Cancel(const AProphecyAgent* A)
{
    if (Pending.IsEmpty() && Brakes.IsEmpty()) return;
    Brakes.Remove(A);
    Pending.RemoveAll([&](const FRequest& R){return R.Agent==A;});Refresh();
}
static void CancelChannel(const AProphecyAgent* A,bool Angular)
{
    Pending.RemoveAll([&](const FRequest& R){return R.Agent==A && R.Angular==Angular;});
    if (!Angular) Brakes.Remove(A);
}
static void SetBrake(AProphecyAgent* A,float Deceleration,bool Active)
{
    if (Deceleration>0 && (!Active || !Read(A,false).IsZero()))
        Brakes.Add(A,{double(Deceleration)*ProphecyBlendClock::TickSeconds,GFrameCounter,Active});
}
static bool Submit(AProphecyAgent* A,FVector V,bool Angular,bool Add,int32 Count,float Delay,float Deceleration=0)
{
    if (!IsInGameThread() || !IsValid(A) || A->IsActorBeingDestroyed() || V.ContainsNaN()
        || Count<1 || !FMath::IsFinite(Delay) || Delay<0 || !FMath::IsFinite(Deceleration) || Deceleration<0) return false;
    if (Angular) V=FVector(0,0,V.Z);
    if (!Angular && FVector3f(V*.01).ContainsNaN()) return false;
    if (Deceleration>0 && (!A->GetWorld() || !A->GetWorld()->IsGameWorld() || A->GetWorld()->bIsTearingDown)) return false;
    if (Count==1 && Delay==0)
    {
        if (!Write(A,V,Angular,Add)) return false;
        CancelChannel(A,Angular);if (!Angular) SetBrake(A,Deceleration,true);Refresh();return true;
    }
    auto* W=A->GetWorld();
    if (!W || !W->IsGameWorld() || W->bIsTearingDown) return false;
    FRequest R;R.Agent=A;R.Value=V;R.Angular=Angular;R.Add=Add;R.Count=Count;R.LastFrame=GFrameCounter;
    if (Delay==0)
    {
        if (!Deliver(R)) return false;
    }
    else R.Remaining=uint64(FMath::Max(1.,FMath::CeilToDouble(FMath::Min(double(Delay)/ProphecyBlendClock::TickSeconds,9.e15)-1.e-5)));
    CancelChannel(A,Angular);Pending.Add(R);
    if (!Angular && Deceleration>0)
        Brakes.Add(A,{double(Deceleration)*ProphecyBlendClock::TickSeconds,GFrameCounter,Delay==0});
    Refresh();return true;
}
}
bool UProphecyRootMagic3Library::SetRootMagicVelocity3(AProphecyAgent* A,FVector V,bool Add,int32 Count,float Delay,float Deceleration)
{ return ProphecyRootMagic3::Submit(A,V,false,Add,Count,Delay,Deceleration); }
bool UProphecyRootMagic3Library::SetRootMagicAngVelocity3(AProphecyAgent* A,FVector V,bool Add,int32 Count,float Delay)
{ return ProphecyRootMagic3::Submit(A,V,true,Add,Count,Delay); }
FVector UProphecyRootMagic3Library::GetRootMagicVelocity3(AProphecyAgent* A) { return ProphecyRootMagic3::Read(A,false); }
FVector UProphecyRootMagic3Library::GetRootMagicAngVelocity3(AProphecyAgent* A) { return ProphecyRootMagic3::Read(A,true); }

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Misc/ScopeExit.h"
#include "ProphecyAttackControls.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRootMagicThreeTest,"Prophecy.Root.MagicThree.DelaySpreadIsolation",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyRootMagicThreeTest::RunTest(const FString&)
{
    using namespace ProphecyRootMagic3;using L=UProphecyRootMagic3Library;using Old=UProphecyRootPhysicsLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Game,false);
    if (!TestNotNull(TEXT("World"),W)) return false;
    auto* A=W->SpawnActor<AProphecyAgent>();
    ON_SCOPE_EXIT { if(A){ProphecyRootMagic::Remove(A);ProphecyAttackControls::Remove(A);}W->DestroyWorld(false); };
    if (!TestNotNull(TEXT("Agent"),A)) return false;
    A->bAutoEnsureStandaloneNNManager=false;
    for (float FPS:{30.f,60.f,120.f})
    {
        ProphecyRootMagic::Remove(A);A->CustomTimeDilation=.2f;
        Old::SetRootMagicVelocity(A,FVector(10,20,30));Old::SetRootMagicVelocity2(A,FVector(-4,5,6));
        TestTrue(TEXT("Delayed spread accepted"),L::SetRootMagicVelocity3(A,FVector(400,0,0),false,3,.03f,0));
        const uint64 Start=GFrameCounter;
        Advance(W,LEVELTICK_All,1/FPS,Start);
        Advance(W,LEVELTICK_All,1/FPS,Start+1);
        TestTrue(TEXT("Two tick delay has not expired"),Read(A,false).IsZero());
        Advance(W,LEVELTICK_PauseTick,1/FPS,Start+2);Advance(W,LEVELTICK_All,0,Start+2);
        TestTrue(TEXT("Paused/zero delta do not advance"),Read(A,false).IsZero());
        for (int I=2;I<=4;++I)
        {
            Advance(W,LEVELTICK_All,1/FPS,Start+I);
            TestTrue(TEXT("Fractions sum to400 independent of FPS/dilation"),FMath::Abs(Read(A,false).X-400.*(I-1)/3.)<.001);
            const FVector Before=Read(A,false);Advance(W,LEVELTICK_All,1/FPS,Start+I);
            TestTrue(TEXT("Duplicate frame ignored"),Read(A,false)==Before);
        }
        TestTrue(TEXT("No idle tick hooks"),Pending.IsEmpty()&&!TickHandle.IsValid()&&!CleanupHandle.IsValid());
        Advance(W,LEVELTICK_All,1/FPS,Start+5);
        TestTrue(TEXT("Final magic persists"),Read(A,false).Equals(FVector(400,0,0),.001));
        TestTrue(TEXT("First/second preserved"),Old::GetRootMagicVelocity(A).Equals(FVector(10,20,30),.001)&&Old::GetRootMagicVelocity2(A).Equals(FVector(-4,5,6),.001));
        TestTrue(TEXT("Cached total includes third"),ProphecyRootMagic::Find(A)->Linear.Equals(FVector3f(4.06,.36,.25),.00001));
        Old::SetRootMagicVelocity(A,FVector(20,0,0));Old::SetRootMagicVelocity2(A,FVector(30,0,0));
        TestTrue(TEXT("Legacy writes cannot overwrite third"),Read(A,false).Equals(FVector(400,0,0),.001));
        TestTrue(TEXT("Updated cached sum"),FMath::Abs(ProphecyRootMagic::Find(A)->Linear.X-4.5f)<.00001);
    }
    L::SetRootMagicAngVelocity3(A,FVector(9,8,90),false,3,0);
    TestTrue(TEXT("Angular first part immediate, only yaw"),Read(A,true).Equals(FVector(0,0,30),.001));
    L::SetRootMagicVelocity3(A,FVector::ZeroVector,false,1,0,0);
    TestTrue(TEXT("Linear clear preserves angular spread"),Read(A,false).IsZero()&&Pending.Num()==1);
    Advance(W,LEVELTICK_All,.016f,GFrameCounter+1);Advance(W,LEVELTICK_All,.016f,GFrameCounter+2);
    TestTrue(TEXT("Angular target reached"),Read(A,true).Equals(FVector(0,0,90),.001));
    L::SetRootMagicVelocity3(A,FVector(100,0,0),false,1,0,0);L::SetRootMagicVelocity3(A,FVector(60,0,0),true,3,.03f,0);
    Advance(W,LEVELTICK_All,.016f,GFrameCounter+1);Advance(W,LEVELTICK_All,.016f,GFrameCounter+2);
    TestTrue(TEXT("Add to current first fraction"),Read(A,false).Equals(FVector(120,0,0),.001));
    L::SetRootMagicVelocity3(A,FVector::ZeroVector,false,1,0,0);
    Advance(W,LEVELTICK_All,.016f,GFrameCounter+3);
    TestTrue(TEXT("Clear cancels remaining spread"),Read(A,false).IsZero()&&Pending.IsEmpty());
    L::SetRootMagicVelocity3(A,FVector(60,0,0),false,3,.03f,0);
    TestFalse(TEXT("Invalid request rejected"),L::SetRootMagicVelocity3(A,FVector::ZeroVector,false,0,0,0));
    TestTrue(TEXT("Invalid request preserves queue"),Pending.Num()==1);
    L::SetRootMagicVelocity3(A,FVector(90,0,0),false,3,.03f,0);
    Advance(W,LEVELTICK_All,.016f,GFrameCounter+1);Advance(W,LEVELTICK_All,.016f,GFrameCounter+2);
    TestTrue(TEXT("Latest call replaces prior request"),Read(A,false).Equals(FVector(30,0,0),.001));
    ProphecyRootMagic::Remove(A);Advance(W,LEVELTICK_All,.016f,GFrameCounter+3);
    TestTrue(TEXT("Reset removal clears queue and cached/source state"),Pending.IsEmpty()&&!ProphecyRootMagic::Find(A)&&Read(A,false).IsZero());
    Old::SetRootMagicVelocity(A,FVector(50,0,0));L::SetRootMagicVelocity3(A,FVector(-50,0,0),false,1,0,0);
    TestTrue(TEXT("Opposing sources preserved when total zero"),!ProphecyRootMagic::Find(A)&&Old::GetRootMagicVelocity(A).Equals(FVector(50,0,0),.001));
    L::SetRootMagicVelocity3(A,FVector::ZeroVector,false,1,0,0);
    TestTrue(TEXT("Clearing third restores first"),Old::GetRootMagicVelocity(A).Equals(FVector(50,0,0),.001)&&ProphecyRootMagic::Find(A));
    L::SetRootMagicVelocity3(A,FVector(400,0,0),false,3,.03f,0);L::SetRootMagicAngVelocity3(A,FVector(0,0,90));
    ProphecyAttackControls::FullAttackStarted(A);
    Advance(W,LEVELTICK_All,.016f,GFrameCounter+10);
    TestTrue(TEXT("Full attack clears all sets and delayed work"),!ProphecyRootMagic::Find(A)&&Read(A,true).IsZero()&&Pending.IsEmpty());
    L::SetRootMagicVelocity3(A,FVector(400,0,0),false,3,.03f,0);Cleanup(W,false,false);
    TestTrue(TEXT("World cleanup releases pending hooks"),Pending.IsEmpty()&&!TickHandle.IsValid()&&!CleanupHandle.IsValid());
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRootMagicThreeBrakeTest,"Prophecy.Root.MagicThree.Braking",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyRootMagicThreeBrakeTest::RunTest(const FString&)
{
    using namespace ProphecyRootMagic3;using L=UProphecyRootMagic3Library;using Old=UProphecyRootPhysicsLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Game,false);
    if (!TestNotNull(TEXT("World"),W)) return false;
    auto* A=W->SpawnActor<AProphecyAgent>();
    ON_SCOPE_EXIT { if(A){ProphecyRootMagic::Remove(A);ProphecyAttackControls::Remove(A);}W->DestroyWorld(false); };
    if (!TestNotNull(TEXT("Agent"),A)) return false;
    A->bAutoEnsureStandaloneNNManager=false;
    for (float FPS:{30.f,60.f,120.f})
    {
        ProphecyRootMagic::Remove(A);A->CustomTimeDilation=.2f;
        Old::SetRootMagicVelocity(A,FVector(10,20,30));Old::SetRootMagicVelocity2(A,FVector(40,50,60));
        L::SetRootMagicAngVelocity3(A,FVector(0,0,90));
        TestTrue(TEXT("Default idle braking accepted"),L::SetRootMagicVelocity3(A,FVector(240,320,0)));
        const uint64 Start=GFrameCounter;
        Advance(W,LEVELTICK_All,1/FPS,Start);
        TestTrue(TEXT("No braking on setter frame"),Read(A,false).Equals(FVector(240,320,0),.001));
        for(int I=1;I<=14;++I)
        {
            Advance(W,LEVELTICK_PauseTick,1/FPS,Start+I);Advance(W,LEVELTICK_TimeOnly,1/FPS,Start+I);Advance(W,LEVELTICK_All,0,Start+I);
            const FVector Before=Read(A,false);
            TestTrue(TEXT("Pause/non-game/zero delta do not advance braking"),FMath::Abs(Before.Size()-FMath::Max(0.,400.-30.*(I-1)))<.002);
            Advance(W,LEVELTICK_All,1/FPS,Start+I);
            const FVector Expected=FVector(.6,.8,0)*FMath::Max(0.,400.-30.*I);
            TestTrue(TEXT("30cm/s per tick, direction retained, zero clamp"),Read(A,false).Equals(Expected,.002));
            const FVector After=Read(A,false);Advance(W,LEVELTICK_All,1/FPS,Start+I);
            TestTrue(TEXT("Duplicate tick cannot brake twice"),Read(A,false)==After);
        }
        TestTrue(TEXT("At rest no brake entry or hooks"),Brakes.IsEmpty()&&!TickHandle.IsValid()&&!CleanupHandle.IsValid());
        TestTrue(TEXT("Other channels and angular3 untouched"),Old::GetRootMagicVelocity(A).Equals(FVector(10,20,30),.001)&&Old::GetRootMagicVelocity2(A).Equals(FVector(40,50,60),.001)&&Read(A,true).Equals(FVector(0,0,90),.001));
    }
    ProphecyRootMagic::Remove(A);
    L::SetRootMagicVelocity3(A,FVector(400,0,0),false,3,.03f);
    const uint64 Start=GFrameCounter;
    Advance(W,LEVELTICK_All,.016f,Start+1);
    TestTrue(TEXT("Delay retains zero before first installment"),Read(A,false).IsZero());
    for(int I=2;I<=4;++I)
    {
        Advance(W,LEVELTICK_All,.016f,Start+I);
        TestTrue(TEXT("Spread never restores previously braked velocity"),FMath::Abs(Read(A,false).X-(400./3.-30.)*(I-1))<.002);
    }
    Advance(W,LEVELTICK_All,.016f,Start+5);
    TestTrue(TEXT("Braking continues after spread"),Read(A,false).Equals(FVector(280,0,0),.002));
    TestTrue(TEXT("Zero braking replacement"),L::SetRootMagicVelocity3(A,Read(A,false),false,1,0,0));
    TestTrue(TEXT("Zero disables braking with no tick or entry"),Brakes.IsEmpty()&&Pending.IsEmpty()&&!TickHandle.IsValid()&&!CleanupHandle.IsValid());
    Advance(W,LEVELTICK_All,.016f,Start+6);
    TestTrue(TEXT("Zero rate leaves velocity constant"),Read(A,false).Equals(FVector(280,0,0),.002));
    L::SetRootMagicVelocity3(A,FVector::ZeroVector);
    L::SetRootMagicVelocity3(A,FVector(30,0,0),false,3,.03f);
    for(int I=1;I<=4;++I)Advance(W,LEVELTICK_All,.016f,Start+I);
    TestTrue(TEXT("Strong braking does not lose later installments or leave an idle hook"),Read(A,false).IsZero()&&Brakes.IsEmpty()&&Pending.IsEmpty()&&!TickHandle.IsValid());
    L::SetRootMagicVelocity3(A,FVector(400,0,0));
    TestFalse(TEXT("Negative braking rejected"),L::SetRootMagicVelocity3(A,FVector::ZeroVector,false,1,0,-1));
    TestTrue(TEXT("Invalid call preserves velocity and braking"),Read(A,false).Equals(FVector(400,0,0),.001)&&Brakes.Num()==1);
    ProphecyAttackControls::FullAttackStarted(A);
    TestTrue(TEXT("Full attack cancels braking"),Brakes.IsEmpty()&&!TickHandle.IsValid()&&Read(A,false).IsZero());
    L::SetRootMagicVelocity3(A,FVector(400,0,0));ProphecyRootMagic::Remove(A);
    TestTrue(TEXT("Reset cancels braking"),Brakes.IsEmpty()&&!TickHandle.IsValid());
    L::SetRootMagicVelocity3(A,FVector(400,0,0));Cleanup(W,false,false);
    TestTrue(TEXT("World cleanup removes braking callbacks"),Brakes.IsEmpty()&&!TickHandle.IsValid()&&!CleanupHandle.IsValid());
    return !HasAnyErrors();
}
#endif
