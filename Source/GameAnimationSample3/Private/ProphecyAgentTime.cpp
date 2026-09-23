#include "ProphecyAgentTime.h"
#include "ProphecyNNLocomotionManager.h"

namespace ProphecyAgentTime
{
void FClocks::Set(int32 Index,double Value)
{
    check(FMath::IsFinite(Value) && Value>0.);
    FLane* Existing=Lanes.Find(Index);
    if (Value==1.)
    {
        if (!Existing || Existing->Joining) return;
        if (FMath::Abs(Existing->Phase-SharedPhase)<1.e-7) { Lanes.Remove(Index);return; }
        Existing->Rate=1.;Existing->Joining=true;
        Existing->JoinRate=(1.-Existing->Phase)/FMath::Max(1.e-9,1.-SharedPhase);
        return;
    }
    if (!Existing)
    {
        FLane New;New.Phase=SharedPhase;
        Existing=&Lanes.Add(Index,New);
    }
    Existing->Rate=Value;Existing->Joining=false;
}
double FClocks::Rate(int32 Index) const
{ const auto* L=Lanes.Find(Index);return L?L->Rate:1.; }
double FClocks::Alpha(int32 Index) const
{ const auto* L=Lanes.Find(Index);return L?L->Phase:SharedPhase; }

void FClocks::Advance(double Delta,double H,int32 Count,int32 MaxSteps,TFunctionRef<void(FStep&)> Step)
{
    if (Delta<=0. || H<=0.) return;
    // Merge local boundaries in chronological order. Special actions advance
    // only on shared boundaries, even when another lane takes extra NN steps.
    double Remaining=Delta/H,Elapsed=0.;
    int32 SharedSteps=0;
    TArray<int32> Counts;Counts.Init(0,Count);
    TBitArray<> Sampled(false,Count);
    FStep Event(Count);
    constexpr double Epsilon=1.e-7;
    while (Remaining>Epsilon)
    {
        double Next=SharedSteps<MaxSteps?FMath::Max(0.,1.-SharedPhase):DBL_MAX;
        for (const auto& Pair:Lanes)
            if (Counts.IsValidIndex(Pair.Key) && Counts[Pair.Key]<MaxSteps && !Pair.Value.Joining)
                Next=FMath::Min(Next,FMath::Max(0.,1.-Pair.Value.Phase)/Pair.Value.Rate);
        const double AdvanceBy=FMath::Min(Next,Remaining);
        SharedPhase+=AdvanceBy;
        for (auto& Pair:Lanes) Pair.Value.Phase+=AdvanceBy*Pair.Value.EffectiveRate();
        Elapsed+=AdvanceBy;Remaining=FMath::Max(0.,Remaining-AdvanceBy);
        if (Next>AdvanceBy+Epsilon) break;
        Event.Due.Init(false,Count);Event.SamplePhysics.Init(false,Count);
        Event.WorldIntervals.Init(H,Count);
        Event.SharedBoundary=SharedSteps<MaxSteps && SharedPhase>=1.-Epsilon;
        Event.ElapsedSeconds=Elapsed*H;
        if (Event.SharedBoundary)
        {
            SharedPhase=FMath::Max(0.,SharedPhase-1.);++SharedSteps;
            Event.Due.Init(true,Count);
        }
        for (auto It=Lanes.CreateIterator();It;++It)
        {
            const int32 I=It.Key();auto& L=It.Value();
            if (!Counts.IsValidIndex(I)) { It.RemoveCurrent();continue; }
            if (L.Joining)
            {
                Event.Due[I]=Event.SharedBoundary;
                if (Event.SharedBoundary) It.RemoveCurrent();
            }
            else
            {
                Event.Due[I]=Counts[I]<MaxSteps && L.Phase>=1.-Epsilon;
                if (Event.Due[I])
                { L.Phase=FMath::Max(0.,L.Phase-1.);Event.WorldIntervals[I]=H/L.Rate; }
            }
        }
        bool Any=false;
        for (int32 I=0;I<Count;++I) if (Event.Due[I])
        {
            Any=true;++Counts[I];Event.SamplePhysics[I]=!Sampled[I];Sampled[I]=true;
        }
        if (Any) Step(Event);
    }
    // Same bounded hitch policy as the existing scheduler, independently per
    // clock. Never retain an unbounded backlog after a debugger pause.
    SharedPhase=FMath::Fmod(SharedPhase,1.);
    for (auto& Pair:Lanes) Pair.Value.Phase=FMath::Fmod(Pair.Value.Phase,1.);
}

static TMap<TWeakObjectPtr<const AProphecyNNLocomotionManager>,TSharedPtr<FClocks>> Managers;
static FContext* Current=nullptr; // Scoped to a synchronous game-thread batch.
const FContext* Context(const AProphecyNNLocomotionManager* Manager)
{ return Current && Current->Manager==Manager ? Current:nullptr; }
static FClocks* Find(const AProphecyNNLocomotionManager* Manager)
{
    const auto* P=Managers.IsEmpty()?nullptr:Managers.Find(Manager);
    return P?P->Get():nullptr;
}
bool HasClocks(const AProphecyNNLocomotionManager* Manager)
{ const auto* C=Find(Manager);return C && !C->Lanes.IsEmpty(); }
void Set(AProphecyNNLocomotionManager* Manager,int32 Index,double Value,float SharedAlpha)
{
    if (Value==1. && !HasClocks(Manager)) return;
    auto& Ptr=Managers.FindOrAdd(Manager);
    if (!Ptr) { Ptr=MakeShared<FClocks>();Ptr->SharedPhase=SharedAlpha; }
    Ptr->Set(Index,Value);
    if (Ptr->Lanes.IsEmpty() && !Context(Manager)) Managers.Remove(Manager);
}
float Rate(const AProphecyNNLocomotionManager* Manager,int32 Index)
{ const auto* C=Find(Manager);return C?float(C->Rate(Index)):1.f; }
float Alpha(const AProphecyNNLocomotionManager* Manager,int32 Index,float SharedAlpha)
{ const auto* C=Find(Manager);return C?float(C->Alpha(Index)):SharedAlpha; }
void Reset(AProphecyNNLocomotionManager* Manager,int32 Index,float SharedAlpha)
{
    Set(Manager,Index,1.,SharedAlpha);
    // An Armed gate may activate a slow defender on a shared step where its
    // locomotion lane was not due. Its new defense pose must still be published.
    if (auto* C=const_cast<FContext*>(Context(Manager));C && C->Step->Due.IsValidIndex(Index))
        C->Step->Due[Index]=true;
}
void Remove(const AProphecyNNLocomotionManager* Manager) { Managers.Remove(Manager); }
void RemoveLane(const AProphecyNNLocomotionManager* Manager,int32 Index)
{
    if (auto* C=Find(Manager))
    {
        C->Lanes.Remove(Index);
        if (C->Lanes.IsEmpty() && !Context(Manager)) Managers.Remove(Manager);
    }
}
void Advance(AProphecyNNLocomotionManager* Manager,float Delta,float H,int32 Count,int32 MaxSteps,
    float& Accumulated,double WorldTime,TFunctionRef<void(FStep&)> Step)
{
    // Retain through callbacks that reset the final custom lane/world.
    const TSharedPtr<FClocks> Clocks=Managers.FindChecked(Manager);
    Clocks->SharedPhase=FMath::Clamp(double(Accumulated)/H,0.,1.);
    Clocks->Advance(Delta,H,Count,MaxSteps,[&](FStep& Event)
    {
        Event.SourceTimeSeconds=WorldTime-Delta+Event.ElapsedSeconds;
        // Keep old helpers that read the shared accumulator at this boundary
        // consistent; agent-specific inertia uses the explicit event timestamp.
        Accumulated=float(H+FMath::Max(0.,double(Delta)-Event.ElapsedSeconds));
        FContext ContextValue{Manager,&Event};
        TGuardValue<FContext*> Guard(Current,&ContextValue);
        Step(Event);
    });
    Accumulated=float(Clocks->SharedPhase*H);
    if (Clocks->Lanes.IsEmpty()) Managers.Remove(Manager);
}
}
