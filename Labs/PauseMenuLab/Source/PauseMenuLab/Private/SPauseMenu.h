#pragma once
#include "PausePainter.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Layout/SBackgroundBlur.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SScaleBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/SInvalidationPanel.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SSlider.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Colors/SColorPicker.h"
#include "Styling/CoreStyle.h"
#include "InputCoreTypes.h"

class SPauseCanvas:public SLeafWidget {
public:
 SLATE_BEGIN_ARGS(SPauseCanvas){}SLATE_END_ARGS()
 TSharedPtr<FPauseModel> Model; TUniquePtr<FPauseArt> Art;
 FSimpleDelegate Changed,Activate;
 TArray<FSlateRect> HitBounds;
 TArray<float> TextCenters;
 void RefreshHitBounds(){
  HitBounds.Reset();TextCenters.Reset();
  float SharedLeft=FLT_MAX,SharedRight=-FLT_MAX;
  for(int32 I=0;I<Model->Labels.Num();++I){
   auto B=Art->MenuBounds(*Model,I);const float Center=(B.Top+B.Bottom)*.5f;
   SharedLeft=FMath::Min(SharedLeft,B.Left);SharedRight=FMath::Max(SharedRight,B.Right);
   const float UnderlineY=PauseLayout::Row(*Model,I).Y+PauseLayout::UnderlineOffset(*Model);
   B.Bottom=UnderlineY+Model->HoverPaddingBottom;
   B.Top=2*Center-UnderlineY-Model->HoverPaddingTop;HitBounds.Add(B);TextCenters.Add(Center);
  }
  for(auto& B:HitBounds){B.Left=SharedLeft;B.Right=SharedRight+Model->HoverPaddingRight;}
 }
 int32 Hit(FVector2f P)const{
  P/=Model->OverallSize;int32 Best=INDEX_NONE;float Distance=FLT_MAX;
  for(int32 I=0;I<HitBounds.Num();++I)if(HitBounds[I].ContainsPoint(P)){
   const float D=FMath::Abs(P.Y-TextCenters[I]);
   if(D<Distance){Distance=D;Best=I;}
  }
  return Best;
 }
 void Construct(const FArguments&,TSharedPtr<FPauseModel> M){Model=M;Art=MakeUnique<FPauseArt>();RefreshHitBounds();SetCanTick(false);}
 virtual FVector2D ComputeDesiredSize(float)const override{return PauseLayout::Design;}
 void Select(int32 I){I=(I+5)%5;if(Model->Selected!=I){Model->Selected=I;Invalidate(EInvalidateWidgetReason::Paint);Changed.ExecuteIfBound();}}
 virtual FReply OnMouseMove(const FGeometry& G,const FPointerEvent& E)override{int32 I=Hit(FVector2f(G.AbsoluteToLocal(E.GetScreenSpacePosition())));if(I!=INDEX_NONE)Select(I);return FReply::Handled();}
 virtual FReply OnMouseButtonDown(const FGeometry& G,const FPointerEvent& E)override{if(E.GetEffectingButton()!=EKeys::LeftMouseButton)return FReply::Unhandled();int32 I=Hit(FVector2f(G.AbsoluteToLocal(E.GetScreenSpacePosition())));if(I!=INDEX_NONE){Select(I);Activate.ExecuteIfBound();}return FReply::Handled();}
 virtual int32 OnPaint(const FPaintArgs&,const FGeometry& G,const FSlateRect&,FSlateWindowElementList& Out,int32 Layer,const FWidgetStyle&,bool)const override{
  auto Scaled=G.MakeChild(G.GetLocalSize(),FSlateLayoutTransform(Model->OverallSize));
  return FPausePainter(Out,Scaled,Layer,*Art).Draw(*Model);
 }
};

class SPauseMenu:public SCompoundWidget {
public:
 SLATE_BEGIN_ARGS(SPauseMenu){}SLATE_END_ARGS()
 TSharedPtr<FPauseModel> Model; TSharedPtr<SPauseCanvas> Canvas;
 TSharedPtr<SBackgroundBlur> Blur;TSharedPtr<SInvalidationPanel> Cache;
 TSharedPtr<SWidget> MenuLayer,Panel,Hint,Status;
 TSharedPtr<FSlateDynamicImageBrush> Background;
 FSimpleDelegate Capture;
 bool bPanel=false,bClean=false;
 void Changed(){Canvas->RefreshHitBounds();Blur->SetBlurStrength(Model->bPaused?Model->Blur:0);Canvas->Invalidate(EInvalidateWidgetReason::Paint);Cache->InvalidateRootLayout();}
 void TogglePanel(){bPanel=!bPanel;Panel->SetVisibility(bPanel?EVisibility::Visible:EVisibility::Collapsed);}
 void Pause(bool B){Model->bPaused=B;MenuLayer->SetVisibility(B?EVisibility::Visible:EVisibility::Collapsed);if(!B&&bPanel)TogglePanel();Changed();}
 void Present(bool Clean){bClean=Clean;Hint->SetVisibility(Clean?EVisibility::Collapsed:EVisibility::Visible);Status->SetVisibility(Clean?EVisibility::Collapsed:EVisibility::HitTestInvisible);}
 void SetColor(FLinearColor C){Model->Accent=C;Model->Accent.A=1;Changed();}
 FReply PickColor(){FColorPickerArgs A(Model->Accent,FOnLinearColorValueChanged::CreateSP(this,&SPauseMenu::SetColor));A.ParentWidget=SharedThis(this);A.bUseAlpha=false;A.bClampValue=true;A.bExpandAdvancedSection=true;A.sRGBOverride=true;A.OnColorPickerCancelled=FOnColorPickerCancelled::CreateSP(this,&SPauseMenu::SetColor);OpenColorPicker(A);return FReply::Handled();}
 void Activate(){if(Model->Selected==0)Pause(false);else if(Model->Selected==3)TogglePanel();else Model->Status=Model->Labels[Model->Selected]+TEXT(" — visual checkpoint; gameplay page not connected");}
 TSharedRef<SWidget> Knob(const FString& Label,float* Value,float Min,float Max,int32 Decimals=2){
  return SNew(SVerticalBox)
   +SVerticalBox::Slot().AutoHeight().Padding(0,9,0,4)[SNew(STextBlock).Text_Lambda([=]{return FText::FromString(FString::Printf(TEXT("%s  %.*f"),*Label,Decimals,*Value));})]
   +SVerticalBox::Slot().AutoHeight()[SNew(SSlider).Value_Lambda([=]{return (*Value-Min)/(Max-Min);}).OnValueChanged_Lambda([=,this](float V){*Value=FMath::Lerp(Min,Max,V);Changed();})];
 }
 void Construct(const FArguments&){
  SetCanTick(false);Model=MakeShared<FPauseModel>();Model->Load();Model->Status=TEXT("");
  Background=MakeShared<FSlateDynamicImageBrush>(FName(*FPaths::ConvertRelativePathToFull(FPaths::ProjectDir()/TEXT("Resources/forest.png"))),PauseLayout::Design);
  ChildSlot[SNew(SOverlay)
   +SOverlay::Slot()[SNew(SScaleBox).Stretch(EStretch::ScaleToFill)[SNew(SImage).Image(Background.Get())]]
   +SOverlay::Slot()[SAssignNew(Blur,SBackgroundBlur).Padding(0).BlurStrength(Model->Blur)]
   +SOverlay::Slot()[SAssignNew(MenuLayer,SScaleBox).Stretch(EStretch::ScaleToFit).HAlign(HAlign_Left).VAlign(VAlign_Center)
    [SNew(SBox).WidthOverride(1672).HeightOverride(941)[SAssignNew(Cache,SInvalidationPanel)[SAssignNew(Canvas,SPauseCanvas,Model)]]]]
   +SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Top).Padding(20,20)
    [SAssignNew(Panel,SBorder).Padding(18).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(FLinearColor(.015f,.014f,.023f,.98f))
     [SNew(SBox).WidthOverride(270).MaxDesiredHeight(780)[SNew(SScrollBox)
      +SScrollBox::Slot()[SNew(SVerticalBox)
       +SVerticalBox::Slot().AutoHeight()[SNew(STextBlock).Text(FText::FromString(TEXT("PAUSE WORKSHOP · CHECKPOINT 01")))]
       // Preserve creation order: append new tuning controls before Save settings.
       +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Overall size"),&Model->OverallSize,.65f,1.15f)]
       +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Title size"),&Model->TitleSize,.6f,1.3f)]
       +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Menu text size"),&Model->MenuSize,.7f,1.3f)]
       +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Menu spacing"),&Model->RowSpacing,52,85)]
       +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Letter spacing"),&Model->Tracking,0,12)]
       +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Background blur"),&Model->Blur,0,15)]
       +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Backdrop darkness"),&Model->Darkness,0,1)]
       +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Gradient width"),&Model->GradientWidth,500,1300)]
       +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Underline length"),&Model->LineWidth,100,380)]
       +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Selection glow"),&Model->Glow,0,1.5f)]
       +SVerticalBox::Slot().AutoHeight().Padding(0,12)[SNew(SButton).Text(FText::FromString(TEXT("Selection color…"))).OnClicked(this,&SPauseMenu::PickColor)]
       +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Menu hairline strength"),&Model->MenuHairlineStrength,0,1)]
       +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Text-to-line spacing"),&Model->UnderlineGap,0,30)]
       +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Underline left crop"),&Model->UnderlineLeftCrop,0,.05f,4)]
       +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Hover top padding"),&Model->HoverPaddingTop,0,20)]
       +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Hover bottom padding"),&Model->HoverPaddingBottom,0,20)]
       +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Hover right extension"),&Model->HoverPaddingRight,0,200)]
       +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Selected text whiteness"),&Model->SelectedTextWhiteness,0,1)]
       +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Unselected text opacity"),&Model->UnselectedTextOpacity,0,1)]
       +SVerticalBox::Slot().AutoHeight()[SNew(SButton).Text(FText::FromString(TEXT("Save settings"))).OnClicked_Lambda([this]{Model->Save();return FReply::Handled();})]
       +SVerticalBox::Slot().AutoHeight().Padding(0,5)[SNew(SButton).Text(FText::FromString(TEXT("Reload settings · F5"))).OnClicked_Lambda([this]{Model->Load();Changed();return FReply::Handled();})]
       +SVerticalBox::Slot().AutoHeight()[SNew(SButton).Text(FText::FromString(TEXT("Capture · F12"))).OnClicked_Lambda([this]{Capture.ExecuteIfBound();return FReply::Handled();})]
       +SVerticalBox::Slot().AutoHeight().Padding(0,5)[SNew(SButton).Text(FText::FromString(TEXT("Close tuning · R"))).OnClicked_Lambda([this]{TogglePanel();return FReply::Handled();})]
      ]]]]
   +SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Bottom).Padding(18,12)
    [SAssignNew(Hint,STextBlock).Font(FCoreStyle::GetDefaultFontStyle("Regular",10)).ColorAndOpacity(FLinearColor(1,1,1,.65f)).Text(FText::FromString(TEXT("01 · ↑ ↓ / mouse · Esc: pause · R: tune · P: clean view · F12: snapshot")))]
   +SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Bottom).Padding(18,40)
    [SAssignNew(Status,STextBlock).Font(FCoreStyle::GetDefaultFontStyle("Regular",10)).Text_Lambda([this]{return FText::FromString(Model->Status);})]
  ];
  Panel->SetVisibility(EVisibility::Collapsed);
  Canvas->Changed.BindLambda([this]{Cache->InvalidateRootLayout();});
  Canvas->Activate.BindSP(this,&SPauseMenu::Activate);
 }
 virtual bool SupportsKeyboardFocus()const override{return true;}
 virtual FReply OnKeyDown(const FGeometry&,const FKeyEvent& E)override{
  auto K=E.GetKey();
  if(K==EKeys::Escape){if(bPanel)TogglePanel();else Pause(!Model->bPaused);}
  else if(K==EKeys::R)TogglePanel();
  else if(K==EKeys::P)Present(!bClean);
  else if(K==EKeys::F12)Capture.ExecuteIfBound();
  else if(K==EKeys::F5){Model->Load();Changed();}
  else if(Model->bPaused&&!bPanel&&(K==EKeys::Down||K==EKeys::Up))Canvas->Select(Model->Selected+(K==EKeys::Down?1:-1));
  else if(Model->bPaused&&!bPanel&&K==EKeys::Enter)Activate();
  else return FReply::Unhandled();
  return FReply::Handled();
 }
};

