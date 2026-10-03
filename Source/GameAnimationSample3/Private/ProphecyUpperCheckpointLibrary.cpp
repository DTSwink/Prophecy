#include "ProphecyUpperCheckpointLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "EngineUtils.h"

namespace
{
AProphecyNNLocomotionManager* UpperManager(AProphecyAgent* Agent)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld() || !Agent->HasValidAgentHandle()) return nullptr;
    for (TActorIterator<AProphecyNNLocomotionManager> It(Agent->GetWorld());It;++It)
        if (It->ResolveAgent(Agent->GetAgentHandle())==Agent) return *It;
    return nullptr;
}
}

bool UProphecyUpperCheckpointLibrary::SetUpperCheckpoint(AProphecyAgent* Agent,EProphecyUpperCheckpoint Checkpoint,FString& OutError)
{
    OutError.Reset();
    auto* M=UpperManager(Agent);
    if (!M) { OutError=TEXT("Agent is not initialized.");return false; }
    return M->SetUpperCheckpointIndex(int32(Checkpoint),OutError);
}

bool UProphecyUpperCheckpointLibrary::GetUpperCheckpoint(AProphecyAgent* Agent,EProphecyUpperCheckpoint& Checkpoint)
{
    Checkpoint=EProphecyUpperCheckpoint::ProjectDefault;
    auto* M=UpperManager(Agent);
    if (!M) return false;
    const int32 Index=M->GetUpperCheckpointIndex();
    if (Index<0) return false;
    Checkpoint=EProphecyUpperCheckpoint(Index);
    return true;
}
