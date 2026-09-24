#include "ProphecyAttackCheckpointLibrary.h"
#include "ProphecyAgent.h"
#include "ProphecyNNLocomotionManager.h"
#include "EngineUtils.h"

namespace
{
AProphecyNNLocomotionManager* Manager(AProphecyAgent* Agent)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed() || !Agent->GetWorld() || !Agent->HasValidAgentHandle()) return nullptr;
    for (TActorIterator<AProphecyNNLocomotionManager> It(Agent->GetWorld());It;++It)
        if (It->ResolveAgent(Agent->GetAgentHandle())==Agent) return *It;
    return nullptr;
}
}
bool UProphecyAttackCheckpointLibrary::SetAttackCheckpoint(AProphecyAgent* Agent,EProphecyAttackCheckpoint Checkpoint,FString& OutError)
{
    OutError.Reset();
    if (Checkpoint!=EProphecyAttackCheckpoint::Current174664 && Checkpoint!=EProphecyAttackCheckpoint::PredictivePin160664 && Checkpoint!=EProphecyAttackCheckpoint::PredictivePin184064)
    { OutError=TEXT("Unknown attack checkpoint.");return false; }
    auto* M=Manager(Agent);
    if (!M) { OutError=TEXT("Agent is not initialized.");return false; }
    return M->SetAgentAttackCheckpointIndex(Agent->GetAgentHandle(),int32(Checkpoint),OutError);
}
bool UProphecyAttackCheckpointLibrary::GetAttackCheckpoint(AProphecyAgent* Agent,EProphecyAttackCheckpoint& Selected,
    EProphecyAttackCheckpoint& Effective,bool& Attacking)
{
    Selected=Effective=EProphecyAttackCheckpoint::Current174664;Attacking=false;
    auto* M=Manager(Agent);if (!M) return false;
    int32 S=0,E=0;
    if (!M->GetAgentAttackCheckpointIndex(Agent->GetAgentHandle(),S,E,Attacking)) return false;
    Selected=EProphecyAttackCheckpoint(S);
    Effective=EProphecyAttackCheckpoint(E);
    return true;
}
