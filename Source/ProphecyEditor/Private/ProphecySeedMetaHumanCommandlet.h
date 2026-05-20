#pragma once

#include "Commandlets/Commandlet.h"

#include "ProphecySeedMetaHumanCommandlet.generated.h"

UCLASS()
class UProphecySeedMetaHumanCommandlet final : public UCommandlet
{
	GENERATED_BODY()

public:
	UProphecySeedMetaHumanCommandlet();

	virtual int32 Main(const FString& Params) override;
};
