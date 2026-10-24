#pragma once
#include "WheelModel.h"
#include "WheelOrnaments.h"
#include "Framework/Application/SlateApplication.h"
#include "Fonts/FontMeasure.h"
#include "Rendering/DrawElements.h"
#include "Rendering/SlateRenderer.h"
#include "Textures/SlateShaderResource.h"
#include "Styling/CoreStyle.h"

// All ornaments are geometry, not baked into the icons or background.
class FWheelPainter
{
    FSlateWindowElementList& Out;
    const FGeometry& G;
    int32 Layer;
    FSlateResourceHandle Resource;
    FVector2f WhiteUV = FVector2f(.5f,.5f);
    const FSlateBrush& SoftDisc;
    const FSlateBrush& OrbitShade;
    const FSlateBrush& NameVeil;
    const FSlateBrush& SelectionHalo;
    const FSlateBrush& GlowSpot;
public:
    const FLinearColor Ivory = FLinearColor(.98f, .975f, .96f, 1.f);
    FWheelPainter(FSlateWindowElementList& InOut, const FGeometry& InG, int32 InLayer, const FSlateBrush& Solid, const FSlateBrush& InSoftDisc, const FSlateBrush& InOrbitShade, const FSlateBrush& InNameVeil, const FSlateBrush& InSelectionHalo, const FSlateBrush& InGlowSpot) : Out(InOut), G(InG), Layer(InLayer), SoftDisc(InSoftDisc), OrbitShade(InOrbitShade), NameVeil(InNameVeil), SelectionHalo(InSelectionHalo), GlowSpot(InGlowSpot)
    {
        // Custom vertices need a real texture resource. CoreStyle's WhiteBrush
        // is a color-only brush and cannot provide one for this draw path.
        Resource = FSlateApplication::Get().GetRenderer()->GetResourceHandle(Solid);
        if(const auto* Proxy=Resource.GetResourceProxy()) WhiteUV=Proxy->StartUV+Proxy->SizeUV*.5f;
    }
    void NextLayer() { ++Layer; }
    int32 GetLayer() const { return Layer; }
    void Mesh(const TArray<FVector2f>& Points, const TArray<FColor>& Colors, const TArray<SlateIndex>& Indices)
    {
        TArray<FSlateVertex> Verts; Verts.Reserve(Points.Num());
        for (int32 I=0; I<Points.Num(); ++I)
            Verts.Add(FSlateVertex::Make<ESlateVertexRounding::Disabled>(G.GetAccumulatedRenderTransform(), Points[I], WhiteUV, Colors[I]));
        FSlateDrawElement::MakeCustomVerts(Out, Layer, Resource, Verts, Indices, nullptr, 0, 0);
    }
    void Line(const TArray<FVector2f>& P, FLinearColor Color, float Thickness=1.2f)
    { FSlateDrawElement::MakeLines(Out, Layer, G.ToPaintGeometry(), TArray<FVector2f>(P), ESlateDrawEffect::None, Color, true, Thickness); }
    void Arc(FVector2f Center, float Radius, float Start, float End, FLinearColor Color, float Thickness=1.2f, float Wobble=0.f)
    {
        TArray<FVector2f> P;
        const int32 Segments = FMath::Max(3, FMath::CeilToInt(FMath::DegreesToRadians(FMath::Abs(End-Start))*Radius/1.5f)); P.Reserve(Segments+1);
        for (int32 I=0; I<=Segments; ++I)
        {
            const float A = FMath::Lerp(Start, End, float(I)/Segments);
            const float R = Radius + Wobble*FMath::Sin(A*.073f);
            P.Add(Center + WheelLayout::Polar(A, R));
        }
        Line(P, Color, Thickness);
    }
    // An explicit one-screen-pixel coverage fringe prevents hard polygon edges
    // on stars and dots. World MSAA/TAA does not antialias Slate geometry.
    void FilledShape(FVector2f Center, const TArray<FVector2f>& Boundary, FLinearColor Color)
    {
        TArray<FVector2f> P{Center}; TArray<FColor> C{Color.ToFColor(true)}; TArray<SlateIndex> Idx;
        const int32 N=Boundary.Num();
        const float AA=.85f/FMath::Max(.1f,G.GetAccumulatedLayoutTransform().GetScale());
        auto Transparent=Color; Transparent.A=0;
        for(int32 I=0;I<N;++I) {P.Add(Boundary[I]);C.Add(Color.ToFColor(true));}
        for(int32 I=0;I<N;++I)
        {
            const auto Before=(Boundary[I]-Boundary[(I+N-1)%N]).GetSafeNormal();
            const auto After=(Boundary[(I+1)%N]-Boundary[I]).GetSafeNormal();
            const FVector2f N1(Before.Y,-Before.X), N2(After.Y,-After.X);
            const auto Bisector=(N1+N2).GetSafeNormal();
            const float Miter=FMath::Min(2.f,1.f/FMath::Max(.2f,FVector2f::DotProduct(Bisector,N1)));
            P.Add(Boundary[I]+Bisector*(AA*Miter)); C.Add(Transparent.ToFColor(true));
        }
        for(int32 I=0;I<N;++I)
        {
            const int32 A=1+I, B=1+(I+1)%N;
            Idx.Append({SlateIndex(0),SlateIndex(A),SlateIndex(B),SlateIndex(A),SlateIndex(A+N),SlateIndex(B+N),SlateIndex(A),SlateIndex(B+N),SlateIndex(B)});
        }
        Mesh(P,C,Idx);
    }
    void Disk(FVector2f Center, float Radius, FLinearColor Color)
    {
        TArray<FVector2f> Boundary;
        for(int32 I=0;I<48;++I) Boundary.Add(Center+WheelLayout::Polar(I*7.5f,Radius));
        FilledShape(Center,Boundary,Color);
    }
    void SoftDisk(FVector2f Center, FVector2f Radius, FLinearColor Color)
    {
        FSlateDrawElement::MakeBox(Out,Layer,G.ToPaintGeometry(Radius*2.f,FSlateLayoutTransform(Center-Radius)),&SoftDisc,ESlateDrawEffect::None,Color);
    }
    void Mask(const FSlateBrush& Brush,FVector2f Center,FVector2f Extent,FLinearColor Color)
    {
        FSlateDrawElement::MakeBox(Out,Layer,G.ToPaintGeometry(Extent*2.f,FSlateLayoutTransform(Center-Extent)),&Brush,ESlateDrawEffect::None,Color);
    }
    void Orbit(FVector2f Center,const FWheelOrbitStroke& S,FLinearColor Color)
    {
        TArray<FVector2f> Points;
        const int32 N=FMath::CeilToInt((S.End-S.Start)*PI/180.f*FMath::Max(S.Axes.X,S.Axes.Y)/1.5f);
        for(int32 I=0;I<=N;++I) Points.Add(Center+WheelOrnaments::Point(S,FMath::Lerp(S.Start,S.End,float(I)/N)));
        // A restrained ink shadow provides separation without making a bevel.
        Line(Points,FLinearColor(0,0,0,.16f*S.Opacity*Color.A),S.Width+1.1f);
        Color.A*=S.Opacity;
        Line(Points,Color,S.Width);
    }
    void Star(FVector2f Center, float Size, FLinearColor Color, float Rotation=0)
    {
        TArray<FVector2f> Boundary;
        for(int32 I=0; I<8; ++I)
            Boundary.Add(Center+WheelLayout::Polar(-90.f+I*45.f+Rotation,Size*(I%2 ? .27f : 1.f)));
        FilledShape(Center,Boundary,Color);
    }
    void Crescent(FVector2f Center,float Radius,float Start,float End,float Width,FLinearColor Color)
    {
        TArray<FVector2f> P; TArray<FColor> C; TArray<SlateIndex> Indices;
        const int32 N=FMath::CeilToInt((End-Start)*Radius*PI/180.f/1.5f);
        const float AA=.9f/FMath::Max(.1f,G.GetAccumulatedLayoutTransform().GetScale());
        auto Transparent=Color; Transparent.A=0;
        for(int32 I=0;I<=N;++I)
        {
            const float T=float(I)/N;
            const float A=FMath::Lerp(Start,End,T);
            const float Half=.5f*Width*FMath::Pow(FMath::Max(0.f,FMath::Sin(PI*T)),.65f);
            const float R=Radius+.65f*FMath::Sin(A*.077f);
            for(float Offset : {Half+AA,Half,-Half,-Half-AA}) P.Add(Center+WheelLayout::Polar(A,R+Offset));
            auto Ink=Color; if(I==0 || I==N) Ink.A=0;
            C.Append({Transparent.ToFColor(true),Ink.ToFColor(true),Ink.ToFColor(true),Transparent.ToFColor(true)});
            if(I<N) for(int32 K=0;K<3;++K)
            {
                const int32 B=I*4+K;
                Indices.Append({SlateIndex(B),SlateIndex(B+4),SlateIndex(B+5),SlateIndex(B),SlateIndex(B+5),SlateIndex(B+1)});
            }
        }
        Mesh(P,C,Indices);
    }
    void Icon(FVector2f Center, float Size, const FSlateBrush& Brush)
    {
        FSlateDrawElement::MakeBox(Out, Layer, G.ToPaintGeometry(FVector2f(Size,Size),FSlateLayoutTransform(Center-FVector2f(Size*.5f))), &Brush, ESlateDrawEffect::None, FLinearColor::White);
    }
    FSlateFontInfo LabelFont(int32 FontSize)
    {
        // Local prototype uses the OS font without redistributing it.
        static const FString FontPath = FPaths::FileExists(TEXT("C:/Windows/Fonts/georgia.ttf")) ? TEXT("C:/Windows/Fonts/georgia.ttf") : FPaths::EngineContentDir()/TEXT("Slate/Fonts/Roboto-Regular.ttf");
        static const TSharedPtr<const FCompositeFont> Typeface = MakeShared<FCompositeFont>(FName(TEXT("Regular")),FontPath,EFontHinting::Default,EFontLoadingPolicy::LazyLoad);
        return FSlateFontInfo(Typeface, FontSize, TEXT("Regular"));
    }
    float LabelWidth(const FString& Text, const FSlateFontInfo& Font)
    {
        const auto Measure=FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
        const float Tracking=5.f;
        float Width=-Tracking;
        for(TCHAR Character : Text) Width+=Measure->Measure(FString::Chr(Character),Font).X+Tracking;
        return Width;
    }
    void Label(const FString& Text, FVector2f Center, int32 FontSize, FLinearColor Color)
    {
        const auto Font=LabelFont(FontSize);
        const auto Measure=FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
        const float Tracking=5.f;
        const float Width=LabelWidth(Text,Font);
        float X=Center.X-Width*.5f;
        for(TCHAR Character : Text)
        {
            const FString Glyph=FString::Chr(Character);
            const FVector2f Size(Measure->Measure(Glyph,Font));
            FSlateDrawElement::MakeText(Out,Layer,G.ToPaintGeometry(Size,FSlateLayoutTransform(FVector2f(X,Center.Y-Size.Y*.5f))),Glyph,Font,ESlateDrawEffect::None,Color);
            X+=Size.X+Tracking;
        }
    }
    void DrawWheel(const FWheelModel& M, const TArray<FSlateBrush>& Icons)
    {
        const auto Center = WheelLayout::Center();
        auto CenterInk=Ivory; CenterInk.A=M.CenterBrightness;
        auto CircleInk=Ivory; CircleInk.A=M.CircleBrightness;
        auto ConnectingInk=Ivory; ConnectingInk.A=M.ConnectingBrightness;
        const FVector2f Extent(M.Radius+100.f);
        FSlateDrawElement::MakeBox(Out,Layer,G.ToPaintGeometry(Extent*2.f,FSlateLayoutTransform(Center-Extent)),&OrbitShade,ESlateDrawEffect::None,FLinearColor(.003f,.003f,.004f,M.ArcShadow));
        for(int32 I=0;I<8;++I) SoftDisk(WheelLayout::Slot(I,M.Radius),FVector2f(108.f,112.f),FLinearColor(.003f,.003f,.004f,M.Shadow));
        Mask(NameVeil,Center,FVector2f(245.f,112.f),FLinearColor(.003f,.003f,.004f,M.LabelShadow));
        NextLayer();
        for(int32 I=0;I<8;++I)
        {
            const float A=-90.f+I*45.f;
            const float OuterRadius=M.Radius+34.f;
            const float JoinAngle=FMath::RadiansToDegrees(FMath::Acos((M.Radius*M.Radius+OuterRadius*OuterRadius-73.f*73.f)/(2.f*M.Radius*OuterRadius)));
            Arc(Center,OuterRadius,A+JoinAngle,A+45.f-JoinAngle,ConnectingInk,1.9f);
            auto Faint=ConnectingInk; Faint.A*=.78f;
            Arc(Center,M.Radius-11.f,A+14.5f,A+30.5f,Faint,1.1f);
            // Stars sit precisely ON their carrying arc, with deliberately varied
            // scale and spacing. No uniform row of floating plus signs.
            static const bool InnerStar[]={true,false,true,false,false,true,false,true};
            static const float StarAt[]={.64f,.54f,.46f,.66f,.47f,.53f,.44f,.67f};
            static const float StarSizes[]={13,10,12,15,11,12,14,11};
            const float StarA=A+FMath::Lerp(InnerStar[I]?14.5f:JoinAngle,InnerStar[I]?30.5f:45.f-JoinAngle,StarAt[I]);
            Star(Center+WheelLayout::Polar(StarA,InnerStar[I]?M.Radius-11.f:OuterRadius),StarSizes[I],ConnectingInk);
            const float PearlA=A+FMath::Lerp(JoinAngle+1,44.f-JoinAngle,I%3==0?.24f:.78f);
            Disk(Center+WheelLayout::Polar(PearlA,OuterRadius),I%3==1?4.8f:3.8f,ConnectingInk);
            Disk(Center+WheelLayout::Polar(PearlA+(I%2?-3.5f:3.5f),OuterRadius),1.3f,Faint);
            const auto P=WheelLayout::Slot(I,M.Radius);
            const auto& Profile=WheelOrnaments::Ring(I);
            Orbit(P,Profile.Outer,CircleInk);
            Orbit(P,Profile.Inner,CircleInk);
            Orbit(P,Profile.Echo,CircleInk);
            for(int32 K=0;K<4;++K)
                Disk(P+WheelOrnaments::Point(Profile.Outer,Profile.Pearls[K]),K==0?4.9f:(K==2?4.1f:2.6f),CircleInk);
            // Short constellations of pinpoints, not a dashed second perimeter.
            static const float DustT[]={0,.13f,.31f,.37f,.72f,1};
            auto Dust=CircleInk; Dust.A*=.64f;
            for(int32 K=0;K<6;++K)
                Disk(P+WheelOrnaments::Point(Profile.Echo,FMath::Lerp(Profile.DustStart,Profile.DustEnd,DustT[K])),K==2?1.15f:.65f,Dust);
        }
        NextLayer();
        const auto Selected=WheelLayout::Slot(M.Selected,M.Radius);
        auto Accent=[&M](float White,float Alpha)
        { auto Color=FMath::Lerp(M.SelectionColor,FLinearColor::White,White); Color.A=Alpha; return Color; };
        Mask(SelectionHalo,Selected,FVector2f(128.f),Accent(0,.65f*M.SelectionGlow));
        Crescent(Selected,86.f,-117.f,88.f,4.4f,Accent(.4f,.98f));
        Crescent(Selected,85.4f,-109.f,80.f,1.05f,Accent(.83f,.98f));
        Crescent(Selected,91.f,-112.f,76.f,1.3f,Accent(.3f,.88f));
        Crescent(Selected,79.5f,-98.f,73.f,1.2f,Accent(.75f,.86f));
        Crescent(Selected,95.f,-128.f,-72.f,1.1f,Accent(.2f,.7f));
        NextLayer();
        for(int32 I=0;I<8;++I) if(Icons.IsValidIndex(M.Items[I].AtlasCell)) Icon(WheelLayout::Slot(I,M.Radius),M.IconSize,Icons[M.Items[I].AtlasCell]);
        NextLayer();
        for(int32 I=0;I<8;++I)
        {
            const auto& Profile=WheelOrnaments::Ring(I);
            Star(WheelLayout::Slot(I,M.Radius)+WheelOrnaments::Point(Profile.Outer,Profile.StarAngle),Profile.StarSize,CircleInk);
        }
        const auto Spark=Selected+WheelLayout::Polar(-39.f,86.f);
        Mask(GlowSpot,Spark,FVector2f(51.f),Accent(.6f,.5f*M.SelectionGlow));
        Mask(GlowSpot,Spark,FVector2f(26.f),FLinearColor(1.f,.84f,.49f,.58f*M.SelectionGlow));
        Star(Spark,25.f,FLinearColor(1.f,.98f,.9f,1.f));
        // The fuse spark follows icon size; it is not left floating on the ring.
        const auto Bomb=WheelLayout::Slot(0,M.Radius);
        const auto Fuse=Bomb+FVector2f(.32f,-.28f)*M.IconSize;
        Star(Fuse,17.f,CircleInk,11.f);
        auto Ray=CircleInk; Ray.A*=.8f;
        for(float A : {-131.f,-67.f,3.f,61.f,153.f})
            Line({Fuse+WheelLayout::Polar(A,20.f),Fuse+WheelLayout::Polar(A,27.f)},Ray,.8f);
        const FString& Name=M.Items[M.Selected].Label;
        Label(Name,Center,FMath::RoundToInt(M.CenterFontSize),CenterInk);
        const float D=M.CenterDecorationSize;
        if(D>0.f)
        {
            // The ornament layout uses the original 22-point label width, never
            // the live font size. Text and decoration sliders are independent.
            const float Wing=LabelWidth(Name,LabelFont(22))*.5f+17.f;
            Star(Center+FVector2f(0,-43)*D,12.f*D,CenterInk);
            Star(Center+FVector2f(0,43)*D,12.f*D,CenterInk);
            for(int32 Side : {-1,1})
            {
                const auto DiamondCenter=Center+FVector2f(Side*Wing,0)*D;
                FilledShape(DiamondCenter,{DiamondCenter+FVector2f(0,-6)*D,DiamondCenter+FVector2f(4.5f,0)*D,DiamondCenter+FVector2f(0,6)*D,DiamondCenter+FVector2f(-4.5f,0)*D},CenterInk);
                Line({Center+FVector2f(Side*(Wing+12.f),0)*D,Center+FVector2f(Side*(Wing+60.f),0)*D},CenterInk,1.3f*D);
            }
        }
    }
};
