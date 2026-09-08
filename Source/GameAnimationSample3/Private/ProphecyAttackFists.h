#pragma once

class AProphecyAgent;
struct FPoseContext;

// Snapshot data stays outside live proxy allocations so Live Coding does not
// change their non-UObject layout. Only PreUpdate touches actors/assets.
namespace ProphecyAttackFists
{
	void EnsureManualSimulation(AProphecyAgent* Agent);
	void PreUpdate(const void* Proxy, const AProphecyAgent* Agent);
	void Evaluate(const void* Proxy, FPoseContext& Output);
	void ReleaseProxy(const void* Proxy);
}
