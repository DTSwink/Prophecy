#pragma once

#include "CoreMinimal.h"

class AActor;
class FJsonObject;
class UObject;
class UWorld;

namespace ProphecyJolt::BenchmarkChaosPause
{
// Explicit -PhysicsBenchPauseChaos diagnostic. Only the NNJoltCrowd call site may acquire it.
// It leaves the world and its normal Start/End physics ticks enabled. Begin only arms;
// two ordinary measured positive-delta frames replace the dynamic handoff pull buffer
// before ValidateFrame applies pause. Every frame remains in the benchmark samples.
bool IsRequested();
bool Begin(const UObject& Owner, UWorld& World,
    TConstArrayView<TObjectPtr<AActor>> KnownActors, FString& OutError);
// Call after EndPhysics, outside the measured world interval.
bool ValidateFrame(const UObject& Owner, FJsonObject& FrameRow, FString& OutError);
// Exact owner/lifetime only; unrelated subsystem teardown is a no-op.
bool Restore(const UObject& Owner, FString& OutError);
TSharedPtr<FJsonObject> ToJson();
}
