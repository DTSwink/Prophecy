#pragma once
#include "CoreMinimal.h"

// Hand-authored decoration around fixed, evenly spaced weapon centers. These
// profiles carry visual variation only; selection and circular layout stay exact.
struct FWheelOrbitStroke
{
    FVector2f Offset;
    FVector2f Axes;
    float Tilt, Start, End, Width, Opacity;
};
struct FWheelRingProfile
{
    FWheelOrbitStroke Outer, Inner, Echo;
    float Pearls[4];
    float StarAngle, StarSize, DustStart, DustEnd;
};
namespace WheelOrnaments
{
    // Bomb, sword, dagger, spear, axe, mace, bow, shield. Long, unequal sweeps
    // replace repeating perimeter dashes. Inner arcs visibly weave underneath ink.
    inline const FWheelRingProfile& Ring(int32 I)
    {
        static const FWheelRingProfile Profiles[8]={
            {{{-2,1},{72,77},-12,-149,162,1.55f,1},{{3,0},{62,73},15,24,184,1.0f,.75f},{{-2,1},{81,81},-12,-170,-82,.8f,.65f},{-147,-66,30,111},75,9,-4,73},
            {{{0,1},{73,75},-8,-174,162,1.55f,1},{{-5,1},{66,78},-20,48,228,1.05f,.78f},{{3,-1},{80,77},5,118,197,.8f,.7f},{-159,-82,18,102},145,10,170,233},
            {{{1,0},{72,76},13,-124,211,1.5f,1},{{-3,-2},{62,75},-17,-55,109,1.0f,.78f},{{2,1},{81,78},9,80,168,.85f,.65f},{-120,-36,56,149},-62,13,189,256},
            {{{-1,1},{72,77},-19,-173,142,1.55f,1},{{4,2},{65,73},12,58,235,.95f,.76f},{{-2,0},{79,82},-10,-154,-61,.8f,.72f},{-167,-76,28,117},-10,11,146,213},
            {{{0,0},{73,76},8,-176,166,1.6f,1},{{-3,1},{65,78},-13,-35,125,1.05f,.8f},{{2,-1},{81,80},4,26,106,.8f,.7f},{-160,-61,36,131},-85,18,165,233},
            {{{-1,-1},{74,75},17,-155,172,1.55f,1},{{3,1},{65,74},-24,-119,57,1.f,.77f},{{0,0},{80,81},12,-26,75,.8f,.7f},{-141,-49,51,142},121,10,-185,-131},
            {{{1,0},{69,77},-8,-153,192,1.55f,1},{{-4,0},{61,73},18,2,195,1.f,.8f},{{-2,1},{77,81},-6,-140,-46,.8f,.68f},{-135,-41,47,139},180,16,164,225},
            {{{-1,0},{73,75},-6,-177,164,1.6f,1},{{2,-1},{65,72},13,-67,127,1.0f,.78f},{{0,1},{81,79},-8,25,113,.85f,.72f},{-157,-57,35,132},-93,13,167,223}
        };
        return Profiles[I%8];
    }
    inline FVector2f Point(const FWheelOrbitStroke& S,float Degrees)
    {
        const auto Unit=WheelLayout::Polar(Degrees,1.f);
        const FVector2f P(Unit.X*S.Axes.X,Unit.Y*S.Axes.Y);
        const auto Rot=WheelLayout::Polar(S.Tilt,1.f);
        return S.Offset+FVector2f(P.X*Rot.X-P.Y*Rot.Y,P.X*Rot.Y+P.Y*Rot.X);
    }
}
