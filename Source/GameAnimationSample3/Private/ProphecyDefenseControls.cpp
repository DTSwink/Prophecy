#include "ProphecyDefenseControls.h"
#include "ProphecyAgent.h"
namespace ProphecyDefenseControls
{
namespace { struct FPair { FSettings Modes[2]; }; TMap<TWeakObjectPtr<const AProphecyAgent>,FPair> Settings; }
namespace { TMap<TWeakObjectPtr<const AProphecyAgent>,int32> DodgeHitDelays; }
const FSettings* Find(const AProphecyAgent* Agent,bool bDodge)
{ const auto* Pair=Settings.Find(Agent);return Pair?&Pair->Modes[bDodge?1:0]:nullptr; }
bool Set(AProphecyAgent* Agent,bool bDodge,ELimb Limb,bool bEnabled,float LeewayCm)
{
    if (!IsInGameThread() || !IsValid(Agent) || !FMath::IsFinite(LeewayCm) || LeewayCm<0) return false;
    auto& Mode=Settings.FindOrAdd(Agent).Modes[bDodge?1:0];
    auto& Clamp=Limb==ELimb::Foot?Mode.Foot:Limb==ELimb::Calf?Mode.Calf:Limb==ELimb::Hand?Mode.Hand:Mode.Forearm;
    Clamp={true,bEnabled,LeewayCm};return true;
}
bool SetDodgeFramesAfterHit(AProphecyAgent* Agent,int32 Frames)
{
    if (!IsInGameThread() || !IsValid(Agent) || Frames<0) return false;
    if (Frames==1) DodgeHitDelays.Remove(Agent);else DodgeHitDelays.Add(Agent,Frames);
    return true;
}
int32 GetDodgeFramesAfterHit(const AProphecyAgent* Agent)
{ const int32* Frames=DodgeHitDelays.Find(Agent);return Frames?*Frames:1; }
void Remove(const AProphecyAgent* Agent) { Settings.Remove(Agent);DodgeHitDelays.Remove(Agent); }
}
