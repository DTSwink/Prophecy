#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyAttackControls
{
bool IsStatic(const AProphecyAgent* Agent);
bool UsesRootBalancingTarget(const AProphecyAgent* Agent);
// Slash input layout: lower previous/current 41 each, upper previous/current 90 each.
inline void MakeHistoryStatic(TArrayView<float> State)
{
    check(State.Num() >= 262);
    FMemory::Memcpy(State.GetData(), State.GetData() + 41, 41 * sizeof(float));
    FMemory::Memcpy(State.GetData() + 82, State.GetData() + 172, 90 * sizeof(float));
}
bool ColliderRoles(FName Attack, TArray<FName>& Bones, bool& Sword);
}
