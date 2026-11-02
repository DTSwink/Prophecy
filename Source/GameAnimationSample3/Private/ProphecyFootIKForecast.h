#pragma once
#include "CoreMinimal.h"
#include "ProphecyFootIKLive.h"
#include "ProphecyFootIKNN.h"

struct FProphecyFootIKForecastInput
{
    int32 CurrentTick=4;
    ProphecyFootIKLive::FSourceSample Previous,Current;
    // Previous/current plus eight controller-authored future roots at30Hz.
    TArray<FTransform> RootWorldWindow;
    // Optional full46-row navigation projection computed on GT. First10 are
    // exactly the supplied actual/controller roots. The worker never queries
    // UWorld; these heights are for terrain planning, not NN vertical motion.
    TArray<FTransform> NavRootWindow;
    FTransform CourseWorld=FTransform::Identity;
    FString Gait=TEXT("walk");
};

// Private speculative recurrence, reset from the actual game pair each job.
// It never initializes a canned gait or modifies the manager's policy history.
class FProphecyFootIKForecast
{
public:
    struct FTiming
    {
        FProphecyFootIKNN::FGenerateTiming NN;
        double RequestSeconds=0,DecodeSeconds=0,PostprocessSeconds=0,SerializeSeconds=0;
    };
    FProphecyFootIKForecast();
    ~FProphecyFootIKForecast();
    // Validate the selected contract; cold bytes/sessions load on one worker.
    // Ready is polled without blocking; no gait is generated during preparation.
    bool Prepare(const FString& GameRuntimeContractPath,FString& Error);
    bool Ready(FString& Error);
    bool Predict(const FProphecyFootIKForecastInput& Input,FString& SourceJson,FString& Error,FTiming* Timing=nullptr,const TFunction<bool()>& Superseded={});
    void Cancel();
    // Cheap game-thread helper also supplies terrain capture's prospective root
    // bounds. Supplied rows stay exact; only the unknown tail is extrapolated.
    static bool ExtendRoots(const FProphecyFootIKForecastInput& Input,TArray<FTransform>& WorldRoots,FString& Error);
    static bool BuildRequest(const FProphecyFootIKForecastInput& Input,FString& RequestJson,FString& Error);
private:
    struct FImpl;
    TUniquePtr<FImpl> Impl;
};
