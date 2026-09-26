#include "ProphecySlashTrainDebugLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "EngineUtils.h"

bool UProphecySlashTrainDebugLibrary::SetSlashTrainStartingPose(AProphecyAgent* Agent,FString& OutError)
{
    OutError=TEXT("Agent is not initialized.");
    if (IsInGameThread() && IsValid(Agent) && Agent->GetWorld() && Agent->HasValidAgentHandle())
        for (TActorIterator<AProphecyNNLocomotionManager> It(Agent->GetWorld());It;++It)
            if (It->ResolveAgent(Agent->GetAgentHandle())==Agent)
                return It->SetSlashTrainStartingPose(Agent->GetAgentHandle(),OutError);
    return false;
}
