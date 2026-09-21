#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
struct FProphecyJoltBodyHandle;

namespace ProphecyJointDamping
{
// Called by the existing pre-physics coordinator; no additional tick or subsystem.
bool Update(AProphecyAgent* Agent,const FProphecyJoltBodyHandle& RigBody,FString& Error);
void Remove(const AProphecyAgent* Agent);
bool Validate(const AProphecyAgent* Agent,FName Bone);
bool Get(const AProphecyAgent* Agent,FName Bone,float& Value);
bool GetProfile(const AProphecyAgent* Agent,FName Bone,float (&Values)[4]);
bool ApplyValue(AProphecyAgent* Agent,FName Bone,float Value);
void ReleasePolicy(const AProphecyAgent* Agent,FName Bone);
}
