#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyLegChainDebug
{
bool IsEnabled(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
}
namespace ProphecyLowerTempering
{
struct FSettings
{
    float FeetTranslation = 1.f, FeetRotation = 1.f;
    float PelvisTranslation = 1.f, PelvisRotation = 1.f;
    float FeetTranslationZ = 1.f, PelvisTranslationZ = 1.f;
    FSettings() = default;
    FSettings(float FeetXY,float FeetR,float PelvisXY,float PelvisR)
        : FeetTranslation(FeetXY),FeetRotation(FeetR),PelvisTranslation(PelvisXY),PelvisRotation(PelvisR),
          FeetTranslationZ(FeetXY),PelvisTranslationZ(PelvisXY) {}
    FSettings(float FeetXY,float FeetR,float PelvisXY,float PelvisR,float FeetZ,float PelvisZ)
        : FeetTranslation(FeetXY),FeetRotation(FeetR),PelvisTranslation(PelvisXY),PelvisRotation(PelvisR),
          FeetTranslationZ(FeetZ),PelvisTranslationZ(PelvisZ) {}
    bool IsIdentity() const { return FeetTranslation == 1.f && FeetRotation == 1.f
        && PelvisTranslation == 1.f && PelvisRotation == 1.f
        && FeetTranslationZ == 1.f && PelvisTranslationZ == 1.f; }
};
const FSettings* Find(const AProphecyAgent* Agent);
float MinimumLegReachMultiplier(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
}
