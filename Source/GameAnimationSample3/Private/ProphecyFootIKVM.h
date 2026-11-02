#pragma once
#include "CoreMinimal.h"

// One isolated native V8 heap. Serial calls only; no process, browser or network.
// Destruction releases the heap and all retained solver/NN callback state.
class FProphecyFootIKVM
{
public:
    using FNN = TFunction<bool(const FString&, FString&, FString&)>;
    FProphecyFootIKVM();
    ~FProphecyFootIKVM();
    FProphecyFootIKVM(const FProphecyFootIKVM&)=delete;
    FProphecyFootIKVM& operator=(const FProphecyFootIKVM&)=delete;
    bool Initialize(FNN Generator, FString& Error);
    bool Command(const FString& Json, FString& Result, FString& Error);
    double LastSeconds() const;
    void Cancel();
private:
    struct FImpl;
    TUniquePtr<FImpl> Impl;
};
