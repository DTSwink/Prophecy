#pragma once
#include "CoreMinimal.h"
#include "ProphecyFootIKVM.h"

// Exact lab-course planner. Every solver/NN operation runs on a private serial
// worker lane; the game thread only polls ready results and publishes frames.
// This is distinct from the explicitly experimental causal live adapter.
class FProphecyFootIKPlanner
{
public:
    using FNN=FProphecyFootIKVM::FNN;
    using FSource=TFunction<bool(FString& OutSourceJson,FString& Error)>;
    using FCancel=TFunction<void()>;
    struct FCounts
    {
        int64 SourceCalls=0,NNCalls=0,SolverCommands=0;
        int32 Workers=0;
        bool Cancelled=false;
    };
    FProphecyFootIKPlanner();
    ~FProphecyFootIKPlanner();
    FProphecyFootIKPlanner(const FProphecyFootIKPlanner&)=delete;
    FProphecyFootIKPlanner& operator=(const FProphecyFootIKPlanner&)=delete;

    // InitJson is a complete {op:"prepare",source,parents,settings,coupled?,...}
    // command. The planner replaces endTime with Horizon. Warm any native NNE
    // model on the game thread first; Generator must not access live UObjects.
    bool Prepare(const FString& InitJson,FNN Generator,double Horizon,FString& Error);
    // Optional worker initializer supplies the source when InitJson omits it.
    // Capture the native stream by shared ownership in both callbacks.
    bool Prepare(const FString& InitJson,FSource Source,FNN Generator,double Horizon,FString& Error,FCancel CancelNative=FCancel());
    bool Extend(double Horizon,FString& Error);
    bool Poll(FString& Error);
    bool Busy() const;
    bool Frame(int32 Index120Hz,FString& Out) const;
    int32 Through() const;
    double LastSeconds() const;
    FString Diagnostics() const;
    FCounts Counts() const;
    void Cancel();
private:
    struct FImpl;
    TUniquePtr<FImpl> Impl;
};
