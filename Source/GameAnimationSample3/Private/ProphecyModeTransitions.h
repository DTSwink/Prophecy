#pragma once
class AProphecyAgent;
struct FPoseContext;
namespace ProphecyModeTransitions
{
	/** Nested Half Sim calls share one outer capture/restore transaction. */
	struct FScope
	{
		explicit FScope(AProphecyAgent* InAgent);
		~FScope();
		AProphecyAgent* Agent;
	};
	void PreUpdate(const void* Proxy, const AProphecyAgent* Agent);
	void Evaluate(const void* Proxy, FPoseContext& Output);
	void ReleaseProxy(const void* Proxy);
	void ReleaseAgent(const AProphecyAgent* Agent);
}
