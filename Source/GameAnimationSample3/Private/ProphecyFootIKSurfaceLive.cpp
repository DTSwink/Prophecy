#include "ProphecyFootIKSurfaceLive.h"
#include "ProphecyFootIKVM.h"
#include "Async/Async.h"
#include "Containers/Queue.h"
#include "Dom/JsonObject.h"
#include "HAL/PlatformTime.h"
#include "Misc/ScopeLock.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"

namespace
{
FCriticalSection SurfaceWorkerLane;
FString SurfaceWorkerSerialize(const TSharedPtr<FJsonObject>& Object)
{FString Text;FJsonSerializer::Serialize(Object.ToSharedRef(),TJsonWriterFactory<>::Create(&Text));return Text;}
TSharedPtr<FJsonObject> SurfaceWorkerParse(const FString& Text)
{TSharedPtr<FJsonObject> Value;FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text),Value);return Value;}
struct FSurfaceLiveRequest { int32 FirstTick=0,Ticks=0;FString Json; };
struct FSurfaceLiveWork
{
    FProphecyFootIKVM VM;
    FProphecyFootIKVM::FNN NN;
    TFunction<void()> CancelNative;
    FString Init;
    bool Causal=false;
    TQueue<FSurfaceLiveRequest,EQueueMode::Spsc> Inputs;
    TQueue<FProphecyFootIKSurfaceLive::FResult,EQueueMode::Spsc> Results;
    TAtomic<bool> Cancelled{false},Ready{false},Failed{false},Initialized{false};
    TAtomic<int32> PendingTicks{0},UnconsumedTicks{0},OutstandingTicks{0},ActiveWorkers{0},CompletedTicks{0},SubmittedTicks{0};
    FCriticalSection DiagnosticMutex;
    FString Error;
    double LastSeconds=0,TotalSeconds=0;
    void Fail(const FString& Text)
    {FScopeLock Lock(&DiagnosticMutex);Error=Text;Failed.Store(true);Ready.Store(false);}
};
void SurfaceLiveDrain(const TSharedPtr<FSurfaceLiveWork,ESPMode::ThreadSafe>& Work)
{
    struct FActive
    {
        FSurfaceLiveWork& W;explicit FActive(FSurfaceLiveWork& In):W(In){++W.ActiveWorkers;}
        ~FActive(){--W.ActiveWorkers;}
    } Active(*Work);
    FScopeLock Lane(&SurfaceWorkerLane);
    if(Work->Cancelled.Load()||Work->Failed.Load())return;
    if(!Work->Initialized.Load())
    {
        FString Error,Reply;
        if(!Work->VM.Initialize([Owner=Work.Get()](const FString& Request,FString& Reply,FString& Why)
        {
            if(Owner->Cancelled.Load()){Why=TEXT("Surface owner cancelled");return false;}
            if(!Owner->Causal||!Owner->NN){Why=TEXT("External-root surface pose must not invoke NN inference");return false;}
            const bool Good=Owner->NN(Request,Reply,Why);
            if(Owner->Cancelled.Load()){Why=TEXT("Surface owner cancelled");return false;}
            return Good;
        },Error))
        {Work->Fail(Error);return;}
        if(Work->Cancelled.Load())return;
        if(!Work->VM.Command(Work->Init,Reply,Error)){if(!Work->Cancelled.Load())Work->Fail(Error);return;}
        Work->Initialized.Store(true);Work->Ready.Store(true);
    }
    FSurfaceLiveRequest Request;
    while(!Work->Cancelled.Load()&&!Work->Failed.Load()&&Work->Inputs.Dequeue(Request))
    {
        FProphecyFootIKSurfaceLive::FResult Result;Result.FirstTick=Request.FirstTick;Result.NextTick=Request.FirstTick+Request.Ticks;
        const double Start=FPlatformTime::Seconds();
        const bool Good=Work->VM.Command(Request.Json,Result.Json,Result.Error);Result.Seconds=FPlatformTime::Seconds()-Start;
        Work->PendingTicks-=Request.Ticks;
        if(Work->Cancelled.Load())break;
        if(!Good){Work->Fail(Result.Error);Work->Results.Enqueue(MoveTemp(Result));break;}
        const auto Object=SurfaceWorkerParse(Result.Json);double Next=-1;const TArray<TSharedPtr<FJsonValue>>* Frames=nullptr;
        if(!Object||!Object->TryGetNumberField(TEXT("tick"),Next)||int32(Next)!=Result.NextTick||!Object->TryGetArrayField(TEXT("frames"),Frames)||Frames->Num()!=Request.Ticks)
        {Result.Error=TEXT("Surface solver skipped or duplicated a causal tick");Work->Fail(Result.Error);Work->Results.Enqueue(MoveTemp(Result));break;}
        Work->CompletedTicks+=Request.Ticks;
        {FScopeLock Lock(&Work->DiagnosticMutex);Work->LastSeconds=Result.Seconds;Work->TotalSeconds+=Result.Seconds;}
        Work->UnconsumedTicks+=Request.Ticks;Work->Results.Enqueue(MoveTemp(Result));
    }
    if(Work->Cancelled.Load()||Work->Failed.Load())while(Work->Inputs.Dequeue(Request))Work->PendingTicks-=Request.Ticks;
}
}
struct FProphecyFootIKSurfaceLive::FImpl
{
    TSharedPtr<FSurfaceLiveWork,ESPMode::ThreadSafe> Work;
    TFuture<void> Future;
    int32 NextSubmitted=0,Limit=240;
    void Dispatch()
    {
        if(Future.IsValid()&&Future.IsReady()){Future.Get();Future=TFuture<void>();}
        if(!Work||Future.IsValid()||Work->Cancelled.Load()||Work->Failed.Load()||(Work->Initialized.Load()&&Work->PendingTicks.Load()==0))return;
        auto Capture=Work;
        // Packaged game pool stacks are128KB; the VM explicitly needs768KB
        // plus host frames. This transient worker self-cleans after its batch.
        Future=AsyncThread([Capture]{SurfaceLiveDrain(Capture);},1024*1024,TPri_Normal);
    }
    void Cancel()
    {
        if(Work){Work->Cancelled.Store(true);Work->Ready.Store(false);Work->VM.Cancel();if(Work->CancelNative)Work->CancelNative();}
        Future=TFuture<void>();Work.Reset();NextSubmitted=0;
    }
    ~FImpl(){Cancel();}
};
FProphecyFootIKSurfaceLive::FProphecyFootIKSurfaceLive():Impl(MakeUnique<FImpl>()){}
FProphecyFootIKSurfaceLive::~FProphecyFootIKSurfaceLive()=default;
bool FProphecyFootIKSurfaceLive::Initialize(const FString& Json,FString& Error,int32 MaxQueuedTicks)
{return InitializeInternal(Json,{}, {},false,Error,MaxQueuedTicks);}
bool FProphecyFootIKSurfaceLive::InitializeCausal(const FString& Json,FProphecyFootIKVM::FNN Generator,TFunction<void()> CancelNative,FString& Error,int32 MaxQueuedTicks)
{return InitializeInternal(Json,MoveTemp(Generator),MoveTemp(CancelNative),true,Error,MaxQueuedTicks);}
bool FProphecyFootIKSurfaceLive::InitializeInternal(const FString& Json,FProphecyFootIKVM::FNN Generator,TFunction<void()> CancelNative,bool Causal,FString& Error,int32 MaxQueuedTicks)
{
    check(IsInGameThread());Error.Reset();const auto Input=SurfaceWorkerParse(Json);double Current=0;
    if(!Input||(!Causal&&!Input->TryGetNumberField(TEXT("currentTick"),Current))||Current<0||Current!=FMath::FloorToDouble(Current)||MaxQueuedTicks<2||MaxQueuedTicks>1200)
    {Error=TEXT("Surface pose initialization needs an integer currentTick and bounded queue");return false;}
    if(Causal&&!Generator){Error=TEXT("Causal surface owner requires the actual native NN stream");return false;}
    if(Causal&&!Input->HasField(TEXT("initialPair"))&&!Input->HasField(TEXT("seeds"))){Error=TEXT("Causal surface owner requires actual current/history poses");return false;}
    double RequestedTick=0;if(Causal&&Input->TryGetNumberField(TEXT("currentTick"),RequestedTick)&&RequestedTick!=0){Error=TEXT("A new causal surface epoch starts at local tick0");return false;}
    Input->SetStringField(TEXT("op"),Causal?TEXT("init"):TEXT("liveSurfaceInit"));if(Causal)Input->SetBoolField(TEXT("policy"),true);
    Impl->Cancel();Impl->Work=MakeShared<FSurfaceLiveWork,ESPMode::ThreadSafe>();Impl->Work->Init=SurfaceWorkerSerialize(Input);Impl->Work->Causal=Causal;Impl->Work->NN=MoveTemp(Generator);Impl->Work->CancelNative=MoveTemp(CancelNative);Impl->NextSubmitted=int32(Current);Impl->Limit=MaxQueuedTicks;Impl->Dispatch();return true;
}
bool FProphecyFootIKSurfaceLive::Submit(int32 FirstTick,int32 Ticks,const FString& Json,FString& Error)
{
    check(IsInGameThread());Error.Reset();Impl->Dispatch();const auto Work=Impl->Work;
    if(!Work||Work->Cancelled.Load()){Error=TEXT("Surface pose solver is disabled");return false;}
    if(Work->Failed.Load()){FScopeLock Lock(&Work->DiagnosticMutex);Error=Work->Error;return false;}
    if(FirstTick!=Impl->NextSubmitted||Ticks<1||Ticks>120){Error=TEXT("Surface pose inputs must be consecutive120Hz intervals");return false;}
    if(Work->OutstandingTicks.Load()+Ticks>Impl->Limit){Error=TEXT("Surface pose worker cannot keep up: bounded queue is full; no input was submitted");return false;}
    auto Input=SurfaceWorkerParse(Json);if(!Input){Error=TEXT("Invalid surface pose step JSON");return false;}
    Input->SetStringField(TEXT("op"),Work->Causal?TEXT("tick"):TEXT("liveSurfaceStep"));Input->SetNumberField(TEXT("currentTick"),FirstTick);Input->SetNumberField(TEXT("ticks"),Ticks);
    FSurfaceLiveRequest Request;Request.FirstTick=FirstTick;Request.Ticks=Ticks;Request.Json=SurfaceWorkerSerialize(Input);
    Work->OutstandingTicks+=Ticks;Work->PendingTicks+=Ticks;Work->SubmittedTicks+=Ticks;Work->Inputs.Enqueue(MoveTemp(Request));Impl->NextSubmitted+=Ticks;Impl->Dispatch();return true;
}
bool FProphecyFootIKSurfaceLive::TakeCompleted(FResult& Out)
{check(IsInGameThread());Impl->Dispatch();if(!Impl->Work||!Impl->Work->Results.Dequeue(Out))return false;if(Out.Error.IsEmpty()){Impl->Work->UnconsumedTicks-=Out.NextTick-Out.FirstTick;Impl->Work->OutstandingTicks-=Out.NextTick-Out.FirstTick;}return true;}
FProphecyFootIKSurfaceLive::FStatus FProphecyFootIKSurfaceLive::Status()
{
    check(IsInGameThread());Impl->Dispatch();FStatus Out;const auto Work=Impl->Work;if(!Work)return Out;
    Out.Ready=Work->Ready.Load();Out.Cancelled=Work->Cancelled.Load();Out.Failed=Work->Failed.Load();Out.PendingTicks=Work->PendingTicks.Load();Out.UnconsumedTicks=Work->UnconsumedTicks.Load();Out.OutstandingTicks=Work->OutstandingTicks.Load();Out.ActiveWorkers=Work->ActiveWorkers.Load();Out.CompletedTicks=Work->CompletedTicks.Load();Out.SubmittedTicks=Work->SubmittedTicks.Load();
    FScopeLock Lock(&Work->DiagnosticMutex);Out.Error=Work->Error;Out.LastSolveSeconds=Work->LastSeconds;Out.TotalSolveSeconds=Work->TotalSeconds;return Out;
}
void FProphecyFootIKSurfaceLive::Cancel(){check(IsInGameThread());Impl->Cancel();}
