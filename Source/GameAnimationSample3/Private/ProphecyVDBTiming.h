#pragma once
#include "CoreMinimal.h"

namespace ProphecyVDB
{
inline uint64 DurationTicks(double Seconds)
{
    return uint64(FMath::Max(0., FMath::CeilToDouble(Seconds*60.-1.e-5)));
}
struct FTimeline
{
    double Framerate=30;
    uint64 FadeStart=0, FadeDuration=0, Finish=0;
    int32 FrameCount=1;
    float TargetDensity=0;
    void Init(int32 Frames,double FPS,double Start,double Duration,float Target)
    {
        FrameCount=Frames; Framerate=FPS; TargetDensity=Target;
        FadeStart=DurationTicks(Start); FadeDuration=DurationTicks(Duration);
        Finish=FMath::Max(DurationTicks(double(Frames)/FPS),FadeStart+FadeDuration);
    }
    float Frame(uint64 Tick) const
    {
        return float(FMath::Min(double(FrameCount-1),double(Tick)*Framerate/60.));
    }
    float Density(uint64 Tick) const
    {
        if(Tick<FadeStart)return 1.f;
        if(Tick-FadeStart>=FadeDuration)return TargetDensity;
        const double Alpha=double(Tick-FadeStart)/double(FadeDuration);
        return float(1.+(double(TargetDensity)-1.)*Alpha);
    }
};
}
