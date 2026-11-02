#include "ProphecyBodyflipPlanner.h"
#include "ProphecyBodyflipVM.h"
#include "ProphecyBodyflipNN.h"
#include "Async/Async.h"
#include "HAL/PlatformTime.h"
#include "Misc/ScopeLock.h"
#include "Dom/JsonObject.h"
#include "Serialization/JsonSerializer.h"

namespace
{
// One planner computes at a time across all agents. No engine/game-thread wait.
FCriticalSection BodyflipPlannerLane;
// Queueing does not spend a solver's execution budget. The worker publishes
// its start only after it owns the serialized planning lane.
struct FBodyflipJobClock
{
    TAtomic<double> Started{0};
    void Begin(double Now){Started.Store(Now);}
    bool Expired(double Now) const{const double Start=Started.Load();return Start>0&&Now-Start>120;}
};
struct FWork : TSharedFromThis<FWork,ESPMode::ThreadSafe>
{
    FProphecyBodyflipVM VM;
    bool Initialized=false;
    int32 Through=-1;
    TAtomic<bool> Cancelled{false};
};
struct FResult
{
    TMap<int32,FString> Frames;
    FString Error;
    double Seconds=0;
    bool Reset=false;
};
}
struct FProphecyBodyflipPlanner::FImpl
{
    TSharedPtr<FWork,ESPMode::ThreadSafe> Work=MakeShared<FWork,ESPMode::ThreadSafe>();
    TFuture<FResult> Future;
    TMap<int32,FString> Frames;
    TSharedPtr<FBodyflipJobClock,ESPMode::ThreadSafe> Clock;
    double Seconds=0;
    bool WorkFailed=false;
    ~FImpl(){auto Retired=MoveTemp(Work);Retired->Cancelled.Store(true);Retired->VM.Cancel();Async(EAsyncExecution::ThreadPool,[Retired=MoveTemp(Retired)]() mutable{FScopeLock Lock(&BodyflipPlannerLane);Retired.Reset();});}
};
FProphecyBodyflipPlanner::FProphecyBodyflipPlanner():Impl(MakeUnique<FImpl>()){}
FProphecyBodyflipPlanner::~FProphecyBodyflipPlanner()=default;
bool FProphecyBodyflipPlanner::Busy() const{return Impl->Future.IsValid();}
bool FProphecyBodyflipPlanner::Frame(int32 Index,FString& Out) const{if(const auto* S=Impl->Frames.Find(Index)){Out=*S;return true;}return false;}
double FProphecyBodyflipPlanner::LastSeconds() const{return Impl->Seconds;}
bool FProphecyBodyflipPlanner::Prepare(const FString& Settings,const FString& Run,double Horizon,bool Reset,FString& Error,const FString& RigProfile)
{
    if(Busy()){Error=TEXT("Bodyflip is still preparing the previous edit");return false;}
    if(!FMath::IsFinite(Horizon)||Horizon<0||Horizon>600){Error=TEXT("Bodyflip horizon must be within0..600seconds");return false;}
    TSharedPtr<FWork,ESPMode::ThreadSafe> Retired;
    if(Impl->WorkFailed){Retired=MoveTemp(Impl->Work);Impl->Work=MakeShared<FWork,ESPMode::ThreadSafe>();Impl->WorkFailed=false;Reset=true;}
    auto Work=Impl->Work;const int32 Last=FMath::CeilToInt(Horizon*60);auto Clock=MakeShared<FBodyflipJobClock,ESPMode::ThreadSafe>();Impl->Clock=Clock;
    Impl->Future=Async(EAsyncExecution::ThreadPool,[Work,Clock,Retired=MoveTemp(Retired),Settings,Run,RigProfile,Last,Reset]() mutable{
        FResult Result;Result.Reset=Reset;FScopeLock Lock(&BodyflipPlannerLane);const double Begin=FPlatformTime::Seconds();Clock->Begin(Begin);
        // An interrupted VM cannot execute again. Retire its potentially large
        // heap on this worker before constructing the replacement, not on GT.
        Retired.Reset();
        if(Work->Cancelled.Load()){Result.Error=TEXT("Bodyflip preparation cancelled");return Result;}
        if(!Work->Initialized){FWork* Owner=Work.Get();Work->Initialized=Work->VM.Initialize([Owner](const FString& Request,FString& Out,FString& E){return ProphecyBodyflip::GenerateNN(nullptr,Request,Out,E,[Owner]{return Owner->Cancelled.Load()||Owner->VM.IsCancelled();});},Result.Error);if(!Work->Initialized)return Result;}
        FString Out;
        if(Reset){const FString Command=TEXT("{\"op\":\"start\",\"settings\":")+Settings+(Run.IsEmpty()?TEXT(""):TEXT(",\"run\":")+Run)+(RigProfile.IsEmpty()?TEXT(""):TEXT(",\"rigProfile\":")+RigProfile)+TEXT(",\"horizon\":0.016666666666666666}");
            if(!Work->VM.Command(Command,Out,Result.Error))return Result;
            if(!RigProfile.IsEmpty()){TSharedPtr<FJsonObject> Description;FString Schema;if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Out),Description)||!Description||!Description->TryGetStringField(TEXT("rigSchema"),Schema)||Schema!=TEXT("bodyflip-native-rig-v1")){Result.Error=TEXT("Packaged Bodyflip solver did not install the native rig profile; regenerate its runtime package");return Result;}}
            Work->Through=-1;}
        if(!Work->VM.Command(FString::Printf(TEXT("{\"op\":\"prepare\",\"time\":%.17g}"),Last/60.),Out,Result.Error))return Result;
        for(int32 I=Work->Through+1;I<=Last;I++){if(Work->Cancelled.Load()){Result.Error=TEXT("Bodyflip preparation cancelled");break;}
            if(!Work->VM.Command(FString::Printf(TEXT("{\"op\":\"sample\",\"time\":%.17g}"),I/60.),Out,Result.Error))break;
            Result.Frames.Add(I,Out);Work->Through=I;
        }
        Result.Seconds=FPlatformTime::Seconds()-Begin;return Result;
    });return true;
}
bool FProphecyBodyflipPlanner::Poll(FString& Error)
{
    if(!Busy())return true;
    if(!Impl->Future.IsReady()){if(Impl->Clock&&Impl->Clock->Expired(FPlatformTime::Seconds()))Impl->Work->VM.Cancel();return true;}
    auto Result=Impl->Future.Get();Impl->Future=TFuture<FResult>();Impl->Seconds=Result.Seconds;
    if(!Result.Error.IsEmpty()){Impl->WorkFailed=true;Error=Result.Error;return false;}
    if(Result.Reset)Impl->Frames.Reset();for(auto& Pair:Result.Frames)Impl->Frames.Add(Pair.Key,MoveTemp(Pair.Value));return true;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyBodyflipQueueBudgetTest,"Prophecy.Bodyflip.Planner.QueueDoesNotSpendExecutionBudget",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyBodyflipQueueBudgetTest::RunTest(const FString&)
{
    FBodyflipJobClock Queued;
    TestFalse(TEXT("A queued job has not started even after a long wait"),Queued.Expired(10000));
    Queued.Begin(10000);
    TestFalse(TEXT("Worker retains its complete execution budget"),Queued.Expired(10119.999));
    TestTrue(TEXT("Active work still expires at the existing120second limit"),Queued.Expired(10120.001));
    FProphecyBodyflipVM Cancelled;Cancelled.Cancel();FString Error;
    TestFalse(TEXT("Cancellation before context initialization cannot revive a queued VM"),Cancelled.Initialize({},Error));
    TestTrue(TEXT("Cancelled queued VM remains cancelled"),Cancelled.IsCancelled());
    TestTrue(TEXT("Queued cancellation reports why it did not start"),Error.Contains(TEXT("cancelled")));
    return !HasAnyErrors();
}
#endif
