#include "SPauseMenu.h"
#include "Modules/ModuleManager.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "Containers/Ticker.h"
#include "HAL/FileManager.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "ImageUtils.h"
#include "Widgets/SWindow.h"

class FPauseMenuLabModule:public FDefaultGameModuleImpl {
 TSharedPtr<SPauseMenu> Root;
 FTSTicker::FDelegateHandle Startup,CaptureTicker;
 FString CapturePath;
 void Capture(const FString& Path){
  TArray<FColor> Pixels;FIntVector Size;
  if(FSlateApplication::Get().TakeScreenshot(Root.ToSharedRef(),Pixels,Size)){
   TArray64<uint8> PNG;FImageUtils::PNGCompressImageArray(Size.X,Size.Y,Pixels,PNG);
   IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path),true);
   FFileHelper::SaveArrayToFile(PNG,*Path);
   UE_LOG(LogTemp,Display,TEXT("PAUSE_CAPTURE %s %dx%d"),*Path,Size.X,Size.Y);
  }
 }
 void Verify(){
  const auto Original=*Root->Model;int32 Passed=0;
  const auto G=Root->Canvas->GetCachedGeometry();
  Root->Model->HoverPaddingTop=Root->Model->HoverPaddingBottom=0;
  for(float TextScale:{.7f,1.f,1.3f})for(float Scale:{.65f,1.f,1.15f}){
   Root->Model->OverallSize=Scale;Root->Model->MenuSize=TextScale;Root->Changed();
   for(int32 I=0;I<5;++I){
    const auto B=Root->Canvas->HitBounds[I];const FVector2f Center((B.Left+B.Right)*.5f,(B.Top+B.Bottom)*.5f);
    auto Hover=[&](FVector2f Local){auto P=G.LocalToAbsolute(FVector2D(Local*Scale));Root->Canvas->OnMouseMove(G,FPointerEvent(0,P,P,TSet<FKey>(),EKeys::Invalid,0,FModifierKeysState()));};
    const auto Ink=Root->Canvas->Art->MenuBounds(*Root->Model,I);
    Passed+=FMath::IsNearlyEqual(B.Top+B.Bottom,Ink.Top+Ink.Bottom,.01f);
    Passed+=FMath::IsNearlyEqual(B.Bottom,PauseLayout::Row(*Root->Model,I).Y+PauseLayout::UnderlineOffset(*Root->Model)+Root->Model->HoverPaddingBottom,.01f);
    Root->Canvas->Select((I+1)%5);Hover(Center);Passed+=Root->Model->Selected==I;
    for(auto Outside:{FVector2f(Center.X,B.Top-3),FVector2f(Center.X,B.Bottom+3),FVector2f(B.Left-3,Center.Y),FVector2f(B.Right+3,Center.Y)}){
     Root->Canvas->Select((I+1)%5);Hover(Outside);
     const bool Clear=Root->Canvas->Hit(Outside*Scale)==INDEX_NONE;
     Passed+=Clear&&Root->Model->Selected==(I+1)%5;
    }
    if(TextScale==1&&Scale==1)UE_LOG(LogTemp,Display,TEXT("PAUSE_HIT %d %.1f %.1f %.1f %.1f"),I,B.Left,B.Top,B.Right,B.Bottom);
   }
  }
  const auto BeforePadding=Root->Canvas->HitBounds;
  Root->Model->HoverPaddingTop+=8;Root->Changed();
  for(int32 I=0;I<5;++I){const auto A=BeforePadding[I],B=Root->Canvas->HitBounds[I];
   Passed+=FMath::IsNearlyEqual(A.Top-8,B.Top,.01f);
   Passed+=FMath::IsNearlyEqual(A.Bottom,B.Bottom,.01f);
   Passed+=A.Left==B.Left&&A.Right==B.Right;
  }
  const auto TopOnly=Root->Canvas->HitBounds;
  Root->Model->HoverPaddingBottom+=5;Root->Changed();
  for(int32 I=0;I<5;++I){const auto A=TopOnly[I],B=Root->Canvas->HitBounds[I];
   Passed+=FMath::IsNearlyEqual(A.Top,B.Top,.01f);
   Passed+=FMath::IsNearlyEqual(A.Bottom+5,B.Bottom,.01f);
   Passed+=A.Left==B.Left&&A.Right==B.Right;
  }
  auto Key=[this](FKey K){Root->OnKeyDown(Root->GetCachedGeometry(),FKeyEvent(K,FModifierKeysState(),0,false,0,0));};
  Root->Canvas->Select(4);Key(EKeys::Down);Passed+=Root->Model->Selected==0;
  Key(EKeys::Up);Passed+=Root->Model->Selected==4;
  Root->Canvas->Select(0);Key(EKeys::Enter);Passed+=!Root->Model->bPaused;
  Key(EKeys::Escape);Passed+=Root->Model->bPaused;
  Key(EKeys::R);Passed+=Root->bPanel;Key(EKeys::Escape);Passed+=!Root->bPanel&&Root->Model->bPaused;
  *Root->Model=Original;Root->Changed();
  UE_LOG(LogTemp,Display,TEXT("PAUSE_VERIFY %d/351 underline bounds at nine scales, independent top/bottom padding and input"),Passed);
 }
public:
 virtual void StartupModule()override{
  if(IsRunningCommandlet()||GIsEditor)return;
  FParse::Value(FCommandLine::Get(),TEXT("PauseCapture="),CapturePath);
  Startup=FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([this](float){
   if(!GEngine||!GEngine->GameViewport||!GEngine->GameViewport->GetWindow())return true;
   Root=SNew(SPauseMenu);GEngine->GameViewport->AddViewportWidgetContent(Root.ToSharedRef(),100);
   GEngine->GameViewport->GetWindow()->SetTitle(FText::FromString(TEXT("Prophecy · Pause Workshop — Checkpoint 01")));
   GEngine->GameViewport->bDisableWorldRendering=true;GEngine->SetMaxFPS(60);
   GEngine->GameViewport->SetMouseCaptureMode(EMouseCaptureMode::NoCapture);
   GEngine->GameViewport->SetMouseLockMode(EMouseLockMode::DoNotLock);
   if(auto W=GEngine->GameViewport->GetWorld())if(auto PC=W->GetFirstPlayerController())PC->bShowMouseCursor=true;
   FSlateApplication::Get().SetKeyboardFocus(Root,EFocusCause::SetDirectly);
   Root->Capture.BindLambda([this]{CaptureTicker=FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([this](float){Capture(FPaths::ProjectSavedDir()/TEXT("Captures/latest.png"));return false;}),.1f);});
   if(!CapturePath.IsEmpty()){
    Root->Present(true);
    CaptureTicker=FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([this,At=FPlatformTime::Seconds()+6.,Stage=0,SavedStroke=Root->Model->MenuHairlineStrength](float)mutable{
     if(FPlatformTime::Seconds()<At)return true;
     if(Stage==0){if(FParse::Param(FCommandLine::Get(),TEXT("PauseVerify")))Verify();++Stage;
      if(FParse::Param(FCommandLine::Get(),TEXT("PauseOpticalVerify"))){Root->Model->MenuHairlineStrength=0;Root->Changed();}
      return true;}
     if(FParse::Param(FCommandLine::Get(),TEXT("PauseOpticalVerify"))&&Stage<=3){
      const TCHAR* Names[]={TEXT("optical-original.png"),TEXT("optical-medium.png"),TEXT("optical-strong.png")};
      Capture(FPaths::GetPath(CapturePath)/Names[Stage-1]);
      Root->Model->MenuHairlineStrength=Stage==1?14.f/18.f:Stage==2?1.f:SavedStroke;
      Root->Changed();++Stage;return true;
     }
     Capture(CapturePath);
     if(FParse::Param(FCommandLine::Get(),TEXT("PauseExitAfterCapture")))FPlatformMisc::RequestExit(false);
     else Root->Present(false);
     return false;
    }),.2f);
   }
   UE_LOG(LogTemp,Display,TEXT("PAUSE_READY"));return false;
  }),.1f);
 }
 virtual void ShutdownModule()override{FTSTicker::GetCoreTicker().RemoveTicker(Startup);FTSTicker::GetCoreTicker().RemoveTicker(CaptureTicker);Root.Reset();}
};
IMPLEMENT_PRIMARY_GAME_MODULE(FPauseMenuLabModule,PauseMenuLab,"PauseMenuLab");

