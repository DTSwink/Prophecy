#include "ProphecyUpperBodyInertiaLibrary.h"
#include "ProphecyUpperBodyInertia.h"
#include "ProphecyPelvisInertiaMath.h"
#include "ProphecyBlendClock.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"
namespace ProphecyUpperBodyInertia
{
using K=ProphecyBlendClock::EKind;
struct FConfig { float Response=.25f,Hold=0,Blend=.5f,Momentum=1; };
struct FMotion { FQuat Rotation=FQuat::Identity;FVector Velocity=FVector::ZeroVector; };
struct FReturn { FConfig Config;TArray<FMotion> Joints;double Elapsed=0; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FConfig> Configs,Baselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FReturn> Returns;
// Separate sidecar: don't resize allocations retained by Live Coding.
static TMap<TWeakObjectPtr<const AProphecyAgent>,TArray<FTransform>> Handoffs;
static TSet<TWeakObjectPtr<const AProphecyAgent>> HandoffReady;
static FDelegateHandle Cleanup;
static void EnsureCleanup()
{
    if(Cleanup.IsValid()) return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        auto Clean=[W](auto& M) { for(auto It=M.CreateIterator();It;++It)
            if(!It.Key().IsValid() || It.Key()->GetWorld()==W) It.RemoveCurrent(); };
        Clean(Configs);Clean(Baselines);Clean(Returns);Clean(Handoffs);
        for(auto It=HandoffReady.CreateIterator();It;++It) if(!It->IsValid() || It->Get()->GetWorld()==W) It.RemoveCurrent();
    });
}
static void Spring(FMotion& M,const FQuat& Target,double Response,double Dt)
{
    using namespace ProphecyPelvisInertia;
    if(Dt<=0) return;
    const double W=2./Response,E=FMath::Exp(-W*Dt);
    const FVector X=RotationVector(M.Rotation*Target.Inverse()),C=M.Velocity+W*X;
    M.Rotation=(RotationIncrement((X+C*Dt)*E)*Target).GetNormalized();
    M.Velocity=(M.Velocity-W*C*Dt)*E;
}
bool Active(const AProphecyAgent* A) { return !Returns.IsEmpty() && Returns.Contains(A); }
void Cancel(const AProphecyAgent* A) { Handoffs.Remove(A);HandoffReady.Remove(A);if(Returns.Remove(A)) ProphecyBlendClock::Stop(A,K::UpperBodyInertia); }
void Remove(const AProphecyAgent* A) { Cancel(A);Configs.Remove(A);Baselines.Remove(A); }
void CaptureReset(const AProphecyAgent* A) { EnsureCleanup();if(const auto* C=Configs.Find(A)) Baselines.Add(A,*C);else Baselines.Remove(A); }
void RestoreReset(const AProphecyAgent* A) { Cancel(A);Configs.Remove(A);if(const auto* C=Baselines.Find(A)) Configs.Add(A,*C); }
void ForgetReset(const AProphecyAgent* A) { Baselines.Remove(A); }
void Begin(const AProphecyAgent* A,TConstArrayView<FTransform> Previous,TConstArrayView<FTransform> World,
    TConstArrayView<FName> Names,TConstArrayView<FName> Core,double Dt)
{
    Cancel(A);const auto* C=Configs.IsEmpty()?nullptr:Configs.Find(A);if(!C || Dt<=0 || World.Num()!=Names.Num() || Previous.Num()!=World.Num()) return;
    FReturn R;R.Config=*C;
    for(FName N:Core)
    {
        const int32 I=Names.IndexOfByKey(N);if(I==INDEX_NONE) return;
        const FQuat Q=World[I].GetRotation();
        R.Joints.Add({Q,ProphecyPelvisInertia::RotationVector(Q*Previous[I].GetRotation().Inverse())*(C->Momentum/Dt)});
    }
    Returns.Add(A,MoveTemp(R));Handoffs.Add(A).Append(World.GetData(),World.Num());
    ProphecyBlendClock::Start(A,K::UpperBodyInertia,double(C->Hold)+C->Blend);
}
void PreserveHandoff(const AProphecyAgent* A,TConstArrayView<int32> Parents,TConstArrayView<FName> Names,
    TConstArrayView<FName> Core,const FTransform& Carrier,TArrayView<FTransform> PreviousPose)
{
    const auto* World=Handoffs.IsEmpty()?nullptr:Handoffs.Find(A);if(!World || !HandoffReady.Contains(A))return;
    // The reduced upper state contains rotations, not the outgoing attack's FK
    // offsets. Re-decoding that previous endpoint would move the head before
    // interpolation even starts. Retain the actual outgoing upper-body endpoint.
    if(World->Num()==PreviousPose.Num()) for(int32 B=0;B<PreviousPose.Num();++B)
        for(int32 P=B;P!=INDEX_NONE;P=Parents[P]) if(Core.Contains(Names[P]))
        { PreviousPose[B]=(*World)[B].GetRelativeTransform(Carrier);break; }
}
void Apply(const AProphecyAgent* A,TConstArrayView<int32> Parents,TConstArrayView<FName> Names,
    TConstArrayView<FName> Core,const FTransform& Carrier,TArrayView<FTransform> Pose,double PoseStepSeconds)
{
    auto* R=Returns.IsEmpty()?nullptr:Returns.Find(A);if(!R) return;
    const double Dt=ProphecyBlendClock::Consume(A,K::UpperBodyInertia);R->Elapsed+=Dt;
    if(R->Elapsed+1.e-8>=double(R->Config.Hold)+R->Config.Blend) {Cancel(A);return;}
    if(HandoffReady.Remove(A)) Handoffs.Remove(A);
    else if(Handoffs.Contains(A)) HandoffReady.Add(A);
    const double T=R->Elapsed<R->Config.Hold?0.:R->Config.Blend>0?FMath::Clamp((R->Elapsed-R->Config.Hold)/R->Config.Blend,0.,1.):1.;
    const double Alpha=T*T*(3.-2.*T);
    TArray<FTransform,TInlineAllocator<32>> Before;Before.Append(Pose.GetData(),Pose.Num());
    // Traverse parent order. FK attachments are preserved, while each joint's
    // world rotation carries its outgoing angular velocity through the handoff.
    for(int32 B=0;B<Pose.Num();++B)
    {
        const int32 I=Core.IndexOfByKey(Names[B]);if(I==INDEX_NONE || !R->Joints.IsValidIndex(I)) continue;
        const int32 P=Parents[B];if(P==INDEX_NONE) continue;
        auto& M=R->Joints[I];const FQuat Goal=(Before[B]*Carrier).GetRotation();
        // A future NN pose spans its complete sample interval, even when its
        // first evaluation is only one game tick after Attack Ended. The
        // ownership clock is still counted in authored 60 Hz ticks separately.
        Spring(M,Goal,R->Config.Response,PoseStepSeconds>=0?PoseStepSeconds:Dt);
        const FQuat Q=FQuat::Slerp(M.Rotation,Goal,Alpha).GetNormalized();
        const FVector Offset=Before[B].GetRelativeTransform(Before[P]).GetLocation();
        Pose[B].SetLocation(Pose[P].TransformPosition(Offset));
        Pose[B].SetRotation((Carrier.GetRotation().Inverse()*Q).GetNormalized());
    }
}
}
bool UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(AProphecyAgent* A,bool Enabled,float Response,float Hold,float Blend,float Momentum)
{
    using namespace ProphecyUpperBodyInertia;
    if(!IsInGameThread() || !IsValid(A) || A->IsActorBeingDestroyed() || !A->GetWorld() || A->GetWorld()->bIsTearingDown) return false;
    for(float V:{Response,Hold,Blend,Momentum}) if(!FMath::IsFinite(V) || V<0) return false;
    if(Enabled && Response>0 && Hold+Blend>0)
    {
        if(const auto* C=Configs.Find(A)) if(C->Response==Response && C->Hold==Hold && C->Blend==Blend && C->Momentum==Momentum) return true;
        EnsureCleanup();Cancel(A);Configs.Add(A,FConfig{Response,Hold,Blend,Momentum});
    }
    else {Cancel(A);Configs.Remove(A);}
    return true;
}
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyCoreInertiaTest,"Prophecy.NN.UpperBodyInertia.SpringAndRetirement",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyCoreInertiaTest::RunTest(const FString&)
{
    using namespace ProphecyUpperBodyInertia;
    FMotion M;M.Velocity=FVector(0,0,2);const double Dt=1.e-5;
    Spring(M,FQuat::Identity,.25,Dt);
    TestTrue(TEXT("Initial outgoing velocity retained in the continuous limit"),FMath::Abs(ProphecyPelvisInertia::RotationVector(M.Rotation).Z/Dt-2)<.001);
    for(int32 I=0;I<600;++I) Spring(M,FQuat::Identity,.25,1./60);
    TestTrue(TEXT("Stationary target settles without residual drift"),M.Velocity.IsNearlyZero(1.e-6) && M.Rotation.AngularDistance(FQuat::Identity)<1.e-6);
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    const TArray<FName> Names={TEXT("pelvis"),TEXT("head")},Core={TEXT("head")};const TArray<int32> Parents={INDEX_NONE,0};
    const TArray<FTransform> Previous={FTransform::Identity,FTransform(FRotator(0,0,0),FVector(0,0,70))};
    const TArray<FTransform> Next={FTransform::Identity,FTransform(FRotator(0,4,0),FVector(0,0,70))};
    for(float FPS:{30.f,60.f,120.f})
    {
        UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,.25,.5,.5,1);
        CaptureReset(A);Begin(A,Previous,Next,Names,Core,1./30);TestTrue(TEXT("Configured attack return starts"),Active(A));
        for(int32 I=0;I<60;++I)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1/FPS);
            TArray<FTransform> Pose=Next;Apply(A,Parents,Names,Core,FTransform::Identity,Pose);
            TestTrue(TEXT("FK offset retained"),Pose[1].GetLocation()==Next[1].GetLocation());
        }
        TestFalse(TEXT("Retires at 60 ticks regardless of FPS"),Active(A));
        RestoreReset(A);Begin(A,Previous,Next,Names,Core,1./30);Cancel(A);TestFalse(TEXT("Special/reset cancels motion"),Active(A));
        UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,.25,0,0,1);Begin(A,Previous,Next,Names,Core,1./30);
        TestFalse(TEXT("Zero durations retain no active work"),Active(A));
    }
    UProphecyUpperBodyInertiaLibrary::SetAttackUpperBodyInertia(A,true,.25,0,.5,1);
    Begin(A,Previous,Next,Names,Core,1./30);
    FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/60);
    TArray<FTransform> Pose=Next;
    Apply(A,Parents,Names,Core,FTransform::Identity,Pose,1./30);
    TestTrue(TEXT("First future pose integrates a full NN interval, not just the first ownership tick"),
        FMath::RadiansToDegrees(Next[1].GetRotation().AngularDistance(Pose[1].GetRotation()))>2.5);
    const FTransform Carrier(FRotator(0,70,0),FVector(100,-80,0));
    for(int32 Repeat=0;Repeat<2;++Repeat)
    {
        TArray<FTransform> Out=Next;Out[1].AddToTranslation(FVector(2,0,0));
        const FTransform Pelvis=Out[0];
        PreserveHandoff(A,Parents,Names,Core,Carrier,Out);
        TestTrue(TEXT("Outgoing upper endpoint retains its actual world pose across root snaps"),(Out[1]*Carrier).Equals(Next[1],1.e-6));
        TestTrue(TEXT("Handoff does not change pelvis or legs"),Out[0].Equals(Pelvis));
    }
    FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/60);
    Apply(A,Parents,Names,Core,FTransform::Identity,Pose,1./30);
    TestTrue(TEXT("Outgoing endpoint cache retires after its one interpolation interval"),Handoffs.IsEmpty() && HandoffReady.IsEmpty());
    Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
#endif
