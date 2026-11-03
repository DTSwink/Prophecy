#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "BirdTypes.h"
#include "BirdTestDirector.generated.h"

class ACameraActor;
class ABird;
class ABirdFlock;
class ABirdZone;
class UMaterialInterface;

/** Headless verification for the birds (-BirdTest=birds|video). Builds a throw-away beach scene, logs BIRDTEST lines,
 *  report.txt, traj.csv and screenshots / video frames into -BeeTestOut, then quits. */
UCLASS(NotPlaceable, Transient)
class ABirdTestDirector : public AActor
{
	GENERATED_BODY()

public:
	ABirdTestDirector();
	FString Scene;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	using FStep = TFunction<bool(float)>;
	TArray<FStep> Steps;
	int32 StepIndex = 0;
	float StepTime = 0.f, TotalTime = 0.f;
	FString OutDir, Report, Csv;
	UPROPERTY() TObjectPtr<ACameraActor> Cam;
	UPROPERTY() TObjectPtr<UMaterialInterface> BaseMat;
	UPROPERTY() TObjectPtr<ABirdFlock> Flock;
	UPROPERTY() TObjectPtr<AActor> Mover;
	UPROPERTY() TObjectPtr<ABird> Subject;
	UPROPERTY() TObjectPtr<UPrimitiveComponent> BallComp;
	FVector BallStart = FVector::ZeroVector;
	FVector MoverVel = FVector::ZeroVector;
	float MoverTime = 0.f;
	FVector CamLoc = FVector::ZeroVector, CamLook = FVector::ZeroVector;
	bool bCamInit = false;
	float MinSepRatio = 99.f;
	int32 Frame = 0;
	bool bRecording = false;
	int32 FrameIndex = 0;
	FDelegateHandle ShotHandle;
	double FrameMsSum = 0.0, GameMsSum = 0.0;
	int32 FrameSamples = 0;

	void Log(const FString& Line);
	void SetCam(const FVector& Loc, const FVector& Target, float Fov);
	void SmoothCam(const FVector& Loc, const FVector& Target, float Fov, float Dt, float Rate = 4.f);
	AActor* SpawnBox(const FVector& Loc, const FVector& SizeCm, const FLinearColor& Color, const TCHAR* Shape = TEXT("Cube"), const FRotator& Rot = FRotator::ZeroRotator, bool bMovable = false);
	void SpawnLighting();
	void BuildBeach();
	ABirdZone* Zone(const FVector& C, const FVector& E, EBirdSpecies Sp, int32 Count, int32 Seed, float AirTime);
	ABird* FindBird(EBirdSpecies Sp, TFunctionRef<bool(const ABird*)> Pred, const FVector& Near = FVector::ZeroVector) const;
	FString StatsJson() const;
	void FrameBird(ABird* B, float Dist, float YawOff, float PitchDeg, float Fov, float ZOff = 0.f);
	FVector ClearCamPos(const FVector& Target, float Yaw, float PitchDeg, float Dist) const;

	void AddWaitShaders(float MinSeconds);
	void AddWait(float Seconds);
	void AddShot(const FString& Name, float Settle = 0.5f);
	void AddCall(TFunction<void()> Fn);
	void AddRecord(float Seconds, TFunction<void(float, float)> CamFn);
	void OnShotCaptured(int32 W, int32 H, const TArray<FColor>& Colors);
	void AddKillTests(bool bVideo);

	void BuildTestScene();
	void BuildVideoScene();
	void BuildFeedingScene();
	void BuildPerfScene();
	// falling leaves (BirdTestDirector_Leaves.cpp)
	void BuildLeafScene();
	FString LeafStatsJson() const;
	void AddLeafShowcase(int32 Flight, int32 Cond, int32 Shape, float Seconds, float Dilation = 1.f);
	UPROPERTY() TObjectPtr<class ALeafFall> LeafFall;
	int32 LeafIdx = -1;
	FVector LeafStart = FVector::ZeroVector, LeafPrev = FVector::ZeroVector;
	float LeafHoriz = 0.f, LeafT = 0.f, LeafLandedAt = -1.f;
	int32 LeafSamples = 0, FadeIdx = -1;
	float FadeLanded = -1.f;
	FVector LeafAnchor = FVector::ZeroVector, LeafDir = FVector::ForwardVector, LeafCanopy = FVector(0, 0, 1100);
	FVector GroundAt(const FVector& P) const;
	void PickLeafTree();
	void AddWindShots();
	void SpawnWindGrass(const FVector& Centre, const FVector& Carpet, const FVector& Dir);
	void SpawnCarpet(const FVector& C, float Half, int32 N, int32 Seed);
	UPROPERTY() TObjectPtr<class AGlobalWind> WindActor;
	int32 BaseSpawned = 0;
	void AddPerfWindow(const FString& Name, float Seconds);
	double PerfGT = 0, PerfRT = 0, PerfGPU = 0, PerfFrame = 0, PerfFlock = 0, PerfParts[6] = { 0, 0, 0, 0, 0, 0 };
	int32 PerfFrames = 0, PerfSamples = 0;
	bool bEndRecord = false;
	bool bHoming = false;
	int32 FeedPhase = 0, LastTask = -1, LastGullTask = -1, FishTries = 0;
	float EndAt = 0.f;
};
