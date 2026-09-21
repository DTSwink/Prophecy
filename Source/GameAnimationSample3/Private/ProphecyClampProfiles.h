#pragma once
#include "CoreMinimal.h"
#include "ProphecyClampProfileLibrary.h"
#include "ProphecyDefenseControls.h"
namespace ProphecyClampProfiles
{
using EMode=EProphecyClampProfileMode;
using ELimb=ProphecyDefenseControls::ELimb;
void Save(AProphecyAgent* Agent,FName Name);
int32 Restore(AProphecyAgent* Agent,FName Name,EMode Mode,int32 Limb,float Duration);
void Cancel(const AProphecyAgent* Agent,EMode Mode=EMode::All,int32 Limb=-1);
void Remove(const AProphecyAgent* Agent);
void Delete(const AProphecyAgent* Agent,FName Name);
FString Debug(const AProphecyAgent* Agent,FName Bone);
}
