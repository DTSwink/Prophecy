#pragma once
#include "CoreMinimal.h"
#include "Engine/DebugCameraController.h"
#include "ProphecyDebugCameraController.generated.h"

/** Editor debug camera that preserves the original agent's Blueprint key events. */
UCLASS(Transient, NotBlueprintable)
class AProphecyDebugCameraController : public ADebugCameraController
{
    GENERATED_BODY()
public:
    virtual void OnActivate(APlayerController* OriginalPC) override;
    virtual void OnDeactivate(APlayerController* RestoredPC) override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
private:
    void ClearForwardedInput();
    UPROPERTY(Transient)
    TObjectPtr<UInputComponent> ForwardedInput;
};
