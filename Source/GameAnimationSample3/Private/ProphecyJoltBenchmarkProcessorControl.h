#pragma once

#include "CoreMinimal.h"

class FJsonObject;
class UObject;
namespace ProphecyJolt::CharacterProfiling { struct FFrame; }

namespace ProphecyJolt::BenchmarkProcessorControl
{
// Explicit -PhysicsBenchPClassGameThread diagnostic only. Begin is called after fixture creation,
// before the first measured timer; repeated calls perform no OS queries. Never changes workers,
// process affinity/priority, CPU-set assignments or power/QoS policy.
bool Begin(const UObject& Owner, FString& OutError);
// Idempotent. Must run on the same game thread on normal/error Finish and subsystem teardown.
// Teardown by an unrelated subsystem is a no-op; only the exact Begin owner can restore it.
bool Restore(const UObject& Owner, FString& OutError);
bool ValidateObservedFrame(const CharacterProfiling::FFrame& Frame, FString& OutError);
TSharedPtr<FJsonObject> ToJson();
}
