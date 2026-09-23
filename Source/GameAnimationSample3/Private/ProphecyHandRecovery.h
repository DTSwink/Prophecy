#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyHandRecovery
{
struct FFollow
{
    float XY=1,Z=1,Rotation=1;
    bool Normal() const { return XY==1 && Z==1 && Rotation==1; }
};
struct FTempering { FFollow Hand[2];bool Normal() const { return Hand[0].Normal() && Hand[1].Normal(); } };
struct FFrame
{
    bool Need[2]={}; // 0 Run, 1 Walk.
    int32 Source[2]={};
    float Alpha[2]={1,1}; // Blend back to ordinary upper prediction.
    float Raw[2][43]={},Lower[2][41]={},Upper[2][90]={};
    bool Ready[2]={};
};
void Begin(const AProphecyAgent* Agent);
void CancelRecovery(const AProphecyAgent* Agent);
void CancelMotion(const AProphecyAgent* Agent);
void Remove(const AProphecyAgent* Agent);
void Step(const AProphecyAgent* Agent);
bool HasRecovery();
FFrame* Frame(const AProphecyAgent* Agent);
const FTempering* Tempering(const AProphecyAgent* Agent);
FTransform TemperTarget(const FFollow& Follow,const FTransform& PreviousReference,const FTransform& Reference,
    const FTransform& PreviousHand,const FTransform& Target);
void CaptureReset(const AProphecyAgent* Agent);
void RestoreReset(const AProphecyAgent* Agent);
void ForgetReset(const AProphecyAgent* Agent);
}
