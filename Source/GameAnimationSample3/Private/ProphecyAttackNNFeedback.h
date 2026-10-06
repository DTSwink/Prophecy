#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyAttackNNFeedback
{
enum : uint8 { StartCore=1,StartHand=2,Hand=4,Cone=8,Wrist=16,All=31 };
uint8 Mask(const AProphecyAgent* Agent);
inline bool Enabled(const AProphecyAgent* Agent,uint8 Bit){return (Mask(Agent)&Bit)!=0;}
void CaptureReset(const AProphecyAgent* Agent);
void RestoreReset(const AProphecyAgent* Agent);
void ForgetReset(const AProphecyAgent* Agent);
}
