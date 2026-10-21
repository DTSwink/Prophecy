#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "ProphecyBloodNiagaraCallbacks.generated.h"

class UActorComponent;

// A delegate receiver only; no world tick or per-effect component is needed.
UCLASS()
class UProphecyBloodNiagaraCallbacks : public UObject
{
	GENERATED_BODY()
public:
	static void Startup();
	static void Shutdown();

	UFUNCTION()
	void OnActivated(UActorComponent* Component, bool bReset);
};
