#pragma once
#include "Units/RigUnit.h"
#include "ProphecyReachBenchmark.generated.h"

// Editor-only measurement unit. It runs the exact copied double-reach kernel;
// never used by gameplay assets and never cooked into the game module.
USTRUCT(meta=(DisplayName="Prophecy Double Reach Benchmark",Category="Prophecy|Benchmark"))
struct FRigUnit_ProphecyDoubleReachBenchmark : public FRigUnitMutable
{
    GENERATED_BODY()
    RIGVM_METHOD()
    virtual void Execute() override;
    UPROPERTY(meta=(Input)) bool Solve=true;
    UPROPERTY(Transient) TArray<int32> CachedIndices;
};
