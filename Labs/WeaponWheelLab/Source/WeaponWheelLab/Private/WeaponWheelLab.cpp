#include "SWeaponWheel.h"
#include "Modules/ModuleManager.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Containers/Ticker.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "ImageUtils.h"
#include "Widgets/SWindow.h"

class FWeaponWheelLabModule : public FDefaultGameModuleImpl
{
    TSharedPtr<SWeaponWheelLab> Root;
    FTSTicker::FDelegateHandle StartupTicker, CaptureTicker;
    FString AutoCapture;
    bool bExitAfterCapture=false;

    // Only used by the explicitly requested checkpoint verification launch.
    // Exercises the same handlers using the actual scaled canvas geometry.
    void VerifyInput()
    {
        const int32 Original=Root->Model->Selected;
        const FGeometry& Geometry=Root->Canvas->GetCachedGeometry();
        int32 Passed=0;
        for(int32 I=0; I<8; ++I)
        {
            const FVector2D Position=Geometry.LocalToAbsolute(FVector2D(Root->Canvas->FromDesign(WheelLayout::Slot(I,Root->Model->Radius))));
            FPointerEvent Move(0,Position,Position,TSet<FKey>(),EKeys::Invalid,0,FModifierKeysState());
            Root->Canvas->OnMouseMove(Geometry,Move);
            Passed+=Root->Model->Selected==I;
        }
        const FVector2D Center=Geometry.LocalToAbsolute(FVector2D(WheelLayout::Center()));
        Root->Canvas->OnMouseMove(Geometry,FPointerEvent(0,Center,Center,TSet<FKey>(),EKeys::Invalid,0,FModifierKeysState()));
        Passed+=Root->Model->Selected==7; // center dead zone retains selection
        auto Key=[this](FKey K){Root->OnKeyDown(Root->GetCachedGeometry(),FKeyEvent(K,FModifierKeysState(),0,false,0,0));};
        Key(EKeys::Right); Passed+=Root->Model->Selected==0;
        Key(EKeys::Left); Passed+=Root->Model->Selected==7;
        Key(EKeys::Tab); Passed+=!Root->bWheelVisible;
        Key(EKeys::Tab); Passed+=Root->bWheelVisible;
        Key(EKeys::R); Passed+=Root->bSettingsVisible;
        Key(EKeys::R); Passed+=!Root->bSettingsVisible;
        Root->Canvas->Select(Original);
        UE_LOG(LogTemp,Display,TEXT("WHEEL_INPUT_CHECK %d/15 scale=%.4f (actual canvas geometry, hover handlers, dead zone, key wrap, visibility, settings)"),Passed,Root->Model->OverallSize);

    }

    void WriteCapture(const FString& Path,TSharedPtr<SWidget> Widget=nullptr)
    {
        if(!Root.IsValid()) return;
        TArray<FColor> Pixels; FIntVector Size;
        if(!Widget.IsValid()) Widget=Root;
        if(FSlateApplication::Get().TakeScreenshot(Widget.ToSharedRef(),Pixels,Size))
        {
            TArray64<uint8> PNG;
            FImageUtils::PNGCompressImageArray(Size.X,Size.Y,Pixels,PNG);
            IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path),true);
            FFileHelper::SaveArrayToFile(PNG,*Path);
            UE_LOG(LogTemp,Display,TEXT("WHEEL_CAPTURE %s %dx%d"),*Path,Size.X,Size.Y);
            Root->Model->Status=TEXT("Screenshot saved in Saved/Captures");
        }
    }
public:
    virtual void StartupModule() override
    {
        if(IsRunningCommandlet() || GIsEditor) return;
        FParse::Value(FCommandLine::Get(),TEXT("WheelCapture="),AutoCapture);
        bExitAfterCapture=FParse::Param(FCommandLine::Get(),TEXT("WheelExitAfterCapture"));
        StartupTicker=FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([this](float)
        {
            if(!GEngine || !GEngine->GameViewport || !GEngine->GameViewport->GetWindow()) return true;
            Root=SNew(SWeaponWheelLab);
            GEngine->GameViewport->AddViewportWidgetContent(Root.ToSharedRef(),100);
            GEngine->GameViewport->GetWindow()->SetTitle(FText::FromString(TEXT("Prophecy · UI Workshop — Checkpoint 03")));
            GEngine->SetMaxFPS(60.f);
            // The lab background is a photograph; avoid drawing an empty 3D scene behind it.
            GEngine->GameViewport->bDisableWorldRendering=true;
            GEngine->GameViewport->SetMouseCaptureMode(EMouseCaptureMode::NoCapture);
            GEngine->GameViewport->SetMouseLockMode(EMouseLockMode::DoNotLock);
            if(auto World=GEngine->GameViewport->GetWorld()) if(auto PC=World->GetFirstPlayerController()) PC->bShowMouseCursor=true;
            FSlateApplication::Get().SetKeyboardFocus(Root,EFocusCause::SetDirectly);
            Root->Capture.BindLambda([this]
            {
                CaptureTicker=FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([this](float)
                { WriteCapture(FPaths::ProjectSavedDir()/TEXT("Captures/latest.png")); return false; }),.1f);
            });
            if(FParse::Param(FCommandLine::Get(),TEXT("WheelPresent"))) Root->Present(true);
            if(!AutoCapture.IsEmpty())
            {
                CaptureTicker=FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda(
                    [this, Stage=0, At=FPlatformTime::Seconds()+5., WithShadow=TArray<FColor>(), SavedShadow=0.f, SavedScale=1.f, SavedAccent=FLinearColor::White](float) mutable
                {
                    if(FPlatformTime::Seconds()<At) return true;
                    if(FParse::Param(FCommandLine::Get(),TEXT("WheelVerify")))
                    {
                        if(Stage==0) {VerifyInput(); ++Stage; return true;}
                        // Compare each independently adjustable layer across real rendered frames.
                        if(Stage>=1 && Stage<=8)
                        {
                            const int32 LayerIndex=(Stage-1)/2;
                            float* Values[]={&Root->Model->Shadow,&Root->Model->ArcShadow,&Root->Model->LabelShadow,&Root->Model->SelectionGlow};
                            const TCHAR* Names[]={TEXT("weapon"),TEXT("arcs"),TEXT("label"),TEXT("selection_glow")};
                            if(Stage%2)
                            {
                                FIntVector Size; FSlateApplication::Get().TakeScreenshot(Root.ToSharedRef(),WithShadow,Size);
                                SavedShadow=*Values[LayerIndex]; *Values[LayerIndex]=0.f; Root->Changed();
                            }
                            else
                            {
                                TArray<FColor> WithoutShadow; FIntVector Size;
                                FSlateApplication::Get().TakeScreenshot(Root.ToSharedRef(),WithoutShadow,Size);
                                int64 ChangedPixels=0;
                                if(WithShadow.Num()==WithoutShadow.Num())
                                    for(int32 I=0;I<WithShadow.Num();++I)
                                        ChangedPixels+=FMath::Abs(int32(WithShadow[I].R)-WithoutShadow[I].R)>2;
                                UE_LOG(LogTemp,Display,TEXT("WHEEL_SHADOW_CHECK layer=%s changed_pixels=%lld (separate frames)"),Names[LayerIndex],ChangedPixels);
                                WithShadow.Empty(); *Values[LayerIndex]=SavedShadow; Root->Changed();
                            }
                            ++Stage; return true;
                        }
                        if(Stage==9)
                        {
                            WriteCapture(AutoCapture);
                            SavedScale=Root->Model->OverallSize;
                            Root->Model->OverallSize=.65f; Root->Changed(); ++Stage; return true;
                        }
                        if(Stage==10)
                        {
                            VerifyInput();
                            WriteCapture(FPaths::GetPath(AutoCapture)/TEXT("checkpoint-03-small.png"));
                            Root->Model->OverallSize=Root->Model->MaxOverallSize(); Root->Changed(); ++Stage; return true;
                        }
                        if(Stage==11)
                        {
                            VerifyInput();
                            Root->Model->OverallSize=SavedScale; Root->Changed();
                            Root->ToggleSettings(); ++Stage; return true;
                        }
                        if(Stage==12)
                        {
                            WriteCapture(FPaths::GetPath(AutoCapture)/TEXT("checkpoint-03-settings.png"));
                            Root->ToggleSettings(); ++Stage; return true;
                        }
                        if(Stage==13)
                        {
                            FIntVector Size; FSlateApplication::Get().TakeScreenshot(Root.ToSharedRef(),WithShadow,Size);
                            SavedAccent=Root->Model->SelectionColor;
                            Root->ChooseSelectionColor(); ++Stage; return true;
                        }
                        if(Stage==14)
                        {
                            UE_LOG(LogTemp,Display,TEXT("WHEEL_COLOR_PICKER opened=%d"),GetColorPicker().IsValid());
                            if(GetColorPicker().IsValid()) WriteCapture(FPaths::GetPath(AutoCapture)/TEXT("checkpoint-03-color-picker.png"),GetColorPicker());
                            DestroyColorPicker();
                            Root->SetSelectionColor(FLinearColor(.04f,.8f,.4f,1.f)); ++Stage; return true;
                        }
                        if(Stage==15)
                        {
                            TArray<FColor> Recolored; FIntVector Size;
                            FSlateApplication::Get().TakeScreenshot(Root.ToSharedRef(),Recolored,Size);
                            int64 ChangedPixels=0;
                            if(WithShadow.Num()==Recolored.Num()) for(int32 I=0;I<Recolored.Num();++I)
                                ChangedPixels+=FMath::Abs(int32(WithShadow[I].R)-Recolored[I].R)>5 || FMath::Abs(int32(WithShadow[I].G)-Recolored[I].G)>5;
                            UE_LOG(LogTemp,Display,TEXT("WHEEL_COLOR_CHECK changed_pixels=%lld original_restored=1"),ChangedPixels);
                            Root->SetSelectionColor(SavedAccent); WithShadow.Empty(); ++Stage; return true;
                        }
                    }
                    WriteCapture(AutoCapture);
                    if(bExitAfterCapture) FPlatformMisc::RequestExit(false);
                    else if(FParse::Param(FCommandLine::Get(),TEXT("WheelReview"))) Root->Present(false);
                    return false;
                }),.2f);
            }
            UE_LOG(LogTemp,Display,TEXT("WHEEL_READY items=%d selected=%s"),Root->Model->Items.Num(),*Root->Model->Items[Root->Model->Selected].Id);
            UE_LOG(LogTemp,Display,TEXT("WHEEL_DPI aware=%d window_scale=%.2f"),IConsoleManager::Get().FindConsoleVariable(TEXT("EnableHighDPIAwareness"))->GetInt(),GEngine->GameViewport->GetWindow()->GetDPIScaleFactor());
            return false;
        }),.1f);
    }
    virtual void ShutdownModule() override
    {
        FTSTicker::GetCoreTicker().RemoveTicker(StartupTicker);
        FTSTicker::GetCoreTicker().RemoveTicker(CaptureTicker);
        Root.Reset();
    }
};
IMPLEMENT_PRIMARY_GAME_MODULE(FWeaponWheelLabModule, WeaponWheelLab, "WeaponWheelLab");
