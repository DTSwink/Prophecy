#pragma once

#include "Commandlets/Commandlet.h"
#include "ProphecyJoltComponentAuditCommandlet.generated.h"

/** Read only: selected manual-agent CDO and inherited SCS templates; no world or asset saves. */
UCLASS()
class UProphecyJoltComponentAuditCommandlet : public UCommandlet
{
    GENERATED_BODY()

public:
    UProphecyJoltComponentAuditCommandlet();
    virtual int32 Main(const FString& Params) override;
};
