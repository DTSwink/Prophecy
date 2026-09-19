#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyLowerTempering
{
struct FSettings
{
    float FeetTranslation = 1.f, FeetRotation = 1.f;
    float PelvisTranslation = 1.f, PelvisRotation = 1.f;
    bool IsIdentity() const { return FeetTranslation == 1.f && FeetRotation == 1.f
        && PelvisTranslation == 1.f && PelvisRotation == 1.f; }
};
const FSettings* Find(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
}
