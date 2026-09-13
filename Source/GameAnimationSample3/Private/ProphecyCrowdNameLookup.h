#pragma once

#include "CoreMinimal.h"

namespace ProphecyCrowd
{
// Layout indices only; values/handles/settings remain live at the callsite. Exact comparisons avoid
// hash collisions and retain IndexOfByKey's first duplicate-name behavior and INDEX_NONE failures.
class FNameIndexLookup
{
public:
    bool Update(TConstArrayView<FName> Source, TConstArrayView<FName> Requested)
    {
        if (bInitialized && Same(SourceNames, Source) && Same(RequestedNames, Requested)) return false;
        SourceNames.Reset(Source.Num()); SourceNames.Append(Source.GetData(), Source.Num());
        RequestedNames.Reset(Requested.Num()); RequestedNames.Append(Requested.GetData(), Requested.Num());
        Indices.SetNumUninitialized(Requested.Num());
        for (int32 Index = 0; Index < Requested.Num(); ++Index)
            Indices[Index] = SourceNames.IndexOfByKey(Requested[Index]);
        bInitialized = true;
        return true;
    }
    const TArray<int32>& GetIndices() const { return Indices; }

private:
    static bool Same(TConstArrayView<FName> A, TConstArrayView<FName> B)
    {
        if (A.Num() != B.Num()) return false;
        for (int32 Index = 0; Index < A.Num(); ++Index)
            if (A[Index] != B[Index]) return false;
        return true;
    }
    TArray<FName> SourceNames, RequestedNames;
    TArray<int32> Indices;
    bool bInitialized = false;
};

// FName already stores a numeric suffix separately. This is exactly the old formatted name,
// including index zero, without constructing an FString for every disabled ghost on every frame.
inline FName KinematicDebugMeshName(int32 AgentIndex)
{
    check(AgentIndex >= 0 && AgentIndex < MAX_int32);
    static const FName Base(TEXT("KinematicDebugMesh"));
    return FName(Base, NAME_EXTERNAL_TO_INTERNAL(AgentIndex));
}
}
