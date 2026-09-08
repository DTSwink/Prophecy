#pragma once

#include "CoreMinimal.h"
#include "ProphecyAgent.h"
#include "ProphecyNativePhysicalAgent.generated.h"

/** Isolated native PhysicalAnimation experiment. Never selected by production by default. */
UCLASS(Blueprintable)
class GAMEANIMATIONSAMPLE3_API AProphecyNativePhysicalAgent : public AProphecyAgent
{
	GENERATED_BODY()
public:
	AProphecyNativePhysicalAgent();
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

	/** Keeps the NN anim instance on this same mesh. No second skeletal component. */
	UFUNCTION(BlueprintCallable, Category="Prophecy|Native Physical Test")
	bool SetNativePhysicalSimulation(bool bEnabled);

	/** Absolute multipliers of PhysicalDriveSettings, not multiplication of the last setting. */
	UFUNCTION(BlueprintCallable, Category="Prophecy|Native Physical Test")
	bool SetNativeBodyStrength(FName BoneName, float LinearScale=1.0f, float AngularScale=1.0f);

	/** Zero strength leaves real simulated colliders and articulation enabled. */
	UFUNCTION(BlueprintCallable, Category="Prophecy|Native Physical Test")
	int32 SetNativeBodyStrengthBelow(FName ParentBone, float LinearScale=1.0f,
		float AngularScale=1.0f, bool bIncludeParent=true);

	UFUNCTION(BlueprintCallable, Category="Prophecy|Native Physical Test")
	void SetNativeContactsAndGravity(bool bContacts, bool bGravity);

	/** Restore PHAT angular limits, or free rotation for NN-target calibration.
	 * Linear joint anchors remain locked as authored: bones never detach. */
	UFUNCTION(BlueprintCallable, Category="Prophecy|Native Physical Test")
	bool SetNativeUseAuthoredAngularLimits(bool bEnabled);

	UFUNCTION(BlueprintPure, Category="Prophecy|Native Physical Test")
	UPhysicalAnimationComponent* GetNativePhysicalAnimation() const;

	/** On-demand native drive target versus actual Chaos body. Read after physics. */
	UFUNCTION(BlueprintCallable, Category="Prophecy|Native Physical Test")
	bool GetNativeBodySample(FName BoneName, FTransform& TargetWorld, FTransform& ActualWorld,
		FVector& LinearVelocity, FVector& AngularVelocityRadians, float& MassKg,
		float& PhysicsBlendWeight) const;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Prophecy|Native Physical Test")
	bool bStartNativeSimulation = true;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Prophecy|Native Physical Test")
	bool bNativeContacts = true;
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Prophecy|Native Physical Test")
	bool bNativeGravity = true;
	/** Original mannequin hinge axes conflict with several NN calf/forearm rotations. */
	UPROPERTY(EditAnywhere, BlueprintReadOnly, Category="Prophecy|Native Physical Test")
	bool bNativeUseAuthoredAngularLimits = false;

private:
	bool bNativeStarted = false;
	uint64 NativeTargetsPendingFrame = MAX_uint64;
	TMap<FName, FVector2D> NativeStrengthScales;
};
