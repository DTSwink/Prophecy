#pragma once

#include "CoreMinimal.h"
#include "UObject/Object.h"
#include "Engine/HitResult.h"
#include "ProphecyHitEventTestSink.generated.h"

class AProphecyAgent;
class UPrimitiveComponent;

// Explicit automation/benchmark observer. Never created by normal gameplay.
UCLASS(Transient, NotBlueprintable)
class UProphecyHitEventTestSink : public UObject
{
    GENERATED_BODY()
public:
    int64 ComponentHits = 0, PhysicalHits = 0;
    int64 ConstraintBreaks = 0;
    FHitResult LastHit;
    FVector LastImpulse = FVector::ZeroVector;
    bool bOnlyGameThread = true;
    TFunction<void()> OnReceived;

    UFUNCTION()
    void ConstraintBroken(int32 ConstraintIndex)
    {
        ++ConstraintBreaks;
        bOnlyGameThread &= IsInGameThread();
        if (OnReceived) OnReceived();
    }

    UFUNCTION()
    void ComponentHit(UPrimitiveComponent* Mine, AActor* Other, UPrimitiveComponent* OtherComponent,
        FVector NormalImpulse, const FHitResult& Hit)
    {
        ++ComponentHits;
        bOnlyGameThread &= IsInGameThread();
        LastHit = Hit; LastImpulse = NormalImpulse;
        if (OnReceived) OnReceived();
    }
    UFUNCTION()
    void PhysicalHit(AProphecyAgent* Agent, AActor* Other, UPrimitiveComponent* OtherComponent,
        FVector NormalImpulse, const FHitResult& Hit)
    {
        ++PhysicalHits;
        bOnlyGameThread &= IsInGameThread();
        LastHit = Hit; LastImpulse = NormalImpulse;
    }
};
