#pragma once

#include "CoreMinimal.h"

class FJsonObject;

namespace ProphecyGameModuleSimd
{
// Benchmark-only startup/reporting, outside its measured interval. These do
// not guard module loading: the separate baseline CPU probe runs before launch.
bool ValidateRequestedProfile(FString& OutError);
TSharedPtr<FJsonObject> Report();
}
