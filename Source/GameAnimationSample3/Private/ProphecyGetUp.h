#pragma once
#include "CoreMinimal.h"
#include "ProphecyGetUpLibrary.h"
#include "ProphecyLowerTempering.h"
#include "ProphecyHandRecovery.h"
#include "UObject/StrongObjectPtr.h"
class UAnimSequence;
namespace ProphecyGetUp
{
struct FTiming { float Hold=0,Duration=1; };
struct FProfile
{
    TWeakObjectPtr<UAnimSequence> Front,Back;
    float Entry=.35f,Magnetization=.35f,GroundOffset=0;
    EProphecyGetUpInterpolation EntryCurve=EProphecyGetUpInterpolation::SmoothStep;
    EProphecyGetUpInterpolation HandoffCurve=EProphecyGetUpInterpolation::SmoothStep;
    FName Snapshot=TEXT("1");
    float LowerStart=1,UpperStart=1,Core=1;
    ProphecyLowerTempering::FSettings Lower;
    ProphecyHandRecovery::FTempering Hands;
    FTiming Feet,Pelvis,Hand[2],CoreTime;
};
struct FActive
{
    FProfile Profile;
    TStrongObjectPtr<UAnimSequence> Animation;
    double Elapsed=0,ClipDuration=0,LastSample=-1;
    float Rate=1,Playback=0,FeetAlpha=0,PelvisAlpha=0,HandAlpha[2]={},CoreAlpha=0;
    ProphecyLowerTempering::FSettings Lower;
    ProphecyHandRecovery::FTempering Hands;
    float Core=1;
    FTransform Anchor,PreviousCarrier,CurrentCarrier;
    FTransform Snapshot[25],Previous[25],Current[25];
    bool Finished=false,Published=false;
};
bool IsActive(const AProphecyAgent* A);
bool FreezeInference(const AProphecyAgent* A);
bool OwnsLower(const AProphecyAgent* A);
FActive* Find(const AProphecyAgent* A);
FProfile Configured(const AProphecyAgent* A);
void Install(const AProphecyAgent* A,FActive&& State);
void Cancel(const AProphecyAgent* A);
void Remove(const AProphecyAgent* A);
void Advance(const AProphecyAgent* A);
void SampleTiming(FActive& S);
float Curve(float X,EProphecyGetUpInterpolation Type);
float Progress(double Elapsed,const FTiming& Timing,EProphecyGetUpInterpolation Type);
const ProphecyLowerTempering::FSettings* Lower(const AProphecyAgent* A);
const ProphecyHandRecovery::FTempering* Hands(const AProphecyAgent* A);
float Core(const AProphecyAgent* A);
}
