#include "ProphecyCoreTemperingLibrary.h"
#include "ProphecyCoreTempering.h"
#include "ProphecyBlendClock.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"

namespace ProphecyCoreTempering
{
using K=ProphecyBlendClock::EKind;
struct FValue { float Current=1,Initial=1,Hold=0,Duration=0;double Elapsed=0;bool Returning=false; };
struct FBaseline { float Config=1,Value=1; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,float> Configs;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FValue> Values;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FBaseline> Baselines;
static FDelegateHandle Cleanup;
static void EnsureCleanup()
{
    if(Cleanup.IsValid()) return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        auto Clean=[W](auto& Map) { for(auto It=Map.CreateIterator();It;++It)
            if(!It.Key().IsValid() || It.Key()->GetWorld()==W) It.RemoveCurrent(); };
        Clean(Configs);Clean(Values);Clean(Baselines);
    });
}
static bool Valid(AProphecyAgent* A)
{ return IsInGameThread() && IsValid(A) && !A->IsActorBeingDestroyed() && A->GetWorld() && !A->GetWorld()->bIsTearingDown; }
void CancelMotion(const AProphecyAgent* A)
{
    if(Values.IsEmpty() || !Values.Remove(A)) return;
    ProphecyBlendClock::Stop(A,K::CoreTempering);
}
static void SetValue(const AProphecyAgent* A,float V)
{ CancelMotion(A);if(V<1) { EnsureCleanup();Values.Add(A,FValue{V}); } }
float Rotation(const AProphecyAgent* A)
{
    auto* V=Values.IsEmpty()?nullptr:Values.Find(A);if(!V) return 1;
    if(V->Returning)
    {
        V->Elapsed+=ProphecyBlendClock::Consume(A,K::CoreTempering);
        const float T=V->Elapsed+1.e-8<V->Hold ? 0.f : V->Duration>0
            ? FMath::Clamp(float((V->Elapsed-V->Hold)/V->Duration),0.f,1.f) : 1.f;
        if(T>=1) { CancelMotion(A);return 1; }
        V->Current=FMath::Lerp(V->Initial,1.f,T*T*(3-2*T));
    }
    return V->Current;
}
void Begin(const AProphecyAgent* A)
{ if(const float* C=Configs.IsEmpty()?nullptr:Configs.Find(A)) SetValue(A,*C); }
void Remove(const AProphecyAgent* A) { CancelMotion(A);Configs.Remove(A);Baselines.Remove(A); }
void CaptureReset(const AProphecyAgent* A)
{
    FBaseline B;if(const float* C=Configs.Find(A)) B.Config=*C;B.Value=Rotation(A);
    EnsureCleanup();Baselines.Add(A,B);
}
void RestoreReset(const AProphecyAgent* A)
{
    CancelMotion(A);
    if(const auto* B=Baselines.Find(A)) { Configs.Add(A,B->Config);SetValue(A,B->Value); }
}
void ForgetReset(const AProphecyAgent* A) { Baselines.Remove(A); }
}

bool UProphecyCoreTemperingLibrary::SetLocomotionFKCoreTempering(AProphecyAgent* A,bool Enabled,float Follow)
{
    using namespace ProphecyCoreTempering;
    if(!Valid(A) || !FMath::IsFinite(Follow) || Follow<0 || Follow>1) return false;
    const float V=Enabled?Follow:1.f;
    EnsureCleanup();if(V<1) Configs.Add(A,V);else Configs.Remove(A);
    SetValue(A,V);return true;
}
bool UProphecyCoreTemperingLibrary::BlendLocomotionFKCoreTemperingToNormal(AProphecyAgent* A,float Hold,float Duration)
{
    using namespace ProphecyCoreTempering;
    if(!Valid(A) || !FMath::IsFinite(Hold) || !FMath::IsFinite(Duration) || Hold<0 || Duration<0) return false;
    const float Initial=Rotation(A);if(Initial==1) return true;
    if(Hold==0 && Duration==0) { CancelMotion(A);return true; }
    Values.FindChecked(A)={Initial,Initial,Hold,Duration,0,true};
    ProphecyBlendClock::Start(A,K::CoreTempering,double(Hold)+Duration);return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyCoreTemperingLifecycleTest,"Prophecy.NN.CoreTempering.Lifecycle",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyCoreTemperingLifecycleTest::RunTest(const FString&)
{
    using namespace ProphecyCoreTempering;using L=UProphecyCoreTemperingLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A) return false;
    for(float FPS:{30.f,60.f,120.f})
    {
        L::SetLocomotionFKCoreTempering(A,true,0);CaptureReset(A);
        L::BlendLocomotionFKCoreTemperingToNormal(A,.5f,1);
        A->CustomTimeDilation=2;
        for(int32 T=1;T<=90;++T)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/FPS);
            const float V=Rotation(A);
            if(T==30) TestEqual(TEXT("30-tick hold"),V,0.f);
            if(T==60) TestTrue(TEXT("Half blend after another 30 ticks"),FMath::IsNearlyEqual(V,.5f));
            TestEqual(TEXT("Repeated reads do not advance blend"),Rotation(A),V);
        }
        TestEqual(TEXT("90 ticks return to normal at every FPS/dilation"),Rotation(A),1.f);
        TestFalse(TEXT("Finished value and return retire"),Values.Contains(A));
        Begin(A);TestEqual(TEXT("Attack exit restores configured follow"),Rotation(A),0.f);
        L::BlendLocomotionFKCoreTemperingToNormal(A,1,0);
        for(int32 T=0;T<60;++T) FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/FPS);
        TestEqual(TEXT("Zero duration snaps after hold even with deferred consumption"),Rotation(A),1.f);
        RestoreReset(A);TestEqual(TEXT("Reset restores captured value"),Rotation(A),0.f);
        TestFalse(TEXT("Reset cancels return"),Values.FindChecked(A).Returning);
        L::BlendLocomotionFKCoreTemperingToNormal(A,0,0);
        TestEqual(TEXT("Zero duration immediate"),Rotation(A),1.f);
        L::SetLocomotionFKCoreTempering(A,false,0);Begin(A);
        TestEqual(TEXT("Disabled config cannot restart on attack exit"),Rotation(A),1.f);
        TestFalse(TEXT("Invalid value rejected"),L::SetLocomotionFKCoreTempering(A,true,-1));
        TestFalse(TEXT("Invalid time rejected"),L::BlendLocomotionFKCoreTemperingToNormal(A,-1,1));
    }
    Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
#endif
