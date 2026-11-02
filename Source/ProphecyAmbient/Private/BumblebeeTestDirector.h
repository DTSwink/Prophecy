#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BumblebeeTestDirector.generated.h"

class ACameraActor;
class ABumblebeeSwarm;
class UMaterialInterface;

/**
 * Headless verification only. Spawned by the module when the game runs with -BeeTest=model|swarm|map.
 * Builds a throw-away scene at runtime (nothing is saved), drives a camera, takes screenshots,
 * logs BEETEST lines + Saved/BeeTest/<scene>/report.txt and quits.
 */
UCLASS(NotPlaceable, Transient)
class ABumblebeeTestDirector : public AActor
{
	GENERATED_BODY()

public:
	ABumblebeeTestDirector();
	FString Scene;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	using FStep = TFunction<bool(float)>;	// returns true when finished
	TArray<FStep> Steps;
	int32 StepIndex = 0;
	float StepTime = 0.f;
	float TotalTime = 0.f;
	FString OutDir;
	FString Report;

	UPROPERTY() TObjectPtr<ACameraActor> Cam;
	UPROPERTY() TObjectPtr<ABumblebeeSwarm> Swarm;
	UPROPERTY() TObjectPtr<AActor> ThreatActor;
	UPROPERTY() TObjectPtr<UMaterialInterface> BaseMat;
	bool bOverrideView = true;
	FVector ThreatCenter = FVector::ZeroVector;
	float ThreatAngle = 0.f;
	bool bMoveThreat = false;

	// frame timing windows
	double FrameMsSum = 0.0, GameMsSum = 0.0, RenderMsSum = 0.0, GpuMsSum = 0.0;
	int32 FrameSamples = 0;
	void ResetTiming();
	FString TimingJson() const;

	void Log(const FString& Line);
	void Flush();
	void SetCam(const FVector& Loc, const FVector& Target, float Fov);
	AActor* SpawnBox(const FVector& Loc, const FVector& SizeCm, const FLinearColor& Color, const TCHAR* Shape = TEXT("Cube"), const FRotator& Rot = FRotator::ZeroRotator, bool bMovable = false);
	void SpawnLighting();
	class ABumblebeeZone* SpawnZone(const FVector& Center, const FVector& Extent, int32 Count, float Preference = 0.85f);
	FString StatsJson() const;

	// step factories
	void AddWaitShaders(float MinSeconds);
	void AddWait(float Seconds);
	void AddShot(const FString& Name, float Settle = 0.6f);
	void AddCall(TFunction<void()> Fn);

	void BuildModelScene();
	void BuildSwarmScene();
	void BuildMapScene();
	int32 FindBee(bool bLanded, const FVector& Near, float MaxDist) const;
	void FrameBee(int32 Index, float Dist, float Yaw, float Pitch, float Fov);
};
