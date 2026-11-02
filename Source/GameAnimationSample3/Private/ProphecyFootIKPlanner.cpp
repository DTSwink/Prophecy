#include "ProphecyFootIKPlanner.h"
#include "ProphecyFootIKPreparation.h"
#include "Async/Async.h"
#include "Dom/JsonObject.h"
#include "HAL/PlatformTime.h"
#include "Misc/ScopeLock.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace
{
// Keep laptop work bounded even when several agents request a course together.
// Waiting happens only inside workers. No game-thread wait or completion task.
FCriticalSection FootIKPlannerLane;
FString Serialize(const TSharedPtr<FJsonObject>& Value)
{FString Text;FJsonSerializer::Serialize(Value.ToSharedRef(),TJsonWriterFactory<>::Create(&Text));return Text;}
struct FCounters
{
    TAtomic<int64> SourceCalls{0},NNCalls{0},SolverCommands{0};
    TAtomic<int32> Workers{0};
    TAtomic<bool> Cancelled{false};
};
struct FWork
{
    FProphecyFootIKVM VM;
    FProphecyFootIKPlanner::FNN NN;
    FProphecyFootIKPlanner::FSource Source;
    FProphecyFootIKPlanner::FCancel CancelNative;
    FString Init;
    bool Initialized=false,Prepared=false;
    int32 Through=-1;
    TAtomic<bool> Cancelled{false};
    TSharedPtr<FCounters,ESPMode::ThreadSafe> Counters;
    bool Command(const FString& Input,FString& Output,FString& Error)
    {
        if(Cancelled.Load())return false;
        ++Counters->SolverCommands;return VM.Command(Input,Output,Error);
    }
};
struct FResult
{
    TMap<int32,FString> Frames;
    FString Error,Diagnostics;
    double Seconds=0;
    int32 Through=-1;
};
FResult Solve(const TSharedPtr<FWork,ESPMode::ThreadSafe>& Work,int32 Last)
{
    FResult Result;
    if(Work->Cancelled.Load())return Result;
    struct FRunning
    {
        FCounters& Value;
        explicit FRunning(FCounters& In):Value(In){++Value.Workers;}
        ~FRunning(){--Value.Workers;}
    } Running(*Work->Counters);
    FScopeLock Lane(&FootIKPlannerLane);
    if(Work->Cancelled.Load())return Result;
    const double Started=FPlatformTime::Seconds();
    if(!Work->Initialized)
    {
        // The running worker already retains Work. A raw callback back-pointer
        // avoids Work -> VM -> callback -> Work retaining the heap forever.
        Work->Initialized=Work->VM.Initialize([Owner=Work.Get()](const FString& Request,FString& Out,FString& Error)
        {
            if(Owner->Cancelled.Load()){Error=TEXT("Foot IK preparation cancelled");return false;}
            if(!Owner->NN){Error=TEXT("The planned Foot IK course requires its native NN stream");return false;}
            ++Owner->Counters->NNCalls;
            return Owner->NN(Request,Out,Error);
        },Result.Error);
        if(!Work->Initialized)return Result;
    }
    if(Work->Cancelled.Load())return Result;
    FString Out;
    if(!Work->Prepared)
    {
        TSharedPtr<FJsonObject> Input;
        if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Work->Init),Input)||!Input)
        {Result.Error=TEXT("Invalid Foot IK course JSON");return Result;}
        if(!Input->HasField(TEXT("source")))
        {
            FString SourceJson;TSharedPtr<FJsonObject> Source;
            if(Work->Source)++Work->Counters->SourceCalls;
            if(!Work->Source||!Work->Source(SourceJson,Result.Error))
            {if(Result.Error.IsEmpty())Result.Error=TEXT("Foot IK source initialization failed");return Result;}
            if(Work->Cancelled.Load())return Result;
            if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(SourceJson),Source)||!Source)
            {Result.Error=TEXT("Native Foot IK NN supplied an invalid source");return Result;}
            Input->SetObjectField(TEXT("source"),Source);
        }
        Input->SetStringField(TEXT("op"),TEXT("prepare"));Input->SetNumberField(TEXT("endTime"),Last/120.);
        if(!Work->Command(Serialize(Input),Out,Result.Error))return Result;
        Work->Prepared=true;
    }
    else if(!Work->Command(FString::Printf(TEXT("{\"op\":\"extend\",\"endTime\":%.17g}"),Last/120.),Out,Result.Error))return Result;
    if(Work->Cancelled.Load())return Result;
    if(!Work->Command(TEXT("{\"op\":\"status\"}"),Result.Diagnostics,Result.Error))return Result;
    // Small batches bound marshaling scratch memory and offer cancellation
    // boundaries. The result cache stores exact120Hz frames, not a resample.
    for(int32 Start=Work->Through+1;Start<=Last;Start+=16)
    {
        if(Work->Cancelled.Load())return Result;
        const int32 Count=FMath::Min(16,Last-Start+1);
        if(!Work->Command(FString::Printf(TEXT("{\"op\":\"frames\",\"start\":%d,\"count\":%d}"),Start,Count),Out,Result.Error))return Result;
        TArray<TSharedPtr<FJsonValue>> Frames;
        if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Out),Frames)||Frames.Num()!=Count)
        {Result.Error=TEXT("Foot IK prepared course is shorter than the requested horizon");return Result;}
        for(int32 I=0;I<Count;++I)
        {
            const TSharedPtr<FJsonObject> Frame=Frames[I]->AsObject();
            if(!Frame){Result.Error=TEXT("Invalid Foot IK prepared frame");return Result;}
            Result.Frames.Add(Start+I,Serialize(Frame));
        }
    }
    Work->Through=Last;Result.Through=Last;Result.Seconds=FPlatformTime::Seconds()-Started;return Result;
}
}

struct FProphecyFootIKPlanner::FImpl
{
    TSharedPtr<FWork,ESPMode::ThreadSafe> Work;
    TSharedPtr<FCounters,ESPMode::ThreadSafe> Counters;
    TFuture<FResult> Future;
    TMap<int32,FString> Frames;
    FString Diagnostics;
    double Seconds=0;
    int32 Through=-1;
    ~FImpl(){Cancel();}
    void Cancel()
    {
        if(Work)
        {
            if(!Work->Cancelled.Load())
            {
                Work->Cancelled.Store(true);
                Work->Counters->Cancelled.Store(true);
                if(Work->CancelNative)Work->CancelNative();
            }
            Work->VM.Cancel();
        }
        // Completed/idle work has no running worker left to release its V8
        // heap. Transfer that final reference explicitly; an in-flight task
        // still retains its own reference until cancellation reaches it.
        Future=TFuture<FResult>();
        if(Work)FProphecyFootIKPreparation::Retire([Retired=MoveTemp(Work)]() mutable {Retired.Reset();});
        Frames.Reset();Diagnostics.Reset();Through=-1;Seconds=0;
    }
};
FProphecyFootIKPlanner::FProphecyFootIKPlanner():Impl(MakeUnique<FImpl>()){}
FProphecyFootIKPlanner::~FProphecyFootIKPlanner()=default;
bool FProphecyFootIKPlanner::Prepare(const FString& InitJson,FNN Generator,double Horizon,FString& Error)
{return Prepare(InitJson,FSource(),MoveTemp(Generator),Horizon,Error);}
bool FProphecyFootIKPlanner::Prepare(const FString& InitJson,FSource Source,FNN Generator,double Horizon,FString& Error,FCancel CancelNative)
{
    if(!FMath::IsFinite(Horizon)||Horizon<0||Horizon>600){Error=TEXT("Foot IK course horizon must be0..600seconds");return false;}
    TSharedPtr<FJsonObject> Input;
    if(!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(InitJson),Input)||!Input||(!Input->HasField(TEXT("source"))&&!Source)||!Input->HasField(TEXT("parents")))
    {Error=TEXT("Foot IK planned mode requires a real NN source and rig parents");return false;}
    // Replacing a course cancels obsolete work immediately. Its isolated state
    // can never publish into the new owner's cache.
    Impl->Cancel();auto Work=MakeShared<FWork,ESPMode::ThreadSafe>();Work->Init=InitJson;Work->NN=MoveTemp(Generator);Work->Source=MoveTemp(Source);Work->CancelNative=MoveTemp(CancelNative);Work->Counters=MakeShared<FCounters,ESPMode::ThreadSafe>();Impl->Counters=Work->Counters;Impl->Work=Work;
    const int32 Last=FMath::CeilToInt(Horizon*120-1.e-8);
    // Packaged UE's global pool has only128KB stacks. V8 needs its explicitly
    // bounded768KB script stack plus native frames; this worker exits on return.
    Impl->Future=AsyncThread([Work,Last]{return Solve(Work,Last);},1024*1024,TPri_Normal);return true;
}
bool FProphecyFootIKPlanner::Extend(double Horizon,FString& Error)
{
    if(!Impl->Work){Error=TEXT("Foot IK has no planned course");return false;}
    if(Busy()){Error=TEXT("Foot IK course is still preparing");return false;}
    if(!FMath::IsFinite(Horizon)||Horizon<0||Horizon>600){Error=TEXT("Foot IK course horizon must be0..600seconds");return false;}
    const int32 Last=FMath::CeilToInt(Horizon*120-1.e-8);if(Last<=Impl->Through)return true;
    auto Work=Impl->Work;Impl->Future=AsyncThread([Work,Last]{return Solve(Work,Last);},1024*1024,TPri_Normal);return true;
}
bool FProphecyFootIKPlanner::Poll(FString& Error)
{
    if(!Busy()||!Impl->Future.IsReady())return true;
    FResult Result=Impl->Future.Get();Impl->Future=TFuture<FResult>();Impl->Seconds=Result.Seconds;
    if(!Result.Error.IsEmpty()){Error=Result.Error;return false;}
    Impl->Diagnostics=MoveTemp(Result.Diagnostics);Impl->Through=Result.Through;
    for(auto& Entry:Result.Frames)Impl->Frames.Add(Entry.Key,MoveTemp(Entry.Value));return true;
}
bool FProphecyFootIKPlanner::Busy() const{return Impl->Future.IsValid();}
bool FProphecyFootIKPlanner::Frame(int32 Index120Hz,FString& Out) const
{if(const FString* Value=Impl->Frames.Find(Index120Hz)){Out=*Value;return true;}return false;}
int32 FProphecyFootIKPlanner::Through() const{return Impl->Through;}
double FProphecyFootIKPlanner::LastSeconds() const{return Impl->Seconds;}
FString FProphecyFootIKPlanner::Diagnostics() const{return Impl->Diagnostics;}
FProphecyFootIKPlanner::FCounts FProphecyFootIKPlanner::Counts() const
{
    FCounts Result;if(!Impl->Counters)return Result;const auto& C=*Impl->Counters;
    Result.SourceCalls=C.SourceCalls.Load();Result.NNCalls=C.NNCalls.Load();Result.SolverCommands=C.SolverCommands.Load();Result.Workers=C.Workers.Load();Result.Cancelled=C.Cancelled.Load();return Result;
}
void FProphecyFootIKPlanner::Cancel(){Impl->Cancel();}
