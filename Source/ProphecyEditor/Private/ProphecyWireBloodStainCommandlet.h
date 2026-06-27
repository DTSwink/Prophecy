#pragma once

#include "Commandlets/Commandlet.h"
#include "ProphecyWireBloodStainCommandlet.generated.h"

UCLASS()
class UProphecyWireBloodStainCommandlet : public UCommandlet
{
	GENERATED_BODY()

public:
	UProphecyWireBloodStainCommandlet();

	virtual int32 Main(const FString& Params) override;
};
