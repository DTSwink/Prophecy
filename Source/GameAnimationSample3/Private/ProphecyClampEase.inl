// Included by PhysicalFootTargetLibrary; no UObject or retained structure changes.
#include "ProphecyClampEase.h"
namespace ProphecyClampEase
{
struct FChannels { FReduction Values[uint8(EChannel::Count)]; };
static TMap<TWeakObjectPtr<const AProphecyAgent>,FChannels> States;
static TSet<TWeakObjectPtr<const AProphecyAgent>> Active;
static FDelegateHandle Tick,Cleanup;
static void Refresh();
static void Advance(UWorld* W,ELevelTick Type,float)
{
    if(Type==LEVELTICK_PauseTick || !W || W->IsPaused())return;
    for(auto It=Active.CreateIterator();It;++It)
    {
        const auto* A=It->Get();
        if(!A || A->IsActorBeingDestroyed()){States.Remove(*It);It.RemoveCurrent();continue;}
        if(A->GetWorld()!=W)continue;
        auto* S=States.Find(*It);bool Running=false;
        if(S)for(auto& C:S->Values){C.Advance(1./60.);Running|=C.Active;}
        if(!Running)It.RemoveCurrent();
    }
    Refresh();
}
static void Refresh()
{
    if(Active.IsEmpty()){FWorldDelegates::OnWorldPreActorTick.Remove(Tick);Tick.Reset();}
    else if(!Tick.IsValid())Tick=FWorldDelegates::OnWorldPreActorTick.AddStatic(&Advance);
    if(States.IsEmpty()){FWorldDelegates::OnWorldCleanup.Remove(Cleanup);Cleanup.Reset();}
    else if(!Cleanup.IsValid())Cleanup=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        for(auto It=States.CreateIterator();It;++It)if(!It.Key().IsValid() || It.Key()->GetWorld()==W)
        {Active.Remove(It.Key());It.RemoveCurrent();}
        Refresh();
    });
}
bool NeedsObservation(const AProphecyAgent* A,EChannel C,float Target)
{
    if(Target<0 || !A || !A->GetWorld())return false;
    const auto* S=States.Find(A);const auto* V=S?&S->Values[uint8(C)]:nullptr;
    return !V || (!V->Active && Target!=V->Target && (V->Value<0 || Target<V->Value));
}
float Resolve(const AProphecyAgent* A,EChannel C,float Target,float Observed)
{
    if(!A || !A->GetWorld())return Target;
    auto* S=States.Find(A);
    if(!S && Target<0)return Target;
    if(!S)S=&States.Add(A);
    auto& V=S->Values[uint8(C)];
    if(Target==V.Target)return V.Value;
    V.Request(Target,Observed);
    if(V.Active)Active.Add(A);
    Refresh();return V.Value;
}
float Current(const AProphecyAgent* A,EChannel C,float Fallback)
{const auto* S=States.IsEmpty()?nullptr:States.Find(A);return S && S->Values[uint8(C)].Target>=0?S->Values[uint8(C)].Value:Fallback;}
void Remove(const AProphecyAgent* A){States.Remove(A);Active.Remove(A);Refresh();}
}
