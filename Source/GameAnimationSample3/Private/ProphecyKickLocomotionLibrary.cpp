#include "ProphecyKickLocomotionLibrary.h"
#include "ProphecyKickLocomotion.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"

namespace ProphecyKickLocomotion
{
static TSet<TWeakObjectPtr<const AProphecyAgent>> DragSettings,DragBaselines,DragRuns;
static TMap<TWeakObjectPtr<const AProphecyAgent>,FRunLegHistory> RunLegs;
static FDelegateHandle DragCleanupHandle;
FRunLegHistory& SaveRunLeg(const AProphecyAgent* A){return RunLegs.FindOrAdd(A);}
const FRunLegHistory* FindRunLeg(const AProphecyAgent* A){return RunLegs.IsEmpty()?nullptr:RunLegs.Find(A);}
void ClearRunLeg(const AProphecyAgent* A){if(!RunLegs.IsEmpty())RunLegs.Remove(A);}
static void EnsureCleanup()
{
    if(DragCleanupHandle.IsValid())return;
    DragCleanupHandle=FWorldDelegates::OnWorldCleanup.AddLambda([](UWorld* W,bool,bool)
    {
        for(auto* Set:{&DragSettings,&DragBaselines,&DragRuns})for(auto It=Set->CreateIterator();It;++It)
            if(!It->IsValid() || It->Get()->GetWorld()==W)It.RemoveCurrent();
        for(auto It=RunLegs.CreateIterator();It;++It)
            if(!It.Key().IsValid() || It.Key()->GetWorld()==W)It.RemoveCurrent();
    });
}
void End(const AProphecyAgent* A){ClearRunLeg(A);if(!DragRuns.IsEmpty())DragRuns.Remove(A);}
void Begin(AProphecyAgent* A,FName Attack)
{
    End(A);
    if(Side(Attack)!=INDEX_NONE && DragSettings.Contains(A))DragRuns.Add(A);
}
uint8 DragMask(const AProphecyAgent* A,FName Attack)
{
    const int32 S=Side(Attack);if(S==INDEX_NONE)return 3;
    return !DragRuns.IsEmpty() && DragRuns.Contains(A) ? uint8(1<<(1-S)) : 0;
}
void Remove(const AProphecyAgent* A){End(A);DragSettings.Remove(A);DragBaselines.Remove(A);}
void CaptureReset(const AProphecyAgent* A){if(DragSettings.Contains(A))DragBaselines.Add(A);else DragBaselines.Remove(A);}
void RestoreReset(const AProphecyAgent* A){End(A);if(DragBaselines.Contains(A))DragSettings.Add(A);else DragSettings.Remove(A);}
void ForgetReset(const AProphecyAgent* A){DragBaselines.Remove(A);}
}

bool UProphecyKickLocomotionLibrary::SetKickLocomotion(AProphecyAgent* Agent,bool NonKickingFootLocoDrag)
{
    if(!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed())return false;
    using namespace ProphecyKickLocomotion;
    if(!NonKickingFootLocoDrag)DragSettings.Remove(Agent);
    else {EnsureCleanup();DragSettings.Add(Agent);}
    return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyKickLocomotionStateTest,"Prophecy.NN.KickLocomotion.State",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyKickLocomotionStateTest::RunTest(const FString&)
{
    using namespace ProphecyKickLocomotion;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    using L=UProphecyKickLocomotionLibrary;
    Begin(A,TEXT("kickL"));
    TestEqual(TEXT("Default kick has no drag"),DragMask(A,TEXT("kickL")),uint8(0));
    TestFalse(TEXT("Default creates no transient entry"),DragRuns.Contains(A));
    for(int32 S=0;S<2;++S)
    {
        const FName Name=S?TEXT("kickR"):TEXT("kickL");
        L::SetKickLocomotion(A,true);Begin(A,Name);
        TestEqual(TEXT("Only supporting foot can drag"),DragMask(A,Name),uint8(1<<(1-S)));
        L::SetKickLocomotion(A,false);
        TestEqual(TEXT("Configuration stays latched for current kick"),DragMask(A,Name),uint8(1<<(1-S)));
        SaveRunLeg(A).Side=S;
        End(A);TestFalse(TEXT("End removes drag and hidden running history"),DragRuns.Contains(A)||FindRunLeg(A));
        Begin(A,Name);TestEqual(TEXT("Next kick uses disabled setting"),DragMask(A,Name),uint8(0));
    }
    L::SetKickLocomotion(A,true);CaptureReset(A);L::SetKickLocomotion(A,false);RestoreReset(A);
    Begin(A,TEXT("kickL"));TestEqual(TEXT("Reset restores drag configuration"),DragMask(A,TEXT("kickL")),uint8(2));
    SaveRunLeg(A).Side=0;RestoreReset(A);
    TestFalse(TEXT("Reset clears episode and hidden history"),DragRuns.Contains(A)||FindRunLeg(A));
    Begin(A,TEXT("slashL"));TestFalse(TEXT("Other attacks create no kick state"),DragRuns.Contains(A));
    TestEqual(TEXT("Other attacks retain both-foot permission"),DragMask(A,TEXT("slashL")),uint8(3));
    Remove(A);W->DestroyWorld(false);
    return !HasAnyErrors();
}
#endif
