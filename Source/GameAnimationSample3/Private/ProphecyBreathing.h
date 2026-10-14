#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
enum class EProphecyBreathingMode : uint8;
namespace ProphecyBreathing
{
EProphecyBreathingMode Apply(const AProphecyAgent* Agent,uint64 GameTick,bool Eligible,
    TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TArrayView<FTransform> Current,TArrayView<FTransform> Local);
void Reset(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
}
