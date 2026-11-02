#pragma once
#include "CoreMinimal.h"

// Owns one isolated, non-I/O JavaScript heap. Invoke serially from one thread.
// Executes the packaged *live* lab algorithms; there are no baked controller frames.
class FProphecyBodyflipVM
{
public:
    using FNN = TFunction<bool(const FString&, FString&, FString&)>;
    struct FStatistics{uint64 HeapBytes=0,PeakHeapBytes=0;uint32 NNCalls=0;double NNSeconds=0,LongestNNSeconds=0;};
    FProphecyBodyflipVM();
#if WITH_DEV_AUTOMATION_TESTS
    // Per-instance smaller budget for bounded failure tests; no gameplay eval
    // or process-wide runtime setting is exposed.
    explicit FProphecyBodyflipVM(uint64 TestSoftHeapBytes);
#endif
    ~FProphecyBodyflipVM();
    FProphecyBodyflipVM(const FProphecyBodyflipVM&)=delete;
    FProphecyBodyflipVM& operator=(const FProphecyBodyflipVM&)=delete;
    bool Initialize(FNN Generator, FString& Error);
    // Synchronous on the owning worker. The caller cancels from another thread;
    // the planner enforces its whole-job deadline, not a per-command timeout.
    bool Command(const FString& Json, FString& Result, FString& Error);
    double LastSeconds() const;
    FStatistics Statistics() const;
    bool IsCancelled() const;
    void Cancel();
private:
    struct FImpl;
    TUniquePtr<FImpl> Impl;
};
