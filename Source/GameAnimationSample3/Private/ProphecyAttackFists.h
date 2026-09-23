#pragma once

#include "CoreMinimal.h"
#include "Containers/ArrayView.h"

class AProphecyAgent;
struct FPoseContext;

// Snapshot data stays outside live proxy allocations so Live Coding does not
// change their non-UObject layout. Only PreUpdate touches actors/assets.
namespace ProphecyAttackFists
{
	// Change attack-specific levels without restarting the closing timeline.
	void RetargetFamily(AProphecyAgent* Agent,FName Attack);
	void EnsureManualSimulation(AProphecyAgent* Agent);
	void PreUpdate(const void* Proxy, const AProphecyAgent* Agent);
	void Evaluate(const void* Proxy, FPoseContext& Output);
	void ApplyToLocalPose(const void* Proxy, TConstArrayView<FName> BoneNames, TArrayView<FTransform> LocalPose);
	void ReleaseProxy(const void* Proxy);
}
