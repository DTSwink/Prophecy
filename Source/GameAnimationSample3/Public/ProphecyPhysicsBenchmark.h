#pragma once

#include "CoreMinimal.h"
#include "Animation/AnimInstance.h"
#include "Subsystems/WorldSubsystem.h"
#include "ProphecyHalfSimDriveComponent.h"
#include "ProphecyPhysicsBenchmark.generated.h"

namespace ProphecyManualServoCapture { struct FCapture; }
class FJsonObject;
struct FProphecyManualCrowdState;
struct FProphecyNNJoltBenchmarkState;

/** Tiny deterministic pose generator, no AnimBP, NN, state machine or gameplay. */
UCLASS(Transient)
class GAMEANIMATIONSAMPLE3_API UProphecyPhysicsBenchAnim : public UAnimInstance
{
    GENERATED_BODY()
public:
    double PoseTime = 0;
protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) override;
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyPhysicsBenchmarkSubsystem : public UWorldSubsystem
{
    GENERATED_BODY()
public:
    virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
    virtual void OnWorldBeginPlay(UWorld& World) override;
    virtual void Deinitialize() override;
private:
    void StartTick(UWorld*, ELevelTick, float);
    void EndTick(UWorld*, ELevelTick, float);
    void PrepareCase();
    void ClearCase();
    void SaveCase();
    void ValidateAgentSwitches();
    bool PrepareManualAgent(int32 Index, bool bFloor, FString& Error);
    bool CaptureManualRig(FString& Error);
    bool RestoreManualReplayState(FString& Error);
    bool PublishManualReplayFrame(FString& Error);
    void PublishManualPose(int32 Index);
    bool SaveManualCapture(TSharedPtr<FJsonObject> CaseResult, FString& Error);
    bool ReplayManualCaptureInJolt(TSharedPtr<FJsonObject> CaseResult, FString& Error);
    bool InitializeLiveJoltCase(FString& Error);
    bool ValidateLiveJoltFrame(FString& Error);
    bool SaveLiveJoltCase(TSharedPtr<FJsonObject> CaseResult, FString& Error);
    bool InitializeMultiJoltCase(FString& Error);
    bool ValidateMultiJoltFrame(FString& Error);
    bool SaveMultiJoltCase(TSharedPtr<FJsonObject> CaseResult, FString& Error);
    bool InitializeManualCrowdCase(FString& Error);
    bool ValidateManualCrowdFrame(FString& Error);
    bool SaveManualCrowdCase(TSharedPtr<FJsonObject> CaseResult, FString& Error);
    bool PrepareNNJoltCase(FString& Error);
    bool InitializeNNJoltCase(FString& Error);
    bool ValidateNNJoltFrame(FString& Error);
    bool SaveNNJoltCase(TSharedPtr<FJsonObject> CaseResult, FString& Error);
    void Finish(const FString& Error = TEXT(""));
    TSharedPtr<class FJsonObject> Audit() const;
    struct FCase { int32 Mode; bool Floor; int32 Repeat; };
    TArray<FCase> Cases;
    UPROPERTY(Transient) TArray<TObjectPtr<AActor>> Actors;
    UPROPERTY(Transient) TArray<TObjectPtr<USkeletalMeshComponent>> Meshes;
    UPROPERTY(Transient) TArray<TObjectPtr<UProphecyHalfSimDriveComponent>> Drivers;
    UPROPERTY(Transient) TObjectPtr<USkeletalMesh> MeshAsset;
    TArray<double> WorldMs, FrameMs;
    TArray<TSharedPtr<class FJsonValue>> Results;
    TArray<TSharedPtr<class FJsonValue>> LiveJoltFrames;
    TArray<TSharedPtr<class FJsonValue>> MovementCameraDetachments;
    uint64 LastLiveJoltRevision = 0;
    TSharedPtr<FJsonObject> Before;
    TSharedPtr<struct FProphecyJoltRigSnapshot> ManualInitialRig;
    TSharedPtr<ProphecyManualServoCapture::FCapture> ManualSealedCapture;
    TSharedPtr<FProphecyManualCrowdState> ManualCrowdState;
    TSharedPtr<FProphecyNNJoltBenchmarkState> NNJoltState;
    FString ManualSealedCapturePath, ManualSealedCaptureHash;
    FDelegateHandle StartHandle, EndHandle;
    int32 CaseIndex = -1, Frame = 0, Count = 100, Warmup = 60, Samples = 180, Repeats = 3;
    double TickStart = 0, PreviousStart = 0, RunStart = 0;
    bool Advance = true, Done = false, Measuring = false;
    FString Output;
};
