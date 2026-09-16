#pragma once
#include "BlueprintCompilerExtension.h"
#include "ProphecyStandardPhysicsCompiler.generated.h"

/** Routes compiled calls, never the user's authored graph or component classes. */
UCLASS()
class UProphecyStandardPhysicsCompiler : public UBlueprintCompilerExtension
{
    GENERATED_BODY()
protected:
    virtual void ProcessBlueprintCompiled(const FKismetCompilerContext& Context, const FBlueprintCompiledData& Data) override;
};

void RegisterProphecyStandardPhysicsCompiler();
void UnregisterProphecyStandardPhysicsCompiler();
