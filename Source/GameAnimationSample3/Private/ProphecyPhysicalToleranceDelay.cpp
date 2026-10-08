#include "ProphecyPhysicalToleranceDelay.h"
#include "ProphecyAgent.h"
#include "ProphecyPhysicalContext.h"
#include "ProphecyBlendClock.h"
#include "Engine/World.h"

namespace ProphecyPhysicalToleranceDelay
{
struct FRequest
{
    TWeakObjectPtr<AProphecyAgent> Agent;
    EScope Scope;
    FName Bone;
    bool IncludeParent;
    float Linear, Angular;
    EProphecyLocomotionSelection Locomotion;
    EProphecyEquipmentSelection Equipment;
    uint64 Remaining;
    uint64 LastFrame;
};
static TArray<FRequest> Pending;
static const AProphecyAgent* ApplyingAgent=nullptr;
bool IsApplying(const AProphecyAgent* Agent) { return Agent && ApplyingAgent==Agent; }
static FDelegateHandle TickHandle, CleanupHandle;
static void Refresh();

static void Tick(UWorld* World, ELevelTick TickType, float Delta)
{
    if (!World || World->IsPaused() || TickType!=LEVELTICK_All || !FMath::IsFinite(Delta) || Delta<=0) return;
    // Collect first: applying a setter can indirectly cancel an agent's other requests.
    TArray<FRequest, TInlineAllocator<8>> Due;
    Pending.RemoveAll([&](FRequest& R)
    {
        auto* A=R.Agent.Get();
        if (!A || A->IsActorBeingDestroyed()) return true;
        if (A->GetWorld()==World && R.LastFrame!=GFrameCounter)
        {
            R.LastFrame=GFrameCounter;
            if (--R.Remaining==0) { Due.Add(R); return true; }
        }
        return false;
    });
    Refresh();
    for (const auto& R:Due)
    {
        auto* A=R.Agent.Get();
        if (!IsValid(A) || A->IsActorBeingDestroyed()) continue;
        TGuardValue<const AProphecyAgent*> Applying(ApplyingAgent,A);
        if (R.Scope==EScope::All) A->SetAllPhysicalFeedbackTolerances(R.Linear,R.Angular);
        else if (R.Scope==EScope::Below)
            A->SetPhysicalFeedbackToleranceBelow(R.Bone,R.IncludeParent,R.Linear,R.Angular,R.Locomotion,R.Equipment);
        else A->SetPhysicalFeedbackTolerance(R.Bone,R.Linear,R.Angular,R.Locomotion,R.Equipment);
    }
}
static void Cleanup(UWorld* World, bool, bool)
{
    Pending.RemoveAll([&](const FRequest& R){return !R.Agent.IsValid() || R.Agent->GetWorld()==World;});
    Refresh();
}
static void Refresh()
{
    if (Pending.IsEmpty())
    {
        FWorldDelegates::OnWorldPreActorTick.Remove(TickHandle); TickHandle.Reset();
        FWorldDelegates::OnWorldCleanup.Remove(CleanupHandle); CleanupHandle.Reset();
    }
    else
    {
        if (!TickHandle.IsValid()) TickHandle=FWorldDelegates::OnWorldPreActorTick.AddStatic(&Tick);
        if (!CleanupHandle.IsValid()) CleanupHandle=FWorldDelegates::OnWorldCleanup.AddStatic(&Cleanup);
    }
}
bool Schedule(AProphecyAgent& Agent, EScope Scope, FName Bone, bool IncludeParent,
    float Linear, float Angular, EProphecyLocomotionSelection Locomotion,
    EProphecyEquipmentSelection Equipment, float Delay)
{
    const auto* World=Agent.GetWorld();
    if (!IsInGameThread() || Agent.IsActorBeingDestroyed() || !World || !World->IsGameWorld()
        || World->bIsTearingDown || !FMath::IsFinite(Delay) || Delay<=0
        || !FMath::IsFinite(Linear) || !FMath::IsFinite(Angular)
        || !ProphecyPhysicalContext::Valid(Locomotion,Equipment)) return false;
    // Same upward tick rounding and float-boundary allowance as ProphecyBlendClock.
    const uint64 Ticks=uint64(FMath::Max(1.,FMath::CeilToDouble(FMath::Min(double(Delay)/ProphecyBlendClock::TickSeconds,9.e15)-1.e-5)));
    Pending.Add({&Agent,Scope,Bone,IncludeParent,Linear,Angular,Locomotion,Equipment,Ticks,GFrameCounter});
    Refresh();
    return true;
}
void Cancel(const AProphecyAgent* Agent)
{
    if (Pending.IsEmpty()) return;
    Pending.RemoveAll([&](const FRequest& R){return R.Agent==Agent;});
    Refresh();
}
}
