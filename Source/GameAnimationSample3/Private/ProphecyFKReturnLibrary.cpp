#include "ProphecyFKReturnLibrary.h"
#include "ProphecyFKReturn.h"
#include "ProphecyFKReturnData.h"
#include "ProphecyAgent.h"
#include "ProphecyBlendClock.h"
#include "Engine/World.h"
#if WITH_EDITOR
#include "HAL/IConsoleManager.h"
#endif

namespace ProphecyFKReturn
{
struct FConfig { bool Enabled=true;float Coefficient=1.f,AlphaHold=0.f;TMap<FName,FProfile> Profiles; };
struct FActive
{
    FCurve Curve;
    FTransform PreviousLocal[BoneCount],CurrentLocal[BoneCount];
#if WITH_EDITOR
    double LastAudit=-1;
#endif
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FConfig> Configs,Baselines;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FActive> Active;
// Publication identity and bounded game-tick progress are separate.
struct FTickPhase
{
    double Elapsed=0,Publication=0;
    uint64 Ticks=0,Limit=0;
    bool Sampled=false,Complete=false,PreviousComplete=false;
};
static TMap<TWeakObjectPtr<const AProphecyAgent>,FTickPhase> TickPhases;
static FDelegateHandle Cleanup;
#if WITH_EDITOR
static TAutoConsoleVariable<int32> Audit(TEXT("Prophecy.FKReturn.Audit"),0,TEXT("Log FK return handoff/weights; diagnostic only."));
#endif
static void EnsureCleanup()
{
    if(Cleanup.IsValid())return;
    Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        auto Clean=[W](auto& Map){for(auto It=Map.CreateIterator();It;++It)
            if(!It.Key().IsValid() || It.Key()->GetWorld()==W)It.RemoveCurrent();};
        Clean(Configs);Clean(Baselines);Clean(Active);Clean(TickPhases);
    });
}
bool Prepare(FCurve& Curve,const FProfile& P,float Coefficient,TConstArrayView<FName> Names,
    TConstArrayView<int32> Parents,TConstArrayView<FTransform> Previous,
    TConstArrayView<FTransform> Current,float Dt)
{
    if(P.Duration<=0 || Dt<=0 || Names.Num()!=Parents.Num() || Names.Num()!=Current.Num() || Current.Num()!=Previous.Num())return false;
    Curve.InverseDuration=1.f/P.Duration;Curve.Easing=P.Easing;Curve.Coefficient=Coefficient;
    Curve.SetAlphaHold(0.f);
    for(int32 G=0;G<GroupCount;++G)
    {
        const float I=P.Inertia*P.Weights[G];Curve.Decay[G]=I>0?Curve.InverseDuration/(.025f+.45f*I):0;
        Curve.DecaySource[G]=G;
        for(int32 Earlier=0;Earlier<G;++Earlier)if(Curve.Decay[Earlier]==Curve.Decay[G])
        {Curve.DecaySource[G]=Earlier;break;}
    }
    for(int32 J=0;J<BoneCount;++J)
    {
        const auto& D=Data::Bones[J];auto& B=Curve.Bones[J];
        B.Index=Names.IndexOfByKey(FName(D.Name));
        if(B.Index==INDEX_NONE)return false;
        B.Parent=Parents[B.Index];B.Group=D.Group;
        if(!Names.IsValidIndex(B.Parent) || Names[B.Parent]!=FName(D.Parent))return false;
        const auto A=Previous[B.Index].GetRelativeTransform(Previous[B.Parent]);
        const auto Z=Current[B.Index].GetRelativeTransform(Current[B.Parent]);
        B.Start=FQuat4f(Z.GetRotation());B.Offset=FVector3f(Z.GetTranslation());
        B.Return.Set(B.Start.Inverse()*FQuat4f(D.Q[0],D.Q[1],D.Q[2],D.Q[3]));
        B.OffsetReturn.Set(Swing(B.Offset,FVector3f(D.P[0],D.P[1],D.P[2])));
        B.Velocity.Set(FQuat4f(A.GetRotation()).Inverse()*B.Start,1.f/Dt);
        B.OffsetVelocity.Set(Swing(FVector3f(A.GetTranslation()),B.Offset),1.f/Dt);
    }
    return true;
}
void Cancel(const AProphecyAgent* Agent)
{
    if(!Active.IsEmpty())Active.Remove(Agent);
    if(!TickPhases.IsEmpty())TickPhases.Remove(Agent);
    ProphecyBlendClock::Stop(Agent,ProphecyBlendClock::EKind::FKReturn);
}
void Remove(const AProphecyAgent* Agent){Cancel(Agent);Configs.Remove(Agent);Baselines.Remove(Agent);}
void CaptureReset(const AProphecyAgent* Agent)
{EnsureCleanup();if(const auto* C=Configs.Find(Agent))Baselines.Add(Agent,*C);else Baselines.Remove(Agent);}
void RestoreReset(const AProphecyAgent* Agent)
{Cancel(Agent);Configs.Remove(Agent);if(const auto* C=Baselines.Find(Agent))Configs.Add(Agent,*C);}
void ForgetReset(const AProphecyAgent* Agent){Baselines.Remove(Agent);}
void Begin(const AProphecyAgent* Agent,FName Attack,TConstArrayView<FName> Names,
    TConstArrayView<int32> Parents,TConstArrayView<FTransform> Previous,
    TConstArrayView<FTransform> Current,double SourceTime,float SampleSeconds,uint32 PublishedAgeTicks)
{
    Cancel(Agent);if(!IsValid(Agent))return;
    const auto* C=Configs.IsEmpty()?nullptr:Configs.Find(Agent);
    if(C && !C->Enabled)return;
    FProfile Profile;
    for(const auto& P:Data::Profiles)if(Attack==FName(P.Attack))
    {
        Profile.Duration=P.Duration;Profile.Inertia=P.Inertia;Profile.Easing=P.Easing;
        FMemory::Memcpy(Profile.Weights,P.Weights,sizeof(Profile.Weights));break;
    }
    if(C)
    {
        const auto* P=C->Profiles.Find(Attack);if(!P)P=C->Profiles.Find(NAME_None);if(P)Profile=*P;
    }
    FActive A;
    if(!Prepare(A.Curve,Profile,C?C->Coefficient:1.f,Names,Parents,Previous,Current,SampleSeconds))return;
    A.Curve.SetAlphaHold(C?C->AlphaHold:0.f);
    for(int32 J=0;J<BoneCount;++J)
    {const auto& B=A.Curve.Bones[J];A.PreviousLocal[J]=Previous[B.Index].GetRelativeTransform(Previous[B.Parent]);
        A.CurrentLocal[J]=Current[B.Index].GetRelativeTransform(Current[B.Parent]);}
    EnsureCleanup();Active.Add(Agent,MoveTemp(A));
    FTickPhase Phase;Phase.Publication=SourceTime;
    // Match the bounded shared clock's integer deadline, including float pins such as .3.
    Phase.Limit=uint64(FMath::Max(1.,FMath::CeilToDouble(FMath::Min(double(Profile.Duration)*60.,9.e15)-1.e-5)));
    // The outgoing endpoint was generated before the stop. The first new
    // endpoint must continue from it, rather than duplicate curve time zero.
    Phase.Ticks=PublishedAgeTicks;Phase.Elapsed=double(Phase.Ticks)/60.;
    TickPhases.Add(Agent,Phase);
    if(Phase.Ticks<Phase.Limit)
        ProphecyBlendClock::Start(Agent,ProphecyBlendClock::EKind::FKReturn,double(Phase.Limit-Phase.Ticks)/60.);
#if WITH_EDITOR
    if(Audit.GetValueOnGameThread())UE_LOG(LogTemp,Display,TEXT("FKReturn begin actor=%s attack=%s duration=%.6f inertia=%.6f easing=%.6f coefficient=%.6f alpha_hold=%.6f source=%.6f"),
        *Agent->GetName(),*Attack.ToString(),Profile.Duration,Profile.Inertia,Profile.Easing,C?C->Coefficient:1.f,C?C->AlphaHold:0.f,SourceTime);
#endif
}
bool Apply(const AProphecyAgent* Agent,double CurrentTime,
    TArrayView<FTransform> Previous,TArrayView<FTransform> Current,TArrayView<FTransform> Local,bool* NewSample)
{
    if(NewSample)*NewSample=false;
    auto* A=Active.IsEmpty()?nullptr:Active.Find(Agent);if(!A)return false;
    auto* Phase=TickPhases.Find(Agent);
    // An old return already active when this patch loads cannot inherit a new clock.
    if(!Phase){Cancel(Agent);return false;}
    if(CurrentTime>Phase->Publication)
    {
        Phase->PreviousComplete=Phase->Complete;
        const double Pending=ProphecyBlendClock::Consume(Agent,ProphecyBlendClock::EKind::FKReturn);
        Phase->Ticks+=uint64(FMath::RoundToDouble(Pending*60.));
        Phase->Elapsed=double(Phase->Ticks)/60.;Phase->Complete=Phase->Ticks>=Phase->Limit;
        Phase->Publication=CurrentTime;Phase->Sampled=false;
        FMemory::Memcpy(A->PreviousLocal,A->CurrentLocal,sizeof(A->CurrentLocal));
        if(!Phase->Complete)A->Curve.Apply(float(Phase->Elapsed),Current,Local);
        for(int32 J=0;J<BoneCount;++J)
        {const auto& B=A->Curve.Bones[J];A->CurrentLocal[J]=Current[B.Index].GetRelativeTransform(Current[B.Parent]);}
    }
    // Keep the final interval until BOTH endpoints are vanilla NN, including repeat publications.
    if(Phase->PreviousComplete)
    {
#if WITH_EDITOR
        if(Audit.GetValueOnGameThread())UE_LOG(LogTemp,Display,TEXT("FKReturn complete actor=%s exact_NN=1"),*Agent->GetName());
#endif
        Cancel(Agent);return false;
    }
    // These are already accepted samples. Reapplying the curve to a fed-back
    // pose would blend it twice and corrupt both history and repeated publishes.
    for(int32 J=0;J<BoneCount;++J)
    {
        const auto& B=A->Curve.Bones[J];
        Previous[B.Index]=A->PreviousLocal[J]*Previous[B.Parent];
        if(!Phase->Complete)
        {
            Current[B.Index]=A->CurrentLocal[J]*Current[B.Parent];
            if(!Local.IsEmpty())Local[B.Index]=A->CurrentLocal[J];
        }
    }
    if(NewSample)*NewSample=!Phase->Sampled;
    Phase->Sampled=true;
#if WITH_EDITOR
    if(Audit.GetValueOnGameThread() && A->LastAudit!=CurrentTime)
    {
        A->LastAudit=CurrentTime;
        UE_LOG(LogTemp,Display,TEXT("FKReturn sample actor=%s tick_seconds=%.6f nn=%.6f"),*Agent->GetName(),Phase->Elapsed,Phase->Complete?1.f:A->Curve.Weights(float(Phase->Elapsed)).NN);
    }
#endif
    return true;
}
bool IsActive(const AProphecyAgent* Agent){return !Active.IsEmpty() && Active.Contains(Agent);}
bool NeedsInference(const AProphecyAgent* Agent)
{
    const auto* A=Active.IsEmpty()?nullptr:Active.Find(Agent);if(!A)return true;
    auto* Phase=TickPhases.Find(Agent);if(!Phase)return true;
    Phase->Ticks+=uint64(FMath::RoundToDouble(ProphecyBlendClock::Consume(Agent,ProphecyBlendClock::EKind::FKReturn)*60.));
    Phase->Elapsed=double(Phase->Ticks)/60.;
    return Phase->Ticks>=Phase->Limit || A->Curve.NNWeight(float(Phase->Elapsed)*A->Curve.InverseDuration)>0.f;
}
static bool Valid(const AProphecyAgent* Agent)
{return IsInGameThread() && IsValid(Agent) && !Agent->IsActorBeingDestroyed() && Agent->GetWorld() && !Agent->GetWorld()->bIsTearingDown;}
}

bool UProphecyFKReturnLibrary::SetAttackFKReturn(AProphecyAgent* Agent,bool Enabled,float Coefficient,float AlphaHold)
{
    using namespace ProphecyFKReturn;
    if(!Valid(Agent) || !FMath::IsFinite(Coefficient) || Coefficient<.01f ||
        !FMath::IsFinite(AlphaHold) || AlphaHold<0.f || AlphaHold>1.f)return false;
    EnsureCleanup();auto& C=Configs.FindOrAdd(Agent);C.Enabled=Enabled;C.Coefficient=Coefficient;C.AlphaHold=AlphaHold;
    if(!Enabled)Cancel(Agent);return true;
}
bool UProphecyFKReturnLibrary::SetAttackFKReturnProfile(AProphecyAgent* Agent,FName Attack,float ReturnTime,
    float Inertia,float Easing,FProphecyFKInertiaWeights BoneInertia)
{
    using namespace ProphecyFKReturn;
    if(!Valid(Agent) || !FMath::IsFinite(ReturnTime) || ReturnTime<0)return false;
    const float W[]={BoneInertia.Spine,BoneInertia.Clavicle,BoneInertia.UpperArm,BoneInertia.LowerArm,
        BoneInertia.Neck01,BoneInertia.Neck02,BoneInertia.Head};
    for(float V:W)if(!FMath::IsFinite(V) || V<0 || V>1)return false;
    for(float V:{Inertia,Easing})if(!FMath::IsFinite(V) || V<0 || V>1)return false;
    FProfile P;P.Duration=ReturnTime;P.Inertia=Inertia;P.Easing=Easing;FMemory::Memcpy(P.Weights,W,sizeof(W));
    EnsureCleanup();auto& C=Configs.FindOrAdd(Agent);
    if(Attack.IsNone())C.Profiles.Reset();
    C.Profiles.Add(Attack,P);return true;
}

#include "ProphecyFKReturnTests.inl"
