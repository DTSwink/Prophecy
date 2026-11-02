#if WITH_DEV_AUTOMATION_TESTS
#include "ProphecyFootIKPlanner.h"
#include "Dom/JsonObject.h"
#include "HAL/Event.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformTime.h"
#include "Misc/AutomationTest.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonSerializer.h"

namespace ProphecyFootIKPlannerTests
{
struct FProbe
{
    FEvent* Gate=FPlatformProcess::GetSynchEventFromPool(true);
    TAtomic<bool> Started{false},Returned{false},SourceOnGameThread{false};
    TAtomic<int32> CancelCalls{0};
    ~FProbe(){FPlatformProcess::ReturnSynchEventToPool(Gate);}
};
struct FReleaseObservation
{
    TAtomic<bool> Released{false},OnGameThread{false};
};
struct FRetainedResource
{
    TSharedRef<FReleaseObservation,ESPMode::ThreadSafe> Observation;
    explicit FRetainedResource(TSharedRef<FReleaseObservation,ESPMode::ThreadSafe> In):Observation(In){}
    ~FRetainedResource(){Observation->OnGameThread.Store(IsInGameThread());Observation->Released.Store(true);}
};
struct FState
{
    FAutomationTestBase* Test=nullptr;
    FProphecyFootIKPlanner Planner;
    TSharedPtr<FProbe,ESPMode::ThreadSafe> Probe=MakeShared<FProbe,ESPMode::ThreadSafe>();
    TSharedRef<FReleaseObservation,ESPMode::ThreadSafe> Release=MakeShared<FReleaseObservation,ESPMode::ThreadSafe>();
    FString Fixture,Prefix;
    int32 Stage=0;
    double Started=FPlatformTime::Seconds(),IdleStarted=0;
    FProphecyFootIKPlanner::FCounts Disabled;
};
// A latent state machine keeps the game thread free while the real worker lane
// is paused, cancelled, drained, then asked to prepare/extend an exact course.
class FCheck final : public IAutomationLatentCommand
{
    TSharedRef<FState> State;
public:
    explicit FCheck(TSharedRef<FState> In):State(In){}
    bool Update() override
    {
        auto& S=*State;auto& T=*S.Test;FString Error,Value;
        if(FPlatformTime::Seconds()-S.Started>30)
        {S.Planner.Cancel();T.AddError(TEXT("Foot IK planner lifecycle timed out"));return true;}
        if(S.Stage==0)
        {
            if(!S.Probe->Started.Load())return false;
            T.TestFalse(TEXT("Source inference runs off the game thread"),S.Probe->SourceOnGameThread.Load());
            const double Begin=FPlatformTime::Seconds();S.Planner.Cancel();
            T.TestTrue(TEXT("Disable does not wait for the source worker"),FPlatformTime::Seconds()-Begin<.1);
            T.TestFalse(TEXT("Disabled planner has no future to poll"),S.Planner.Busy());
            T.TestEqual(TEXT("Disabled cache is removed"),S.Planner.Through(),-1);
            T.TestFalse(TEXT("Disabled cache cannot publish a pose"),S.Planner.Frame(0,Value));
            T.TestFalse(TEXT("Disabled course cannot extend"),S.Planner.Extend(.1,Error));
            S.Stage=1;return false;
        }
        if(S.Stage==1)
        {
            if(!S.Probe->Returned.Load()||S.Planner.Counts().Workers)return false;
            S.Disabled=S.Planner.Counts();S.IdleStarted=FPlatformTime::Seconds();
            T.TestEqual(TEXT("Native cancellation invoked once"),S.Probe->CancelCalls.Load(),1);
            T.TestEqual(TEXT("Cancelled source initialization invoked once"),S.Disabled.SourceCalls,int64(1));
            T.TestEqual(TEXT("Cancelled source never begins solver commands"),S.Disabled.SolverCommands,int64(0));
            T.TestEqual(TEXT("Cancelled source never begins inference"),S.Disabled.NNCalls,int64(0));
            T.TestTrue(TEXT("Cancelled diagnostics retained"),S.Disabled.Cancelled);S.Stage=2;return false;
        }
        if(S.Stage==2)
        {
            T.TestTrue(TEXT("Disabled poll is an empty success"),S.Planner.Poll(Error));
            if(FPlatformTime::Seconds()-S.IdleStarted<.1)return false;
            const auto C=S.Planner.Counts();
            T.TestEqual(TEXT("No solver work after disable"),C.SolverCommands,S.Disabled.SolverCommands);
            T.TestEqual(TEXT("No NN work after disable"),C.NNCalls,S.Disabled.NNCalls);
            T.TestEqual(TEXT("No source work after disable"),C.SourceCalls,S.Disabled.SourceCalls);
            T.TestEqual(TEXT("No worker survives disable"),C.Workers,0);
            // A resource captured by the real completed planner callback has
            // the same lifetime as its VM/NN ownership. No caller keeps it.
            auto Resource=MakeShared<FRetainedResource,ESPMode::ThreadSafe>(S.Release);
            if(!S.Planner.Prepare(S.Fixture,[Resource](const FString&,FString&,FString& Failure){Failure=TEXT("Flat fixture unexpectedly requested NN inference");return false;},.1,Error)){T.AddError(Error);return true;}
            S.Stage=3;return false;
        }
        if(S.Stage==5)
        {
            if(!S.Release->Released.Load())return false;
            T.TestFalse(TEXT("Idle planner resources release off the game thread"),S.Release->OnGameThread.Load());
            T.TestEqual(TEXT("Released planner has no source work"),S.Planner.Counts().SourceCalls,S.Disabled.SourceCalls);
            T.TestEqual(TEXT("Released planner has no NN work"),S.Planner.Counts().NNCalls,S.Disabled.NNCalls);
            T.TestEqual(TEXT("Released planner has no solver work"),S.Planner.Counts().SolverCommands,S.Disabled.SolverCommands);
            return true;
        }
        if(!S.Planner.Poll(Error)){T.AddError(Error);S.Planner.Cancel();return true;}
        if(S.Planner.Busy())return false;
        if(S.Stage==3)
        {
            T.TestEqual(TEXT("Initial exported horizon is twelve120Hz ticks"),S.Planner.Through(),12);
            if(!S.Planner.Frame(12,S.Prefix)){T.AddError(TEXT("Missing initial course frame"));return true;}
            if(!S.Planner.Extend(.2,Error)){T.AddError(Error);return true;}S.Stage=4;return false;
        }
        T.TestEqual(TEXT("Extension exports through twenty-four120Hz ticks"),S.Planner.Through(),24);
        T.TestTrue(TEXT("Extension retains existing prefix frame"),S.Planner.Frame(12,Value));
        T.TestEqual(TEXT("Extension does not rewrite the exact prefix"),Value,S.Prefix);
        T.TestTrue(TEXT("Extension contains the new frame"),S.Planner.Frame(24,Value));
        const auto Before=S.Planner.Counts();T.TestTrue(TEXT("No-op extension succeeds"),S.Planner.Extend(.2,Error));
        T.TestEqual(TEXT("No-op extension schedules no solver work"),S.Planner.Counts().SolverCommands,Before.SolverCommands);
        T.TestFalse(TEXT("No-op extension schedules no worker"),S.Planner.Busy());
        S.Planner.Cancel();T.TestEqual(TEXT("Completed course drops all cached frames on disable"),S.Planner.Through(),-1);
        T.TestEqual(TEXT("Completed course has no active worker"),S.Planner.Counts().Workers,0);
        S.Disabled=S.Planner.Counts();S.Stage=5;return false;
    }
};
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFootIKPlannerLifecycle,"Prophecy.FootIK.PlannerLifecycle",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFootIKPlannerLifecycle::RunTest(const FString&)
{
    using namespace ProphecyFootIKPlannerTests;
    auto State=MakeShared<FState>();State->Test=this;
    const FString File=FPaths::ProjectSavedDir()/TEXT("Diagnostics/FootIKPort20261030/walk-flat.input.json");
    if(!FFileHelper::LoadFileToString(State->Fixture,*File))
    {AddError(TEXT("Generate the independent fixtures first: node Tools/FootIK/parity-export.cjs"));return false;}
    auto Probe=State->Probe;FString Error;
    // A tiny valid header is sufficient: cancellation occurs before the source
    // result enters the VM. The cancellation callback releases this worker gate.
    if(!State->Planner.Prepare(TEXT("{\"parents\":[],\"settings\":{}}"),
        [Probe](FString&,FString& SourceError)
        {
            Probe->SourceOnGameThread.Store(IsInGameThread());Probe->Started.Store(true);
            Probe->Gate->Wait(10000);Probe->Returned.Store(true);SourceError=TEXT("Cancelled source probe");return false;
        },{},.1,Error,[Probe]{++Probe->CancelCalls;Probe->Gate->Trigger();}))
    {AddError(Error);return false;}
    ADD_LATENT_AUTOMATION_COMMAND(FCheck(State));return true;
}
#endif
