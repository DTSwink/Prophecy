#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ProphecyDoubleReachBallTest.generated.h"

class AProphecyDoubleReachCharacter;
class UBoxComponent;
class UCameraComponent;
class UPhysicalMaterial;
class USceneComponent;
class UStaticMeshComponent;

UCLASS(Blueprintable)
class GAMEANIMATIONSAMPLE3_API AProphecyDoubleReachBallTest : public AActor
{
	GENERATED_BODY()

public:
	AProphecyDoubleReachBallTest();

	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void Tick(float DeltaSeconds) override;

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Reach Test")
	void ResetBalls();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Reach Test")
	TObjectPtr<USceneComponent> SceneRoot;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Reach Test")
	TObjectPtr<UStaticMeshComponent> LeftBall;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Reach Test")
	TObjectPtr<UStaticMeshComponent> RightBall;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Reach Test")
	TObjectPtr<UCameraComponent> TestCamera;

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Reach Test")
	TArray<TObjectPtr<UBoxComponent>> BoundaryWalls;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Reach Test|Bounds")
	FVector BoxCenterOffset = FVector(0.0, 0.0, 125.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Reach Test|Bounds", meta = (ClampMin = "30.0"))
	FVector BoxHalfExtent = FVector(145.0, 120.0, 105.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Reach Test|Bounds", meta = (ClampMin = "1.0"))
	float WallThicknessCm = 10.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Reach Test|Bounds")
	bool bDrawBounds = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Reach Test|Balls", meta = (ClampMin = "2.0"))
	float BallRadiusCm = 12.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Reach Test|Balls", meta = (ClampMin = "1.0", Units = "cm/s"))
	float BallSpeedCmPerSecond = 165.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Reach Test|Balls")
	FVector LeftBallStartOffset = FVector(-55.0, -48.0, 28.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Reach Test|Balls")
	FVector RightBallStartOffset = FVector(48.0, 44.0, -24.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Reach Test|Balls")
	FVector LeftBallInitialDirection = FVector(0.72, 0.46, 0.52);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Reach Test|Balls")
	FVector RightBallInitialDirection = FVector(-0.58, 0.70, -0.41);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Reach Test|Balls")
	bool bMaintainBallSpeed = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Reach Test|Character")
	TSubclassOf<AProphecyDoubleReachCharacter> ReachCharacterClass;

	UPROPERTY(EditInstanceOnly, BlueprintReadWrite, Category = "Prophecy|Reach Test|Character")
	TObjectPtr<AProphecyDoubleReachCharacter> ReachCharacterOverride;

	UPROPERTY(VisibleInstanceOnly, BlueprintReadOnly, Category = "Prophecy|Reach Test|Character")
	TObjectPtr<AProphecyDoubleReachCharacter> ActiveReachCharacter;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Reach Test|Character")
	FVector CharacterSpawnOffset = FVector(0.0, 0.0, 88.0);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Reach Test|Character", meta = (ClampMin = "0.0", Units = "s"))
	float ReachTransitionDuration = 0.25f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Reach Test|Camera")
	bool bAutoViewOnBeginPlay = true;

protected:
	virtual void BeginPlay() override;
	virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

private:
	void UpdateBoundsGeometry();
	void ConfigureBall(UStaticMeshComponent* Ball, const FVector& InitialDirection);
	void MaintainBall(UStaticMeshComponent* Ball, const FVector& FallbackDirection);
	void SpawnOrAcquireReachCharacter();
	void UpdateReachTargets();

	UPROPERTY(Transient)
	TObjectPtr<UPhysicalMaterial> BouncePhysicalMaterial;

	bool bOwnsReachCharacter = false;
};
