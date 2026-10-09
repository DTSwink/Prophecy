#include "ProphecyUpperCheckpointLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "EngineUtils.h"
#include "ProphecyDefenseCheckpoint.h"

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

bool UProphecyUpperCheckpointLibrary::SetParryCheckpoint(AProphecyAgent* Agent,EProphecyParryCheckpoint Checkpoint,FString& OutError)
{
    auto* M=UpperManager(Agent);if(!M){OutError=TEXT("Agent is not initialized.");return false;}
    return ProphecyDefenseCheckpoint::Set(M,false,int32(Checkpoint),OutError);
}
bool UProphecyUpperCheckpointLibrary::GetParryCheckpoint(AProphecyAgent* Agent,EProphecyParryCheckpoint& Checkpoint)
{
    Checkpoint=EProphecyParryCheckpoint::ProjectDefault;auto* M=UpperManager(Agent);if(!M)return false;
    Checkpoint=EProphecyParryCheckpoint(ProphecyDefenseCheckpoint::Get(M,false));return true;
}
bool UProphecyUpperCheckpointLibrary::SetDodgeCheckpoint(AProphecyAgent* Agent,EProphecyDodgeCheckpoint Checkpoint,FString& OutError)
{
    auto* M=UpperManager(Agent);if(!M){OutError=TEXT("Agent is not initialized.");return false;}
    return ProphecyDefenseCheckpoint::Set(M,true,int32(Checkpoint),OutError);
}
bool UProphecyUpperCheckpointLibrary::GetDodgeCheckpoint(AProphecyAgent* Agent,EProphecyDodgeCheckpoint& Checkpoint)
{
    Checkpoint=EProphecyDodgeCheckpoint::ProjectDefault;auto* M=UpperManager(Agent);if(!M)return false;
    Checkpoint=EProphecyDodgeCheckpoint(ProphecyDefenseCheckpoint::Get(M,true));return true;
}
