#include "ProphecyRootVelocityLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "EngineUtils.h"

namespace
{
bool SetVelocity(AProphecyAgent* Agent,const FVector& Value,bool Angular,bool Add)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()
        || Value.ContainsNaN() || !Agent->GetWorld() || !Agent->HasValidAgentHandle()) return false;
    for (TActorIterator<AProphecyNNLocomotionManager> It(Agent->GetWorld());It;++It)
        if (It->ResolveAgent(Agent->GetAgentHandle())==Agent)
            return It->SetAgentRootVelocity(Agent->GetAgentHandle(),Value,Angular,Add);
    return false;
}
}
bool UProphecyRootVelocityLibrary::SetRootVelocity(AProphecyAgent* Agent,FVector WorldVelocity,bool bAddToCurrent)
{ return SetVelocity(Agent,WorldVelocity,false,bAddToCurrent); }
bool UProphecyRootVelocityLibrary::SetRootAngVelocity(AProphecyAgent* Agent,FVector WorldAngularVelocityDegrees,bool bAddToCurrent)
{ return SetVelocity(Agent,WorldAngularVelocityDegrees,true,bAddToCurrent); }
