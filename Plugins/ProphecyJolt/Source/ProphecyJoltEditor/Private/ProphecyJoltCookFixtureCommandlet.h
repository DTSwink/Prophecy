#pragma once

#include "Commandlets/Commandlet.h"
#include "ProphecyJoltCookFixtureCommandlet.generated.h"

/** Saves only the smoke host's fixed compound fixture, after validating it. */
UCLASS()
class UProphecyJoltCookFixtureCommandlet : public UCommandlet
{
	GENERATED_BODY()

public:
	UProphecyJoltCookFixtureCommandlet();
	virtual int32 Main(const FString& Params) override;
};
