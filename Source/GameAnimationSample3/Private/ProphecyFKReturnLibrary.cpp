#include "ProphecyFKReturnLibrary.h"
#include "ProphecyNNModifierDebug.h"
#include "ProphecyFKReturn.h"
#include "ProphecyFKReturnData.h"
#include "ProphecyAgent.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyBlendClock.h"
#include "Engine/World.h"
#if WITH_EDITOR
#include "HAL/IConsoleManager.h"
#endif

namespace ProphecyFKReturn
{
constexpr int32 AttackCount=16;
static_assert(UE_ARRAY_COUNT(Data::Profiles)==AttackCount);
struct FConfig
{
    bool Enabled=true;float Coefficient=1.f;TMap<FName,FProfile> Profiles;
    FVector2f Timing[AttackCount]; // Same stable family order as Data::Profiles.
    FConfig(){for(auto& T:Timing)T=FVector2f(.1f,.34f);}
};
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
struct FParryConfig { FProfile Profile;float Coefficient=1;FVector2f Timing{.1f,.34f}; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FParryConfig> ParryConfigs,ParryBaselines;
static TSet<TWeakObjectPtr<const AProphecyAgent>> ParryActive;
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
        Clean(Configs);Clean(Baselines);Clean(Active);Clean(TickPhases);Clean(ParryConfigs);Clean(ParryBaselines);
        for(auto It=ParryActive.CreateIterator();It;++It)if(!It->IsValid() || It->Get()->GetWorld()==W)It.RemoveCurrent();
    });
}
// UE yaw about +world Z is clockwise viewed from above (X forward, Y right).
// This changes a cached arc only; unaffected returns use exactly the old sampler.
static bool SelectSlashWinding(FCurve& Curve,FName Attack,TConstArrayView<FTransform> Current)
{
    static const FName Left[]={TEXT("slashL"),TEXT("slashLU"),TEXT("slashLD")};
    static const FName Right[]={TEXT("slashR"),TEXT("slashRU"),TEXT("slashRD")};
    const float Direction=(Attack==Left[0] || Attack==Left[1] || Attack==Left[2])?1.f:
        (Attack==Right[0] || Attack==Right[1] || Attack==Right[2])?-1.f:0.f;
    if(Direction==0)return false;
    // Fixed canonical slots: spine_05, upperarm_r, lowerarm_r. All six sword
    // slashes use the right arm. Manny spine_05 local +Z points to its right.
    const auto& Spine=Current[Curve.Bones[4].Index];
    auto& Arm=Curve.Bones[10];
    const FVector Shaft=Current[Curve.Bones[11].Index].GetLocation()-Current[Arm.Index].GetLocation();
    if(Spine.GetRotation().UnrotateVector(Shaft).Z>=-1.e-4* Shaft.Size())return false;
    const FVector Up=Curve.SeedFrame.UnrotateVector(FVector::UpVector);
    const FVector Omega=Current[Arm.Index].GetRotation().RotateVector(FVector(Arm.Return.Axis));
    // Signed horizontal motion of the actual shoulder->elbow direction, not
    // humeral roll or a bone Euler angle. Near-vertical/zero arcs retain the old path.
    const double Sweep=FVector::DotProduct(Up,FVector::CrossProduct(Shaft,FVector::CrossProduct(Omega,Shaft)));
    if(Arm.Return.HalfAngle<=1.e-5f || Direction*Sweep>=-1.e-4* Shaft.SizeSquared())return false;
    Arm.Return.Axis=-Arm.Return.Axis;
    Arm.Return.HalfAngle=PI-Arm.Return.HalfAngle;
    return true;
}
static bool PrepareForAttack(FCurve& Curve,const FProfile& P,float Coefficient,TConstArrayView<FName> Names,
    TConstArrayView<int32> Parents,TConstArrayView<FTransform> Previous,
    TConstArrayView<FTransform> Current,float Dt,TConstArrayView<FVector3f> AngularVelocity,FName Attack)
{
    if(P.Duration<=0 || Dt<=0 || Names.Num()!=Parents.Num() || Names.Num()!=Current.Num() || Current.Num()!=Previous.Num())return false;
    Curve.Easing=P.Easing;Curve.Coefficient=Coefficient;
    Curve.InertiaHold=P.InertiaHold;Curve.InertiaDecay=P.InertiaDecay;Curve.WorldInertia=P.WorldInertia;
    Curve.UpperArmTwistRemoval=P.UpperArmTwistRemoval;
    Curve.TakeoverTimeScale=1.f;
    Curve.SetAlphaHold(0.f);
    for(int32 G=0;G<GroupCount;++G)
    {
        const float I=P.Inertia*P.Weights[G];Curve.Decay[G]=I>0?1.f/(.025f+.45f*I):0;
        Curve.DecaySource[G]=G;
        for(int32 Earlier=0;Earlier<G;++Earlier)if(Curve.Decay[Earlier]==Curve.Decay[G])
        {Curve.DecaySource[G]=Earlier;break;}
    }
    for(int32 J=0;J<BoneCount;++J)
    {
        const auto& D=Data::Bones[J];auto& B=Curve.Bones[J];
        B.Index=Names.IndexOfByKey(FName(D.Name));
        if(B.Index==INDEX_NONE)return false;
        B.Parent=Parents[B.Index];B.Group=D.Group;B.ParentSlot=INDEX_NONE;
        for(int32 K=0;K<J;++K)if(Curve.Bones[K].Index==B.Parent){B.ParentSlot=K;break;}
        if(!Names.IsValidIndex(B.Parent) || Names[B.Parent]!=FName(D.Parent))return false;
        const auto A=Previous[B.Index].GetRelativeTransform(Previous[B.Parent]);
        const auto Z=Current[B.Index].GetRelativeTransform(Current[B.Parent]);
        B.Start=FQuat4f(Z.GetRotation());B.Offset=FVector3f(Z.GetTranslation());
        B.Return.Set(B.Start.Inverse()*FQuat4f(D.Q[0],D.Q[1],D.Q[2],D.Q[3]));
        B.OffsetReturn.Set(Swing(B.Offset,FVector3f(D.P[0],D.P[1],D.P[2])));
        B.Velocity.Set(FQuat4f(A.GetRotation()).Inverse()*B.Start,1.f/Dt);
        B.OffsetVelocity.Set(Swing(FVector3f(A.GetTranslation()),B.Offset),1.f/Dt);
    }
    Curve.StartPelvis=FQuat4f(Current[Curve.Bones[0].Parent].GetRotation());
    const float AngleDegrees=FMath::RadiansToDegrees(2.f*Curve.Bones[0].Return.HalfAngle);
    Curve.InverseDuration=1.f/(P.Duration+P.AngleTimeSeconds*AngleDegrees/90.f);
    SelectSlashWinding(Curve,Attack,Current);
    FVector3f BaseRate[BoneCount],ReturnRate[BoneCount];
    for(int32 J=0;J<BoneCount;++J)
    {
        auto& B=Curve.Bones[J];const FQuat4f End(Current[B.Index].GetRotation());
        const FVector3f IdleRate=B.Return.Axis*(2.f*B.Return.HalfAngle*(1-P.Easing)*Curve.InverseDuration);
        FArc Outgoing;Outgoing.Set(FQuat4f(Current[B.Index].GetRotation()*Previous[B.Index].GetRotation().Inverse()),1.f/Dt);
        const FVector3f Velocity=AngularVelocity.Num()==Current.Num()?AngularVelocity[B.Index]:Outgoing.Axis*(2.f*Outgoing.HalfAngle);
        const FVector3f ParentBase=B.ParentSlot<0?FVector3f::ZeroVector:BaseRate[B.ParentSlot];
        const FVector3f ParentReturn=B.ParentSlot<0?FVector3f::ZeroVector:ReturnRate[B.ParentSlot];
        BaseRate[J]=ParentBase+End.RotateVector(IdleRate);
        auto SetRate=[](FArc& Arc,const FVector3f& V){const float N=V.Size();Arc.Axis=N>1.e-10f?V/N:FVector3f::ZeroVector;Arc.HalfAngle=N*.5f;};
        SetRate(B.WorldCorrection,Velocity-BaseRate[J]);
        const bool Enabled=B.Group<GroupCount && Curve.Decay[B.Group]>0;
        const FVector3f LocalRate=Enabled?End.UnrotateVector(Velocity-ParentReturn)-IdleRate:FVector3f::ZeroVector;
        SetRate(B.Velocity,LocalRate);
        ReturnRate[J]=ParentReturn+End.RotateVector(IdleRate+LocalRate);
    }
    return true;
}
bool Prepare(FCurve& Curve,const FProfile& P,float Coefficient,TConstArrayView<FName> Names,
    TConstArrayView<int32> Parents,TConstArrayView<FTransform> Previous,
    TConstArrayView<FTransform> Current,float Dt,TConstArrayView<FVector3f> AngularVelocity)
{
    return PrepareForAttack(Curve,P,Coefficient,Names,Parents,Previous,Current,Dt,AngularVelocity,NAME_None);
}
void Cancel(const AProphecyAgent* Agent)
{
    if(!Active.IsEmpty())Active.Remove(Agent);ParryActive.Remove(Agent);
    if(!TickPhases.IsEmpty())TickPhases.Remove(Agent);
    ProphecyBlendClock::Stop(Agent,ProphecyBlendClock::EKind::FKReturn);
}
void Remove(const AProphecyAgent* Agent){Cancel(Agent);Configs.Remove(Agent);Baselines.Remove(Agent);ParryConfigs.Remove(Agent);ParryBaselines.Remove(Agent);}
void CaptureReset(const AProphecyAgent* Agent)
{EnsureCleanup();if(const auto* C=Configs.Find(Agent))Baselines.Add(Agent,*C);else Baselines.Remove(Agent);if(const auto* P=ParryConfigs.Find(Agent))ParryBaselines.Add(Agent,*P);else ParryBaselines.Remove(Agent);}
void RestoreReset(const AProphecyAgent* Agent)
{Cancel(Agent);Configs.Remove(Agent);if(const auto* C=Baselines.Find(Agent))Configs.Add(Agent,*C);ParryConfigs.Remove(Agent);if(const auto* P=ParryBaselines.Find(Agent))ParryConfigs.Add(Agent,*P);}
void ForgetReset(const AProphecyAgent* Agent){Baselines.Remove(Agent);ParryBaselines.Remove(Agent);}
static void BeginResolved(const AProphecyAgent* Agent,FName Attack,const FProfile& Profile,
    float Coefficient,FVector2f Timing,TConstArrayView<FName> Names,
    TConstArrayView<int32> Parents,TConstArrayView<FTransform> Previous,
    TConstArrayView<FTransform> Current,double SourceTime,float SampleSeconds,uint32 PublishedAgeTicks)
{
    const float AlphaHold=Timing.X,Trim=Timing.Y;if(Trim>=1.f)return;
    FActive A;
    // Capture published WORLD angular rates once, including the mover's carrier yaw.
    // The live source interpolates bone rotations; seed that source rather than a
    // parent-local difference, which loses pelvis motion at the upper boundary.
    TArray<FVector3f,TInlineAllocator<32>> Rates;
    int32 PoseId;float Interval;bool Interpolate;FProphecyNNPoseSnapshot Snapshot;
    if(Agent->GetNNPoseDataSource(PoseId,Interval,Interpolate) &&
        FProphecyNNPoseStore::GetAgentLocalPose(PoseId,Snapshot) && Snapshot.SourceTimeSeconds==SourceTime)
    {
        A.Curve.SeedFrame=Snapshot.ComponentWorldTransform.GetRotation();
        const FQuat PreviousFrame=Snapshot.PreviousComponentWorldTransform.GetRotation();
        Rates.SetNum(Current.Num());
        for(int32 J=0;J<Current.Num();++J)
        {
            const FQuat End=A.Curve.SeedFrame*Current[J].GetRotation();
            const FQuat Start=PreviousFrame*Previous[J].GetRotation();
            FQuat Delta=(End*Start.Inverse()).GetNormalized();if(Delta.W<0)Delta=Delta*-1.;
            const double N=FVector(Delta.X,Delta.Y,Delta.Z).Size();
            const double Angle=2.*FMath::Atan2(N,Delta.W);
            // Current presentation uses the polar rotation of a matrix lerp.
            const double Scale=Snapshot.InterpolationMode==EProphecyNNInterpolationMode::Current && Angle>1.e-6?FMath::Sin(Angle)/Angle:1.;
            const FVector Rate=N>1.e-12?FVector(Delta.X,Delta.Y,Delta.Z)*(Angle*Scale/(N*SampleSeconds)):FVector::ZeroVector;
            Rates[J]=FVector3f(A.Curve.SeedFrame.UnrotateVector(Rate));
        }
    }
    if(!PrepareForAttack(A.Curve,Profile,Coefficient,Names,Parents,Previous,Current,SampleSeconds,Rates,Attack))return;
    A.Curve.SetAlphaHold(AlphaHold);
    A.Curve.TakeoverTimeScale=1.f/(1.f-Trim);
    for(int32 J=0;J<BoneCount;++J)
    {const auto& B=A.Curve.Bones[J];A.PreviousLocal[J]=Previous[B.Index].GetRelativeTransform(Previous[B.Parent]);
        A.CurrentLocal[J]=Current[B.Index].GetRelativeTransform(Current[B.Parent]);}
    EnsureCleanup();Active.Add(Agent,MoveTemp(A));
    FTickPhase Phase;Phase.Publication=SourceTime;
    // Match the bounded shared clock's integer deadline, including float pins such as .3.
    const double EndDuration=(1./double(A.Curve.InverseDuration))*(1.-double(Trim));
    Phase.Limit=uint64(FMath::Max(1.,FMath::CeilToDouble(FMath::Min(EndDuration*60.,9.e15)-1.e-5)));
    // The outgoing endpoint was generated before the stop. The first new
    // endpoint must continue from it, rather than duplicate curve time zero.
    Phase.Ticks=PublishedAgeTicks;Phase.Elapsed=double(Phase.Ticks)/60.;
    TickPhases.Add(Agent,Phase);
    if(Phase.Ticks<Phase.Limit)
        ProphecyBlendClock::Start(Agent,ProphecyBlendClock::EKind::FKReturn,double(Phase.Limit-Phase.Ticks)/60.);
#if WITH_EDITOR
    if(Audit.GetValueOnGameThread())UE_LOG(LogTemp,Display,TEXT("FKReturn begin actor=%s attack=%s duration=%.6f inertia=%.6f easing=%.6f coefficient=%.6f alpha_hold=%.6f trim=%.6f end_duration=%.6f source=%.6f inertia_hold=%.6f decay=%.6f world=%d angle_seconds=%.6f world_seed=%d"),
        *Agent->GetName(),*Attack.ToString(),Profile.Duration,Profile.Inertia,Profile.Easing,Coefficient,AlphaHold,Trim,EndDuration,SourceTime,Profile.InertiaHold,Profile.InertiaDecay,int32(Profile.WorldInertia),Profile.AngleTimeSeconds,int32(!Rates.IsEmpty()));
#endif
}
void Begin(const AProphecyAgent* Agent,FName Attack,TConstArrayView<FName> Names,
    TConstArrayView<int32> Parents,TConstArrayView<FTransform> Previous,
    TConstArrayView<FTransform> Current,double SourceTime,float SampleSeconds,uint32 PublishedAgeTicks)
{
    Cancel(Agent);if(!IsValid(Agent))return;
    const auto* C=Configs.IsEmpty()?nullptr:Configs.Find(Agent);
    if(C && !C->Enabled)return;
    FVector2f Timing(.1f,.34f);FProfile Profile;
    for(int32 I=0;I<AttackCount;++I)if(Attack==FName(Data::Profiles[I].Attack))
    {
        const auto& P=Data::Profiles[I];if(C)Timing=C->Timing[I];
        Profile.Duration=P.Duration;Profile.Inertia=P.Inertia;Profile.Easing=P.Easing;
        Profile.InertiaHold=P.InertiaHold;Profile.InertiaDecay=P.InertiaDecay;Profile.AngleTimeSeconds=P.AngleTimeSeconds;Profile.WorldInertia=P.WorldInertia;
        Profile.UpperArmTwistRemoval=P.UpperArmTwistRemoval;
        FMemory::Memcpy(Profile.Weights,P.Weights,sizeof(Profile.Weights));break;
    }
    if(C)
    {
        const auto* P=C->Profiles.Find(Attack);if(!P)P=C->Profiles.Find(NAME_None);if(P)Profile=*P;
    }
    BeginResolved(Agent,Attack,Profile,C?C->Coefficient:1.f,Timing,Names,Parents,Previous,Current,SourceTime,SampleSeconds,PublishedAgeTicks);
}
void BeginParry(const AProphecyAgent* Agent,TConstArrayView<FName> Names,
    TConstArrayView<int32> Parents,TConstArrayView<FTransform> Previous,
    TConstArrayView<FTransform> Current,double SourceTime,float SampleSeconds,uint32 PublishedAgeTicks)
{
    Cancel(Agent);if(!IsValid(Agent))return;
    const auto* C=ParryConfigs.IsEmpty()?nullptr:ParryConfigs.Find(Agent);if(!C)return;
    BeginResolved(Agent,NAME_None,C->Profile,C->Coefficient,C->Timing,Names,Parents,Previous,Current,SourceTime,SampleSeconds,PublishedAgeTicks);
    if(Active.Contains(Agent))ParryActive.Add(Agent);
}
bool Apply(const AProphecyAgent* Agent,double CurrentTime,
    TArrayView<FTransform> Previous,TArrayView<FTransform> Current,TArrayView<FTransform> Local,bool* NewSample,const FQuat& Frame)
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
        if(!Phase->Complete)A->Curve.Apply(float(Phase->Elapsed),Current,Local,Frame);
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
// Resolve only when a setter executes; the handoff/tick path is unchanged.
static FProfile CurrentProfile(const FConfig& C,FName Attack)
{
    if(const auto* P=C.Profiles.Find(Attack))return *P;
    if(const auto* P=C.Profiles.Find(NAME_None))return *P;
    FProfile R;
    for(const auto& P:Data::Profiles)if(Attack==FName(P.Attack))
    {
        R.Duration=P.Duration;R.Inertia=P.Inertia;R.Easing=P.Easing;
        R.InertiaHold=P.InertiaHold;R.InertiaDecay=P.InertiaDecay;
        R.WorldInertia=P.WorldInertia;R.AngleTimeSeconds=P.AngleTimeSeconds;
        R.UpperArmTwistRemoval=P.UpperArmTwistRemoval;
        FMemory::Memcpy(R.Weights,P.Weights,sizeof(R.Weights));break;
    }
    return R;
}
template<typename F> static void UpdateProfileFields(AProphecyAgent* Agent,FName Attack,F&& Update)
{
    EnsureCleanup();auto& C=Configs.FindOrAdd(Agent);
    if(!Attack.IsNone())
    {
        FProfile P=CurrentProfile(C,Attack);Update(P);C.Profiles.Add(Attack,P);return;
    }
    // Resolve every family before replacing the fallback, preserving per-attack differences.
    TMap<FName,FProfile> Updated=C.Profiles;
    for(const auto& P:Data::Profiles)Updated.FindOrAdd(FName(P.Attack));
    Updated.FindOrAdd(NAME_None);
    for(auto& Entry:Updated){Entry.Value=CurrentProfile(C,Entry.Key);Update(Entry.Value);}
    C.Profiles=MoveTemp(Updated);
}
}

bool UProphecyFKReturnLibrary::SetAttackFKReturnTwistInertia(AProphecyAgent* Agent,FName Attack,float RemoveTwist)
{
    using namespace ProphecyFKReturn;
    if(!Valid(Agent) || !FMath::IsFinite(RemoveTwist) || RemoveTwist<0 || RemoveTwist>1)return false;
    UpdateProfileFields(Agent,Attack,[=](FProfile& P){P.UpperArmTwistRemoval=RemoveTwist;});return true;
}

bool UProphecyFKReturnLibrary::SetParryFKReturn(AProphecyAgent* Agent,bool Enabled,float ReturnTime,float Inertia,float Easing,
    FVector2D HoldTrim,float Coefficient,FProphecyFKInertiaWeights BoneInertia,float InertiaHold,float InertiaDecay,bool WorldInertia,float SpineAngleTime)
{
    using namespace ProphecyFKReturn;
    if(!Valid(Agent) || !FMath::IsFinite(ReturnTime) || ReturnTime<0 || !FMath::IsFinite(Coefficient) || Coefficient<.01f)return false;
    for(double V:{double(Inertia),double(Easing),HoldTrim.X,HoldTrim.Y})if(!FMath::IsFinite(V) || V<0 || V>1)return false;
    const float W[]={BoneInertia.Spine,BoneInertia.Clavicle,BoneInertia.UpperArm,BoneInertia.LowerArm,BoneInertia.Neck01,BoneInertia.Neck02,BoneInertia.Head};
    for(float V:W)if(!FMath::IsFinite(V) || V<0 || V>1)return false;
    if(!FMath::IsFinite(InertiaHold) || InertiaHold<0 || InertiaHold>.8f || !FMath::IsFinite(InertiaDecay) || InertiaDecay<0 || InertiaDecay>4 ||
        !FMath::IsFinite(SpineAngleTime) || SpineAngleTime<0 || SpineAngleTime>4)return false;
    if(!Enabled){ParryConfigs.Remove(Agent);if(ParryActive.Contains(Agent))Cancel(Agent);return true;}
    FParryConfig C;C.Coefficient=Coefficient;C.Timing=FVector2f(HoldTrim);
    C.Profile.Duration=ReturnTime;C.Profile.Inertia=Inertia;C.Profile.Easing=Easing;C.Profile.InertiaHold=InertiaHold;
    C.Profile.InertiaDecay=InertiaDecay;C.Profile.WorldInertia=WorldInertia;C.Profile.AngleTimeSeconds=SpineAngleTime;
    FMemory::Memcpy(C.Profile.Weights,W,sizeof(W));EnsureCleanup();ParryConfigs.Add(Agent,C);return true;
}

bool UProphecyFKReturnLibrary::SetAttackFKReturn(AProphecyAgent* Agent,bool Enabled,float Coefficient,
    FVector2D Headbutt, FVector2D HookL, FVector2D HookR, FVector2D JabL, FVector2D JabR, FVector2D KickL, FVector2D KickR, FVector2D OverL, FVector2D OverR, FVector2D Pike, FVector2D SlashL, FVector2D SlashLD, FVector2D SlashLU, FVector2D SlashR, FVector2D SlashRD, FVector2D SlashRU)
{
    using namespace ProphecyFKReturn;
    if(!Valid(Agent) || !FMath::IsFinite(Coefficient) || Coefficient<.01f)return false;
    const FVector2D Values[]={Headbutt,HookL,HookR,JabL,JabR,KickL,KickR,OverL,OverR,Pike,SlashL,SlashLD,SlashLU,SlashR,SlashRD,SlashRU};
    static_assert(UE_ARRAY_COUNT(Values)==AttackCount);
    // Validate the complete set before changing any agent configuration.
    for(const auto& V:Values)if(!FMath::IsFinite(V.X) || !FMath::IsFinite(V.Y) ||
        V.X<0 || V.X>1 || V.Y<0 || V.Y>1)return false;
    EnsureCleanup();auto& C=Configs.FindOrAdd(Agent);C.Enabled=Enabled;C.Coefficient=Coefficient;
    for(int32 I=0;I<AttackCount;++I)C.Timing[I]=FVector2f(Values[I]);
    if(!Enabled && !ParryActive.Contains(Agent))Cancel(Agent);return true;
}
bool UProphecyFKReturnLibrary::SetAttackFKReturnValues(AProphecyAgent* Agent,FName Attack,float ReturnTime,float Inertia,float Easing)
{
    using namespace ProphecyFKReturn;
    if(!Valid(Agent) || !FMath::IsFinite(ReturnTime) || ReturnTime<0)return false;
    for(float V:{Inertia,Easing})if(!FMath::IsFinite(V) || V<0 || V>1)return false;
    UpdateProfileFields(Agent,Attack,[=](FProfile& P){P.Duration=ReturnTime;P.Inertia=Inertia;P.Easing=Easing;});
    return true;
}
bool UProphecyFKReturnLibrary::SetAttackFKReturnInertiaProfile(AProphecyAgent* Agent,FName Attack,
    FProphecyFKInertiaWeights BoneInertia,float InertiaHold,float InertiaDecay,bool WorldInertia,float SpineAngleTime)
{
    using namespace ProphecyFKReturn;
    if(!Valid(Agent))return false;
    const float W[]={BoneInertia.Spine,BoneInertia.Clavicle,BoneInertia.UpperArm,BoneInertia.LowerArm,
        BoneInertia.Neck01,BoneInertia.Neck02,BoneInertia.Head};
    for(float V:W)if(!FMath::IsFinite(V) || V<0 || V>1)return false;
    if(!FMath::IsFinite(InertiaHold) || InertiaHold<0 || InertiaHold>.8f ||
        !FMath::IsFinite(InertiaDecay) || InertiaDecay<0 || InertiaDecay>4 ||
        !FMath::IsFinite(SpineAngleTime) || SpineAngleTime<0 || SpineAngleTime>4)return false;
    UpdateProfileFields(Agent,Attack,[&](FProfile& P){P.InertiaHold=InertiaHold;P.InertiaDecay=InertiaDecay;
        P.WorldInertia=WorldInertia;P.AngleTimeSeconds=SpineAngleTime;FMemory::Memcpy(P.Weights,W,sizeof(W));});
    return true;
}
bool UProphecyFKReturnLibrary::SetAttackFKReturnProfile(AProphecyAgent* Agent,FName Attack,float ReturnTime,
    float Inertia,float Easing,FProphecyFKInertiaWeights BoneInertia,float InertiaHold,float InertiaDecay,bool WorldInertia,float SpineAngleTime)
{
    using namespace ProphecyFKReturn;
    if(!Valid(Agent) || !FMath::IsFinite(ReturnTime) || ReturnTime<0)return false;
    const float W[]={BoneInertia.Spine,BoneInertia.Clavicle,BoneInertia.UpperArm,BoneInertia.LowerArm,
        BoneInertia.Neck01,BoneInertia.Neck02,BoneInertia.Head};
    for(float V:W)if(!FMath::IsFinite(V) || V<0 || V>1)return false;
    for(float V:{Inertia,Easing})if(!FMath::IsFinite(V) || V<0 || V>1)return false;
    if(!FMath::IsFinite(InertiaHold) || InertiaHold<0 || InertiaHold>.8f ||
        !FMath::IsFinite(InertiaDecay) || InertiaDecay<0 || InertiaDecay>4 ||
        !FMath::IsFinite(SpineAngleTime) || SpineAngleTime<0 || SpineAngleTime>4)return false;
    FProfile P;P.InertiaHold=InertiaHold;P.InertiaDecay=InertiaDecay;P.WorldInertia=WorldInertia;P.AngleTimeSeconds=SpineAngleTime;P.Duration=ReturnTime;P.Inertia=Inertia;P.Easing=Easing;FMemory::Memcpy(P.Weights,W,sizeof(W));
    EnsureCleanup();auto& C=Configs.FindOrAdd(Agent);
    if(Attack.IsNone())C.Profiles.Reset();
    C.Profiles.Add(Attack,P);return true;
}

#include "ProphecyFKReturnTests.inl"
#include "Tests/ProphecyFKReturnWindingTests.inl"
#include "Tests/ProphecyParryReturnTests.inl"


void ProphecyNNModifierDebug::FKReturn(FReport& R)
{
    using namespace ProphecyFKReturn;
    if(!R.UpperLoco)return;
    const auto* S=Active.Find(R.Agent);const auto* P=TickPhases.Find(R.Agent);if(!S || !P)return;
    const auto W=S->Curve.Weights(float(P->Elapsed));
    R.Add(TEXT("FKReturn"),TEXT("POSE+HISTORY"),ParryActive.Contains(R.Agent)?TEXT("Parry FK return / lab inertia"):TEXT("Attack FK return / lab inertia"),
        FString::Printf(TEXT("NN %.3f | tick %llu/%llu | coeff %.3g | ease %.3g | hold %.3g%s"),
        P->Complete?1.f:W.NN,P->Ticks,P->Limit,S->Curve.Coefficient,S->Curve.Easing,S->Curve.AlphaHold,
        P->Complete?TEXT(" | previous endpoint still returning"):TEXT("")));
    if(P->Complete)return;
    const TCHAR* Names[]={TEXT("spine"),TEXT("clav"),TEXT("upperarm"),TEXT("forearm"),TEXT("neck1"),TEXT("neck2"),TEXT("head")};
    FString Groups;
    for(int32 I=0;I<GroupCount;++I)Groups+=FString::Printf(TEXT("%s%s %.3g"),I?TEXT(" | "):TEXT(""),Names[I],W.Momentum[I]);
    R.Add(TEXT("FKMomentum"),TEXT("POSE+HISTORY"),TEXT("FK momentum coefficients (seconds)"),Groups);
}

#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFKModifierReadTest,"Prophecy.NN.Modifiers.FKReadOnly",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFKModifierReadTest::RunTest(const FString&)
{
    using namespace ProphecyFKReturn;
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    FActive S;S.Curve.InverseDuration=1;S.Curve.Coefficient=2;
    FTickPhase P;P.Elapsed=.25;P.Ticks=15;P.Limit=60;P.Sampled=true;
    Active.Add(A,S);TickPhases.Add(A,P);
    ProphecyBlendClock::Start(A,ProphecyBlendClock::EKind::FKReturn,1);
    for(int I=0;I<3;++I)FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/120);
    ProphecyNNModifierDebug::FReport R;R.Agent=A;R.UpperLoco=true;
    ProphecyNNModifierDebug::FKReturn(R);const auto Text=R.Text();R.Rows.Reset();ProphecyNNModifierDebug::FKReturn(R);
    TestEqual(TEXT("Repeated FK read is exact"),Text,R.Text());
    TestTrue(TEXT("Current NN weight is reported"),Text.Contains(TEXT("NN 0.062"))||Text.Contains(TEXT("NN 0.063")));
    TestEqual(TEXT("No phase advance"),TickPhases.FindChecked(A).Elapsed,.25);
    TestEqual(TEXT("Pending game ticks not consumed"),ProphecyBlendClock::Consume(A,ProphecyBlendClock::EKind::FKReturn),3./60.);
    TickPhases.FindChecked(A).Complete=true;R.Rows.Reset();ProphecyNNModifierDebug::FKReturn(R);
    TestTrue(TEXT("Final interpolation tail distinguished from active current FK"),R.Text().Contains(TEXT("previous endpoint still returning")));
    R.UpperLoco=false;R.Rows.Reset();ProphecyNNModifierDebug::FKReturn(R);
    TestTrue(TEXT("Return hidden when another upper owner wins"),R.Rows.IsEmpty());
    Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
#endif
#include "Tests/ProphecyFKLabTimingTests.inl"
#include "Tests/ProphecyFKPerAttackTimingTests.inl"
#include "Tests/ProphecyFKTwistInertiaTests.inl"
