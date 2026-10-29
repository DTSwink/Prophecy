#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyThrow
{
bool AnyActive();
bool Active(const AProphecyAgent* Agent);
bool Apply(AProphecyAgent* Agent,TConstArrayView<FName> Names,TConstArrayView<int32> Parents,
    TArrayView<FTransform> Previous,TArrayView<FTransform> Current,TArrayView<FTransform> Local,
    const FTransform& ComponentWorld,double SourceTime);
}
