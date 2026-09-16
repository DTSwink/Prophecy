#include "ProphecyNNDefenseLibrary.h"
#include "ProphecyNNLocomotionManager.h"
#include "EngineUtils.h"
namespace
{
AProphecyNNLocomotionManager* Manager(AProphecyAgent* Agent)
{
    if (!IsInGameThread() || !IsValid(Agent) || !Agent->GetWorld() || !Agent->HasValidAgentHandle()) return nullptr;
    for (TActorIterator<AProphecyNNLocomotionManager> It(Agent->GetWorld());It;++It)
        if (It->ResolveAgent(Agent->GetAgentHandle())==Agent) return *It;
    return nullptr;
}
}
bool UProphecyNNDefenseLibrary::StartNNParry(AProphecyAgent* Agent,AProphecyAgent* Attacker,EProphecyParryBlocker Blocker,FString& OutError,float MaximumDurationSeconds)
{
    auto* M=Manager(Agent);if (!M) { OutError=TEXT("Agent has no initialized NN manager.");return false; }
    return M->StartAgentNNParry(Agent->GetAgentHandle(),Attacker,Blocker,MaximumDurationSeconds,OutError);
}
bool UProphecyNNDefenseLibrary::StopNNDefense(AProphecyAgent* Agent)
{ auto* M=Manager(Agent);return M && M->StopAgentNNDefense(Agent->GetAgentHandle()); }
bool UProphecyNNDefenseLibrary::StartNNDodge(AProphecyAgent* Agent,AProphecyAgent* Attacker,FString& OutError,float MaximumDurationSeconds)
{
    auto* M=Manager(Agent);if (!M) { OutError=TEXT("Agent has no initialized NN manager.");return false; }
    return M->StartAgentNNDodge(Agent->GetAgentHandle(),Attacker,MaximumDurationSeconds,OutError);
}
bool UProphecyNNDefenseLibrary::GetNNDefenseStatus(AProphecyAgent* Agent,FProphecyNNDefenseStatus& Status)
{ Status={};auto* M=Manager(Agent);return M && M->GetAgentNNDefenseStatus(Agent->GetAgentHandle(),Status); }
