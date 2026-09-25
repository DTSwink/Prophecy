#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyLegRecovery
{
struct FStep { float MaxTurnRadians=0; bool Expired=false; };
void Begin(const AProphecyAgent* Agent);
void Cancel(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
bool Step(const AProphecyAgent* Agent,FStep& Out);
void FinishStep(const AProphecyAgent* Agent,bool Limited);
}
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
    bool FeetAreIdentity() const { return FeetTranslation==1.f && FeetTranslationZ==1.f && FeetRotation==1.f; }
    bool IsIdentity() const { return FeetTranslation == 1.f && FeetRotation == 1.f
        && PelvisTranslation == 1.f && PelvisRotation == 1.f
        && FeetTranslationZ == 1.f && PelvisTranslationZ == 1.f; }
};
void SelectAttackProfile(const AProphecyAgent* Agent,FName Attack);
void ClearAttackSelection(const AProphecyAgent* Agent);
void ForgetProfiles(const AProphecyAgent* Agent);
const FSettings* Find(const AProphecyAgent* Agent);
// Find samples the existing clocks first; this accessor reads the already sampled right foot.
const FSettings& RightFootSettings(const AProphecyAgent* Agent,const FSettings& Left);
void RestoreRightFootSettings(const AProphecyAgent* Agent,const FSettings& Right);
float MinimumLegReachMultiplier(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
}
