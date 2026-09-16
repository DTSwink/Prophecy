#pragma once

#include "CoreMinimal.h"
#include "ProphecyAgent.h"
#include "Subsystems/WorldSubsystem.h"
#include "ProphecyPhysicalBlendSubsystem.generated.h"

class AProphecyNNLocomotionManager;

enum class EProphecyPhysicalBlend : uint8 { Magnetization, Feedback };

struct FProphecyPhysicalBlend
{
	FName Bone;
	EProphecyPhysicalBlend Kind;
	FVector2f Start, Target;
	double Elapsed = 0.0;
	double Duration = 1.0;
};

struct FProphecyPhysicalBlendAgent
{
	TWeakObjectPtr<AProphecyAgent> Agent;
	TWeakObjectPtr<AProphecyNNLocomotionManager> Manager;
	FProphecyAgentHandle ManagerHandle;
	TArray<FProphecyPhysicalBlend> Blends;
};

/** Only active agents are registered. One pre-actor callback, absent while idle; no extra actor ticks. */
UCLASS()
class UProphecyPhysicalBlendSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()
public:
	virtual bool DoesSupportWorldType(EWorldType::Type WorldType) const override;
	virtual void OnWorldEndPlay(UWorld& InWorld) override;
	virtual void Deinitialize() override;
	bool Start(AProphecyAgent& Agent, FName Bone, EProphecyPhysicalBlend Kind,
		FVector2f Target, float Duration);
	void Cancel(AProphecyAgent& Agent, FName Bone, EProphecyPhysicalBlend Kind);
	void RemoveAgent(AProphecyAgent& Agent);
	void MoveBlendsToContext(AProphecyAgent& Agent);

private:
	friend class FProphecyPhysicalBlendsTest;
	void Advance(UWorld* World, ELevelTick TickType, float DeltaSeconds);
	void RefreshCallback();
	void Clear();
	TArray<FProphecyPhysicalBlendAgent> ActiveAgents;
	FDelegateHandle TickHandle;
	bool bEnding = false;
};
