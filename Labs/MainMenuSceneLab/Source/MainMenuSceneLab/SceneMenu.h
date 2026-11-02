#pragma once

#include "CoreMinimal.h"
#include "Widgets/SLeafWidget.h"
#include "Rendering/DrawElementTypes.h"
#include "Framework/Application/SlateApplication.h"
#include "Rendering/SlateRenderer.h"
#include "Fonts/FontMeasure.h"
#include "Fonts/CompositeFont.h"
#include "Styling/CoreStyle.h"
#include "Misc/Paths.h"
#include "InputCoreTypes.h"

/** Reference-space, resolution-independent main-menu artwork and hit targets. */
class SSceneMenu final : public SLeafWidget
{
public:
 SLATE_BEGIN_ARGS(SSceneMenu){}
  SLATE_ARGUMENT(TFunction<float(FName,float)>,Get)
  SLATE_ARGUMENT(TFunction<void(FName,float)>,Set)
  SLATE_ARGUMENT(TFunction<void(int32)>,Activate)
 SLATE_END_ARGS()

 void Construct(const FArguments& A)
 {
  Get=A._Get;Set=A._Set;Activate=A._Activate;
  Selected=FMath::Clamp(FMath::RoundToInt(Read(TEXT("menu_selected"),0)),0,4);
  for(int32 I=0;I<5;++I)Weights[I]=I==Selected?1.f:0.f;
  FontFace=MakeShared<FCompositeFont>(FName(TEXT("Regular")),FPaths::ProjectDir()/TEXT("Resources/Fonts/CormorantSC-Regular.ttf"),EFontHinting::AutoLight,EFontLoadingPolicy::LazyLoad);
  SetCanTick(true);SetClipping(EWidgetClipping::ClipToBounds);
 }
 virtual FVector2D ComputeDesiredSize(float)const override
 {return FVector2D(Width(),Height())*MenuScale();}
 virtual bool SupportsKeyboardFocus()const override{return true;}
 FSlateFontInfo GetFontInfo(float Size)const{return FSlateFontInfo(FontFace,Size,FName(TEXT("Regular")));}
 int32 GetSelected()const{return Selected;}
 void Select(int32 Index)
 {
  Index=FMath::Clamp(Index,0,4);
  if(Selected==Index)return;
  Selected=Index;if(Set)Set(TEXT("menu_selected"),float(Index));
  Invalidate(EInvalidateWidgetReason::Paint);
 }
 float RowCenter(int32 Index)const
 {
  const float H=Height(),Ratio=H/544.f;
  const float Top=FMath::Clamp(Read(TEXT("menu_top"),129)*Ratio,55.f,H-240.f);
  const float Gap=103.f*Ratio,Step=FMath::Max(25.f,Read(TEXT("menu_row_spacing"),66))*Ratio;
  const float Fit=FMath::Min(1.f,(H-44.f-Top)/(Gap+3.f*Step));
  return Top+(Index==0?0:(Gap+(Index-1)*Step)*Fit);
 }
 int32 RowAt(FVector2D Local)const{return DesignRowAt(Local/MenuScale());}
 bool HandleMenuKey(FKey Key)
 {
  if(Key==EKeys::Up||Key==EKeys::Gamepad_DPad_Up){Select((Selected+4)%5);return true;}
  if(Key==EKeys::Down||Key==EKeys::Gamepad_DPad_Down){Select((Selected+1)%5);return true;}
  if(Key==EKeys::Enter||Key==EKeys::Gamepad_FaceButton_Bottom){if(Activate)Activate(Selected);return true;}
  return false;
 }
 virtual void Tick(const FGeometry& G,const double Time,const float Delta)override
 {
  SLeafWidget::Tick(G,Time,Delta);AnimationTime=Time;
  const FVector2D Desired=ComputeDesiredSize(1);
  if(!Desired.Equals(LastDesired,.01)){LastDesired=Desired;Invalidate(EInvalidateWidgetReason::Layout);}
  const int32 Saved=FMath::Clamp(FMath::RoundToInt(Read(TEXT("menu_selected"),Selected)),0,4);
  Selected=Saved;
  for(int32 I=0;I<5;++I)Weights[I]=FMath::FInterpTo(Weights[I],I==Selected?1.f:0.f,Delta,18.f);
  Invalidate(EInvalidateWidgetReason::Paint);
 }
 virtual FReply OnMouseMove(const FGeometry& G,const FPointerEvent& E)override
 {
  const int32 Row=DesignRowAt(ToDesign(G,G.AbsoluteToLocal(E.GetScreenSpacePosition())));
  if(Row>=0)Select(Row);
  return Row>=0?FReply::Handled():FReply::Unhandled();
 }
 virtual FReply OnMouseButtonDown(const FGeometry& G,const FPointerEvent& E)override
 {
  if(E.GetEffectingButton()!=EKeys::LeftMouseButton)return FReply::Unhandled();
  Pressed=DesignRowAt(ToDesign(G,G.AbsoluteToLocal(E.GetScreenSpacePosition())));
  if(Pressed<0)return FReply::Unhandled();Select(Pressed);
  return FReply::Handled().SetUserFocus(SharedThis(this),EFocusCause::Mouse).CaptureMouse(SharedThis(this));
 }
 virtual FReply OnMouseButtonUp(const FGeometry& G,const FPointerEvent& E)override
 {
  if(E.GetEffectingButton()!=EKeys::LeftMouseButton||Pressed<0)return FReply::Unhandled();
  const int32 Row=DesignRowAt(ToDesign(G,G.AbsoluteToLocal(E.GetScreenSpacePosition()))),WasPressed=Pressed;Pressed=-1;
  if(Row==WasPressed&&Activate)Activate(Row);
  return FReply::Handled().ReleaseMouseCapture();
 }
 virtual void OnMouseCaptureLost(const FCaptureLostEvent&)override{Pressed=-1;}
 virtual FReply OnKeyDown(const FGeometry&,const FKeyEvent& E)override
 {return HandleMenuKey(E.GetKey())?FReply::Handled():FReply::Unhandled();}
 virtual FCursorReply OnCursorQuery(const FGeometry& G,const FPointerEvent& E)const override
 {return FCursorReply::Cursor(DesignRowAt(ToDesign(G,G.AbsoluteToLocal(E.GetScreenSpacePosition())))>=0?EMouseCursor::Hand:EMouseCursor::Default);}

 virtual int32 OnPaint(const FPaintArgs&,const FGeometry& G,const FSlateRect&,FSlateWindowElementList& Out,int32 Layer,const FWidgetStyle& Style,bool bEnabled)const override
 {
  const float W=Width(),H=Height(),S=GeometryScale(G);
  const FGeometry Canvas=G.MakeChild(FVector2D(W,H),FSlateLayoutTransform(S));
  const float Border=FMath::Clamp(Read(TEXT("menu_border_opacity"),1.f),0.f,1.f);
  const float Rule=FMath::Clamp(Read(TEXT("menu_border_width"),1.5f),.4f,3.f);
  const float Red=FMath::Clamp(Read(TEXT("menu_red"),.65f),0.f,1.5f);
  const float Glow=FMath::Clamp(Read(TEXT("menu_glow"),1.f),0.f,2.f);
  const float Pulse=1.f+.045f*FMath::Clamp(Read(TEXT("menu_motion"),.35f),0.f,1.f)*FMath::Sin(AnimationTime*.8);
  const float TextGain=FMath::Clamp(Read(TEXT("menu_text_brightness"),1),.15f,2.f);
  const FLinearColor Ivory(.95f,.84f,.68f,Border);
  const FLinearColor Ruby(.42f*Red,.013f,.008f,Border*.85f);
  const FLinearColor Pale(.82f,.70f,.52f,Border*.9f);
  const FSlateBrush* White=FCoreStyle::Get().GetBrush("WhiteBrush");
  auto Box=[&](float X,float Y,float BW,float BH,FLinearColor Color,int32 Z){
   FSlateDrawElement::MakeBox(Out,Layer+Z,Canvas.ToPaintGeometry(FVector2D(BW,BH),FSlateLayoutTransform(FVector2D(X,Y))),White,ESlateDrawEffect::None,Color);};
  auto Line=[&](TArray<FVector2f> P,FLinearColor Color,float Thickness,int32 Z){
   FSlateDrawElement::MakeLines(Out,Layer+Z,Canvas.ToPaintGeometry(),MoveTemp(P),ESlateDrawEffect::None,Color,true,Thickness);};
  auto Segment=[&](float X1,float Y1,float X2,float Y2,FLinearColor C,float Thickness,int32 Z){Line({FVector2f(X1,Y1),FVector2f(X2,Y2)},C,Thickness,Z);};
  auto Rect=[&](float X,float Y,float RW,float RH,FLinearColor C,float Thickness,int32 Z){
   Line({FVector2f(X,Y),FVector2f(X+RW,Y),FVector2f(X+RW,Y+RH),FVector2f(X,Y+RH),FVector2f(X,Y)},C,Thickness,Z);};
  auto RuleFrame=[&](float Inset,FLinearColor C,float Thickness){
   const float Gap=13;
   Line({FVector2f(W*.5f-Gap,Inset),FVector2f(Inset,Inset),FVector2f(Inset,H-Inset),FVector2f(W*.5f-Gap,H-Inset)},C,Thickness,3);
   Line({FVector2f(W*.5f+Gap,Inset),FVector2f(W-Inset,Inset),FVector2f(W-Inset,H-Inset),FVector2f(W*.5f+Gap,H-Inset)},C,Thickness,3);};
  auto Diamond=[&](float X,float Y,float R,FLinearColor C,float Thickness,int32 Z){Line({FVector2f(X,Y-R),FVector2f(X+R,Y),FVector2f(X,Y+R),FVector2f(X-R,Y),FVector2f(X,Y-R)},C,Thickness,Z);};
  auto Gradient=[&](float X,float Y,float GW,float GH,TArray<FSlateGradientStop> Stops,EOrientation Orientation,int32 Z){
   FSlateDrawElement::MakeGradient(Out,Layer+Z,Canvas.ToPaintGeometry(FVector2D(GW,GH),FSlateLayoutTransform(FVector2D(X,Y))),MoveTemp(Stops),Orientation);};

  // Dark translucent glass permits the actual water and reflections to remain visible.
  const float Opacity=FMath::Clamp(Read(TEXT("menu_panel_opacity"),.66f),0.f,1.f);
  Box(1,1,W-2,H-2,FLinearColor(.012f*Red,.00016f,.00022f,Opacity),0);
  Gradient(2,2,W-4,H-4,{FSlateGradientStop(FVector2f(0,0),FLinearColor(.022f*Red,.0002f,.0003f,.16f*Opacity)),FSlateGradientStop(FVector2f(0,H*.52f),FLinearColor(.001f,.00005f,.0001f,.08f*Opacity)),FSlateGradientStop(FVector2f(0,H-4),FLinearColor(.026f*Red,.0002f,.0004f,.08f*Opacity))},Orient_Vertical,1);
  Rect(.6f,.6f,W-1.2f,H-1.2f,Ruby,Rule,2);
  RuleFrame(8,Ivory,Rule*1.15f);RuleFrame(13,Pale,Rule*.85f);
  RuleFrame(19,FLinearColor(.36f*Red,.039f,.025f,Border*.68f),Rule*.75f);

  const float Ornament=FMath::Clamp(Read(TEXT("menu_ornament_scale"),1.f),.25f,2.f);
  const float Radius=29.f*Ornament;
  for(int32 Corner=0;Corner<4;++Corner){
   const bool Right=(Corner&1)!=0,Bottom=(Corner&2)!=0;
   const float CX=Right?W-8:8,CY=Bottom?H-8:8;
   TArray<FVector2f> Arc;
   for(int32 I=0;I<=24;++I){const float A=HALF_PI*I/24;Arc.Add(FVector2f(CX+(Right?-1:1)*Radius*FMath::Cos(A),CY+(Bottom?-1:1)*Radius*FMath::Sin(A)));}
   Line(MoveTemp(Arc),Ivory,Rule*.95f,4);
  }
  for(float Y:{12.f,H-12.f}){
   Diamond(W*.5f,Y,9.f*Ornament,Ivory,Rule*1.1f,5);
   Diamond(W*.5f,Y,4.4f*Ornament,Pale,Rule*.85f,5);
   Box(W*.5f-.8f,Y-.8f,1.6f,1.6f,FLinearColor(.98f,.88f,.68f,Border),5);
  }

  const auto Measure=FSlateApplication::Get().GetRenderer()->GetFontMeasureService();
  static const TCHAR* Labels[]={TEXT("Continue"),TEXT("New Game"),TEXT("Load Game"),TEXT("Settings"),TEXT("Quit")};
  for(int32 I=0;I<5;++I){
   const float Weight=Weights[I],Y=RowCenter(I),Left=32,Right=W-32,BW=Right-Left;
   if(Weight>.002f){
    const float A=Weight*(Pressed==I?.82f:1.f);
    Gradient(Left,Y-33,BW,70,{FSlateGradientStop(FVector2f(0,0),FLinearColor(.22f*Red,.0018f,.003f,.28f*A)),FSlateGradientStop(FVector2f(0,35),FLinearColor(.055f*Red,.0003f,.001f,.35f*A)),FSlateGradientStop(FVector2f(0,70),FLinearColor(.17f*Red,.0007f,.001f,.30f*A))},Orient_Vertical,6);
    Rect(Left,Y-33,BW,70,FLinearColor(.48f*Red,.026f,.014f,.75f*A),Rule*.8f,7);
    // A bright lower hairline, not a broad blurry button. Its glow is drawn
    // separately so reducing Glow preserves the crisp source and diamond.
    const float LY=Y+34,Half=FMath::Min(120.f,BW*.37f),Gap=11.f;
    for(int32 J=-7;J<=7;++J){
     const float Alpha=.25f*FMath::Exp(-float(J*J)/12.f)*Glow*Pulse*A;
     Gradient(W*.5f-Half-7,LY+J,Half*2+14,1,{FSlateGradientStop(FVector2f(0,0),FLinearColor(.95f,.16f,.04f,0)),FSlateGradientStop(FVector2f(16,0),FLinearColor(.95f,.16f,.04f,Alpha)),FSlateGradientStop(FVector2f(Half*2-2,0),FLinearColor(.95f,.16f,.04f,Alpha)),FSlateGradientStop(FVector2f(Half*2+14,0),FLinearColor(.95f,.16f,.04f,0))},Orient_Horizontal,8);
    }
    const FLinearColor Core(.99f,.87f,.72f,A);
    Segment(W*.5f-Half,LY,W*.5f-Gap,LY,Core,2.f,9);
    Segment(W*.5f+Gap,LY,W*.5f+Half,LY,Core,2.f,9);
    Diamond(W*.5f,LY,6.5f*Ornament,Core,1.4f,10);
    Diamond(W*.5f,LY,2.7f*Ornament,Core,.8f,10);
    for(float X:{W*.5f-Half,W*.5f+Half})Box(X-1,LY-1,2,2,FLinearColor(1,.91f,.70f,A),10);
   }
   const float PixelSize=FMath::Clamp(Read(TEXT("menu_font_size"),34.f),16.f,54.f);
   const float SelectedScale=FMath::Clamp(Read(TEXT("menu_selected_scale"),1.25f),1.f,1.6f);
   FSlateFontInfo Font=GetFontInfo(PixelSize*.75f*FMath::Lerp(1.f,SelectedScale,Weight));
   Font.LetterSpacing=0;
   float Tracking=FMath::Clamp(Read(TEXT("menu_tracking"),3.f),0.f,8.f);
   const FString Label(Labels[I]);
   FVector2D Measured=Measure->Measure(Label,Font);
   const float TextFit=FMath::Min(1.f,(W-84.f)/FMath::Max(1.f,float(Measured.X)+(Label.Len()-1)*Tracking));
   if(TextFit<1){Font.Size*=TextFit;Tracking*=TextFit;Measured=Measure->Measure(Label,Font);}
   const FVector2D Size(Measured.X+(Label.Len()-1)*Tracking,Measured.Y);
   const FVector2D Position(W*.5f-Size.X*.5f,Y-Size.Y*.5f-1.f+(Pressed==I?1.f:0.f));
   const FLinearColor TextColor(FMath::Lerp(.85f,.98f,Weight)*TextGain,FMath::Lerp(.80f,.90f,Weight)*TextGain,FMath::Lerp(.69f,.76f,Weight)*TextGain,1);
   // Draw tracked glyphs explicitly: the simple MakeText path does not apply
   // FSlateFontInfo::LetterSpacing consistently. Keep both measurement and
   // placement in reference pixels so the live spacing control is predictable.
   for(int32 GlyphIndex=0;GlyphIndex<Label.Len();++GlyphIndex){
    const FString Glyph=Label.Mid(GlyphIndex,1);
    const FVector2D GlyphSize=Measure->Measure(Glyph,Font);
    const FVector2D PrefixSize=Measure->Measure(Label.Left(GlyphIndex),Font);
    const FVector2D GlyphPosition=Position+FVector2D(PrefixSize.X+GlyphIndex*Tracking,0);
    FSlateDrawElement::MakeText(Out,Layer+11,Canvas.ToPaintGeometry(GlyphSize,FSlateLayoutTransform(GlyphPosition+FVector2D(0,1))),Glyph,Font,ESlateDrawEffect::None,FLinearColor(0,0,0,.65f));
    FSlateDrawElement::MakeText(Out,Layer+12,Canvas.ToPaintGeometry(GlyphSize,FSlateLayoutTransform(GlyphPosition)),Glyph,Font,ESlateDrawEffect::None,TextColor*Style.GetColorAndOpacityTint());
   }
  }
  return Layer+13;
 }
private:
 TFunction<float(FName,float)> Get;
 TFunction<void(FName,float)> Set;
 TFunction<void(int32)> Activate;
 TSharedPtr<const FCompositeFont> FontFace;
 int32 Selected=0,Pressed=-1;
 float Weights[5]={1,0,0,0,0};
 double AnimationTime=0;
 FVector2D LastDesired=FVector2D::ZeroVector;
 float Read(FName Key,float Default)const{return Get?Get(Key,Default):Default;}
 float Width()const{return FMath::Clamp(Read(TEXT("menu_width"),400.f),260.f,650.f);}
 float Height()const{return FMath::Clamp(Read(TEXT("menu_height"),544.f),400.f,680.f);}
 float MenuScale()const{return FMath::Min(FMath::Clamp(Read(TEXT("menu_scale"),1.f),.6f,1.3f),720.f/Height());}
 float GeometryScale(const FGeometry& G)const{return FMath::Max(.001f,FMath::Min(float(G.GetLocalSize().X/Width()),float(G.GetLocalSize().Y/Height())));}
 FVector2D ToDesign(const FGeometry& G,FVector2D Local)const{return Local/GeometryScale(G);}
 int32 DesignRowAt(FVector2D P)const
 {
  if(P.X<30||P.X>Width()-30||P.Y<20||P.Y>Height()-20)return -1;
  const float HalfHit=FMath::Min(32.f,(RowCenter(4)-RowCenter(3))*.48f);
  for(int32 I=0;I<5;++I)if(FMath::Abs(P.Y-RowCenter(I))<HalfHit)return I;
  return -1;
 }
};
