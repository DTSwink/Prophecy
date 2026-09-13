#pragma once

#include "CoreMinimal.h"
class FJsonObject;
class UObject;
class UWorld;

namespace ProphecyJolt::BenchmarkQueryPadding
{
// Explicit benchmark-only application, including Shipping where ExecCmds is unavailable.
bool Begin(const UObject& Owner, UWorld& World, FString& OutError);
bool Restore(const UObject& Owner, FString& OutError);
TSharedPtr<FJsonObject> ToJson();
}
