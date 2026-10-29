#pragma once
#include "Widgets/SLeafWidget.h"
#include "Rendering/DrawElementTypes.h"
#include "GameFramework/PlayerController.h"
#include "Engine/LocalPlayer.h"
#include "Engine/GameViewportClient.h"
#include "SceneView.h"
#include "Components/SkeletalMeshComponent.h"
#include "Styling/CoreStyle.h"

// Projected world-axis handles. The same pick/drag paths are used by Slate and
// isolated native checks; never synthesize desktop input to test the tool.
class SSceneGizmo final:public SLeafWidget
{
public:
 SLATE_BEGIN_ARGS(SSceneGizmo){}
  SLATE_ARGUMENT(APlayerController*,Controller)
  SLATE_ARGUMENT(USkeletalMeshComponent*,Body)
  SLATE_ARGUMENT(TFunction<FVector()>,GetOffset)
  SLATE_ARGUMENT(TFunction<void(FVector)>,SetOffset)
 SLATE_END_ARGS()
 void Construct(const FArguments& A){PC=A._Controller;Body=A._Body;GetOffset=A._GetOffset;SetOffset=A._SetOffset;SetCanTick(false);}
 bool IsSelected()const{return Selected;}
 bool IsDragging()const{return DragAxis>=0;}
 int ActiveAxis()const{return DragAxis;}
 void Select(bool Value){Finish(false);Selected=Value;}
 FVector Anchor()const{return Body->GetComponentLocation()+FVector(0,0,90);}
 static FVector Axis(int I){return I==0?FVector::ForwardVector:I==1?FVector::RightVector:FVector::UpVector;}
 virtual FVector2D ComputeDesiredSize(float)const override{return FVector2D(1,1);}
 virtual bool SupportsKeyboardFocus()const override{return true;}
 FVector2D Pixels(const FGeometry& G,FVector2D P)const{
  int X=0,Y=0;PC->GetViewportSize(X,Y);const FVector2D S=G.GetLocalSize();
  return FVector2D(P.X*X/FMath::Max(1.,S.X),P.Y*Y/FMath::Max(1.,S.Y));
 }
 bool Project(const FGeometry& G,FVector P,FVector2D& Out)const{
  FVector2D Pixel;if(!PC||!PC->ProjectWorldLocationToScreen(P,Pixel,false))return false;
  int X=0,Y=0;PC->GetViewportSize(X,Y);if(X<=0||Y<=0)return false;
  Out=Pixel*G.GetLocalSize()/FVector2D(X,Y);return true;
 }
 bool Ray(const FGeometry& G,FVector2D P,FVector& O,FVector& D)const{
  // Engine's convenience deprojection truncates screen positions to pixels.
  // Continuous coordinates avoid visible steps along a foreshortened depth axis.
  const auto LP=PC?PC->GetLocalPlayer():nullptr;FSceneViewProjectionData View;
  if(!LP||!LP->ViewportClient||!LP->GetProjectionData(LP->ViewportClient->Viewport,View))return false;
  const auto Pixel=Pixels(G,P);const auto Rect=View.GetConstrainedViewRect();
  if(Rect.Width()<=0||Rect.Height()<=0)return false;
  const double X=2*(Pixel.X-Rect.Min.X)/Rect.Width()-1,Y=1-2*(Pixel.Y-Rect.Min.Y)/Rect.Height();
  const FMatrix Inverse=View.ComputeViewProjectionMatrix().InverseFast();
  const FVector4 Near=Inverse.TransformFVector4(FVector4(X,Y,1,1)),Far=Inverse.TransformFVector4(FVector4(X,Y,.01,1));
  if(FMath::Abs(Near.W)<SMALL_NUMBER||FMath::Abs(Far.W)<SMALL_NUMBER)return false;
  O=FVector(Near)/Near.W;D=(FVector(Far)/Far.W-O).GetSafeNormal();return !D.IsNearlyZero();
 }
 bool Handles(const FGeometry& G,FVector2D& Origin,FVector2D Ends[3],float Lengths[3])const{
  if(!Body||!Project(G,Anchor(),Origin))return false;
  for(int I=0;I<3;++I){
   Lengths[I]=38;
   if(!Project(G,Anchor()+Axis(I)*Lengths[I],Ends[I]))return false;
   // Keep foreshortened handles pickable without changing their world direction.
   if((Ends[I]-Origin).Size()<30){Lengths[I]=120;Project(G,Anchor()+Axis(I)*Lengths[I],Ends[I]);}
  }return true;
 }
 bool PickBody(const FGeometry& G,FVector2D P)const{
  FVector O,D;if(!Body||!Ray(G,P,O,D))return false;
  FHitResult Hit;FCollisionQueryParams Q(SCENE_QUERY_STAT(SceneMannequinPick),false);
  return Body->LineTraceComponent(Hit,O,O+D*20000,Q);
 }
 bool Begin(const FGeometry& G,FVector2D P){
  FVector2D Origin,Ends[3];float Lengths[3];
  if(Selected&&Handles(G,Origin,Ends,Lengths)){
   int Best=-1;double Distance=11;
   for(int I=0;I<3;++I){
    const FVector2D V=Ends[I]-Origin;const double T=FMath::Clamp(FVector2D::DotProduct(P-Origin,V)/FMath::Max(1.,V.SizeSquared()),.18,1.);
    const double D=(P-(Origin+T*V)).Size();if(D<Distance){Distance=D;Best=I;}
   }
   if(Best>=0){
    DragAxis=Best;StartOffset=GetOffset();DragOrigin=Anchor();StartPointer=P;
    ScreenAxis=(Ends[Best]-Origin).GetSafeNormal();WorldPerPixel=Lengths[Best]/FMath::Max(1.,(Ends[Best]-Origin).Size());
    FVector O,D;if(!Ray(G,P,O,D)){DragAxis=-1;return false;}const double Dot=FVector::DotProduct(D,Axis(Best));
    UseRay=1-Dot*Dot>.015;StartDistance=AxisDistance(O,D);return true;
   }
  }
  Selected=PickBody(G,P);return Selected;
 }
 void Move(const FGeometry& G,FVector2D P){
  if(DragAxis<0)return;
  FVector O,D;if(!Ray(G,P,O,D))return;
  const double Delta=UseRay?AxisDistance(O,D)-StartDistance:FVector2D::DotProduct(P-StartPointer,ScreenAxis)*WorldPerPixel;
  if(FMath::IsFinite(Delta))SetOffset(StartOffset+Axis(DragAxis)*FMath::Clamp(Delta,-1500.,1500.));
 }
 void Finish(bool Cancel){if(Cancel&&DragAxis>=0)SetOffset(StartOffset);DragAxis=-1;}
 virtual FReply OnMouseButtonDown(const FGeometry& G,const FPointerEvent& E)override{
  if(E.GetEffectingButton()!=EKeys::LeftMouseButton)return FReply::Unhandled();
  if(!Begin(G,G.AbsoluteToLocal(E.GetScreenSpacePosition())))return FReply::Unhandled();
  auto Reply=FReply::Handled().SetUserFocus(SharedThis(this),EFocusCause::Mouse);
  if(IsDragging())Reply.CaptureMouse(SharedThis(this));return Reply;
 }
 virtual FReply OnMouseMove(const FGeometry& G,const FPointerEvent& E)override{
  if(!IsDragging())return FReply::Unhandled();Move(G,G.AbsoluteToLocal(E.GetScreenSpacePosition()));return FReply::Handled();
 }
 virtual FReply OnMouseButtonUp(const FGeometry&,const FPointerEvent& E)override{
  if(E.GetEffectingButton()!=EKeys::LeftMouseButton||(!IsDragging()&&!HasMouseCapture()))return FReply::Unhandled();Finish(false);return FReply::Handled().ReleaseMouseCapture();
 }
 virtual void OnMouseCaptureLost(const FCaptureLostEvent&)override{Finish(false);}
 virtual FReply OnKeyDown(const FGeometry&,const FKeyEvent& E)override{
  if(E.GetKey()!=EKeys::Escape)return FReply::Unhandled();if(IsDragging())Finish(true);else Selected=false;return FReply::Handled().ReleaseMouseCapture();
 }
 virtual int32 OnPaint(const FPaintArgs&,const FGeometry& G,const FSlateRect&,FSlateWindowElementList& Out,int32 Layer,const FWidgetStyle&,bool)const override{
  if(!Selected)return Layer;FVector2D O,Ends[3];float Lengths[3];if(!Handles(G,O,Ends,Lengths))return Layer;
  const FLinearColor Colors[]={FLinearColor(1,.12,.08),FLinearColor(.15,1,.3),FLinearColor(.18,.5,1)};
  for(int I=0;I<3;++I){
   FVector2D D=(Ends[I]-O).GetSafeNormal(),N(-D.Y,D.X);
   TArray<FVector2f> Line={FVector2f(O),FVector2f(Ends[I])};
   FSlateDrawElement::MakeLines(Out,Layer,G.ToPaintGeometry(),Line,ESlateDrawEffect::None,FLinearColor(.005,.005,.005,.85),true,6);
   FSlateDrawElement::MakeLines(Out,Layer+1,G.ToPaintGeometry(),Line,ESlateDrawEffect::None,DragAxis==I?FLinearColor(1,.8,.15):Colors[I],true,3);
   TArray<FVector2f> Head={FVector2f(Ends[I]-D*10+N*5),FVector2f(Ends[I]),FVector2f(Ends[I]-D*10-N*5)};
   FSlateDrawElement::MakeLines(Out,Layer+1,G.ToPaintGeometry(),Head,ESlateDrawEffect::None,Colors[I],true,3);
   FSlateDrawElement::MakeText(Out,Layer+2,G.ToPaintGeometry(FVector2D(20,18),FSlateLayoutTransform(Ends[I]+D*7)),FString(I==0?TEXT("X"):I==1?TEXT("Y"):TEXT("Z")),FCoreStyle::GetDefaultFontStyle("Bold",10),ESlateDrawEffect::None,Colors[I]);
  }return Layer+3;
 }
private:
 double AxisDistance(FVector O,FVector D)const{
  const FVector A=Axis(DragAxis),R=O-DragOrigin;const double Dot=FVector::DotProduct(A,D);
  return (FVector::DotProduct(A,R)-Dot*FVector::DotProduct(D,R))/FMath::Max(.00001,1-Dot*Dot);
 }
 APlayerController* PC=nullptr;USkeletalMeshComponent* Body=nullptr;
 TFunction<FVector()> GetOffset;TFunction<void(FVector)> SetOffset;
 bool Selected=false,UseRay=true;int DragAxis=-1;
 FVector DragOrigin,StartOffset;FVector2D StartPointer,ScreenAxis;double WorldPerPixel=1,StartDistance=0;
};
