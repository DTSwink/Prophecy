#include "ProphecyNNDefenseLibrary.h"
#include "ProphecyDefenseControls.h"
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
EProphecyAgentState UProphecyNNDefenseLibrary::GetAgentState(AProphecyAgent* Agent)
{
    auto* M=Manager(Agent);
    return M ? M->GetAgentActivityState(Agent->GetAgentHandle()) : EProphecyAgentState::Locomotion;
}
bool UProphecyNNDefenseLibrary::StartNNParry(AProphecyAgent* Agent,AProphecyAgent* Attacker,FString& OutError,float MaximumDurationSeconds)
{
    auto* M=Manager(Agent);if (!M) { OutError=TEXT("Agent has no initialized NN manager.");return false; }
    return M->StartAgentNNParry(Agent->GetAgentHandle(),Attacker,MaximumDurationSeconds,OutError);
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

#define DEFENSE_CLAMP(Mode, Dodge, Limb) \
bool UProphecyNNDefenseLibrary::Set##Mode##Limb##Clamp(AProphecyAgent* Agent,bool bEnabled,float LeewayCm) \
{ return ProphecyDefenseControls::Set(Agent,Dodge,ProphecyDefenseControls::ELimb::Limb,bEnabled,LeewayCm); }
DEFENSE_CLAMP(Parry,false,Foot)
DEFENSE_CLAMP(Parry,false,Calf)
DEFENSE_CLAMP(Parry,false,Hand)
DEFENSE_CLAMP(Parry,false,Forearm)
DEFENSE_CLAMP(Dodge,true,Foot)
DEFENSE_CLAMP(Dodge,true,Calf)
DEFENSE_CLAMP(Dodge,true,Hand)
DEFENSE_CLAMP(Dodge,true,Forearm)
#undef DEFENSE_CLAMP

bool UProphecyNNDefenseLibrary::SetDodgeFramesAfterHit(AProphecyAgent* Agent,int32 Frames)
{ return ProphecyDefenseControls::SetDodgeFramesAfterHit(Agent,Frames); }
int32 UProphecyNNDefenseLibrary::GetDodgeFramesAfterHit(AProphecyAgent* Agent)
{ return ProphecyDefenseControls::GetDodgeFramesAfterHit(Agent); }
