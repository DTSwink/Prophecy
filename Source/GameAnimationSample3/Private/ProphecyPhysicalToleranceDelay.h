#pragma once
#include "CoreMinimal.h"
#include "ProphecyPhysicalContextTypes.h"
class AProphecyAgent;

namespace ProphecyPhysicalToleranceDelay
{
enum class EScope : uint8 { Single, Below, All };
bool Schedule(AProphecyAgent& Agent, EScope Scope, FName Bone, bool IncludeParent,
    float Linear, float Angular, EProphecyLocomotionSelection Locomotion,
    EProphecyEquipmentSelection Equipment, float Delay);
void Cancel(const AProphecyAgent* Agent);
// A delayed tolerance write may change the source of a snapshot return that
// is still holding; it must not cancel that scheduled return.
bool IsApplying(const AProphecyAgent* Agent);
}
