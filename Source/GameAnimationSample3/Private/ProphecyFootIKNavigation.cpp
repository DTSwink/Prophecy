#include "ProphecyFootIKNavigation.h"
#include "ProphecyAgent.h"
#include "Components/CapsuleComponent.h"
#include "Components/PrimitiveComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"

namespace ProphecyFootIKNavigation
{
namespace
{
// Keep the movement capsule just outside the support contact. An exact sweep
// contact is unsafe as the start of the next swept move: a tangent/roundoff
// overlap with the floor can block that move at t=0. This is a collision skin,
// not an accumulated root displacement or a change to the NN's virtual height.
constexpr double SupportSkinCm=.1;
struct FState
{
    double Offset=0,MaximumIncline=80,SourceTime=-1;
    FVector LastActual=FVector::ZeroVector,LastVirtual=FVector::ZeroVector;
    FVector PreviousPublishedVirtual=FVector::ZeroVector,CurrentPublishedVirtual=FVector::ZeroVector;
    FVector PreviousPublishedActual=FVector::ZeroVector,CurrentPublishedActual=FVector::ZeroVector;
    bool Published=false;
};
TMap<TWeakObjectPtr<AProphecyAgent>,FState> States;
FDelegateHandle CleanupHandle;
void EnsureCleanup()
{
    if(CleanupHandle.IsValid())return;
    CleanupHandle=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* World,bool,bool)
    {
        for(auto It=States.CreateIterator();It;++It)
            if(!It.Key().IsValid()||It.Key()->GetWorld()==World)It.RemoveCurrent();
        if(States.IsEmpty()){FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);CleanupHandle.Reset();}
    });
}
struct FQuery
{
    AProphecyAgent* Agent;
    UWorld* World;
    FCollisionQueryParams Params{SCENE_QUERY_STAT(FootIKNavigation),false};
    FCollisionShape Shape;
    ECollisionChannel Channel=ECC_GameTraceChannel8;
    double HalfHeight=0,Radius=0,MinimumNormalZ=0,MaximumSlope=0;
    explicit FQuery(AProphecyAgent* InAgent,double MaximumIncline)
        :Agent(InAgent),World(InAgent->GetWorld())
    {
        const auto* Capsule=Agent->GetAgentCapsule();HalfHeight=Capsule->GetScaledCapsuleHalfHeight();Radius=Capsule->GetScaledCapsuleRadius();
        Shape=FCollisionShape::MakeCapsule(float(Radius),float(HalfHeight));Channel=Capsule->GetCollisionObjectType();
        const double Angle=FMath::DegreesToRadians(FMath::Clamp(MaximumIncline,0.,89.));
        MinimumNormalZ=FMath::Cos(Angle);MaximumSlope=FMath::Tan(Angle);
        Params.bFindInitialOverlaps=true;
        for(TActorIterator<AProphecyAgent> It(World);It;++It)Params.AddIgnoredActor(*It);
    }
    bool Support(const FVector& PreviousActual,const FVector& DesiredActual,FVector& Out,FVector* Normal=nullptr)
    {
        Out=DesiredActual;
        const double Travel=FVector::Dist2D(PreviousActual,DesiredActual);
        // This reach follows local travel, not world height or a hardcoded
        // staircase. The small collision tolerance permits support continuity
        // while standing still and through capsule/finite-plane edge rounding.
        const double VerticalReach=FMath::Max(2.,Travel*MaximumSlope+2.);
        const FVector Start(DesiredActual.X,DesiredActual.Y,PreviousActual.Z+VerticalReach+HalfHeight);
        const FVector End(DesiredActual.X,DesiredActual.Y,PreviousActual.Z-VerticalReach+HalfHeight);
        auto Query=Params;
        for(int32 Retry=0;Retry<8;++Retry)
        {
            FHitResult Hit;
            if(!World->SweepSingleByChannel(Hit,Start,End,FQuat::Identity,Channel,Shape,Query))return false;
            auto* Component=Hit.Component.Get();
            if(!Component)return false;
            const bool FeetOnly=Component->ComponentHasTag(TEXT("FootIKFeet"))&&!Component->ComponentHasTag(TEXT("FootIKRoot"));
            const FVector SurfaceNormal=Hit.ImpactNormal.GetSafeNormal();
            if(FeetOnly||Hit.bStartPenetrating||SurfaceNormal.Z<MinimumNormalZ)
            {
                // A tagged tread, ceiling underside or vertical side is not a
                // support plane. It still blocks the separate movement sweep.
                Query.AddIgnoredComponent(Component);continue;
            }
            const double LowZ=Hit.Location.Z-HalfHeight;
            if(!FMath::IsFinite(LowZ)||FMath::Abs(LowZ-PreviousActual.Z)>VerticalReach+.01)return false;
            // Apply the skin normal to the plane while retaining the authored
            // XY trajectory. Compute from the new contact each time, never from
            // the preceding supported height, so a stationary root cannot drift.
            Out.Z=LowZ+SupportSkinCm/SurfaceNormal.Z;
            if(Normal)*Normal=SurfaceNormal;return true;
        }
        return false;
    }
};
}
void Begin(AProphecyAgent* Agent,double VirtualHeight,double MaximumInclineDegrees)
{
    check(IsInGameThread());if(!IsValid(Agent)||!Agent->GetWorld()||!Agent->GetAgentCapsule()||!FMath::IsFinite(VirtualHeight)||!FMath::IsFinite(MaximumInclineDegrees))return;
    EnsureCleanup();if(States.Contains(Agent))return;
    auto& State=States.Add(Agent);State.LastActual=Agent->GetRootLowPoint();State.LastVirtual=State.LastActual;State.LastVirtual.Z=VirtualHeight;
    State.Offset=State.LastActual.Z-VirtualHeight;State.MaximumIncline=FMath::Clamp(MaximumInclineDegrees,0.,89.);
}
bool Active(const AProphecyAgent* Agent){return States.Contains(const_cast<AProphecyAgent*>(Agent));}
double Lift(const AProphecyAgent* Agent){const auto* S=States.Find(const_cast<AProphecyAgent*>(Agent));return S?S->Offset:0.;}
bool PrepareMove(AProphecyAgent* Agent,const FVector& DesiredVirtualRoot,FMove& Out)
{
    check(IsInGameThread());auto* State=States.Find(Agent);if(!State||DesiredVirtualRoot.ContainsNaN())return false;
    Out={};Out.VirtualRoot=DesiredVirtualRoot;Out.PreviousActualRoot=Agent->GetRootLowPoint();Out.PreviousVirtualRoot=Out.PreviousActualRoot-FVector(0,0,State->Offset);
    Out.ActualRoot=DesiredVirtualRoot+FVector(0,0,State->Offset);
    FQuery Query(Agent,State->MaximumIncline);Out.HasSupport=Query.Support(Out.PreviousActualRoot,Out.ActualRoot,Out.ActualRoot,&Out.SupportNormal);return true;
}
FVector CommitMove(AProphecyAgent* Agent,const FMove& Move,const FVector& AppliedActualRoot)
{
    check(IsInGameThread());auto* State=States.Find(Agent);if(!State)return AppliedActualRoot;
    State->LastActual=AppliedActualRoot;State->LastVirtual=AppliedActualRoot;State->LastVirtual.Z=Move.VirtualRoot.Z;
    State->Offset=AppliedActualRoot.Z-Move.VirtualRoot.Z;return State->LastVirtual;
}
bool PublicationCarriers(AProphecyAgent* Agent,double SourceTime,
    const FVector& PreviousVirtualRoot,const FVector& CurrentVirtualRoot,FVector& PreviousActualRoot,FVector& CurrentActualRoot)
{
    check(IsInGameThread());auto* S=States.Find(Agent);if(!S||!FMath::IsFinite(SourceTime)||PreviousVirtualRoot.ContainsNaN()||CurrentVirtualRoot.ContainsNaN())return false;
    if(S->Published&&S->SourceTime==SourceTime&&S->PreviousPublishedVirtual==PreviousVirtualRoot&&S->CurrentPublishedVirtual==CurrentVirtualRoot)
    {PreviousActualRoot=S->PreviousPublishedActual;CurrentActualRoot=S->CurrentPublishedActual;return true;}
    FQuery Query(Agent,S->MaximumIncline);
    PreviousActualRoot=PreviousVirtualRoot+FVector(0,0,S->Offset);
    if(S->Published&&SourceTime>S->SourceTime&&S->CurrentPublishedVirtual==PreviousVirtualRoot)PreviousActualRoot=S->CurrentPublishedActual;
    else Query.Support(S->LastActual,PreviousActualRoot,PreviousActualRoot);
    CurrentActualRoot=CurrentVirtualRoot+FVector(0,0,S->Offset);Query.Support(PreviousActualRoot,CurrentActualRoot,CurrentActualRoot);
    S->SourceTime=SourceTime;S->PreviousPublishedVirtual=PreviousVirtualRoot;S->CurrentPublishedVirtual=CurrentVirtualRoot;
    S->PreviousPublishedActual=PreviousActualRoot;S->CurrentPublishedActual=CurrentActualRoot;S->Published=true;return true;
}
bool ProjectWindow(AProphecyAgent* Agent,TArray<FTransform>& WorldRoots)
{
    check(IsInGameThread());auto* S=States.Find(Agent);if(!S||WorldRoots.IsEmpty())return false;
    FQuery Query(Agent,S->MaximumIncline);FVector Previous=WorldRoots[0].GetLocation();
    double OriginalZ=Previous.Z;
    for(int32 I=1;I<WorldRoots.Num();++I)
    {
        const FVector Original=WorldRoots[I].GetLocation();FVector Desired=Original;Desired.Z=Previous.Z+(Original.Z-OriginalZ);
        FVector Projected;Query.Support(Previous,Desired,Projected);WorldRoots[I].SetLocation(Projected);Previous=Projected;OriginalZ=Original.Z;
    }
    return true;
}
double Remove(AProphecyAgent* Agent)
{
    check(IsInGameThread());const double Offset=Lift(Agent);States.Remove(Agent);
    if(States.IsEmpty()&&CleanupHandle.IsValid()){FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle);CleanupHandle.Reset();}
    return Offset;
}
}
