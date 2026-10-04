#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyCustomAttack
{
bool PlacePhysical(AProphecyAgent* Agent,TConstArrayView<FName> Names,
    TConstArrayView<FTransform> Previous,TConstArrayView<FTransform> Current,const FTransform& Carrier,FString& Error);
}
