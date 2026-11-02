#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ProphecyOilDebris.generated.h"
class UMaterialInstanceDynamic;
class AStaticMeshActor;
class AProphecyOilBottle;

/** One bounded fade clock per broken bottle; intact bottles never tick. */
UCLASS(NotBlueprintable,Transient)
class AProphecyOilDebris : public AActor
{
    GENERATED_BODY()
public:
    AProphecyOilDebris();
    void Initialize(AProphecyOilBottle& Source,const FVector& Velocity,const FVector& Angular,const FVector& COM);
    virtual void Tick(float DeltaSeconds) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
private:
    UPROPERTY(Transient) TArray<TObjectPtr<AStaticMeshActor>> Pieces;
    UPROPERTY(Transient) TArray<TObjectPtr<UMaterialInstanceDynamic>> Materials;
    uint64 LastFrame=0;
    int32 Age=0,Lifetime=0,Fade=0;
};
