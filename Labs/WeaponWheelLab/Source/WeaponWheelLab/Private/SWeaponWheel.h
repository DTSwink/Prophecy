#pragma once
#include "WheelPainter.h"
#include "WheelTextures.h"
#include "WheelMasks.h"
#include "Brushes/SlateDynamicImageBrush.h"
#include "Widgets/SLeafWidget.h"
#include "Widgets/SCompoundWidget.h"
#include "Widgets/SOverlay.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Layout/SBackgroundBlur.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SInvalidationPanel.h"
#include "Widgets/Layout/SScaleBox.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SSlider.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Colors/SColorPicker.h"
#include "Widgets/Colors/SColorBlock.h"
#include "Input/Reply.h"
#include "InputCoreTypes.h"

class SConstellationCanvas : public SLeafWidget
{
public:
    SLATE_BEGIN_ARGS(SConstellationCanvas) {} SLATE_END_ARGS()
    TSharedPtr<FWheelModel> Model;
    TStrongObjectPtr<UTexture2D> AtlasTexture;
    TSharedPtr<FSlateDynamicImageBrush> Solid;
    TSharedPtr<FSlateDynamicImageBrush> SoftDisc;
    TSharedPtr<FSlateDynamicImageBrush> OrbitShade;
    TSharedPtr<FSlateDynamicImageBrush> NameVeil, SelectionHalo, GlowSpot;
    float ShadowRadius=-1.f;
    uint32 ShadowRevision=0;
    FSimpleDelegate OnSelectionChanged;
    TArray<FSlateBrush> Icons;
    void PrepareOrbitShade()
    {
        if(ShadowRadius==Model->Radius) return;
        ShadowRadius=Model->Radius;
        constexpr int32 N=512;
        TArray<uint8> Pixels; Pixels.SetNumUninitialized(N*N*4);
        const float Extent=Model->Radius+100.f;
        auto Smooth=[](float T){T=FMath::Clamp(T,0.f,1.f);return T*T*(3.f-2.f*T);};
        for(int32 Y=0;Y<N;++Y) for(int32 X=0;X<N;++X)
        {
            const FVector2f P(((X+.5f)/N*2.f-1.f)*Extent,((Y+.5f)/N*2.f-1.f)*Extent);
            const float R=P.Size();
            const float Angle=FMath::Atan2(P.Y,P.X)+PI*.5f;
            const float Sector=Angle-FMath::RoundToFloat(Angle/(PI*.25f))*(PI*.25f);
            const float SlotDistance=FMath::Sqrt(FMath::Max(0.f,R*R+ShadowRadius*ShadowRadius-2.f*R*ShadowRadius*FMath::Cos(Sector)));
            const float Band=1.f-Smooth((FMath::Abs(R-(ShadowRadius+10.f))-12.f)/42.f);
            // This mask owns only the connecting arcs. Icon discs stay separately adjustable.
            const float A=Band*Smooth((SlotDistance-70.f)/35.f);
            const int32 I=(Y*N+X)*4;
            Pixels[I]=Pixels[I+1]=Pixels[I+2]=255; Pixels[I+3]=uint8(FMath::RoundToInt(A*255.f));
        }
        OrbitShade=FSlateDynamicImageBrush::CreateWithImageData(FName(*FString::Printf(TEXT("WheelOrbitShade_%u"),++ShadowRevision)),FVector2D(N,N),Pixels);
    }
    void Construct(const FArguments&, TSharedPtr<FWheelModel> InModel)
    {
        Model=InModel;
        SetCanTick(false);
        SetCursor(EMouseCursor::Default);
        TArray<uint8> WhitePixels; WhitePixels.Init(255,16);
        Solid=FSlateDynamicImageBrush::CreateWithImageData(FName(TEXT("WeaponWheelSolidWhite")),FVector2D(2,2),WhitePixels);
        // Reusable procedural alpha falloff: nine tinted quads instead of thousands of shadow vertices.
        TArray<uint8> DiscPixels; DiscPixels.SetNumUninitialized(64*64*4);
        for(int32 Y=0;Y<64;++Y) for(int32 X=0;X<64;++X)
        {
            const float Radius=FVector2f((X+.5f)/32.f-1.f,(Y+.5f)/32.f-1.f).Size();
            const float T=FMath::Clamp((Radius-.55f)/.45f,0.f,1.f);
            const int32 P=(Y*64+X)*4;
            DiscPixels[P]=DiscPixels[P+1]=DiscPixels[P+2]=255;
            DiscPixels[P+3]=uint8(FMath::RoundToInt(255.f*(1.f-T*T*(3.f-2.f*T))));
        }
        SoftDisc=FSlateDynamicImageBrush::CreateWithImageData(FName(TEXT("WeaponWheelSoftDisc")),FVector2D(64,64),DiscPixels);
        NameVeil=WheelMasks::NameVeil();
        SelectionHalo=WheelMasks::SelectionHalo();
        GlowSpot=WheelMasks::GlowSpot();
        PrepareOrbitShade();
        const FString Path=FPaths::ConvertRelativePathToFull(FPaths::ProjectDir()/TEXT("Resources/weapons.png"));
        AtlasTexture=LoadWheelIconTexture(Path);
        for(int32 I=0;I<8;++I)
        {
            FSlateBrush B;
            B.DrawAs=ESlateBrushDrawType::Image;
            B.SetResourceObject(AtlasTexture.Get());
            B.ImageSize=FVector2D(1774,887);
            B.SetUVRegion(FBox2f(FVector2f((I%4)*.25f,(I/4)*.5f),FVector2f((I%4+1)*.25f,(I/4+1)*.5f)));
            Icons.Add(B);
        }
    }
    virtual FVector2D ComputeDesiredSize(float) const override {return FVector2D(1024,949);}
    virtual bool SupportsKeyboardFocus() const override {return true;}
    FVector2f FromDesign(FVector2f P) const {return WheelLayout::Center()+(P-WheelLayout::Center())*Model->OverallSize;}
    FVector2f ToDesign(FVector2f P) const {return WheelLayout::Center()+(P-WheelLayout::Center())/Model->OverallSize;}
    void Select(int32 Index)
    {
        const int32 Next=(Index+8)%8;
        if(Model->Selected!=Next) {Model->Selected=Next;Invalidate(EInvalidateWidgetReason::Paint);OnSelectionChanged.ExecuteIfBound();}
    }
    virtual FReply OnMouseMove(const FGeometry& G,const FPointerEvent& E) override
    {
        Select(WheelLayout::HitTest(ToDesign(FVector2f(G.AbsoluteToLocal(E.GetScreenSpacePosition()))),Model->Radius,Model->Selected));
        return FReply::Handled();
    }
    virtual FReply OnMouseButtonDown(const FGeometry& G,const FPointerEvent& E) override
    {
        if(E.GetEffectingButton()==EKeys::LeftMouseButton)
        {
            OnMouseMove(G,E);
            Model->Status=FString::Printf(TEXT("Selected: %s"),*Model->Items[Model->Selected].Label);
            return FReply::Handled().SetUserFocus(SharedThis(this));
        }
        return FReply::Unhandled();
    }
    virtual int32 OnPaint(const FPaintArgs&,const FGeometry& G,const FSlateRect&,FSlateWindowElementList& Out,int32 Layer,const FWidgetStyle&,bool) const override
    {
        const FGeometry Scaled=G.MakeChild(G.GetLocalSize(),FSlateLayoutTransform(Model->OverallSize,FVector2D(WheelLayout::Center()*(1.f-Model->OverallSize))));
        FWheelPainter Painter(Out,Scaled,Layer,*Solid,*SoftDisc,*OrbitShade,*NameVeil,*SelectionHalo,*GlowSpot);
        if(Model->Items.Num()==8) Painter.DrawWheel(*Model,Icons);
        return Painter.GetLayer();
    }
};

class SWeaponWheelLab : public SCompoundWidget
{
public:
    SLATE_BEGIN_ARGS(SWeaponWheelLab) {} SLATE_END_ARGS()
    TSharedPtr<FWheelModel> Model;
    TSharedPtr<SConstellationCanvas> Canvas;
    TSharedPtr<SBackgroundBlur> BlurWidget;
    TSharedPtr<SInvalidationPanel> PaintCache;
    TSharedPtr<SWidget> SettingsPanel, WheelLayer, Footer;
    TSharedPtr<FSlateDynamicImageBrush> Background;
    bool bWheelVisible=true, bSettingsVisible=false, bPresentation=false;
    FSimpleDelegate Capture;
    void SetSelectionColor(FLinearColor Color)
    {
        Model->SelectionColor=Color.GetClamped(0.f,1.f); Model->SelectionColor.A=1.f;
        Changed();
    }
    FReply ChooseSelectionColor()
    {
        FColorPickerArgs Args(Model->SelectionColor,FOnLinearColorValueChanged::CreateSP(this,&SWeaponWheelLab::SetSelectionColor));
        Args.ParentWidget=SharedThis(this);
        Args.bUseAlpha=false; Args.bClampValue=true; Args.bExpandAdvancedSection=true;
        Args.sRGBOverride=true;
        Args.OnColorPickerCancelled=FOnColorPickerCancelled::CreateSP(this,&SWeaponWheelLab::SetSelectionColor);
        OpenColorPicker(Args);
        return FReply::Handled();
    }

    void Changed()
    {
        Model->OverallSize=FMath::Min(Model->OverallSize,Model->MaxOverallSize());
        BlurWidget->SetBlurStrength(bWheelVisible?Model->Blur:0.f);
        Canvas->PrepareOrbitShade();
        Canvas->Invalidate(EInvalidateWidgetReason::Paint);
        PaintCache->InvalidateRootLayout();
    }
    TSharedRef<SWidget> Knob(const FString& Name,float Min,float Max,float* Value,bool bWholeNumber=false)
    {
        return SNew(SVerticalBox)
        +SVerticalBox::Slot().AutoHeight().Padding(0,8,0,6)
        [SNew(STextBlock).Text_Lambda([Name,Value]{return FText::FromString(FString::Printf(TEXT("%s   %.2f"),*Name,*Value));})]
        +SVerticalBox::Slot().AutoHeight()
        [SNew(SSlider).Value_Lambda([Value,Min,Max]{return (*Value-Min)/(Max-Min);})
            .OnValueChanged_Lambda([this,Value,Min,Max,bWholeNumber](float V)
            {const float Next=FMath::Lerp(Min,Max,V); *Value=bWholeNumber?FMath::RoundToFloat(Next):Next;Changed();})];
    }
    TSharedRef<SWidget> SizeKnob()
    {
        return SNew(SVerticalBox)
        +SVerticalBox::Slot().AutoHeight().Padding(0,8,0,6)
        [SNew(STextBlock).Text_Lambda([this]{return FText::FromString(FString::Printf(TEXT("Overall UI size   %.0f%%"),Model->OverallSize*100.f));})]
        +SVerticalBox::Slot().AutoHeight()
        [SNew(SSlider).Value_Lambda([this]{return (Model->OverallSize-.45f)/(Model->MaxOverallSize()-.45f);})
            .OnValueChanged_Lambda([this](float V){Model->OverallSize=FMath::Lerp(.45f,Model->MaxOverallSize(),V);Changed();})];
    }
    void Construct(const FArguments&)
    {
        SetCanTick(false);
        Model=MakeShared<FWheelModel>();
        if(!Model->Load())
        {
            static const TCHAR* Labels[]={TEXT("BOMB"),TEXT("SWORD"),TEXT("DAGGER"),TEXT("SPEAR"),TEXT("AXE"),TEXT("MACE"),TEXT("BOW"),TEXT("SHIELD")};
            for(int32 I=0;I<8;++I) Model->Items.Add({FString::FromInt(I),Labels[I],I});
        }
        const FString Path=FPaths::ConvertRelativePathToFull(FPaths::ProjectDir()/TEXT("Resources/forest.png"));
        Background=MakeShared<FSlateDynamicImageBrush>(FName(*Path),FVector2D(885,820));
        ChildSlot
        [SNew(SOverlay)
            +SOverlay::Slot()
            [SNew(SScaleBox).Stretch(EStretch::ScaleToFill)
                [SNew(SImage).Image(Background.Get())]]
            +SOverlay::Slot()
            [SAssignNew(BlurWidget,SBackgroundBlur).Padding(0).BlurStrength(Model->Blur)]
            +SOverlay::Slot()
            [SAssignNew(WheelLayer,SScaleBox).Stretch(EStretch::ScaleToFit).HAlign(HAlign_Center).VAlign(VAlign_Center)
                [SNew(SBox).WidthOverride(1024).HeightOverride(949)
                    [SAssignNew(PaintCache,SInvalidationPanel)
                        [SAssignNew(Canvas,SConstellationCanvas,Model)]]]]
            +SOverlay::Slot().HAlign(HAlign_Right).VAlign(VAlign_Top).Padding(18,18)
            [SAssignNew(SettingsPanel,SBorder).Padding(18).BorderImage(FCoreStyle::Get().GetBrush("WhiteBrush")).BorderBackgroundColor(FLinearColor(.018f,.018f,.025f,.97f))
                [SNew(SBox).WidthOverride(248)
                    [SNew(SVerticalBox)
                        +SVerticalBox::Slot().AutoHeight()[SNew(STextBlock).Text(FText::FromString(TEXT("UI WORKSHOP · CHECKPOINT 03")))]
                        +SVerticalBox::Slot().AutoHeight()[SizeKnob()]
                        +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Background blur"),0,20,&Model->Blur)]
                        +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Weapon circle darkness"),0,.8f,&Model->Shadow)]
                        +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Connecting arc darkness"),0,.8f,&Model->ArcShadow)]
                        +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Name backdrop darkness"),0,.8f,&Model->LabelShadow)]
                        +SVerticalBox::Slot().AutoHeight().Padding(0,12,0,4)
                        [SNew(SButton).OnClicked(this,&SWeaponWheelLab::ChooseSelectionColor)
                            [SNew(SHorizontalBox)
                                +SHorizontalBox::Slot().AutoWidth().Padding(0,0,10,0)
                                [SNew(SColorBlock).Color_Lambda([this]{return Model->SelectionColor;}).Size(FVector2D(22,16)).ShowBackgroundForAlpha(false)]
                                +SHorizontalBox::Slot().FillWidth(1).VAlign(VAlign_Center)
                                [SNew(STextBlock).Text(FText::FromString(TEXT("Selection color…")))]]]
                        +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Selection glow"),0,1.5f,&Model->SelectionGlow)]
                        +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Weapon size"),110,200,&Model->IconSize)]
                        +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Wheel radius"),240,340,&Model->Radius)]
                        +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Center brightness"),0,1,&Model->CenterBrightness)]
                        +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Center font size"),12,36,&Model->CenterFontSize,true)]
                        +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Center decoration size"),0,1.5f,&Model->CenterDecorationSize)]
                        +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Circle line brightness"),0,1,&Model->CircleBrightness)]
                        +SVerticalBox::Slot().AutoHeight()[Knob(TEXT("Connecting line brightness"),0,1,&Model->ConnectingBrightness)]
                        +SVerticalBox::Slot().AutoHeight().Padding(0,16,0,4)
                        [SNew(SButton).Text(FText::FromString(TEXT("Save settings"))).OnClicked_Lambda([this]{Model->Save();return FReply::Handled();})]
                        +SVerticalBox::Slot().AutoHeight().Padding(0,4)
                        [SNew(SButton).Text(FText::FromString(TEXT("Reload settings · F5"))).OnClicked_Lambda([this]{Model->Load();Changed();return FReply::Handled();})]
                        +SVerticalBox::Slot().AutoHeight().Padding(0,4)
                        [SNew(SButton).Text(FText::FromString(TEXT("Capture · F12"))).OnClicked_Lambda([this]{Capture.ExecuteIfBound();return FReply::Handled();})]
                        +SVerticalBox::Slot().AutoHeight().Padding(0,10,0,0)
                        [SNew(STextBlock).AutoWrapText(true).Text_Lambda([this]{return FText::FromString(Model->Status);})]
                    ]]]
            +SOverlay::Slot().VAlign(VAlign_Bottom).HAlign(HAlign_Center).Padding(0,0,0,13)
            [SAssignNew(Footer,SHorizontalBox)
                +SHorizontalBox::Slot().AutoWidth().VAlign(VAlign_Center).Padding(8,0)
                [SNew(STextBlock).Font(FCoreStyle::GetDefaultFontStyle("Regular",10)).ColorAndOpacity(FLinearColor(1,1,1,.65f))
                    .Text(FText::FromString(TEXT("03   ·   Mouse / ← →   ·   Tab: open / close   ·   P: clean view")))]
                +SHorizontalBox::Slot().AutoWidth()
                [SNew(SButton).Text(FText::FromString(TEXT("Settings · R"))).OnClicked_Lambda([this]{ToggleSettings();return FReply::Handled();})]
            ]
        ];
        SettingsPanel->SetVisibility(EVisibility::Collapsed);
        Canvas->OnSelectionChanged.BindLambda([this]{PaintCache->InvalidateRootLayout();});
    }
    virtual bool SupportsKeyboardFocus() const override {return true;}
    void ToggleSettings()
    {
        bSettingsVisible=!bSettingsVisible;
        SettingsPanel->SetVisibility(bSettingsVisible?EVisibility::Visible:EVisibility::Collapsed);
    }
    void Present(bool bInPresent)
    {
        bPresentation=bInPresent;
        Footer->SetVisibility(bPresentation?EVisibility::Collapsed:EVisibility::Visible);
        if(bPresentation) {bSettingsVisible=false;SettingsPanel->SetVisibility(EVisibility::Collapsed);}
    }
    virtual FReply OnKeyDown(const FGeometry&,const FKeyEvent& E) override
    {
        const auto Key=E.GetKey();
        if(Key==EKeys::R) ToggleSettings();
        else if(Key==EKeys::P) Present(!bPresentation);
        else if(Key==EKeys::F5) {Model->Load();Changed();}
        else if(Key==EKeys::F12) Capture.ExecuteIfBound();
        else if(Key==EKeys::Right || Key==EKeys::Down) Canvas->Select(Model->Selected+1);
        else if(Key==EKeys::Left || Key==EKeys::Up) Canvas->Select(Model->Selected-1);
        else if(Key==EKeys::Tab)
        {
            bWheelVisible=!bWheelVisible;
            WheelLayer->SetVisibility(bWheelVisible?EVisibility::Visible:EVisibility::Collapsed); Changed();
        }
        else return FReply::Unhandled();
        return FReply::Handled();
    }
};
