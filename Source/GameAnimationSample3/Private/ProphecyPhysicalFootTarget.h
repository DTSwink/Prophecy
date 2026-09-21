#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyPhysicalFootTarget
{
float Leeway(const AProphecyAgent* Agent);
inline FVector Clamp(const FVector& Target, const FVector& CalfEnd, float LeewayCm)
{
    if (LeewayCm<=0.f) return CalfEnd;
    const FVector Offset=Target-CalfEnd;
    if (Offset.SizeSquared()<=double(LeewayCm)*LeewayCm) return Target;
    return CalfEnd+Offset.GetSafeNormal()*LeewayCm;
}
}
