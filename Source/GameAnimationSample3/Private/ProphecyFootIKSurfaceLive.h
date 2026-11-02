#pragma once
#include "CoreMinimal.h"
#include "ProphecyFootIKVM.h"

// A serialized, bounded causal surface worker. The full mode owns root, feet,
// and policy together; the external-root mode exists for decomposition tests.
class FProphecyFootIKSurfaceLive
{
public:
    struct FResult
    {
        int32 FirstTick=0,NextTick=0;
        FString Json,Error; // liveSurfaceStep result: frames plus actual supports
        double Seconds=0;
    };
    struct FStatus
    {
        bool Ready=false,Cancelled=false,Failed=false;
        int32 PendingTicks=0,UnconsumedTicks=0,OutstandingTicks=0,ActiveWorkers=0,CompletedTicks=0,SubmittedTicks=0;
        double LastSolveSeconds=0,TotalSolveSeconds=0;
        FString Error;
    };
    FProphecyFootIKSurfaceLive();
    ~FProphecyFootIKSurfaceLive();
    FProphecyFootIKSurfaceLive(const FProphecyFootIKSurfaceLive&)=delete;
    FProphecyFootIKSurfaceLive& operator=(const FProphecyFootIKSurfaceLive&)=delete;

    // GT: validates and copies initialization; VM creation is worker-only.
    bool Initialize(const FString& InitJson,FString& Error,int32 MaxQueuedTicks=240);
    // Faithful surface mode: one canonical root/feet/NN recurrence. Seeds are
    // actual current/history; Generator retains the game's matching NN stream.
    // CancelNative must be thread-safe and interrupt native inference promptly.
    bool InitializeCausal(const FString& InitJson,FProphecyFootIKVM::FNN Generator,
        TFunction<void()> CancelNative,FString& Error,int32 MaxQueuedTicks=240);
    // GT: every120Hz tick must be submitted once in order. False means explicit
    // backpressure/error; no submitted interval is silently replaced or dropped.
    bool Submit(int32 FirstTick,int32 Ticks,const FString& StepJson,FString& Error);
    // GT: nonblocking ordered completion. Reading does not start new simulation.
    bool TakeCompleted(FResult& Out);
    FStatus Status();
    // GT: interrupts script, drops queued work/results, never waits for a solve.
    void Cancel();
private:
    bool InitializeInternal(const FString& InitJson,FProphecyFootIKVM::FNN Generator,
        TFunction<void()> CancelNative,bool Causal,FString& Error,int32 MaxQueuedTicks);
    struct FImpl;
    TUniquePtr<FImpl> Impl;
};
