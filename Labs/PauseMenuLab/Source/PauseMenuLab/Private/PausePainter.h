#pragma once
#include "PauseModel.h"
#include "Brushes/SlateDynamicImageBrush.h"
#include "Framework/Application/SlateApplication.h"
#include "Fonts/FontMeasure.h"
#include "Fonts/FontCache.h"
#include "Rendering/DrawElements.h"
#include "Rendering/SlateRenderer.h"
#include "Textures/SlateShaderResource.h"

// Small reusable masks; no full-screen generated UI texture.
struct FPauseArt {
 TSharedPtr<FSlateDynamicImageBrush> Gradient,Glow,Solid;
 TSharedPtr<const FCompositeFont> DisplayFont,TextFont;
 TArray<TSharedPtr<const FCompositeFont>> MenuFonts;
 FSlateFontInfo MenuFont(float Size,float Strength)const{return FSlateFontInfo(MenuFonts[FMath::Clamp(FMath::RoundToInt(Strength*18),0,18)],Size);}
 FSlateRect MenuBounds(const FPauseModel& M,int32 Index)const {
  const auto F=MenuFont(18*M.MenuSize,M.MenuHairlineStrength);
  const auto SpacingFont=MenuFont(18*M.MenuSize,14.f/18.f);
  auto Renderer=FSlateApplication::Get().GetRenderer();
  auto& Chars=Renderer->GetFontCache()->GetCharacterList(F,1.f);
  const auto Measure=Renderer->GetFontMeasureService();
  const auto Origin=PauseLayout::Row(M,Index);
  float X=Origin.X;FSlateRect Bounds(FLT_MAX,FLT_MAX,-FLT_MAX,-FLT_MAX);
  for(TCHAR C:M.Labels[Index]){
   const auto E=Chars.GetCharacter(C,F.FontFallback);
   if(E.Valid&&E.USize&&E.VSize&&!FChar::IsWhitespace(C)){
    const float Left=X+E.HorizontalOffset;
    const float Top=Origin.Y-E.VerticalOffset+Chars.GetMaxHeight()+E.GlobalDescender;
    Bounds.Left=FMath::Min(Bounds.Left,Left);Bounds.Top=FMath::Min(Bounds.Top,Top);
    Bounds.Right=FMath::Max(Bounds.Right,Left+E.USize);Bounds.Bottom=FMath::Max(Bounds.Bottom,Top+E.VSize);
   }
   X+=Measure->Measure(FString::Chr(C),SpacingFont).X+M.Tracking;
  }
  // One design pixel of edge forgiveness; no full-row hit volume.
  return FSlateRect(Bounds.Left-1,Bounds.Top-1,Bounds.Right+1,Bounds.Bottom+1);
 }
 FPauseArt() {
  auto Mask=[](const TCHAR* Name,int32 W,int32 H,TFunctionRef<float(float,float)> Sample){
   TArray<uint8> P;P.SetNumUninitialized(W*H*4);
   for(int32 Y=0;Y<H;++Y)for(int32 X=0;X<W;++X){int32 I=(Y*W+X)*4;P[I]=P[I+1]=P[I+2]=255;P[I+3]=uint8(FMath::Clamp(Sample(float(X)/(W-1),float(Y)/(H-1))*255.f,0.f,255.f));}
   return FSlateDynamicImageBrush::CreateWithImageData(FName(Name),FVector2D(W,H),P);
  };
  Gradient=Mask(TEXT("PauseGradient"),512,2,[](float X,float){return 1-X*X*(3-2*X);});
  Glow=Mask(TEXT("PauseGlow"),128,128,[](float X,float Y){return FMath::Max(0.f,(FMath::Exp(-6.f*(FMath::Square(X*2-1)+FMath::Square(Y*2-1)))-.0025f)/.9975f);});
  Solid=Mask(TEXT("PauseWhite"),2,2,[](float,float){return 1.f;});
  DisplayFont=MakeShared<FCompositeFont>(FName("Regular"),FPaths::ProjectDir()/TEXT("Resources/Fonts/AnticDidone-Regular.ttf"),EFontHinting::AutoLight,EFontLoadingPolicy::LazyLoad);
  TextFont=MakeShared<FCompositeFont>(FName("Regular"),FPaths::ProjectDir()/TEXT("Resources/Fonts/BodoniModa-Text.ttf"),EFontHinting::AutoLight,EFontLoadingPolicy::LazyLoad);
  for(int32 Optical=24;Optical>=6;--Optical)
   MenuFonts.Add(MakeShared<FCompositeFont>(FName("Regular"),FPaths::ProjectDir()/FString::Printf(TEXT("Resources/Fonts/BodoniModa-Optical-%d.ttf"),Optical),EFontHinting::AutoLight,EFontLoadingPolicy::LazyLoad));
 }
};

class FPausePainter {
 FSlateWindowElementList& Out; const FGeometry& G; int32 L;
 const FPauseArt& Art;
 FSlateFontInfo Font(bool Display,float Size) const {return FSlateFontInfo(Display?Art.DisplayFont:Art.TextFont,Size);}
 void Box(const FSlateBrush& B,FVector2f P,FVector2f S,FLinearColor C) const {FSlateDrawElement::MakeBox(Out,L,G.ToPaintGeometry(S,FSlateLayoutTransform(P)),&B,ESlateDrawEffect::None,C);}
 void Line(FVector2f A,FVector2f B,FLinearColor C,float W=1)const {FSlateDrawElement::MakeLines(Out,L,G.ToPaintGeometry(),TArray<FVector2f>{A,B},ESlateDrawEffect::None,C,true,W);}
 void Star(FVector2f Center,float Radius,FLinearColor Color) const {
  auto Resource=FSlateApplication::Get().GetRenderer()->GetResourceHandle(*Art.Solid);
  TArray<FSlateVertex> V; TArray<SlateIndex> I;
  const auto T=G.GetAccumulatedRenderTransform();FColor C=Color.ToFColor(true),Transparent=C;Transparent.A=0;
  auto Vert=[&](FVector2f P,FColor Col){V.Add(FSlateVertex::Make<ESlateVertexRounding::Disabled>(T,P,FVector2f(.5f,.5f),Col));};
  Vert(Center,C);
  const float AA=.7f/G.GetAccumulatedLayoutTransform().GetScale();
  for(int32 K=0;K<8;++K){float A=(-90+45*K)*PI/180;float R=Radius*(K%2?.14f:1);Vert(Center+FVector2f(.7f*FMath::Cos(A),FMath::Sin(A))*R,C);}
  for(int32 K=0;K<8;++K){float A=(-90+45*K)*PI/180;float R=Radius*(K%2?.14f:1)+AA;Vert(Center+FVector2f(.7f*FMath::Cos(A),FMath::Sin(A))*R,Transparent);}
  for(int32 K=0;K<8;++K){SlateIndex A=1+K,B=1+(K+1)%8;I.Append({0,A,B,A,SlateIndex(A+8),SlateIndex(B+8),A,SlateIndex(B+8),B});}
  FSlateDrawElement::MakeCustomVerts(Out,L,Resource,V,I,nullptr,0,0);
 }
public:
 FPausePainter(FSlateWindowElementList& O,const FGeometry& InG,int32 Layer,const FPauseArt& A):Out(O),G(InG),L(Layer),Art(A){}
 float Text(const FString& S,FVector2f P,float Size,float Tracking,FLinearColor C,float HairlineStrength=-1) const {
  // Actual authored outlines: optical size24 to6, weight400 throughout.
  const auto F=HairlineStrength<0?Font(false,Size):Art.MenuFont(Size,HairlineStrength);
  // Keep the approved Medium layout fixed; only glyph outlines change.
  const auto SpacingFont=HairlineStrength<0?F:Art.MenuFont(Size,14.f/18.f);
  const auto Measure=FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
  float X=P.X;
  for(int32 I=0;I<S.Len();++I){const FString Char=S.Mid(I,1);FSlateDrawElement::MakeText(Out,L,G.ToPaintGeometry(FVector2f(800,100),FSlateLayoutTransform(FVector2f(X,P.Y))),Char,F,ESlateDrawEffect::None,C);X+=Measure->Measure(Char,SpacingFont).X+Tracking;}
  return X-P.X-Tracking;
 }
 int32 Draw(const FPauseModel& M) {
  Box(*Art.Gradient,FVector2f::ZeroVector,FVector2f(M.GradientWidth,941),FLinearColor(0,0,0,M.Darkness));++L;
  // Title fitted independently of menu text and ornaments.
  const auto F=Font(true,160);
  const auto Measure=FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
  const float Width=Measure->Measure(TEXT("PAUSED"),F).X;
  const FGeometry TitleG=G.MakeChild(FVector2D(1000,400),FSlateLayoutTransform(1,FVector2D(80,103)),FSlateRenderTransform(FScale2D(574.f/Width*M.TitleSize,M.TitleSize)),FVector2D::ZeroVector);
  FSlateDrawElement::MakeText(Out,L,TitleG.ToPaintGeometry(),TEXT("PAUSED"),F,ESlateDrawEffect::None,FLinearColor(.95f,.94f,.92f,1));
  ++L;
  for(int32 I=0;I<M.Labels.Num();++I){
   FLinearColor Ink(.96f,.95f,.93f,I==M.Selected?1.f:M.UnselectedTextOpacity);
   if(I==M.Selected)Ink=FMath::Lerp(Ink,FLinearColor::White,M.SelectedTextWhiteness);
   Text(M.Labels[I],PauseLayout::Row(M,I),18*M.MenuSize,M.Tracking,Ink,M.MenuHairlineStrength);
  }
  ++L;
  const auto Origin=PauseLayout::Row(M,M.Selected)+FVector2f(-5,PauseLayout::UnderlineOffset(M));
  const FVector2f Tip=Origin+FVector2f(M.LineWidth,0);
  const float Remaining=M.LineWidth*(1-M.UnderlineLeftCrop);
  const auto P=Tip-FVector2f(Remaining,0);
  FLinearColor Halo=M.Accent;Halo.A=.42f*M.Glow;
  if(Remaining>0)Box(*Art.Glow,P+FVector2f(-25,-15),FVector2f(Remaining+50,30),Halo);
  Halo.A=.6f*M.Glow;Box(*Art.Glow,Tip-FVector2f(37,37),FVector2f(74,74),Halo);++L;
  FLinearColor Core=FMath::Lerp(M.Accent,FLinearColor::White,.62f);
  if(Remaining>0)Line(P,Tip+FVector2f(10,0),Core,1.15f);
  Star(Tip,14,FLinearColor(.98f,.91f,1,1));
  ++L;
  const FLinearColor Quiet(.85f,.84f,.82f,.85f);
  Line(FVector2f(82,855),FVector2f(132,855),Quiet,.8f);
  Line(FVector2f(82,885),FVector2f(132,885),Quiet,.8f);
  Line(FVector2f(82,855),FVector2f(82,885),Quiet,.8f);
  Line(FVector2f(132,855),FVector2f(132,885),Quiet,.8f);
  Text(TEXT("Esc"),FVector2f(93,855),13,0,Quiet);
  Text(TEXT("Resume"),FVector2f(152,855),13,3,Quiet);
  return L;
 }
};


