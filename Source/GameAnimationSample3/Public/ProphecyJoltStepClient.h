#pragma once

#include "CoreMinimal.h"
#include "UObject/Interface.h"
#include "ProphecyJoltStepClient.generated.h"

// Native-only interface: no Blueprint event dispatch occurs inside the shared step.
UINTERFACE(MinimalAPI, meta = (CannotImplementInterfaceInBlueprint))
class UProphecyJoltStepClient : public UInterface
{
    GENERATED_BODY()
};

/** Game-thread callbacks owned by a registered UActorComponent. No callback creates or steps a world.
 * Active/automatic queries must not mutate registration. Active means the binding is still owned,
 * including a stopped binding awaiting explicit recovery. Prepare may publish inputs; Consume reads
 * the one completed world step and updates presentation. Explicit removal during a callback is supported.
 * Clients cancel pending admission and unregister their exact registration before EndPlay/OnUnregister
 * tears down native state. Callback-capable presentation must recheck its registration and body handles.
 */
class GAMEANIMATIONSAMPLE3_API IProphecyJoltStepClient
{
    GENERATED_BODY()

public:
    virtual bool IsJoltStepClientActive() const = 0;
    virtual bool WantsAutomaticJoltStep() const = 0;
    virtual bool PrepareJoltWorldStep(float DeltaSeconds, bool bPublishMissingTargets, FString& OutError) = 0;
    virtual bool ConsumeCompletedJoltWorldStep(FString& OutError) = 0;
    // Retain native ownership while reporting a shared failure; recovery is an explicit disable/enable.
    virtual void LatchJoltStepError(const FString& Error) = 0;
};
