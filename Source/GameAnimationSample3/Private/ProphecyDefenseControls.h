#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyDefenseControls
{
enum class ELimb : uint8 { Foot, Calf, Hand, Forearm };
struct FClamp { bool bOverride=false,bEnabled=false; float LeewayCm=0; };
struct FSettings { FClamp Foot,Calf,Hand,Forearm; };
const FSettings* Find(const AProphecyAgent* Agent,bool bDodge);
bool Set(AProphecyAgent* Agent,bool bDodge,ELimb Limb,bool bEnabled,float LeewayCm);
void RestoreClamp(AProphecyAgent* Agent,bool bDodge,ELimb Limb,FClamp Value);
bool SetDodgeFramesAfterHit(AProphecyAgent* Agent,int32 Frames);
int32 GetDodgeFramesAfterHit(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
}
