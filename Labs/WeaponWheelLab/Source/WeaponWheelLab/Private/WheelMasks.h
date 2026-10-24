#pragma once
#include "Brushes/SlateDynamicImageBrush.h"

// Small reusable masks, computed once. No scene bloom pass or ticking blur is
// needed for the UI highlight, and no hard-edged oval is used behind the name.
namespace WheelMasks
{
    template<typename F> TSharedPtr<FSlateDynamicImageBrush> Create(const TCHAR* Name,int32 W,int32 H,F Alpha)
    {
        TArray<uint8> Pixels; Pixels.SetNumUninitialized(W*H*4);
        for(int32 Y=0;Y<H;++Y) for(int32 X=0;X<W;++X)
        {
            const float U=(X+.5f)/W*2.f-1.f, V=(Y+.5f)/H*2.f-1.f;
            const int32 P=(Y*W+X)*4;
            Pixels[P]=Pixels[P+1]=Pixels[P+2]=255;
            Pixels[P+3]=uint8(FMath::RoundToInt(FMath::Clamp(Alpha(U,V),0.f,1.f)*255.f));
        }
        return FSlateDynamicImageBrush::CreateWithImageData(FName(Name),FVector2D(W,H),Pixels);
    }
    inline float Edge(float X)
    {
        const float T=FMath::Clamp((1.f-FMath::Abs(X))/.15f,0.f,1.f);
        return T*T*(3.f-2.f*T);
    }
    inline auto NameVeil()
    {
        return Create(TEXT("WheelNameVeil"),256,128,[](float X,float Y)
        {
            // Broad horizontal haze plus a small central falloff, no plateau.
            const float Wide=FMath::Exp(-3.8f*X*X-8.f*Y*Y);
            const float Core=FMath::Exp(-8.f*X*X-4.f*Y*Y);
            return (.58f*Wide+.42f*Core)*Edge(X)*Edge(Y);
        });
    }
    inline auto GlowSpot()
    {
        return Create(TEXT("WheelGlowSpot"),128,128,[](float X,float Y)
        {return FMath::Exp(-5.5f*(X*X+Y*Y))*Edge(X)*Edge(Y);});
    }
    inline auto SelectionHalo()
    {
        return Create(TEXT("WheelSelectionHalo"),256,256,[](float X,float Y)
        {
            const FVector2f P(X*128.f,Y*128.f);
            float A=FMath::RadiansToDegrees(FMath::Atan2(P.Y,P.X));
            if(A < -123.f) A+=360.f;
            if(A>94.f) return 0.f;
            const float T=(A+123.f)/217.f;
            const float Envelope=FMath::Pow(FMath::Max(0.f,FMath::Sin(T*PI)),.65f);
            const float D=P.Size()-86.f;
            return Envelope*(.62f*FMath::Exp(-D*D/65.f)+.24f*FMath::Exp(-D*D/360.f));
        });
    }
}
