#include "ProphecyWalkPinningLibrary.h"
#include "ProphecyWalkPinning.h"
#include "ProphecyWalkTickPinning.h"
#include "ProphecyNNPoseTypes.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"
#include "ProphecyRootPhysicsLibrary.h"
#include "DrawDebugHelpers.h"

namespace ProphecyWalkPinning
{
static TMap<TWeakObjectPtr<const AProphecyAgent>,FTickPinning> TickPins;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FTickPinOffsets> TickPinOffsets;
FTickPinOffsets& TickOffsets(const AProphecyAgent* A) {return TickPinOffsets.FindOrAdd(A);}
FTickPinning* FindTickPinning(const AProphecyAgent* A) {return TickPins.IsEmpty()?nullptr:TickPins.Find(A);}
bool AnyTickPinning() {return !TickPins.IsEmpty();}
void ResetTickPinning(const AProphecyAgent* A)
{
    TickPinOffsets.Remove(A);
    if(auto* T=FindTickPinning(A))
    {
        if(T->HasBase) FProphecyNNPoseStore::UpdateTickPinningLegs(T->PoseId,MakeArrayView(T->Bones),MakeArrayView(T->BasePrevious),MakeArrayView(T->BaseCurrent));
        *T=FTickPinning{};
    }
}
static TMap<TWeakObjectPtr<const AProphecyAgent>,FSettings> Settings;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FReachGuard> ReachGuards;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FSmoothing> Smoothing;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FBackwardBound> BackwardBounds;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FBackwardBound> CircleBounds;
static TMap<TWeakObjectPtr<const AProphecyAgent>,float> BackwardTransfers;
static TMap<TWeakObjectPtr<const AProphecyAgent>,float> RunBoosts;
void BoostRunPin(const AProphecyAgent* Agent,float& Left,float& Right)
{
    const float* Alpha=RunBoosts.IsEmpty()?nullptr:RunBoosts.Find(Agent);
    if(!Alpha)return;
    float& Highest=Left>=Right?Left:Right;
    Highest=FMath::Lerp(Highest,1.f,*Alpha);
}
// Separate storage keeps existing retained bound structs and circle settings intact.
static TMap<TWeakObjectPtr<const AProphecyAgent>,float> BackwardTargetLerps;
void ApplyBackwardTargetHeading(const AProphecyAgent* Agent,FVector& Heading)
{
    const float* Alpha=BackwardTargetLerps.IsEmpty()?nullptr:BackwardTargetLerps.Find(Agent);
    if (!Alpha) return;
    FVector Velocity,Target;float Speed;bool Run;
    if (Agent && Agent->GetLocomotionTarget(Velocity,Speed,Target,Run))
        Heading=BlendBackwardHeading(Heading,Target,*Alpha);
}
float BackwardTransferMultiplier(const AProphecyAgent* Agent)
{
    const auto* Value=BackwardTransfers.IsEmpty()?nullptr:BackwardTransfers.Find(Agent);
    return Value?*Value:0.f;
}
const FBackwardBound* FindBackwardBound(const AProphecyAgent* Agent)
{ return BackwardBounds.IsEmpty() ? nullptr : BackwardBounds.Find(Agent); }
const FBackwardBound* FindCircleBound(const AProphecyAgent* Agent)
{ return CircleBounds.IsEmpty() ? nullptr : CircleBounds.Find(Agent); }
static FDelegateHandle CleanupHandle;
static FDelegateHandle ReachTickHandle;
static FDelegateHandle SmoothTickHandle;
static void RefreshSmoothTick();
static void TickSmoothing(UWorld* World,ELevelTick Type,float Dt)
{
    if (!World || World->IsPaused() || Type!=LEVELTICK_All || Dt<=0) return;
    for (auto It=Smoothing.CreateIterator();It;++It)
    {
        const auto* Agent=It.Key().Get();
        if (!Agent || Agent->IsActorBeingDestroyed()) { It.RemoveCurrent();continue; }
        if (Agent->GetWorld()!=World) continue;
        auto& S=It.Value();
        for (int32 I=0;I<2;++I)
        {
            if (S.Current[I]==S.Target[I]) continue;
            const int32 Frames=S.Target[I]>S.Current[I] ? S.InFrames : S.OutFrames;
            const double Travel=Frames>0 ? double(++S.Elapsed[I])/double(Frames) : 1.;
            const double Distance=double(S.Target[I])-double(S.Start[I]);
            S.Current[I]=Travel>=FMath::Abs(Distance) ? S.Target[I]
                : float(double(S.Start[I])+FMath::Sign(Distance)*Travel);
        }
    }
    RefreshSmoothTick();
}
static void RefreshSmoothTick()
{
    bool Active=false;
    for (const auto& Pair:Smoothing) Active|=Pair.Value.Active();
    if (Active && !SmoothTickHandle.IsValid()) SmoothTickHandle=FWorldDelegates::OnWorldPreActorTick.AddStatic(&TickSmoothing);
    else if (!Active && SmoothTickHandle.IsValid())
    { FWorldDelegates::OnWorldPreActorTick.Remove(SmoothTickHandle);SmoothTickHandle.Reset(); }
}
FSmoothing* FindSmoothing(const AProphecyAgent* Agent)
{ return Smoothing.IsEmpty() ? nullptr : Smoothing.Find(Agent); }
void ClearSmoothedFoot(FSmoothing& State,int32 Side)
{
    State.Current[Side]=State.Target[Side]=0;
    State.Start[Side]=0;State.Elapsed[Side]=0;
    RefreshSmoothTick();
}
void ResetSmoothing(const AProphecyAgent* Agent)
{
    ResetTickPinning(Agent);
    if (auto* S=FindSmoothing(Agent))
    { for (int32 I=0;I<2;++I) { S->Current[I]=S->Target[I]=S->Start[I]=0;S->Elapsed[I]=0; } RefreshSmoothTick(); }
}
void SmoothPins(FSmoothing& S,float& Left,float& Right)
{
    float* Pins[2]={&Left,&Right};
    for (int32 I=0;I<2;++I)
    {
        const float Target=FMath::Clamp(*Pins[I],0.f,1.f);
        if (Target!=S.Target[I])
        { S.Target[I]=Target;S.Start[I]=S.Current[I];S.Elapsed[I]=0; }
        if ((S.Target[I]>S.Current[I] ? S.InFrames : S.OutFrames)==0) S.Current[I]=S.Target[I];
        *Pins[I]=S.Current[I];
    }
    RefreshSmoothTick();
}
static void RefreshReachTick();
static void TickReach(UWorld* World,ELevelTick Type,float Dt)
{
    if (!World || World->IsPaused() || Type!=LEVELTICK_All || Dt<=0) return;
    for (auto It=ReachGuards.CreateIterator();It;++It)
    {
        const auto* Agent=It.Key().Get();
        if (!Agent || Agent->IsActorBeingDestroyed()) { It.RemoveCurrent();continue; }
        if (Agent->GetWorld()!=World) continue;
        for (int32& Remaining:It.Value().Remaining) if (Remaining>0) --Remaining;
    }
    RefreshReachTick();
}
static void RefreshReachTick()
{
    bool Active=false;
    for (const auto& Pair:ReachGuards) Active|=Pair.Value.HasCooldown();
    if (Active && !ReachTickHandle.IsValid()) ReachTickHandle=FWorldDelegates::OnWorldPreActorTick.AddStatic(&TickReach);
    else if (!Active && ReachTickHandle.IsValid())
    { FWorldDelegates::OnWorldPreActorTick.Remove(ReachTickHandle);ReachTickHandle.Reset(); }
}
FReachGuard* FindReachGuard(const AProphecyAgent* Agent)
{
    return ReachGuards.IsEmpty() ? nullptr : ReachGuards.Find(Agent);
}
bool RejectPin(FReachGuard& Guard,int32 Side,const FVector3f& Hip,const FVector3f& PinnedFoot,float Reach)
{
    if (Guard.Remaining[Side]>0) return true; // Do not restart an active lockout.
    if (Reach<=0 || (PinnedFoot-Hip).SizeSquared()<Reach*Reach) return false;
    Guard.Remaining[Side]=Guard.Frames;
    if (Guard.Frames>0) RefreshReachTick();
    return true;
}
void ClearReachCooldown(const AProphecyAgent* Agent)
{
    if (auto* Guard=FindReachGuard(Agent))
    { Guard->Remaining[0]=Guard->Remaining[1]=0;RefreshReachTick(); }
}
static void RefreshCleanup()
{
    if (TickPins.IsEmpty() && Settings.IsEmpty() && ReachGuards.IsEmpty() && Smoothing.IsEmpty() && BackwardBounds.IsEmpty() && CircleBounds.IsEmpty() && BackwardTransfers.IsEmpty() && RunBoosts.IsEmpty())
    {
        FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);
        CleanupHandle.Reset();
    }
    else if (!CleanupHandle.IsValid())
        CleanupHandle=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
        {
            for (auto It=Settings.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            for (auto It=ReachGuards.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            for (auto It=TickPinOffsets.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            for (auto It=TickPins.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            for (auto It=Smoothing.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            for (auto It=BackwardBounds.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            for (auto It=CircleBounds.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            for (auto It=BackwardTransfers.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            for (auto It=BackwardTargetLerps.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            for (auto It=RunBoosts.CreateIterator();It;++It)
                if (!It.Key().IsValid() || It.Key()->GetWorld()==World) It.RemoveCurrent();
            RefreshReachTick();
            RefreshSmoothTick();
            RefreshCleanup();
        });
}
bool Apply(const AProphecyAgent* Agent,float Left,float Right,float PinScale,float& LeftPin,float& RightPin)
{
    const auto* Config=Settings.IsEmpty() ? nullptr : Settings.Find(Agent);
    return Config && Config->Apply(Left,Right,PinScale,LeftPin,RightPin);
}

}
bool UProphecyWalkPinningLibrary::SetRunPinningBoost(AProphecyAgent* Agent,float Alpha)
{
    using namespace ProphecyWalkPinning;
    if(!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() ||
        !FMath::IsFinite(Alpha) || Alpha<0 || Alpha>1)return false;
    if(Alpha>0)RunBoosts.Add(Agent,Alpha);else RunBoosts.Remove(Agent);
    RefreshCleanup();return true;
}
bool UProphecyWalkPinningLibrary::SetWalkPinningEveryTick(AProphecyAgent* Agent,bool Enabled)
{
    using namespace ProphecyWalkPinning;
    if(!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed())return false;
    if(Enabled) TickPins.FindOrAdd(Agent);
    else {ResetTickPinning(Agent);TickPins.Remove(Agent);}
    RefreshCleanup();return true;
}
bool UProphecyWalkPinningLibrary::SetWalkPinningBackwardTransfer(AProphecyAgent* Agent,bool Enabled,float Multiplier)
{
    using namespace ProphecyWalkPinning;
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()) return false;
    if (Enabled && (!FMath::IsFinite(Multiplier) || Multiplier<0)) return false;
    if (Enabled && Multiplier>0) BackwardTransfers.Add(Agent,Multiplier);
    else BackwardTransfers.Remove(Agent);
    RefreshCleanup();return true;
}
bool UProphecyWalkPinningLibrary::SetWalkPinningBackwardBound(AProphecyAgent* Agent,bool Enabled,float DistanceMinCm,float DistanceMaxCm,int32 RootIndex,float LerpTarget)
{
    using namespace ProphecyWalkPinning;
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()) return false;
    if (Enabled)
    {
        if (!FMath::IsFinite(DistanceMinCm) || !FMath::IsFinite(DistanceMaxCm) || DistanceMaxCm<DistanceMinCm || RootIndex<0 || RootIndex>8
            || !FMath::IsFinite(LerpTarget) || LerpTarget<0 || LerpTarget>1) return false;
        BackwardBounds.Add(Agent,FBackwardBound{DistanceMinCm,DistanceMaxCm,RootIndex});
        if (LerpTarget>0) BackwardTargetLerps.Add(Agent,LerpTarget);
        else BackwardTargetLerps.Remove(Agent);
    }
    else { BackwardBounds.Remove(Agent);BackwardTargetLerps.Remove(Agent); }
    RefreshCleanup();return true;
}
bool UProphecyWalkPinningLibrary::SetWalkPinningCircleBound(AProphecyAgent* Agent,bool Enabled,float DistanceMinCm,float DistanceMaxCm,int32 RootIndex)
{
    using namespace ProphecyWalkPinning;
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()) return false;
    if (Enabled)
    {
        if (!FMath::IsFinite(DistanceMinCm) || !FMath::IsFinite(DistanceMaxCm) || DistanceMinCm<0 || DistanceMaxCm<DistanceMinCm || RootIndex<0 || RootIndex>8) return false;
        CircleBounds.Add(Agent,FBackwardBound{DistanceMinCm,DistanceMaxCm,RootIndex});
    }
    else CircleBounds.Remove(Agent);
    RefreshCleanup();return true;
}
static bool DrawWalkPinBound(AProphecyAgent* Agent,const ProphecyWalkPinning::FBackwardBound* Bound,float WidthCm,float GroundOffsetCm,bool Circle)
{
#if ENABLE_DRAW_DEBUG
    using namespace ProphecyWalkPinning;
    if (!IsInGameThread() || !IsValid(Agent) || !Agent->GetWorld() || !FMath::IsFinite(WidthCm) || WidthCm<=0 || !FMath::IsFinite(GroundOffsetCm)) return false;
    if (!Bound) return false;
    TArray<FTransform> Roots;TArray<float> Times;
    if (!UProphecyRootPhysicsLibrary::GetContinuousLocomotionRootWindow(Agent,Roots,Times) || !Roots.IsValidIndex(Bound->RootIndex)) return false;
    FVector Origin,Heading;
    BackwardReference(Roots[0],Roots[Bound->RootIndex],Origin,Heading);
    if (Circle) Origin=Roots[Bound->RootIndex].GetLocation();
    else ApplyBackwardTargetHeading(Agent,Heading);
    if (Heading.IsNearlyZero()) return false;
    const FVector Side(-Heading.Y,Heading.X,0);
    UWorld* World=Agent->GetWorld();
    FCollisionQueryParams Query(SCENE_QUERY_STAT(WalkPinBoundDebug),false,Agent);
    auto Ground=[&](FVector Point)
    {
        FHitResult Hit;
        if (World->LineTraceSingleByObjectType(Hit,Point+FVector(0,0,1000),Point-FVector(0,0,10000),
            FCollisionObjectQueryParams(ECC_WorldStatic),Query)) Point.Z=Hit.ImpactPoint.Z;
        else Point.Z=Agent->GetRootLowPoint().Z;
        Point.Z+=GroundOffsetCm;return Point;
    };
    auto Arrow=[&](const FVector& A,const FVector& B,FColor Color)
    { DrawDebugDirectionalArrow(World,Ground(A),Ground(B),8.f,Color,false,0.f,0,2.f); };
    Arrow(Origin,Origin+Heading*40.f,FColor::White);
    if (Circle)
    {
        constexpr int32 Segments=32;
        FVector Rings[3][Segments];
        const FColor Colors[3]={FColor::Green,FColor::Yellow,FColor::Red};
        for (int32 Ring=0;Ring<3;++Ring)
        {
            const double Radius=FMath::Lerp(double(Bound->MinCm),double(Bound->MaxCm),Ring*.5);
            for (int32 I=0;I<Segments;++I)
            {
                const double Angle=2.*UE_PI*I/Segments;
                Rings[Ring][I]=Ground(Origin+FVector(FMath::Cos(Angle),FMath::Sin(Angle),0)*Radius);
            }
            for (int32 I=0;I<Segments;++I)
                DrawDebugLine(World,Rings[Ring][I],Rings[Ring][(I+1)%Segments],Colors[Ring],false,0.f,0,2.f);
        }
        if (Bound->MaxCm>Bound->MinCm) for (int32 I=0;I<Segments;I+=4)
            for (int32 Ring=0;Ring<2;++Ring)
                DrawDebugDirectionalArrow(World,Rings[Ring][I],Rings[Ring+1][I],5.f,Colors[Ring],false,0.f,0,1.5f);
        return true;
    }
    const FVector Start=Origin-Heading*Bound->MinCm,End=Origin-Heading*Bound->MaxCm;
    Arrow(Start-Side*(WidthCm*.5),Start+Side*(WidthCm*.5),FColor::Green);
    Arrow(End-Side*(WidthCm*.5),End+Side*(WidthCm*.5),FColor::Red);
    for (int32 I=0;I<8 && Bound->MaxCm>Bound->MinCm;++I)
    {
        const float T=(I+.5f)/8.f;
        const FColor Color(uint8(FMath::RoundToInt(255.f*FMath::Min(1.f,2.f*T))),
            uint8(FMath::RoundToInt(255.f*FMath::Min(1.f,2.f*(1.f-T)))),0);
        Arrow(FMath::Lerp(Start,End,double(I)/8.),FMath::Lerp(Start,End,double(I+1)/8.),Color);
    }
    return true;
#else
    return false;
#endif
}
bool UProphecyWalkPinningLibrary::DrawWalkPinningBackwardBound(AProphecyAgent* Agent,float WidthCm,float GroundOffsetCm)
{ return IsInGameThread() && DrawWalkPinBound(Agent,ProphecyWalkPinning::FindBackwardBound(Agent),WidthCm,GroundOffsetCm,false); }
bool UProphecyWalkPinningLibrary::DrawWalkPinningCircleBound(AProphecyAgent* Agent,float GroundOffsetCm)
{ return IsInGameThread() && DrawWalkPinBound(Agent,ProphecyWalkPinning::FindCircleBound(Agent),100.f,GroundOffsetCm,true); }
bool UProphecyWalkPinningLibrary::SetWalkPinningSmoothing(AProphecyAgent* Agent,bool Enabled,int32 PinInFrames,int32 PinOutFrames)
{
    using namespace ProphecyWalkPinning;
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || PinInFrames<0 || PinOutFrames<0) return false;
    if (Enabled && (PinInFrames>0 || PinOutFrames>0))
    {
        auto& S=Smoothing.FindOrAdd(Agent);
        if (S.InFrames!=PinInFrames || S.OutFrames!=PinOutFrames) for (int32 I=0;I<2;++I)
        {
            S.Start[I]=S.Current[I];S.Elapsed[I]=0;
            if ((S.Target[I]>S.Current[I] ? PinInFrames : PinOutFrames)==0) S.Current[I]=S.Target[I];
        }
        S.InFrames=PinInFrames;S.OutFrames=PinOutFrames;
    }
    else {ResetTickPinning(Agent);Smoothing.Remove(Agent);}
    RefreshSmoothTick();RefreshCleanup();return true;
}
bool UProphecyWalkPinningLibrary::SetWalkPinningReachGuard(AProphecyAgent* Agent,bool Enabled,int32 Frames)
{
    using namespace ProphecyWalkPinning;
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || Frames<0) return false;
    if (Enabled) ReachGuards.FindOrAdd(Agent).Frames=Frames;
    else ReachGuards.Remove(Agent);
    RefreshReachTick();RefreshCleanup();return true;
}
bool UProphecyWalkPinningLibrary::SetWalkPinningTolerance(AProphecyAgent* Agent,float Tolerance,float ToleranceFallback)
{
    using namespace ProphecyWalkPinning;
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !FMath::IsFinite(Tolerance) || Tolerance<0 || !FMath::IsFinite(ToleranceFallback)
        || ToleranceFallback<0 || ToleranceFallback>1) return false;
    if (Tolerance==0) Settings.Remove(Agent);
    else Settings.Add(Agent,FSettings{Tolerance,ToleranceFallback});
    RefreshCleanup();
    return true;
}
bool UProphecyWalkPinningLibrary::GetWalkPinningTolerance(AProphecyAgent* Agent,float& Tolerance,float& ToleranceFallback)
{
    Tolerance=ToleranceFallback=0;
    if (!IsValid(Agent)) return false;
    if (const auto* Config=ProphecyWalkPinning::Settings.Find(Agent))
    { Tolerance=Config->Tolerance; ToleranceFallback=Config->Fallback; }
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRunPinningBoostTest,"Prophecy.NN.RunPinning.HighestBoost",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyRunPinningBoostTest::RunTest(const FString&)
{
    using namespace ProphecyWalkPinning;
    UWorld* W=UWorld::CreateWorld(EWorldType::Game,false);
    AProphecyAgent* A=W->SpawnActor<AProphecyAgent>();AProphecyAgent* B=W->SpawnActor<AProphecyAgent>();
    float L=.2f,R=.6f;BoostRunPin(A,L,R);
    TestEqual(TEXT("Default inactive"),R,.6f);
    TestTrue(TEXT("Configure half boost"),UProphecyWalkPinningLibrary::SetRunPinningBoost(A,.5f));
    BoostRunPin(A,L,R);TestNearlyEqual(TEXT("Higher right interpolated"),R,.8f,1.e-6f);TestEqual(TEXT("Lower left untouched"),L,.2f);
    L=.6f;R=.2f;BoostRunPin(A,L,R);TestNearlyEqual(TEXT("Higher left interpolated"),L,.8f,1.e-6f);TestEqual(TEXT("Lower right untouched"),R,.2f);
    L=.2f;R=.6f;BoostRunPin(B,L,R);TestEqual(TEXT("Other agent unaffected"),R,.6f);
    UProphecyWalkPinningLibrary::SetRunPinningBoost(A,1);L=.2f;R=.6f;BoostRunPin(A,L,R);
    TestEqual(TEXT("Alpha one reaches exactly one"),R,1.f);TestEqual(TEXT("Other pin retained"),L,.2f);
    L=R=.4f;BoostRunPin(A,L,R);TestEqual(TEXT("Tie deterministically selects left"),L,1.f);TestEqual(TEXT("Tie does not pin both"),R,.4f);
    TestFalse(TEXT("Reject invalid alpha"),UProphecyWalkPinningLibrary::SetRunPinningBoost(A,-1));
    UProphecyWalkPinningLibrary::SetRunPinningBoost(A,0);L=.2f;R=.6f;BoostRunPin(A,L,R);
    TestFalse(TEXT("Alpha zero removes storage"),RunBoosts.Contains(A));TestEqual(TEXT("Zero exact bypass"),R,.6f);
    TestFalse(TEXT("No smoothing timer"),SmoothTickHandle.IsValid());TestFalse(TEXT("No reach timer"),ReachTickHandle.IsValid());
    UProphecyWalkPinningLibrary::SetRunPinningBoost(A,.5f);W->DestroyWorld(false);
    TestFalse(TEXT("World cleanup removes setting"),RunBoosts.Contains(A));
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyWalkPinningCircleBoundTest,"Prophecy.NN.WalkPinning.CircleBound",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyWalkPinningCircleBoundTest::RunTest(const FString&)
{
    using namespace ProphecyWalkPinning;
    const FBackwardBound B{20,60,3};const FVector Root(100,-200,50);
    TestEqual(TEXT("Circle center is unrestricted"),CircleBoundPin(1,B,Root,Root),1.f);
    TestEqual(TEXT("Min radius inclusive"),CircleBoundPin(1,B,Root+FVector(20,0,0),Root),1.f);
    TestEqual(TEXT("Max radius inclusive"),CircleBoundPin(1,B,Root+FVector(0,60,0),Root),0.f);
    TestEqual(TEXT("Outside circle"),CircleBoundPin(1,B,Root+FVector(-100,0,0),Root),0.f);
    for (int32 I=0;I<16;++I)
    {
        const double A=2.*UE_PI*I/16.;
        const FVector Foot=Root+FVector(FMath::Cos(A)*40.,FMath::Sin(A)*40.,500.);
        TestNearlyEqual(TEXT("All horizontal directions identical; height ignored"),CircleBoundPin(1,B,Foot,Root),.5f,1.e-6f);
    }
    TestEqual(TEXT("Upper bound preserves lower smoothed weight"),CircleBoundPin(.25f,B,Root+FVector(40,0,0),Root),.25f);
    TestEqual(TEXT("Unpinned stays unpinned"),CircleBoundPin(0,B,Root,Root),0.f);
    const FVector Foot=Root+FVector(0,40,0);
    TestEqual(TEXT("Independent future center affects radius"),CircleBoundPin(1,B,Foot,Root+FVector(0,100,0)),0.f);
    const FVector Heading(0,1,0),Behind=Root-FVector(0,40,0);
    const FBackwardBound Tight{0,40,0};
    TestEqual(TEXT("Tightest enabled bound wins"),CircleBoundPin(BoundPin(.8f,B,Behind,Root,Heading),Tight,Behind,Root),0.f);
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false);
    if (!TestNotNull(TEXT("Isolated world"),World)) return false;
    auto* Agent=World->SpawnActor<AProphecyAgent>();
    if (!TestNotNull(TEXT("Isolated agent"),Agent)) { World->DestroyWorld(false);return false; }
    TestNull(TEXT("Circle off by default"),FindCircleBound(Agent));
    UProphecyWalkPinningLibrary::SetWalkPinningBackwardBound(Agent,true,20,60,0);
    TestTrue(TEXT("Enable circle with its own root"),UProphecyWalkPinningLibrary::SetWalkPinningCircleBound(Agent,true,30,90,3));
    TestEqual(TEXT("Circle root retained"),FindCircleBound(Agent)->RootIndex,3);
    TestEqual(TEXT("Line root unchanged"),FindBackwardBound(Agent)->RootIndex,0);
    TestFalse(TEXT("Negative radius rejected"),UProphecyWalkPinningLibrary::SetWalkPinningCircleBound(Agent,true,-1,90,3));
    TestFalse(TEXT("Bad root rejected"),UProphecyWalkPinningLibrary::SetWalkPinningCircleBound(Agent,true,30,90,9));
    TestFalse(TEXT("Bad radii order rejected"),UProphecyWalkPinningLibrary::SetWalkPinningCircleBound(Agent,true,90,30,3));
    TestFalse(TEXT("Missing window debug returns false"),UProphecyWalkPinningLibrary::DrawWalkPinningCircleBound(Agent));
    UProphecyWalkPinningLibrary::SetWalkPinningBackwardBound(Agent,false);
    TestNotNull(TEXT("Disabling line preserves circle"),FindCircleBound(Agent));
    UProphecyWalkPinningLibrary::SetWalkPinningCircleBound(Agent,false);
    TestNull(TEXT("Disabling circle removes its state"),FindCircleBound(Agent));
    TestFalse(TEXT("Disabled circle draw does nothing"),UProphecyWalkPinningLibrary::DrawWalkPinningCircleBound(Agent));
    World->DestroyWorld(false);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyWalkPinningBackwardBoundTest,"Prophecy.NN.WalkPinning.BackwardBound",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyWalkPinningBackwardBoundTest::RunTest(const FString&)
{
    using namespace ProphecyWalkPinning;
    const FVector Forward(0,1,0),Target(1,0,0);
    TestTrue(TEXT("Target lerp0 preserves selected heading exactly"),BlendBackwardHeading(Forward,Target,0)==Forward);
    TestTrue(TEXT("Target lerp1 reaches unrestricted final goal"),BlendBackwardHeading(Forward,Target,1)==Target);
    TestTrue(TEXT("Half target lerp follows halfway heading"),BlendBackwardHeading(Forward,Target,.5f).Equals(FVector(FMath::Sqrt(.5),FMath::Sqrt(.5),0),1.e-6));
    TestTrue(TEXT("Missing target preserves root heading"),BlendBackwardHeading(Forward,FVector::ZeroVector,.5f)==Forward);
    const FVector Opposite=BlendBackwardHeading(Forward,-Forward,.5f);
    TestTrue(TEXT("Opposing headings do not collapse to zero"),!Opposite.ContainsNaN() && FMath::IsNearlyEqual(Opposite.Size(),1.,1.e-6) && FMath::Abs(Opposite.Y)<1.e-6);
    const FVector WrapA(FMath::Cos(FMath::DegreesToRadians(170.)),FMath::Sin(FMath::DegreesToRadians(170.)),0);
    const FVector WrapB(WrapA.X,-WrapA.Y,0);
    TestTrue(TEXT("Wrapped headings take the short turn"),BlendBackwardHeading(WrapA,WrapB,.5f).Equals(FVector(-1,0,0),1.e-6));
    {
        float L=1,R=0;
        TransferBackwardPins(1,FVector2f(.5f,1),FVector2f(.5f,1),L,R);
        TestEqual(TEXT("Half released source retains its own half cap"),L,.5f);
        TestEqual(TEXT("Multiplier1 transfers fifty percent"),R,.5f);
        L=1;R=0;TransferBackwardPins(2,FVector2f(.5f,1),FVector2f(.5f,1),L,R);
        TestEqual(TEXT("Multiplier2 transfers full pin"),R,1.f);
        L=0;R=1;TransferBackwardPins(2,FVector2f(1,.5f),FVector2f(1,.5f),L,R);
        TestEqual(TEXT("Right-to-left symmetry"),L,1.f);
        L=.8f;R=.9f;TransferBackwardPins(1,FVector2f(1,.5f),FVector2f(1,.5f),L,R);
        TestEqual(TEXT("Stronger existing receiving pin remains"),L,.8f);
        TestEqual(TEXT("Source still respects own bound"),R,.5f);
        L=1;R=0;TransferBackwardPins(2,FVector2f(.5f,1),FVector2f(.5f,.2f),L,R);
        TestEqual(TEXT("Receiving circle cap wins"),R,.2f);
        L=R=0;TransferBackwardPins(2,FVector2f(.5f,.5f),FVector2f(.5f,.5f),L,R);
        TestTrue(TEXT("Simultaneous release has no sequential feedback"),L==.5f && R==.5f);
        L=R=1;TransferBackwardPins(10,FVector2f(0,0),FVector2f(0,0),L,R);
        TestTrue(TEXT("Both outside bounds leaves neither pinned"),L==0 && R==0);
        L=R=0;TransferBackwardPins(1,FVector2f(1,1),FVector2f(1,1),L,R);
        TestTrue(TEXT("No release does not invent pins"),L==0 && R==0);
        L=.7f;R=.3f;TransferBackwardPins(0,FVector2f(0,0),FVector2f(0,0),L,R);
        TestTrue(TEXT("Zero multiplier is exact bypass"),L==.7f && R==.3f);
    }
    const FBackwardBound B{20,60,0};
    const FTransform Root(FRotator::ZeroRotator,FVector(100,200,50));
    const FVector H=BoundHeading(Root),P=Root.GetLocation();
    TestEqual(TEXT("Native root heading is +Y at zero yaw"),H,FVector(0,1,0));
    TestEqual(TEXT("In front has full cap"),BoundPin(1,B,P+H*80,P,H),1.f);
    TestEqual(TEXT("Minimum inclusive full cap"),BoundPin(1,B,P-H*20,P,H),1.f);
    TestEqual(TEXT("Maximum inclusive zero cap"),BoundPin(1,B,P-H*60,P,H),0.f);
    TestEqual(TEXT("Far behind zero cap"),BoundPin(1,B,P-H*90,P,H),0.f);
    TestEqual(TEXT("Halfway cap"),BoundPin(1,B,P-H*40,P,H),.5f);
    TestEqual(TEXT("Lateral distance and height ignored"),BoundPin(1,B,P-H*40+FVector(300,0,500),P,H),.5f);
    TestEqual(TEXT("Cap is minimum, not multiplication"),BoundPin(.25f,B,P-H*40,P,H),.25f);
    TestEqual(TEXT("Cap reduces high smoothed pin"),BoundPin(.75f,B,P-H*40,P,H),.5f);
    TestEqual(TEXT("Never creates a pin"),BoundPin(0,B,P-H*10,P,H),0.f);
    const FTransform Moved(FRotator(0,73,0),FVector(430,-280,90));
    const FVector MovedRoot=Moved.TransformPosition(P),MovedFoot=Moved.TransformPosition(P-H*40+FVector(200,0,400));
    TestNearlyEqual(TEXT("Projection is yaw/translation equivariant"),BoundPin(1,B,MovedFoot,MovedRoot,Moved.TransformVectorNoScale(H)),.5f,1.e-6f);
    const FTransform Future(FRotator(0,90,0),FVector(180,200,50));
    const FVector Foot(140,200,50);
    FVector Origin,Direction;
    BackwardReference(Root,Future,Origin,Direction);
    TestEqual(TEXT("Same foot is not behind root0"),BoundPin(1,B,Foot,P,H),1.f);
    TestEqual(TEXT("Future heading retains current root origin"),Origin,P);
    TestNearlyEqual(TEXT("Future heading turns bound around root0"),BoundPin(1,B,Foot,Origin,Direction),.5f,1.e-6f);
    for(const FVector Offset:{FVector(500,-700,90),FVector(-300,800,-120)})
    {
        FTransform Shifted=Future;Shifted.AddToTranslation(Offset);
        BackwardReference(Root,Shifted,Origin,Direction);
        TestNearlyEqual(TEXT("Future position cannot change backward cap"),BoundPin(1,B,Foot,Origin,Direction),.5f,1.e-6f);
    }
    BackwardReference(Root,Root,Origin,Direction);
    TestEqual(TEXT("Root0 keeps previous current-heading behavior"),BoundPin(1,B,Foot,Origin,Direction),1.f);
    AddInfo(TEXT("BackwardReference: current-root origin, selected heading, future-translation invariance and root0 compatibility passed."));
    TestEqual(TEXT("Equal thresholds retain full pin at boundary"),FBackwardBound{30,30,0}.Cap(30),1.f);
    TestEqual(TEXT("Equal thresholds hard-release beyond boundary"),FBackwardBound{30,30,0}.Cap(30.1),0.f);
    TestEqual(TEXT("Signed thresholds can start ahead of root"),FBackwardBound{-20,20,0}.Cap(0),.5f);
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false);
    if (!TestNotNull(TEXT("Isolated world"),World)) return false;
    auto* Agent=World->SpawnActor<AProphecyAgent>();
    if (!TestNotNull(TEXT("Isolated agent"),Agent)) { World->DestroyWorld(false);return false; }
    TestNull(TEXT("Off by default"),FindBackwardBound(Agent));
    TestEqual(TEXT("Transfer off by default"),BackwardTransferMultiplier(Agent),0.f);
    TestTrue(TEXT("Enable transfer"),UProphecyWalkPinningLibrary::SetWalkPinningBackwardTransfer(Agent,true,2.f));
    TestEqual(TEXT("Multiplier stored per agent"),BackwardTransferMultiplier(Agent),2.f);
    TestFalse(TEXT("Negative multiplier rejected"),UProphecyWalkPinningLibrary::SetWalkPinningBackwardTransfer(Agent,true,-1.f));
    TestEqual(TEXT("Invalid setter preserves multiplier"),BackwardTransferMultiplier(Agent),2.f);
    auto* Other=World->SpawnActor<AProphecyAgent>();
    TestEqual(TEXT("Other agent unchanged"),BackwardTransferMultiplier(Other),0.f);
    TestTrue(TEXT("Zero retires configuration"),UProphecyWalkPinningLibrary::SetWalkPinningBackwardTransfer(Agent,true,0.f));
    TestEqual(TEXT("Zero lookup bypasses transfer"),BackwardTransferMultiplier(Agent),0.f);
    UProphecyWalkPinningLibrary::SetWalkPinningBackwardTransfer(Agent,true,2.f);
    UProphecyWalkPinningLibrary::SetWalkPinningBackwardTransfer(Agent,false);
    TestEqual(TEXT("Disabled retires configuration"),BackwardTransferMultiplier(Agent),0.f);
    TestTrue(TEXT("Enable selected future root"),UProphecyWalkPinningLibrary::SetWalkPinningBackwardBound(Agent,true,20,60,3));
    TestEqual(TEXT("Root3 remains index3 without previous-frame offset"),FindBackwardBound(Agent)->RootIndex,3);
    TestFalse(TEXT("Default target lerp has no stored override"),BackwardTargetLerps.Contains(Agent));
    TestTrue(TEXT("Target lerp stored per agent"),UProphecyWalkPinningLibrary::SetWalkPinningBackwardBound(Agent,true,20,60,3,.5f));
    TestEqual(TEXT("Target lerp value"),BackwardTargetLerps.FindChecked(Agent),.5f);
    TestFalse(TEXT("Other agent target unchanged"),BackwardTargetLerps.Contains(Other));
    TestFalse(TEXT("Out of range target lerp rejected"),UProphecyWalkPinningLibrary::SetWalkPinningBackwardBound(Agent,true,20,60,3,1.1f));
    TestEqual(TEXT("Invalid edit retains target lerp"),BackwardTargetLerps.FindChecked(Agent),.5f);
    FVector NoTarget=Forward;ApplyBackwardTargetHeading(Agent,NoTarget);
    TestTrue(TEXT("Agent without mover target keeps root heading"),NoTarget==Forward);
    TestFalse(TEXT("Invalid window index rejected"),UProphecyWalkPinningLibrary::SetWalkPinningBackwardBound(Agent,true,20,60,9));
    TestFalse(TEXT("Reversed thresholds rejected"),UProphecyWalkPinningLibrary::SetWalkPinningBackwardBound(Agent,true,60,20,3));
    TestEqual(TEXT("Rejected settings preserve previous ones"),FindBackwardBound(Agent)->MinCm,20.f);
    TestFalse(TEXT("No available window makes debug draw fail cleanly"),UProphecyWalkPinningLibrary::DrawWalkPinningBackwardBound(Agent));
    TestTrue(TEXT("Disable removes configuration"),UProphecyWalkPinningLibrary::SetWalkPinningBackwardBound(Agent,false,20,60,3));
    TestNull(TEXT("Disabled lookup bypasses projection"),FindBackwardBound(Agent));
    TestFalse(TEXT("Disabled retires target interpolation too"),BackwardTargetLerps.Contains(Agent));
    TestFalse(TEXT("Disabled debug node is a no-op"),UProphecyWalkPinningLibrary::DrawWalkPinningBackwardBound(Agent));
    World->DestroyWorld(false);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyWalkPinningTickTest,"Prophecy.NN.WalkPinning.EveryTick",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyWalkPinningTickTest::RunTest(const FString&)
{
    using namespace ProphecyWalkPinning;
    FTickPinFrame F;F.Valid=true;F.Delta[0]=FVector3f(-.06f,.02f,0);F.Applied=FVector2f(1,0);F.WalkWeight=FVector2f(1,.5f);
    TestTrue(TEXT("Policy-time sample preserves existing endpoint"),F.Shift(0,1).IsZero());
    TestTrue(TEXT("Next tick can remove cached pin without another NN prediction"),F.Shift(0,0).Equals(FVector3f(.06f,-.02f,0),1.e-7f));
    TestEqual(TEXT("Pinning never changes vertical target"),F.Shift(0,.5f).Z,0.f);
    F.Cap.X=.4f;F.Minimum.X=.6f;
    TestEqual(TEXT("Receiving own bound still wins"),F.Effective(0,.1f),.4f);
    F.Cap.X=1;TestEqual(TEXT("Opposite transfer remains a lower bound"),F.Effective(0,.8f),.8f);
    F.Cap.X=0;TestEqual(TEXT("Reach rejection remains immediate"),F.Effective(0,1),0.f);
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false);AProphecyAgent* A=World?World->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    TestNull(TEXT("Experimental path defaults off"),FindTickPinning(A));
    UProphecyWalkPinningLibrary::SetWalkPinningEveryTick(A,true);
    UProphecyWalkPinningLibrary::SetWalkPinningSmoothing(A,true,3,1);
    auto* S=FindSmoothing(A);S->Current[0]=S->Target[0]=1;
    float L=0,R=1;SmoothPins(*S,L,R);
    TestEqual(TEXT("527 retains last value at new decision"),L,1.f);
    TickSmoothing(World,LEVELTICK_All,1.f/60);
    TestEqual(TEXT("528 unpins with cached decision, no NN call"),S->Current[0],0.f);
    TestEqual(TEXT("Other foot progresses independently between NN calls"),S->Current[1],1.f/3);
    L=1;R=0;SmoothPins(*S,L,R);TestEqual(TEXT("Reversal begins from actual current value"),L,0.f);
    TickSmoothing(World,LEVELTICK_All,1.f/120);TestEqual(TEXT("Authored game tick, not wall seconds"),S->Current[0],1.f/3);
    ResetSmoothing(A);TestNotNull(TEXT("Special/reset preserves toggle"),FindTickPinning(A));
    TestFalse(TEXT("Special/reset clears pose cache"),FindTickPinning(A)->HasBase);
    UProphecyWalkPinningLibrary::SetWalkPinningEveryTick(A,false);
    TestNull(TEXT("Disabled retires cache"),FindTickPinning(A));
    UProphecyWalkPinningLibrary::SetWalkPinningSmoothing(A,false,3,1);World->DestroyWorld(false);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyWalkPinningSmoothingTest,"Prophecy.NN.WalkPinning.Smoothing",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyWalkPinningSmoothingTest::RunTest(const FString&)
{
    using namespace ProphecyWalkPinning;
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false);
    if (!TestNotNull(TEXT("Isolated world"),World)) return false;
    AProphecyAgent* Agent=World->SpawnActor<AProphecyAgent>();
    if (!TestNotNull(TEXT("Isolated agent"),Agent)) { World->DestroyWorld(false);return false; }
    TestNull(TEXT("Disabled by default"),FindSmoothing(Agent));
    for (float Dt:{1.f/30,1.f/60,1.f/120})
    {
        UProphecyWalkPinningLibrary::SetWalkPinningSmoothing(Agent,true,4,2);
        ResetSmoothing(Agent);
        auto* S=FindSmoothing(Agent);
        float L=1,R=0;SmoothPins(*S,L,R);
        TestEqual(TEXT("New pin starts from zero"),L,0.f);
        TickSmoothing(World,LEVELTICK_PauseTick,Dt);
        TestEqual(TEXT("Pause does not age smoothing"),S->Current[0],0.f);
        for (int32 Frame=1;Frame<=4;++Frame)
        {
            TickSmoothing(World,LEVELTICK_All,Dt);
            L=1;R=0;SmoothPins(*S,L,R);
            TestEqual(TEXT("Four game ticks rise independent of FPS"),L,float(Frame)/4.f);
            L=1;R=0;SmoothPins(*S,L,R);
            UProphecyWalkPinningLibrary::SetWalkPinningSmoothing(Agent,true,4,2);
            TestEqual(TEXT("Extra NN evaluations / same setter do not advance or restart"),S->Current[0],float(Frame)/4.f);
        }
        TestFalse(TEXT("Stable pin removes callback"),SmoothTickHandle.IsValid());
        L=0;R=1;SmoothPins(*S,L,R);
        TestEqual(TEXT("Release starts continuously"),L,1.f);
        TickSmoothing(World,LEVELTICK_All,Dt);
        TestEqual(TEXT("Independent release direction"),S->Current[0],.5f);
        TestEqual(TEXT("Other foot independently pins in"),S->Current[1],.25f);
        L=1;R=0;SmoothPins(*S,L,R);
        TestEqual(TEXT("Mid-ramp reversal has no jump"),L,.5f);
        TickSmoothing(World,LEVELTICK_All,Dt);
        TestEqual(TEXT("Reversal uses pin-in speed"),S->Current[0],.75f);
        TestEqual(TEXT("Opposite partial pin releases within one tick"),S->Current[1],0.f);
        TickSmoothing(World,LEVELTICK_All,Dt);
        L=0;R=0;SmoothPins(*S,L,R);
        TickSmoothing(World,LEVELTICK_All,Dt);TickSmoothing(World,LEVELTICK_All,Dt);
        TestEqual(TEXT("Full release takes exactly two game ticks"),S->Current[0],0.f);
    }
    UProphecyWalkPinningLibrary::SetWalkPinningSmoothing(Agent,true,60,60);
    auto* S=FindSmoothing(Agent);
    float L=1,R=1;SmoothPins(*S,L,R);
    for (int32 I=0;I<60;++I) TickSmoothing(World,LEVELTICK_All,1.f/45);
    TestEqual(TEXT("Sixty ticks reaches exact endpoint without float accumulation"),S->Current[0],1.f);
    TestFalse(TEXT("Exact endpoint retires callback"),SmoothTickHandle.IsValid());
    L=0;R=1;SmoothPins(*S,L,R);
    TestEqual(TEXT("Release retains smoothing instead of an obsolete raw veto"),L,1.f);
    ClearSmoothedFoot(*S,1);
    TestEqual(TEXT("Reach rejection clears the affected foot"),S->Current[1],0.f);
    L=1;R=1;SmoothPins(*S,L,R);
    TickSmoothing(World,LEVELTICK_All,1.f/60);
    ResetSmoothing(Agent);
    TestFalse(TEXT("Reset/special cancels both pending ramps"),S->Active());
    TestEqual(TEXT("Reset preserves configuration"),S->InFrames,60);
    TestFalse(TEXT("Reset retires callback"),SmoothTickHandle.IsValid());
    UProphecyWalkPinningLibrary::SetWalkPinningSmoothing(Agent,true,0,2);
    L=1;R=0;SmoothPins(*S,L,R);
    TestEqual(TEXT("Zero pin-in is immediate"),L,1.f);
    UProphecyWalkPinningLibrary::SetWalkPinningSmoothing(Agent,true,2,0);
    L=0;R=0;SmoothPins(*S,L,R);
    TestEqual(TEXT("Zero pin-out is immediate"),L,0.f);
    UProphecyWalkPinningLibrary::SetWalkPinningSmoothing(Agent,true,0,0);
    TestNull(TEXT("Both zero is full bypass"),FindSmoothing(Agent));
    UProphecyWalkPinningLibrary::SetWalkPinningSmoothing(Agent,true,3,3);
    S=FindSmoothing(Agent);L=1;R=0;SmoothPins(*S,L,R);
    UProphecyWalkPinningLibrary::SetWalkPinningSmoothing(Agent,false,3,3);
    TestNull(TEXT("Disable removes history"),FindSmoothing(Agent));
    TestFalse(TEXT("Disable removes callback"),SmoothTickHandle.IsValid());
    TestFalse(TEXT("Negative duration rejected"),UProphecyWalkPinningLibrary::SetWalkPinningSmoothing(Agent,true,-1,3));
    World->DestroyWorld(false);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyWalkPinningReachTest,"Prophecy.NN.WalkPinning.ReachGuard",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyWalkPinningReachTest::RunTest(const FString&)
{
    using namespace ProphecyWalkPinning;
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false);
    if (!TestNotNull(TEXT("Isolated world"),World)) return false;
    AProphecyAgent* Agent=World->SpawnActor<AProphecyAgent>();
    if (!TestNotNull(TEXT("Isolated agent"),Agent)) { World->DestroyWorld(false);return false; }
    const FVector3f Hip(0,0,.8f),Safe(0,0,.1f),Straight(0,0,0);
    TestNull(TEXT("Feature defaults off"),FindReachGuard(Agent));
    TestFalse(TEXT("No default cooldown tick"),ReachTickHandle.IsValid());
    TestTrue(TEXT("Enable six-frame guard"),UProphecyWalkPinningLibrary::SetWalkPinningReachGuard(Agent,true,6));
    auto* Guard=FindReachGuard(Agent);
    TestFalse(TEXT("Enabled but idle does not tick"),ReachTickHandle.IsValid());
    TestFalse(TEXT("Reachable pin remains"),RejectPin(*Guard,0,Hip,Safe,.8f));
    TestTrue(TEXT("Exact full extension rejects"),RejectPin(*Guard,0,Hip,Straight,.8f));
    TestEqual(TEXT("Only affected foot gets cooldown"),Guard->Remaining[1],0);
    TestFalse(TEXT("Opposite foot's reachable pin remains"),RejectPin(*Guard,1,Hip,Safe,.8f));
    TestTrue(TEXT("Cooldown has timer only while active"),ReachTickHandle.IsValid());
    for (float Dt:{1.f/30,1.f/60,1.f/120})
    {
        ClearReachCooldown(Agent);
        RejectPin(*Guard,0,Hip,Straight,.8f);
        TickReach(World,LEVELTICK_PauseTick,Dt);
        TestEqual(TEXT("Paused tick does not age cooldown"),Guard->Remaining[0],6);
        for (int32 Frame=1;Frame<6;++Frame)
        {
            TickReach(World,LEVELTICK_All,Dt);
            TestTrue(TEXT("Reject reachable pin during cooldown"),RejectPin(*Guard,0,Hip,Safe,.8f));
            RejectPin(*Guard,0,Hip,Straight,.8f);
            TestEqual(TEXT("Repeated policy reads do not extend or age cooldown"),Guard->Remaining[0],6-Frame);
        }
        TickReach(World,LEVELTICK_All,Dt);
        TestFalse(TEXT("Reachable pin allowed after six ticks at any FPS"),RejectPin(*Guard,0,Hip,Safe,.8f));
        TestFalse(TEXT("Completed cooldown removes tick"),ReachTickHandle.IsValid());
    }
    RejectPin(*Guard,1,Hip,Straight,.8f);
    ClearReachCooldown(Agent);
    TestFalse(TEXT("Agent reset clears both cooldowns"),Guard->HasCooldown());
    TestEqual(TEXT("Reset retains configured duration"),Guard->Frames,6);
    TestFalse(TEXT("Reset removes idle timer"),ReachTickHandle.IsValid());
    UProphecyWalkPinningLibrary::SetWalkPinningReachGuard(Agent,true,0);
    TestTrue(TEXT("Zero frames still rejects unsafe pin"),RejectPin(*Guard,0,Hip,Straight,.8f));
    TestFalse(TEXT("Zero frames leaves no cooldown"),Guard->HasCooldown());
    TestFalse(TEXT("Zero frames has no timer"),ReachTickHandle.IsValid());
    TestFalse(TEXT("Zero frames permits subsequent safe pin"),RejectPin(*Guard,0,Hip,Safe,.8f));
    UProphecyWalkPinningLibrary::SetWalkPinningReachGuard(Agent,true,6);
    RejectPin(*Guard,0,Hip,Straight,.8f);
    UProphecyWalkPinningLibrary::SetWalkPinningReachGuard(Agent,false,6);
    TestNull(TEXT("Disable removes settings and cooldown"),FindReachGuard(Agent));
    TestFalse(TEXT("Disable removes timer"),ReachTickHandle.IsValid());
    World->DestroyWorld(false);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyWalkPinningToleranceTest,"Prophecy.NN.WalkPinning.Tolerance",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyWalkPinningToleranceTest::RunTest(const FString&)
{
    using namespace ProphecyWalkPinning;
    float L=1,R=0;
    TestFalse(TEXT("Default preserves even positive ties"),FSettings{}.Apply(.125f,.125f,8,L,R));
    TestEqual(TEXT("Bypass leaves legacy result untouched"),L,1.f);
    FSettings Config{.125f,0};
    TestTrue(TEXT("Inclusive tolerance boundary"),Config.Apply(.125f,.25f,8,L,R));
    TestEqual(TEXT("Zero fallback left"),L,0.f);
    TestEqual(TEXT("Zero fallback right"),R,0.f);
    Config.Fallback=1;
    TestTrue(TEXT("Raw fallback applies"),Config.Apply(.125f,.25f,8,L,R));
    TestNearlyEqual(TEXT("Left decoded soft probability"),L,.26894142f,1.e-6f);
    TestNearlyEqual(TEXT("Right decoded soft probability"),R,.11920292f,1.e-6f);
    Config.Fallback=.5f;
    Config.Apply(.125f,.25f,8,L,R);
    TestNearlyEqual(TEXT("Intermediate fallback scales soft weights"),L,.13447071f,1.e-6f);
    TestFalse(TEXT("Outside tolerance retains hard selection"),Config.Apply(.125f,.375f,8,L,R));
    TestFalse(TEXT("Two negative values retain both-pinned rule"),Config.Apply(-.125f,-.25f,8,L,R));
    TestFalse(TEXT("Mixed signs retain hard selection"),Config.Apply(-.125f,.125f,8,L,R));
    TestFalse(TEXT("Zero is not strictly positive"),Config.Apply(0,.125f,8,L,R));
    return true;
}
#endif
