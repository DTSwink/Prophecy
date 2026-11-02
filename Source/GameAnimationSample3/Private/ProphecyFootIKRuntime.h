#pragma once
#include "CoreMinimal.h"
#include "ProphecyFootIKVM.h"

// Opt-in native owner. No retained state exists until Enable succeeds. The
// JSON boundary is lab Y-up metres; the public library converts world UE units.
// Current/previous source poses have the canonical26-bone order. Root windows
// contain previous/current plus8future transforms at30Hz. Step advances one or
// more120Hz ticks; caller publishes every2ticks (60authored game ticks/second).
class FProphecyFootIKRuntime
{
public:
    using FNN = FProphecyFootIKVM::FNN;
    bool Enable(const FString& InitJson, FNN Generator, FString& Result, FString& Error);
    bool EnablePrepared(TUniquePtr<FProphecyFootIKVM> Prepared,const FString& InitJson,FString& Result,FString& Error);
    TUniquePtr<FProphecyFootIKVM> ReleaseVM();
    bool Step(const FString& TickJson, FString& Result, FString& Error);
    bool Command(const FString& Json, FString& Result, FString& Error);
    void Disable();
    bool IsEnabled() const { return VM.IsValid(); }
    double LastSeconds() const;
    uint64 CommandCount() const { return Commands; }
private:
    TUniquePtr<FProphecyFootIKVM> VM;
    uint64 Commands=0;
};
