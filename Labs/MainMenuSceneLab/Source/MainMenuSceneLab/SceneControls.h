#pragma once

#include "CoreMinimal.h"
#include "Brushes/SlateRoundedBoxBrush.h"
#include "Framework/Application/SlateApplication.h"
#include "Styling/CoreStyle.h"
#include "Styling/SlateTypes.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SSlider.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Text/STextBlock.h"

struct FSceneControlsCallbacks
{
 TFunction<float(FName, float)> Get;
 TFunction<void(FName, float)> Set;
 TFunction<void()> Save;
 TFunction<void()> Revert;
 TFunction<void()> ResetPosition;
 TFunction<void()> ClearWaves;
 TFunction<FText()> StatusText;
 TFunction<void()> ToggleBodyView;
 TFunction<bool()> BodyView;
 int32 InitialTab=1;
};

/** Live scene controls. The owner handles Tab visibility and persistence. */
class SSceneControls final : public SCompoundWidget
{
public:
 SLATE_BEGIN_ARGS(SSceneControls) {}
  SLATE_ARGUMENT(FSceneControlsCallbacks, Callbacks)
 SLATE_END_ARGS()

 void Construct(const FArguments& Args)
 {
  Callbacks = Args._Callbacks;
  ActiveTab=Callbacks.InitialTab;
  PanelBrush = FSlateRoundedBoxBrush(
   FLinearColor(.017f, .020f, .026f, .96f), 9.f,
   FLinearColor(.24f, .18f, .16f, .9f), 1.f);
  SliderStyle = FCoreStyle::Get().GetWidgetStyle<FSliderStyle>("Slider");
  SliderStyle.SetBarThickness(3.f)
   .SetNormalBarImage(FSlateRoundedBoxBrush(FLinearColor::White, 1.5f))
   .SetHoveredBarImage(FSlateRoundedBoxBrush(FLinearColor::White, 1.5f))
   .SetNormalThumbImage(FSlateRoundedBoxBrush(FLinearColor::White, 5.f, FVector2f(10.f, 10.f)))
   .SetHoveredThumbImage(FSlateRoundedBoxBrush(FLinearColor::White, 5.f, FVector2f(10.f, 10.f)));
  ButtonStyle = FCoreStyle::Get().GetWidgetStyle<FButtonStyle>("Button");
  ButtonStyle.SetNormal(FSlateRoundedBoxBrush(FLinearColor(.055f, .059f, .068f, 1.f), 4.f))
   .SetHovered(FSlateRoundedBoxBrush(FLinearColor(.095f, .102f, .117f, 1.f), 4.f))
   .SetPressed(FSlateRoundedBoxBrush(FLinearColor(.035f, .038f, .045f, 1.f), 4.f))
   .SetNormalPadding(FMargin(8.f, 6.f)).SetPressedPadding(FMargin(8.f, 6.f));
  SaveStyle = ButtonStyle;
  SaveStyle.SetNormal(FSlateRoundedBoxBrush(FLinearColor(.28f, .035f, .045f, 1.f), 4.f))
   .SetHovered(FSlateRoundedBoxBrush(FLinearColor(.42f, .052f, .065f, 1.f), 4.f))
   .SetPressed(FSlateRoundedBoxBrush(FLinearColor(.18f, .023f, .03f, 1.f), 4.f));

  auto Rows = SNew(SVerticalBox);
  auto Ground = SNew(SVerticalBox).Visibility_Lambda([this](){return ActiveTab==0?EVisibility::Visible:EVisibility::Collapsed;});
  auto Rain = SNew(SVerticalBox).Visibility_Lambda([this](){return ActiveTab==1?EVisibility::Visible:EVisibility::Collapsed;});
  auto Air = SNew(SVerticalBox).Visibility_Lambda([this](){return ActiveTab==2?EVisibility::Visible:EVisibility::Collapsed;});
  auto Wet = SNew(SVerticalBox).Visibility_Lambda([this](){return ActiveTab==3?EVisibility::Visible:EVisibility::Collapsed;});
  Rows->AddSlot().AutoHeight()[Ground];Rows->AddSlot().AutoHeight()[Rain];Rows->AddSlot().AutoHeight()[Air];Rows->AddSlot().AutoHeight()[Wet];
  auto Water = SNew(SVerticalBox).Visibility_Lambda([this](){return ActiveTab==4?EVisibility::Visible:EVisibility::Collapsed;});
  Rows->AddSlot().AutoHeight()[Water];
  auto AllRows=Rows;Rows=Ground;
  AddSection(Rows, TEXT("GROUND"), TEXT("Scale, shape and dark areas"));
  AddSlider(Rows, TEXT("ground_scale"), TEXT("Pattern size"), .4f, 3.f, 1.f, EValueFormat::Multiplier,
   TEXT("Change the size of the ground forms without changing the camera."));
  AddSlider(Rows, TEXT("ground_shape"), TEXT("Broad forms"), 0.f, 1.f, 1.f, EValueFormat::Percent,
   TEXT("Blend from the earlier fine grain to the broader flowing forms in the reference."));
  AddSlider(Rows, TEXT("ground_darkness"), TEXT("Dark areas"), 0.f, 1.f, 1.f, EValueFormat::Percent,
   TEXT("Keep the deeper black areas at 100%, or lift them toward dark crimson."));
  AddSlider(Rows, TEXT("ground_contrast"), TEXT("Contrast"), .5f, 2.f, 1.f, EValueFormat::Multiplier,
   TEXT("Adjust the separation between the crimson and darker forms."));

  AddSlider(Rows, TEXT("wind_strength"), TEXT("Background ripple"), 0.f, 1.f, .16f, EValueFormat::Percent,
   TEXT("Ambient water movement. Zero removes it; rain and mannequin contact remain independent."));

  Rows=Rain;
  AddSection(Rows, TEXT("RAIN"), TEXT("Fine drops, gusts and surface impacts"));
  Rows->AddSlot().AutoHeight().Padding(0.f,3.f,0.f,8.f)
  [SNew(SButton).ButtonStyle(&ButtonStyle).IsFocusable(false).HAlign(HAlign_Center)
   .OnClicked_Lambda([this](){if(Callbacks.Set){Callbacks.Set(TEXT("rain_amount"),3.8f);Callbacks.Set(TEXT("rain_width"),.07f);Callbacks.Set(TEXT("rain_length"),16.f);Callbacks.Set(TEXT("rain_brightness"),1.4f);Callbacks.Set(TEXT("rain_gust"),.35f);Callbacks.Set(TEXT("rain_slant"),.65f);Callbacks.Set(TEXT("fog_amount"),.55f);Callbacks.Set(TEXT("haze_amount"),.5f);}RestoreViewportFocus();return FReply::Handled();})
   [SNew(STextBlock).Text(FText::FromString(TEXT("Try fine storm"))).Font(FCoreStyle::GetDefaultFontStyle("Bold",10)).ColorAndOpacity(Ivory)]];
  AddSlider(Rows, TEXT("rain_amount"), TEXT("Density"), 0.f, 4.f, .35f, EValueFormat::RainPercent,
   TEXT("Four times the previous maximum. Old 80% is now 20%; 100% is a dense downpour. Zero turns rain off."));
  AddSlider(Rows, TEXT("rain_width"), TEXT("Drop width"), .025f, .6f, .12f, EValueFormat::Millimetres,
   TEXT("Use a narrow width and high density for fine rain."));
  AddSlider(Rows, TEXT("rain_length"), TEXT("Streak length"), 2.f, 40.f, 18.f, EValueFormat::Centimetres,
   TEXT("Length of the visible rain streaks."));
  AddSlider(Rows, TEXT("rain_brightness"), TEXT("Brightness"), .25f, 6.f, 2.4f, EValueFormat::Multiplier,
   TEXT("Control how strongly the drops catch the light."));
  AddSlider(Rows, TEXT("rain_gust"), TEXT("Turbulence"), 0.f, 2.f, .65f, EValueFormat::Multiplier,
   TEXT("Moving gusts bend and vary the rain through its height."));
  AddSlider(Rows, TEXT("rain_speed"), TEXT("Fall speed"), .3f, 2.f, 1.f, EValueFormat::Multiplier,
   TEXT("Change how quickly the visible drops fall."));
  AddSlider(Rows, TEXT("rain_slant"), TEXT("Slant"), -1.f, 1.f, .08f, EValueFormat::Percent,
   TEXT("Negative leans left; zero falls straight; positive leans right."));
  AddSlider(Rows, TEXT("rain_ripple_strength"), TEXT("Surface impact"), 0.f, 1.f, .35f, EValueFormat::Percent,
   TEXT("Adjust rain ripples independently from mannequin contact."));
  AddSlider(Rows, TEXT("rain_ripple_size"), TEXT("Ripple size"), .4f, 2.f, 1.f, EValueFormat::Multiplier,
   TEXT("Change the size of the small rings made by rain."));

  Rows=Air;
  AddSection(Rows, TEXT("COLD SMOKE"), TEXT("Rolling upper bank with a clear center"));
  Rows->AddSlot().AutoHeight().Padding(0.f,3.f,0.f,8.f)
  [SNew(SButton).ButtonStyle(&ButtonStyle).IsFocusable(false).HAlign(HAlign_Center)
   .ToolTipText(FText::FromString(TEXT("Gather the smoke above the scene and turn off middle mist. Save look keeps these settings.")))
   .OnClicked_Lambda([this](){
    if(Callbacks.Set){
     Callbacks.Set(TEXT("fog_amount"),0.f);
     Callbacks.Set(TEXT("haze_amount"),.65f);
     Callbacks.Set(TEXT("haze_height"),350.f);
     Callbacks.Set(TEXT("haze_spread"),1.f);
     Callbacks.Set(TEXT("smoke_horizontal_width"),1.f);
     Callbacks.Set(TEXT("haze_speed"),.12f);
     Callbacks.Set(TEXT("smoke_roll"),.65f);
     Callbacks.Set(TEXT("smoke_lower_edge"),.28f);
     Callbacks.Set(TEXT("smoke_edge_softness"),.06f);
     Callbacks.Set(TEXT("smoke_horizontal_shift"),200.f);
    }
    RestoreViewportFocus();return FReply::Handled();
   })
   [SNew(STextBlock).Text(FText::FromString(TEXT("Cold smoke / black center")))
    .Font(FCoreStyle::GetDefaultFontStyle("Bold",10)).ColorAndOpacity(Ivory)]];
  AddSlider(Rows, TEXT("haze_amount"), TEXT("Density"), 0.f, 1.f, .65f, EValueFormat::Percent,
   TEXT("Density of the upper smoke bank; zero disables it."));
  AddSlider(Rows, TEXT("haze_height"), TEXT("Bank height"), 200.f, 1200.f, 350.f, EValueFormat::Centimetres,
   TEXT("Move the smoke bank vertically above the ground."));
  AddSlider(Rows, TEXT("smoke_lower_edge"), TEXT("Lower edge"), .05f, .65f, .28f, EValueFormat::Percent,
   TEXT("Set how far smoke reaches down from the top. Lower values keep more of the frame black."));
  AddSlider(Rows, TEXT("smoke_edge_softness"), TEXT("Edge softness"), .01f, .2f, .06f, EValueFormat::Percent,
   TEXT("Feather the lower boundary of the smoke bank."));
  AddSlider(Rows, TEXT("smoke_horizontal_width"), TEXT("Horizontal width"), .25f, 8.f, 1.f, EValueFormat::Multiplier,
   TEXT("Widen the actual smoke source horizontally, up to 8x, keeping its height and thickness. Very wide changes resize the gas grid after a brief pause in dragging; let the smoke reform."));
  AddSlider(Rows, TEXT("haze_speed"), TEXT("Drift speed"), 0.f, 1.f, .12f, EValueFormat::Percent,
   TEXT("Speed of the downward plume and rising return flow; zero pauses the smoke."));
  AddSlider(Rows, TEXT("smoke_roll"), TEXT("Rolling motion"), 0.f, 1.f, .65f, EValueFormat::Percent,
   TEXT("Adjust the curling and rolling motion within the smoke."));
  AddSlider(Rows, TEXT("smoke_horizontal_shift"), TEXT("Left / right"), -1000.f, 1000.f, 200.f, EValueFormat::Centimetres,
   TEXT("Move the whole smoke bank horizontally. Negative moves left; positive moves right."));
  AddSection(Rows, TEXT("OPTIONAL MIST"), TEXT("Fills the middle; leave off for black"));
  AddSlider(Rows, TEXT("fog_amount"), TEXT("Middle mist"), 0.f, 1.f, 0.f, EValueFormat::Percent,
   TEXT("Optional mist around the rain and mannequin. It fills the middle of the scene; keep it at zero for a black center."));
  Rows=Wet;
  AddSection(Rows, TEXT("MANNEQUIN"), TEXT("Water beads and flowing trails"));
  Rows->AddSlot().AutoHeight().Padding(0.f,4.f,0.f,12.f)
  [SNew(SButton).ButtonStyle(&ButtonStyle).IsFocusable(false).HAlign(HAlign_Center)
   .OnClicked_Lambda([this](){if(Callbacks.ToggleBodyView)Callbacks.ToggleBodyView();RestoreViewportFocus();return FReply::Handled();})
   [SNew(STextBlock).Text_Lambda([this](){return FText::FromString(Callbacks.BodyView&&Callbacks.BodyView()?TEXT("Return to whole scene"):TEXT("Inspect body close-up"));})
    .Font(FCoreStyle::GetDefaultFontStyle("Bold",10)).ColorAndOpacity(Ivory)]];
  AddSlider(Rows, TEXT("wet_amount"), TEXT("Wetness"), 0.f, 1.f, .65f, EValueFormat::Percent,
   TEXT("Water coating strength; zero restores the dry material."));
  AddSlider(Rows, TEXT("bead_density"), TEXT("Bead density"), 0.f, 1.f, .55f, EValueFormat::Percent,
   TEXT("Amount of pearled droplets on the surface."));
  AddSlider(Rows, TEXT("bead_size"), TEXT("Bead size"), .3f, 3.f, 1.f, EValueFormat::Multiplier,
   TEXT("Scale of the individual water beads."));
  AddSlider(Rows, TEXT("bead_strength"), TEXT("Bead relief"), 0.f, 2.f, .65f, EValueFormat::Multiplier,
   TEXT("Rounded water relief and the strength of its glints."));
  AddSlider(Rows, TEXT("trail_amount"), TEXT("Trails"), 0.f, 1.f, .45f, EValueFormat::Percent,
   TEXT("Amount of elongated runoff and trails behind moving droplets."));
  AddSlider(Rows, TEXT("runoff_speed"), TEXT("Runoff speed"), 0.f, 2.f, .3f, EValueFormat::Multiplier,
   TEXT("Movement of runoff; zero holds the droplets still."));
  Rows=Water;
  AddSection(Rows,TEXT("COLLISION"),TEXT("Mannequin pushes the puddle"));
  AddSlider(Rows,TEXT("collision_strength"),TEXT("Push strength"),0.f,3.f,1.f,EValueFormat::Multiplier,
   TEXT("Velocity transferred from the mannequin to water. Zero stops new collision forcing; old waves remain until they settle or are cleared."));
  AddSlider(Rows,TEXT("collision_min_speed"),TEXT("Motion threshold"),0.f,20.f,1.f,EValueFormat::Speed,
   TEXT("Ignore horizontal contact speeds below this value. Raise it to reject tiny idle movements. Very slow deliberate movement will also be ignored."));
  AddSlider(Rows,TEXT("collision_softness"),TEXT("Contact softness"),.5f,20.f,4.f,EValueFormat::Centimetres,
   TEXT("Blend collision coupling over this distance inside the collider. Larger values soften contact; small values make it firmer."));
  AddSlider(Rows,TEXT("water_damping"),TEXT("Damping"),0.f,1.f,0.f,EValueFormat::Percent,
   TEXT("Higher values dissipate wave motion faster. Zero preserves the earlier long-lived puddle response."));
  AddSlider(Rows,TEXT("interaction_strength"),TEXT("Wave relief"),0.f,3.f,1.f,EValueFormat::Multiplier,
   TEXT("Visible relief of collision waves in the water and reflections. Does not alter the simulation or rain."));
  Rows->AddSlot().AutoHeight().Padding(0,8,0,4)
  [SNew(SCheckBox).IsChecked_Lambda([this](){return Read(TEXT("water_resting_contact"),0)>.5f?ECheckBoxState::Checked:ECheckBoxState::Unchecked;})
   .ToolTipText(FText::FromString(TEXT("Keep stationary body shapes in the solver, as before. Leave off to gate contact by actual submerged-body movement. Clear waves to compare.")))
   .OnCheckStateChanged_Lambda([this](ECheckBoxState State){if(Callbacks.Set)Callbacks.Set(TEXT("water_resting_contact"),State==ECheckBoxState::Checked?1.f:0.f);RestoreViewportFocus();})
   [SNew(STextBlock).Text(FText::FromString(TEXT("Allow resting contact (legacy)"))).Font(FCoreStyle::GetDefaultFontStyle("Regular",10)).ColorAndOpacity(Ivory)]];
  Rows->AddSlot().AutoHeight().Padding(0,10,0,5)
  [SNew(SButton).ButtonStyle(&ButtonStyle).IsFocusable(false).HAlign(HAlign_Center)
   .OnClicked_Lambda([this](){if(Callbacks.Set){Callbacks.Set(TEXT("collision_strength"),.6f);Callbacks.Set(TEXT("collision_min_speed"),5.f);Callbacks.Set(TEXT("collision_softness"),4.f);Callbacks.Set(TEXT("water_damping"),.3f);Callbacks.Set(TEXT("water_resting_contact"),0);}if(Callbacks.ClearWaves)Callbacks.ClearWaves();RestoreViewportFocus();return FReply::Handled();})
   [SNew(STextBlock).Text(FText::FromString(TEXT("Try calmer contact"))).Font(FCoreStyle::GetDefaultFontStyle("Bold",10)).ColorAndOpacity(Ivory)]];
  Rows->AddSlot().AutoHeight().Padding(0,3,0,8)
  [SNew(SButton).ButtonStyle(&ButtonStyle).IsFocusable(false).HAlign(HAlign_Center)
   .OnClicked_Lambda([this](){if(Callbacks.ClearWaves)Callbacks.ClearWaves();RestoreViewportFocus();return FReply::Handled();})
   [SNew(STextBlock).Text(FText::FromString(TEXT("Clear existing waves"))).Font(FCoreStyle::GetDefaultFontStyle("Regular",10)).ColorAndOpacity(Ivory)]];
  Rows->AddSlot().AutoHeight()[SNew(STextBlock).Text(FText::FromString(TEXT("Start with Motion threshold to filter idle motion.\nUse Damping to shorten the wake. Clear waves\nto compare settings from a calm surface."))).Font(FCoreStyle::GetDefaultFontStyle("Regular",9)).ColorAndOpacity(Muted)];
  Rows=AllRows;

  SetVisibility(EVisibility::SelfHitTestInvisible);
  ChildSlot.HAlign(HAlign_Left).VAlign(VAlign_Top)
  [
   SNew(SBox).WidthOverride(310.f).HeightOverride(668.f)
   [
    SNew(SBorder).BorderImage(&PanelBrush).Padding(FMargin(14.f, 12.f))
    [
     SNew(SVerticalBox)
     + SVerticalBox::Slot().AutoHeight()
     [
      SNew(SHorizontalBox)
      + SHorizontalBox::Slot().FillWidth(1.f)
      [SNew(STextBlock).Text(FText::FromString(TEXT("Scene studio")))
       .Font(FCoreStyle::GetDefaultFontStyle("Bold", 16)).ColorAndOpacity(Ivory)]
      + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
      [SNew(STextBlock).Text(FText::FromString(TEXT("TAB  hide")))
       .Font(FCoreStyle::GetDefaultFontStyle("Regular", 9)).ColorAndOpacity(Muted)]
     ]
     + SVerticalBox::Slot().AutoHeight().Padding(0.f, 3.f, 0.f, 9.f)
     [SNew(STextBlock).Text(FText::FromString(TEXT("Rain & atmosphere / live preview")))
      .Font(FCoreStyle::GetDefaultFontStyle("Regular", 9)).ColorAndOpacity(Muted)]
     + SVerticalBox::Slot().AutoHeight().Padding(0.f, 0.f, 0.f, 10.f)
     [
      SNew(SHorizontalBox)
      + SHorizontalBox::Slot().FillWidth(1.f)[Tab(TEXT("Ground"),0)]
      + SHorizontalBox::Slot().FillWidth(1.f)[Tab(TEXT("Water"),4)]
      + SHorizontalBox::Slot().FillWidth(1.f)[Tab(TEXT("Rain"),1)]
      + SHorizontalBox::Slot().FillWidth(1.f)[Tab(TEXT("Air"),2)]
      + SHorizontalBox::Slot().FillWidth(1.f)[Tab(TEXT("Body"),3)]
     ]
     + SVerticalBox::Slot().FillHeight(1.f)
     [
      SNew(SScrollBox).AllowOverscroll(EAllowOverscroll::No)
      .ScrollBarThickness(FVector2f(3.f, 3.f))
      + SScrollBox::Slot()[Rows]
     ]
     + SVerticalBox::Slot().AutoHeight().Padding(0.f, 7.f, 0.f, 0.f)
     [SNew(SButton).ButtonStyle(&ButtonStyle).IsFocusable(false).HAlign(HAlign_Center)
      .ToolTipText(FText::FromString(TEXT("Return the mannequin to the starting position. Click him in the scene to show the X/Y/Z move handles.")))
      .OnClicked_Lambda([this](){if(Callbacks.ResetPosition)Callbacks.ResetPosition();RestoreViewportFocus();return FReply::Handled();})
      [SNew(STextBlock).Text(FText::FromString(TEXT("Reset position"))).Font(FCoreStyle::GetDefaultFontStyle("Regular",10)).ColorAndOpacity(Ivory)]]
     + SVerticalBox::Slot().AutoHeight().Padding(0.f, 8.f, 0.f, 0.f)
     [
      SNew(SHorizontalBox)
      + SHorizontalBox::Slot().FillWidth(1.f).Padding(0.f, 0.f, 4.f, 0.f)
      [
       SNew(SButton).ButtonStyle(&SaveStyle).IsFocusable(false).HAlign(HAlign_Center)
       .ToolTipText(FText::FromString(TEXT("Save this look for the next launch.")))
       .OnClicked_Lambda([this]() { if (Callbacks.Save) Callbacks.Save(); RestoreViewportFocus(); return FReply::Handled(); })
       [SNew(STextBlock).Text(FText::FromString(TEXT("Save look")))
        .Font(FCoreStyle::GetDefaultFontStyle("Bold", 10)).ColorAndOpacity(Ivory)]
      ]
      + SHorizontalBox::Slot().FillWidth(1.f).Padding(4.f, 0.f, 0.f, 0.f)
      [
       SNew(SButton).ButtonStyle(&ButtonStyle).IsFocusable(false).HAlign(HAlign_Center)
       .ToolTipText(FText::FromString(TEXT("Restore the last saved look.")))
       .OnClicked_Lambda([this]() { if (Callbacks.Revert) Callbacks.Revert(); RestoreViewportFocus(); return FReply::Handled(); })
       [SNew(STextBlock).Text(FText::FromString(TEXT("Revert")))
        .Font(FCoreStyle::GetDefaultFontStyle("Regular", 10)).ColorAndOpacity(Ivory)]
      ]
     ]
     + SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 0.f)
     [SNew(STextBlock).Text_Lambda([this]() {
       return Callbacks.StatusText ? Callbacks.StatusText() : FText::FromString(TEXT("Changes are live. Save to keep this look."));
      }).Font(FCoreStyle::GetDefaultFontStyle("Regular", 9)).ColorAndOpacity(Muted).WrapTextAt(282.f)]
     + SVerticalBox::Slot().AutoHeight().Padding(0.f, 6.f, 0.f, 0.f)
     [SNew(STextBlock).Text(FText::FromString(TEXT("Click mannequin: drag XYZ   Esc cancel\nWASD move   Space demo   P pause")))
      .Font(FCoreStyle::GetDefaultFontStyle("Regular", 9)).ColorAndOpacity(Muted)]
    ]
   ]
  ];
 }

private:
 enum class EValueFormat { Percent, RainPercent, Multiplier, Centimetres, Millimetres, Speed };
 int32 ActiveTab=1;
 FSceneControlsCallbacks Callbacks;
 FSlateRoundedBoxBrush PanelBrush{FLinearColor::Black, 9.f};
 FSliderStyle SliderStyle;
 FButtonStyle ButtonStyle, SaveStyle;
 const FLinearColor Ivory{.9f, .865f, .8f, 1.f};
 const FLinearColor Muted{.40f, .43f, .48f, 1.f};

 float Read(FName Key, float Default) const { return Callbacks.Get ? Callbacks.Get(Key, Default) : Default; }
 TSharedRef<SWidget> Tab(const TCHAR* Label,int32 Index)
 {
  return SNew(SButton).ButtonStyle(&ButtonStyle).ContentPadding(FMargin(3.f,6.f)).IsFocusable(false).HAlign(HAlign_Center)
   .OnClicked_Lambda([this,Index](){ActiveTab=Index;RestoreViewportFocus();return FReply::Handled();})
   [SNew(STextBlock).Text(FText::FromString(Label)).Font(FCoreStyle::GetDefaultFontStyle("Bold",9))
    .ColorAndOpacity_Lambda([this,Index](){return ActiveTab==Index?Ivory:Muted;})];
 }

 static void RestoreViewportFocus()
 {
  if (FSlateApplication::IsInitialized())
   FSlateApplication::Get().SetAllUserFocusToGameViewport(EFocusCause::SetDirectly);
 }

 void AddSection(TSharedRef<SVerticalBox> Rows, const TCHAR* Name, const TCHAR* Description)
 {
  Rows->AddSlot().AutoHeight().Padding(0.f, 7.f, 0.f, 5.f)
  [
   SNew(SHorizontalBox)
   + SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center)
   [SNew(STextBlock).Text(FText::FromString(Name)).Font(FCoreStyle::GetDefaultFontStyle("Bold", 10))
    .ColorAndOpacity(FLinearColor(.69f, .40f, .32f, 1.f))]
   + SHorizontalBox::Slot().FillWidth(1.f).Padding(8.f, 0.f, 0.f, 0.f).VAlign(VAlign_Center)
   [SNew(STextBlock).Text(FText::FromString(Description)).Font(FCoreStyle::GetDefaultFontStyle("Regular", 8))
    .ColorAndOpacity(Muted)]
  ];
 }

 void AddSlider(TSharedRef<SVerticalBox> Rows, FName Key, const TCHAR* Label,
  float Min, float Max, float Default, EValueFormat Format, const TCHAR* Tooltip)
 {
  Rows->AddSlot().AutoHeight().Padding(0.f, 0.f, 4.f, 2.f)
  [
   SNew(SVerticalBox)
   + SVerticalBox::Slot().AutoHeight()
   [
    SNew(SHorizontalBox)
    + SHorizontalBox::Slot().FillWidth(1.f)
    [SNew(STextBlock).Text(FText::FromString(Label)).Font(FCoreStyle::GetDefaultFontStyle("Regular", 10))
     .ColorAndOpacity(Ivory).ToolTipText(FText::FromString(Tooltip))]
    + SHorizontalBox::Slot().AutoWidth()
    [SNew(STextBlock).Text_Lambda([this, Key, Default, Format]() {
      const float V = Read(Key, Default);
      if (Format == EValueFormat::Speed) return FText::FromString(FString::Printf(TEXT("%.1f cm/s"), V));
      if (Format == EValueFormat::Centimetres) return FText::FromString(FString::Printf(TEXT("%.0f cm"), V));
      if (Format == EValueFormat::Millimetres) return FText::FromString(FString::Printf(TEXT("%.2f mm"), V*10.f));
      if (Format == EValueFormat::Multiplier) return FText::FromString(FString::Printf(TEXT("%.2fx"), V));
      if (Format == EValueFormat::RainPercent) return FText::FromString(FString::Printf(TEXT("%.0f%%"), V * 25.f));
      return FText::FromString(FString::Printf(TEXT("%.0f%%"), V * 100.f));
     }).Font(FCoreStyle::GetDefaultFontStyle("Regular", 9)).ColorAndOpacity(Muted)]
   ]
   + SVerticalBox::Slot().AutoHeight()
   [
    SNew(SBox).HeightOverride(15.f)
    [
     SNew(SSlider).Style(&SliderStyle).IsFocusable(false).IndentHandle(false)
     .SliderBarColor(FLinearColor(.18f, .115f, .12f, 1.f))
     .SliderHandleColor(FLinearColor(.8f, .69f, .56f, 1.f))
     .Value_Lambda([this, Key, Min, Max, Default]() { return (FMath::Clamp(Read(Key, Default), Min, Max) - Min) / (Max - Min); })
     .OnValueChanged_Lambda([this, Key, Min, Max](float V) { if (Callbacks.Set) Callbacks.Set(Key, FMath::Lerp(Min, Max, V)); })
     .OnMouseCaptureEnd_Lambda([]() { RestoreViewportFocus(); })
     .ToolTipText(FText::FromString(Tooltip))
    ]
   ]
  ];
 }
};

inline TSharedRef<SSceneControls> MakeSceneControls(FSceneControlsCallbacks Callbacks)
{
 return SNew(SSceneControls).Callbacks(MoveTemp(Callbacks));
}
