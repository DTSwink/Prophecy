#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecySpecialStart
{
bool Enabled(const AProphecyAgent* Agent);
struct FSeed
{
    TArray<FTransform,TInlineAllocator<32>> Previous,Current;
};
// False leaves the existing NN entry path intact, including when sampling is unavailable.
bool Sample(AProphecyAgent* Agent,TConstArrayView<FName> Names,
    const FTransform& PreviousCarrier,const FTransform& Carrier,float StepSeconds,FSeed& Out);
}
