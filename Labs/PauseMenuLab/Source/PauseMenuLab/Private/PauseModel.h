#pragma once
#include "CoreMinimal.h"
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonReader.h"
struct FPauseModel {
 float OverallSize=1,TitleSize=1,MenuSize=1,RowSpacing=72,Tracking=7,Blur=3,Darkness=.83f,GradientWidth=930,Glow=.75f,LineWidth=220;
 float MenuHairlineStrength=14.f/18.f;
 float SelectedTextWhiteness=0;
 float UnselectedTextOpacity=.9f;
 float UnderlineGap=16;
 float UnderlineLeftCrop=0;
 float HoverPaddingTop=0,HoverPaddingBottom=0;
 float HoverPaddingRight=0;
 FLinearColor Accent=FLinearColor(.65f,.15f,.95f,1);
 int32 Selected=0;
 bool bPaused=true;
 FString Status;
 inline static const TArray<FString> Labels={TEXT("RESUME"),TEXT("INVENTORY"),TEXT("JOURNAL"),TEXT("SETTINGS"),TEXT("QUIT TO MENU")};
 FString Path() const {return FPaths::ProjectDir()/TEXT("Resources/pause.json");}
 void Fields(TFunctionRef<void(const TCHAR*,float&,float,float)> F) {
 F(TEXT("overall_size"),OverallSize,.65f,1.15f); F(TEXT("title_size"),TitleSize,.6f,1.3f);
 F(TEXT("menu_size"),MenuSize,.7f,1.3f); F(TEXT("row_spacing"),RowSpacing,52,85);
 F(TEXT("menu_hairline_strength"),MenuHairlineStrength,0,1);
 F(TEXT("selected_text_whiteness"),SelectedTextWhiteness,0,1);
 F(TEXT("unselected_text_opacity"),UnselectedTextOpacity,0,1);
 F(TEXT("tracking"),Tracking,0,12); F(TEXT("blur"),Blur,0,15);
 F(TEXT("darkness"),Darkness,0,1); F(TEXT("gradient_width"),GradientWidth,500,1300);
 F(TEXT("glow"),Glow,0,1.5f); F(TEXT("line_width"),LineWidth,100,380);
 F(TEXT("underline_gap"),UnderlineGap,0,30);
 F(TEXT("underline_left_crop"),UnderlineLeftCrop,0,.05f);
 F(TEXT("hover_padding_top"),HoverPaddingTop,0,20);
 F(TEXT("hover_padding_bottom"),HoverPaddingBottom,0,20);
 F(TEXT("hover_padding_right"),HoverPaddingRight,0,200);
 F(TEXT("accent_r"),Accent.R,0,1); F(TEXT("accent_g"),Accent.G,0,1); F(TEXT("accent_b"),Accent.B,0,1);
 }
 bool Load() {FString S; TSharedPtr<FJsonObject> J; if(!FFileHelper::LoadFileToString(S,*Path())||!FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(S),J)||!J.IsValid())return false;
 double LegacyPadding;
 if(J->TryGetNumberField(TEXT("hover_padding"),LegacyPadding)&&FMath::IsFinite(LegacyPadding)){
  if(!J->HasField(TEXT("hover_padding_top")))HoverPaddingTop=FMath::Clamp(float(LegacyPadding),0.f,20.f);
  if(!J->HasField(TEXT("hover_padding_bottom")))HoverPaddingBottom=FMath::Clamp(float(LegacyPadding),0.f,20.f);
 }
 Fields([&](const TCHAR* K,float& V,float Lo,float Hi){double N;if(J->TryGetNumberField(K,N)&&FMath::IsFinite(N))V=FMath::Clamp(float(N),Lo,Hi);});
 Status=TEXT("Settings loaded");return true;}
 bool Save() {auto J=MakeShared<FJsonObject>();Fields([&](const TCHAR* K,float& V,float,float){J->SetNumberField(K,V);});FString S;FJsonSerializer::Serialize(J,TJsonWriterFactory<>::Create(&S));bool OK=FFileHelper::SaveStringToFile(S,*Path());Status=OK?TEXT("Settings saved"):TEXT("Save failed");return OK;}
};
namespace PauseLayout {
 const FVector2D Design(1672,941);
 inline float UnderlineOffset(const FPauseModel& M){return 29*M.MenuSize+M.UnderlineGap;}
 inline FVector2f Row(const FPauseModel& M,int32 I) {return FVector2f(86,434+M.RowSpacing*I);}
}


