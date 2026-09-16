#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyWalkPinning
{
struct FSettings
{
    float Tolerance=0,Fallback=0;
    bool Apply(float Left,float Right,float PinScale,float& LeftPin,float& RightPin) const
    {
        if (Tolerance<=0 || Left<=0 || Right<=0 || !FMath::IsFinite(Left) || !FMath::IsFinite(Right)
            || FMath::Abs(Left-Right)>Tolerance) return false;
        LeftPin=RightPin=0;
        if (Fallback>0)
        {
            LeftPin=Fallback/(1.f+FMath::Exp(Left*PinScale));
            RightPin=Fallback/(1.f+FMath::Exp(Right*PinScale));
        }
        return true;
    }
};
bool Apply(const AProphecyAgent* Agent,float Left,float Right,float PinScale,float& LeftPin,float& RightPin);
}
