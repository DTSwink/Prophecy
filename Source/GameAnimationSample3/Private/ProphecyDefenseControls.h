#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
struct FProphecyNNDefenseStatus;
namespace ProphecyDefenseFeatures { struct FContext; }
namespace ProphecyDefenseControls
{
enum class ELimb : uint8 { Foot, Calf };
struct FClamp { bool bOverride=false,bEnabled=false; float LeewayCm=0; };
struct FSettings { FClamp Foot,Calf; };
const FSettings* Find(const AProphecyAgent* Agent,bool bDodge);
bool Set(AProphecyAgent* Agent,bool bDodge,ELimb Limb,bool bEnabled,float LeewayCm);
void RestoreClamp(AProphecyAgent* Agent,bool bDodge,ELimb Limb,FClamp Value);
bool SetDodgeFramesAfterHit(AProphecyAgent* Agent,int32 Frames);
int32 GetDodgeFramesAfterHit(const AProphecyAgent* Agent);
bool SetDefenseFramesAfterHit(AProphecyAgent* Agent,int32 Frames);
int32 GetFramesAfterHit(const AProphecyAgent* Agent,bool bDodge);
void CaptureRelativeTarget(AProphecyAgent* Agent,const FVector& WorldTarget,const FProphecyNNDefenseStatus& Status);
void ClearRelativeTarget(const AProphecyAgent* Agent);
bool GetRelativeTarget(const AProphecyAgent* Agent,FVector& WorldTarget,FVector& RootLocalTarget);
void Remove(const AProphecyAgent* Agent);
bool SetRemoveHorizontalVelocity(AProphecyAgent* Agent,bool Enabled,bool UseRoot=false);
void FilterHalfAttack(const AProphecyAgent* Agent,bool Half,ProphecyDefenseFeatures::FContext& Context,
    const FVector3f& PreviousRoot,const FVector3f& CurrentRoot);
}
