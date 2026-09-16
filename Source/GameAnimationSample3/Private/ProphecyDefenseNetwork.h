#pragma once
#include "CoreMinimal.h"

// Shared, lazy defense-model storage. Callers own their reusable input/output
// buffers and batch only active defenders; no actor, Tick or registration here.
class FProphecyDefenseNetwork
{
public:
    FProphecyDefenseNetwork();
    ~FProphecyDefenseNetwork();
    bool Initialize(const FString& Filename, int32 InputWidth, int32 OutputWidth, FString& Error);
    bool SetBatch(int32 Count);
    bool Run(TConstArrayView<float> Input, TArrayView<float> Output);
private:
    struct FState;
    TUniquePtr<FState> State;
};
