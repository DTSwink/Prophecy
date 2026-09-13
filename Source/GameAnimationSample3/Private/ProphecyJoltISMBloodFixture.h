#pragma once

#include "CoreMinimal.h"

class UWorld;
class FJsonObject;

namespace ProphecyJolt::ISMBloodFixture
{
// Opt-in real-RHI fixture. Placement must be rigid/unit-scale in a clear area.
// Invokes the existing BP callback on an unfinished deferred actor, validates two promotions,
// preserves an untouched third instance, then destroys all objects made by this fixture.
bool ValidatePromotion(UWorld& World, const FTransform& Placement,
    TSharedPtr<FJsonObject>& OutReport, FString& OutError);
}
