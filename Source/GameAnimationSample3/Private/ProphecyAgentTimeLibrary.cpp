#include "ProphecyAgentTimeLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "EngineUtils.h"

namespace
{
AProphecyNNLocomotionManager* TimeManager(AProphecyAgent* Agent)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || !Agent->GetWorld() || !Agent->HasValidAgentHandle()) return nullptr;
    for (TActorIterator<AProphecyNNLocomotionManager> It(Agent->GetWorld());It;++It)
        if (It->ResolveAgent(Agent->GetAgentHandle())==Agent) return *It;
    return nullptr;
}
}
bool UProphecyAgentTimeLibrary::SetAgentTimeDilation(AProphecyAgent* Agent,float Multiplier)
{
    auto* Manager=TimeManager(Agent);
    return Manager && Manager->SetAgentTimeDilation(Agent->GetAgentHandle(),Multiplier);
}
float UProphecyAgentTimeLibrary::GetAgentTimeDilation(AProphecyAgent* Agent)
{
    auto* Manager=TimeManager(Agent);
    return Manager?Manager->GetAgentTimeDilation(Agent->GetAgentHandle()):1.f;
}
