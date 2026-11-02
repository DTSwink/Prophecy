#pragma once
#include "CoreMinimal.h"
#include "ProphecyFootIKVM.h"
#include "ProphecyFootIKNN.h"

// One private, sleeping 1MB worker serializes cold graph and V8 preparation.
// No pose, world or UObject is captured. The caller supplies actual history
// only after Take succeeds. Cancel retracts queued work and retires ready
// heaps/sessions on the same worker; it never waits on the game thread.
class FProphecyFootIKPreparation
{
public:
    enum class EState : uint8 { Pending, Ready, Failed };
    FProphecyFootIKPreparation(const FString& SettingsJson,bool WithVM,EProphecyFootIKNNWarmup Mode=EProphecyFootIKNNWarmup::All);
    ~FProphecyFootIKPreparation();
    EState State(FString& Error) const;
    bool Take(TSharedPtr<FProphecyFootIKNN,ESPMode::ThreadSafe>& NN,
        TUniquePtr<FProphecyFootIKVM>& VM,FString& Error);
    // Off-thread diagnostic/forecast callers may wait. Gameplay polls State.
    bool Wait(FString& Error);
    void Cancel();
    static void Retire(TSharedPtr<FProphecyFootIKNN,ESPMode::ThreadSafe> NN,
        TUniquePtr<FProphecyFootIKVM> VM);
    // Moves the final owner of solver/forecast resources onto the same serial
    // release queue, including completed workers with no running task left.
    static void Retire(TUniqueFunction<void()> Release);
private:
    struct FJob;
    struct FWork;
    TSharedPtr<FJob,ESPMode::ThreadSafe> Job;
};
