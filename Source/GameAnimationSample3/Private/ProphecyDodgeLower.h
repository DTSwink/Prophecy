#pragma once
#include "ProphecyDodgeRuntime.h"

namespace ProphecyDefense
{
struct FDodgeLowerSettings
{
    float PoseDeltaScale=2.f/30.f,SpeedScale=5.f/30.f,TurnScale=4.f*PI/30.f;
    float Ground=0,SideBlend=8.f*PI/180.f,FullHeight=.015f,FadeHeight=.020f,MinimumPin=1.f;
    int32 IntegrationSteps=60;
    bool bLegacyPin=false,bHeightGate=false;
    bool Load(const FString& Filename,const FString& Policy,FString& Error);
};
void DodgeLowerInput(const FDodgeState& State,const FDodgeLowerSettings& Settings,float* Out152);
void CleanDodgeLower(const float* Raw43,const float* Current,const FGeometry& Geometry,
    const FDodgeLowerSettings& Settings,float* Out41,float* Pins2);
}
