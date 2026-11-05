#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Subsystems/WorldSubsystem.h"
#include "ProphecySceneTest.generated.h"

class ACameraActor;
class USkeletalMeshComponent;

/**
 * Headless scripted scene check: -SceneTest=<script file> -SceneTestOut=<dir> on a -game run.
 * The script places cameras relative to an anchor actor, records frames, calls Blueprint
 * functions on it, pokes bodies and logs probes. Development tool; absent from Shipping use.
 */
UCLASS(NotPlaceable, Transient)
class AProphecySceneTestDirector : public AActor
{
	GENERATED_BODY()
public:
	AProphecySceneTestDirector();
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;
	virtual void EndPlay(const EEndPlayReason::Type Reason) override;
	FString ScriptPath;
private:
	struct FCmd { double T = 0; FString Op; TArray<FString> Args; bool bDone = false; };
	struct FRamp { double T0 = 0, T1 = 0, From = 0, To = 0; FString Fn; };
	TArray<FRamp> Ramps;
	void Call(const FString& Function, double Value, bool bLog);
	struct FCamKey { double T = 0; FVector Loc = FVector::ZeroVector, Target = FVector::ZeroVector; float Fov = 50; bool bCut = true; };
	void Log(const FString& Line);
	void OnShot(int32 W, int32 H, const TArray<FColor>& Colors);
	void Run(FCmd& C);
	void Probe(double T);
	bool BodyPose(USkeletalMeshComponent* Mesh, FName Bone, FVector& Pos, FVector& Vel) const;
	USkeletalMeshComponent* Rope() const;
	FTransform Frame() const;
	TArray<FCmd> Cmds;
	TArray<FCamKey> Cams;
	// orbit <t0> <t1> <radius cm> <elevation deg> <fov> [turns]: circles the noose, following it live.
	struct FOrbit { double T0 = 0, T1 = 0, Radius = 80, Elevation = 15, Fov = 45, Turns = 1; };
	TArray<FOrbit> Orbits;
	FString OutDir, Report, PendingName, AnchorClass = TEXT("A_Potence");
	UPROPERTY() TObjectPtr<ACameraActor> Cam;
	UPROPERTY() TObjectPtr<AActor> Anchor;
	FDelegateHandle ShotHandle;
	int64 Tick60 = 0, StartTick = -1;
	int32 FrameIndex = 0, RecordEvery = 2;
	double RecordFrom = -1, RecordTo = -1, ProbeEvery = 0, NextProbe = 0, RestLength = -1;
	bool bStarted = false;
	// Physical props driven by the script (placed skeletal actors, e.g. a UEFN mannequin ragdoll).
	TArray<FString> HoldLabels, HeldLabels;
	FString FocusLabel;
	double Amount = 0;	// last value this script sent to the reel function
	AActor* FindActor(const FString& Label) const;
	USkeletalMeshComponent* MeshOf(const FString& Label) const;
	bool TieArgs(const FCmd& C, USkeletalMeshComponent*& Mesh, FName& Body, FName& At, float& Clearance) const;
	bool SetBodyVelocityDelta(USkeletalMeshComponent* Mesh, FName Bone, const FVector& Dv);
};

UCLASS()
class UProphecySceneTestSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()
public:
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
	virtual void OnWorldBeginPlay(UWorld& World) override;
};
