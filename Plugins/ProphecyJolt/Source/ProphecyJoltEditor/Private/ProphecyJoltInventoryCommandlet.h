#pragma once

#include "Commandlets/Commandlet.h"
#include "ProphecyJoltInventoryCommandlet.generated.h"

/** On-disk asset inventory. Never edits or saves a package. */
UCLASS()
class UProphecyJoltInventoryCommandlet : public UCommandlet
{
    GENERATED_BODY()

public:
    UProphecyJoltInventoryCommandlet();
    virtual int32 Main(const FString& Params) override;
};
