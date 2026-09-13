#pragma once

#include "CoreMinimal.h"

// History is authored input, never the simulated body pose. Repeated publications
// before a world step replace its endpoint without advancing its start time.
struct FProphecyJoltAuthoredTargetHistory
{
    TArray<FTransform> Endpoint;
    TArray<FTransform> StepStart;
    uint64 PublishedAtCompletedStep = MAX_uint64;

    const FTransform* GetStart(int32 BodyIndex, uint64 CompletedSteps) const
    {
        const TArray<FTransform>& Source = PublishedAtCompletedStep == CompletedSteps ? StepStart : Endpoint;
        return Source.IsValidIndex(BodyIndex) ? &Source[BodyIndex] : nullptr;
    }

    // Only call after successful native publication. A rejected packet cannot
    // change the next accepted trajectory. A new character binding starts empty.
    void Commit(TConstArrayView<FTransform> Current, uint64 CompletedSteps)
    {
        if (PublishedAtCompletedStep != CompletedSteps)
        {
            StepStart = Endpoint;
            if (StepStart.Num() != Current.Num())
            {
                StepStart.Reset(Current.Num());
                StepStart.Append(Current.GetData(), Current.Num());
            }
        }
        Endpoint.Reset(Current.Num());
        Endpoint.Append(Current.GetData(), Current.Num());
        PublishedAtCompletedStep = CompletedSteps;
    }
};
