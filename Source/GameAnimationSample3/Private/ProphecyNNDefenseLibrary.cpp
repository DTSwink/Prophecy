#include "ProphecyNNDefenseLibrary.h"
#include "ProphecyDefenseControls.h"
#include "ProphecyDefenseArmedGate.h"
#include "ProphecyNNLocomotionManager.h"
#include "EngineUtils.h"
#define DEFENSE_START_DELAYS(Mode, Dodge) \
bool UProphecyNNDefenseLibrary::Set##Mode##StartHitThresholds(AProphecyAgent* Agent, \
    int32 Headbutt,int32 HookL,int32 HookR,int32 JabL,int32 JabR,int32 KickL,int32 KickR, \
    int32 OverL,int32 OverR,int32 Pike,int32 SlashL,int32 SlashLD,int32 SlashLU,int32 SlashR,int32 SlashRD,int32 SlashRU) \
{ \
    const int32 Values[]={Headbutt,HookL,HookR,JabL,JabR,KickL,KickR,OverL,OverR,Pike,SlashL,SlashLD,SlashLU,SlashR,SlashRD,SlashRU}; \
    return ProphecyDefenseArmedGate::SetStartDelays(Agent,Dodge,Values); \
}
DEFENSE_START_DELAYS(Parry,false)
DEFENSE_START_DELAYS(Dodge,true)
#undef DEFENSE_START_DELAYS
bool UProphecyNNDefenseLibrary::SetDefenseHalfAttackHorizontalVelocity(AProphecyAgent* Agent,bool bRemove,bool bUseRootVelocity)
{ return ProphecyDefenseControls::SetRemoveHorizontalVelocity(Agent,bRemove,bUseRootVelocity); }
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
bool UProphecyNNDefenseLibrary::VisualizeDefenseInputGhost(AProphecyAgent* Agent,bool Enabled,
    FVector WorldOffset,bool ShowPrevious,float Duration,float Thickness)
{
#if !UE_BUILD_SHIPPING
    if(!Enabled || WorldOffset.ContainsNaN() || !FMath::IsFinite(Duration) || Duration<0 || !FMath::IsFinite(Thickness) || Thickness<0)return false;
    auto* M=Manager(Agent);
    return M && M->DrawAgentDefenseInputGhost(Agent->GetAgentHandle(),WorldOffset,ShowPrevious,Duration,Thickness);
#else
    return false;
#endif
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
bool UProphecyNNDefenseLibrary::GetNNDefenseRelativeTarget(AProphecyAgent* Agent,FVector& WorldTarget,FVector& RootLocalTarget)
{ return ProphecyDefenseControls::GetRelativeTarget(Agent,WorldTarget,RootLocalTarget); }

#define DEFENSE_CLAMP(Mode, Dodge, Limb) \
bool UProphecyNNDefenseLibrary::Set##Mode##Limb##Clamp(AProphecyAgent* Agent,bool bEnabled,float LeewayCm) \
{ return ProphecyDefenseControls::Set(Agent,Dodge,ProphecyDefenseControls::ELimb::Limb,bEnabled,LeewayCm); }
DEFENSE_CLAMP(Parry,false,Foot)
DEFENSE_CLAMP(Parry,false,Calf)
DEFENSE_CLAMP(Dodge,true,Foot)
DEFENSE_CLAMP(Dodge,true,Calf)
#undef DEFENSE_CLAMP

bool UProphecyNNDefenseLibrary::SetDodgeFramesAfterHit(AProphecyAgent* Agent,int32 Frames)
{ return ProphecyDefenseControls::SetDodgeFramesAfterHit(Agent,Frames); }
int32 UProphecyNNDefenseLibrary::GetDodgeFramesAfterHit(AProphecyAgent* Agent)
{ return ProphecyDefenseControls::GetDodgeFramesAfterHit(Agent); }
bool UProphecyNNDefenseLibrary::SetDefenseFramesAfterHit(AProphecyAgent* Agent,int32 Frames)
{ return ProphecyDefenseControls::SetDefenseFramesAfterHit(Agent,Frames); }
void UProphecyNNDefenseLibrary::GetDefenseFramesAfterHit(AProphecyAgent* Agent,int32& DodgeFrames,int32& ParryFrames)
{ DodgeFrames=ProphecyDefenseControls::GetFramesAfterHit(Agent,true);ParryFrames=ProphecyDefenseControls::GetFramesAfterHit(Agent,false); }
