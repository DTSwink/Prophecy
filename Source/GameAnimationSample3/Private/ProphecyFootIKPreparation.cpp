#include "ProphecyFootIKPreparation.h"
#include "ProphecyFootIKNN.h"
#include "Async/Async.h"
#include "HAL/Event.h"
#include "HAL/PlatformProcess.h"
#include "Misc/IQueuedWork.h"
#include "Misc/QueuedThreadPool.h"
#include "Misc/ScopeLock.h"
#include <atomic>

namespace FootIKPreparationQueue
{
// Trivially destructible, initialized before the function-local queue. Late
// module-global owners can retire after queue teardown without touching it.
static std::atomic<bool> Closing{false};
// The tiny lifetime gate survives module-global owner destruction order. The
// actual pool/thread is destroyed; this process-lifetime lock never grows.
FCriticalSection& Gate(){static FCriticalSection* Value=new FCriticalSection;return *Value;}
struct FQueue
{
    FQueuedThreadPool* Pool=FQueuedThreadPool::Allocate();
    FQueue(){if(!Pool->Create(1,1024*1024,TPri_BelowNormal,TEXT("FootIKPrepare"))){delete Pool;Pool=nullptr;}}
    ~FQueue(){FQueuedThreadPool* Old=nullptr;{FScopeLock L(&Gate());Closing.store(true);Old=Pool;Pool=nullptr;}if(Old){Old->Destroy();delete Old;}}
};
FQueuedThreadPool* Get(){if(Closing.load())return nullptr;static FQueue Queue;return Queue.Pool;}
}
struct FProphecyFootIKPreparation::FJob
{
    FCriticalSection Mutex;
    FEvent* Done=FPlatformProcess::GetSynchEventFromPool(true);
    TSharedPtr<FProphecyFootIKNN,ESPMode::ThreadSafe> NN;
    TUniquePtr<FProphecyFootIKVM> VM;
    TUniqueFunction<void()> RetireCallback;
    FString Settings,Error;
    EProphecyFootIKNNWarmup Mode=EProphecyFootIKNNWarmup::All;
    FWork* Queued=nullptr;
    bool WithVM=false,Complete=false,Stopped=false,Retiring=false,Taken=false;
    ~FJob(){FPlatformProcess::ReturnSynchEventToPool(Done);}
};
struct FProphecyFootIKPreparation::FWork final: IQueuedWork
{
    TSharedPtr<FJob,ESPMode::ThreadSafe> Job;
    bool Dispose=false;
    explicit FWork(TSharedPtr<FJob,ESPMode::ThreadSafe> In,bool Retire=false):Job(MoveTemp(In)),Dispose(Retire){}
    static void Release(FJob& J)
    {
        TSharedPtr<FProphecyFootIKNN,ESPMode::ThreadSafe> NN;TUniquePtr<FProphecyFootIKVM> VM;TUniqueFunction<void()> Callback;
        {FScopeLock L(&J.Mutex);NN=MoveTemp(J.NN);VM=MoveTemp(J.VM);Callback=MoveTemp(J.RetireCallback);}
        // V8's callback retains NN. Destroy the heap first, outside all locks.
        VM.Reset();NN.Reset();if(Callback)Callback();
    }
    virtual void DoThreadedWork() override
    {
        if(Dispose){Release(*Job);delete this;return;}
        bool Stop=false;{FScopeLock L(&Job->Mutex);Job->Queued=nullptr;Stop=Job->Stopped;}
        FString Error;bool Good=false;
        if(!Stop)
        {
            auto NN=MakeShared<FProphecyFootIKNN,ESPMode::ThreadSafe>();
            // Prepare may replace Impl. Keep NN private until that finishes so
            // cancellation never races the retained-implementation pointer.
            Good=NN->Prepare(Job->Settings,Error);
            if(Good)
            {
                {FScopeLock L(&Job->Mutex);Stop=Job->Stopped;if(!Stop)Job->NN=NN;}
                Good=!Stop&&NN->PrewarmSessions(Error,Job->Mode);
            }
            if(Good&&Job->WithVM)
            {
                FProphecyFootIKVM* VM=nullptr;
                {FScopeLock L(&Job->Mutex);Stop=Job->Stopped;if(!Stop){Job->VM=MakeUnique<FProphecyFootIKVM>();VM=Job->VM.Get();}}
                Good=VM&&VM->Initialize([NN](const FString& In,FString& Out,FString& Failure){return NN->Generate(In,Out,Failure);},Error);
            }
        }
        bool ReleaseNow=false;
        {
            FScopeLock L(&Job->Mutex);ReleaseNow=Job->Stopped||!Good;
            Job->Error=Job->Stopped?TEXT("Foot IK preparation canceled"):MoveTemp(Error);
            if(!Good&&Job->Error.IsEmpty())Job->Error=TEXT("Foot IK preparation failed");
            // Complete only after all NN/VM accesses above. Take can now move
            // the objects to the game thread without stale history attached.
            Job->Complete=true;Job->Done->Trigger();
        }
        if(ReleaseNow)Release(*Job);delete this;
    }
    virtual void Abandon() override
    {
        {FScopeLock L(&Job->Mutex);Job->Queued=nullptr;Job->Stopped=true;Job->Complete=true;Job->Error=TEXT("Foot IK preparation stopped");Job->Done->Trigger();}
        Release(*Job);delete this;
    }
};
FProphecyFootIKPreparation::FProphecyFootIKPreparation(const FString& Settings,bool WithVM,EProphecyFootIKNNWarmup Mode):Job(MakeShared<FJob,ESPMode::ThreadSafe>())
{
    Job->Settings=Settings;Job->WithVM=WithVM;Job->Mode=Mode;
    FScopeLock QueueLock(&FootIKPreparationQueue::Gate());
    if(auto* Pool=FootIKPreparationQueue::Get()){Job->Queued=new FWork(Job);Pool->AddQueuedWork(Job->Queued);}
    else{Job->Error=TEXT("Cannot start the Foot IK preparation worker");Job->Complete=true;Job->Done->Trigger();}
}
FProphecyFootIKPreparation::~FProphecyFootIKPreparation(){Cancel();}
FProphecyFootIKPreparation::EState FProphecyFootIKPreparation::State(FString& Error) const
{
    FScopeLock L(&Job->Mutex);Error=Job->Error;
    if(Job->Stopped)return EState::Failed;
    return !Job->Complete?EState::Pending:(!Error.IsEmpty()||Job->Taken?EState::Failed:EState::Ready);
}
bool FProphecyFootIKPreparation::Take(TSharedPtr<FProphecyFootIKNN,ESPMode::ThreadSafe>& NN,TUniquePtr<FProphecyFootIKVM>& VM,FString& Error)
{
    FScopeLock L(&Job->Mutex);Error=Job->Error;
    if(!Job->Complete||!Error.IsEmpty()||Job->Stopped||Job->Taken)return false;
    NN=MoveTemp(Job->NN);VM=MoveTemp(Job->VM);Job->Taken=true;return NN.IsValid();
}
bool FProphecyFootIKPreparation::Wait(FString& Error)
{
    if(IsInGameThread()){Error=TEXT("Poll Foot IK preparation on the game thread");return false;}
    Job->Done->Wait();return State(Error)==EState::Ready;
}
void FProphecyFootIKPreparation::Cancel()
{
    FWork* Retracted=nullptr;bool Retire=false;
    {
        FScopeLock L(&Job->Mutex);if(Job->Stopped||Job->Taken)return;Job->Stopped=true;Job->Error=TEXT("Foot IK preparation canceled");Job->Done->Trigger();
        if(Job->NN)Job->NN->Cancel();if(Job->VM)Job->VM->Cancel();
        FScopeLock QueueLock(&FootIKPreparationQueue::Gate());auto* Pool=FootIKPreparationQueue::Get();
        if(Job->Queued&&Pool&&Pool->RetractQueuedWork(Job->Queued))
        {Retracted=Job->Queued;Job->Queued=nullptr;Job->Complete=true;Job->Error=TEXT("Foot IK preparation canceled");Job->Done->Trigger();}
        if(Job->Complete&&!Job->Retiring&&(Job->NN||Job->VM)){Job->Retiring=true;Retire=true;}
    }
    delete Retracted;
    if(Retire)
    {
        bool Queued=false;{FScopeLock QueueLock(&FootIKPreparationQueue::Gate());if(auto* Pool=FootIKPreparationQueue::Get()){Pool->AddQueuedWork(new FWork(Job,true),EQueuedWorkPriority::High);Queued=true;}}
        if(!Queued)FWork::Release(*Job);
    }
}
void FProphecyFootIKPreparation::Retire(TSharedPtr<FProphecyFootIKNN,ESPMode::ThreadSafe> NN,TUniquePtr<FProphecyFootIKVM> VM)
{
    if(!NN&&!VM)return;if(NN)NN->Cancel();if(VM)VM->Cancel();
    auto J=MakeShared<FJob,ESPMode::ThreadSafe>();J->NN=MoveTemp(NN);J->VM=MoveTemp(VM);J->Stopped=J->Complete=J->Retiring=true;
    {FScopeLock QueueLock(&FootIKPreparationQueue::Gate());if(auto* Pool=FootIKPreparationQueue::Get())Pool->AddQueuedWork(new FWork(J,true),EQueuedWorkPriority::High);}
}
void FProphecyFootIKPreparation::Retire(TUniqueFunction<void()> Release)
{
    if(!Release)return;
    auto J=MakeShared<FJob,ESPMode::ThreadSafe>();J->RetireCallback=MoveTemp(Release);J->Stopped=J->Complete=J->Retiring=true;
    bool Queued=false;
    {FScopeLock QueueLock(&FootIKPreparationQueue::Gate());if(auto* Pool=FootIKPreparationQueue::Get()){Pool->AddQueuedWork(new FWork(J,true),EQueuedWorkPriority::High);Queued=true;}}
    if(!Queued)
    {
        // At process teardown the shared queue is already drained. During
        // gameplay, even failure to create it must not move heap destruction
        // onto the game thread. This exceptional task is finite, never a poller.
        if(FootIKPreparationQueue::Closing.load()||!IsInGameThread())FWork::Release(*J);
        else (void)AsyncThread([J]{FWork::Release(*J);},1024*1024,TPri_BelowNormal);
    }
}
