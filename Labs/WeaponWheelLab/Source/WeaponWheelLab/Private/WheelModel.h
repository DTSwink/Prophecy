#pragma once
#include "CoreMinimal.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"

// Coordinates are independent from the viewport and from the renderer.
namespace WheelLayout
{
    constexpr float Width = 1024.f;
    constexpr float Height = 949.f;
    inline FVector2f Center() { return FVector2f(512.f, 465.f); }
    inline FVector2f Polar(float Degrees, float Radius)
    {
        const float A = FMath::DegreesToRadians(Degrees);
        return FVector2f(FMath::Cos(A), FMath::Sin(A)) * Radius;
    }
    inline FVector2f Slot(int32 Index, float Radius) { return Center() + Polar(-90.f + Index * 45.f, Radius); }
    inline int32 HitTest(FVector2f Point, float Radius, int32 Previous)
    {
        const FVector2f D = Point - Center();
        if (D.Size() < Radius * .42f || D.Size() > Radius + 115.f) return Previous;
        const float Degrees = FMath::RadiansToDegrees(FMath::Atan2(D.Y, D.X)) + 90.f;
        return (FMath::FloorToInt((Degrees + 22.5f + 360.f) / 45.f)) % 8;
    }
}

struct FWheelItem { FString Id; FString Label; int32 AtlasCell = 0; };
struct FWheelModel
{
    float Blur = 9.f, Shadow = .46f, ArcShadow = .24f, LabelShadow = .58f;
    float Radius = 300.f, IconSize = 170.f, OrnamentOpacity = 1.f;
    float CenterBrightness = 1.f, CircleBrightness = 1.f, ConnectingBrightness = 1.f;
    float CenterFontSize = 22.f;
    float CenterDecorationSize = 1.f;
    float OverallSize = 1.f, SelectionGlow = 1.f;
    FLinearColor SelectionColor = FLinearColor(.57f,.075f,1.f,1.f);
    int32 Selected = 1;
    TArray<FWheelItem> Items;
    FString Status;
    static FString ConfigPath() { return FPaths::ProjectDir() / TEXT("Resources/wheel.json"); }
    float MaxOverallSize() const { return FMath::Min(1.4f,455.f/(Radius+115.f)); }

    bool Load()
    {
        FString Text;
        TSharedPtr<FJsonObject> Root;
        if (!FFileHelper::LoadFileToString(Text, *ConfigPath()) || !FJsonSerializer::Deserialize(TJsonReaderFactory<>::Create(Text), Root) || !Root)
        { Status = TEXT("Could not read settings"); return false; }
        const TArray<TSharedPtr<FJsonValue>>* List;
        if (!Root->TryGetArrayField(TEXT("items"), List) || List->Num() != 8)
        { Status = TEXT("The file must contain eight weapons"); return false; }
        TArray<FWheelItem> NewItems;
        for (const auto& Value : *List)
        {
            const auto Item = Value->AsObject();
            FWheelItem NewItem;
            double Cell;
            if (!Item || !Item->TryGetStringField(TEXT("id"), NewItem.Id) || !Item->TryGetStringField(TEXT("label"), NewItem.Label) || !Item->TryGetNumberField(TEXT("atlas_cell"), Cell) || Cell < 0 || Cell > 7)
            { Status = TEXT("Invalid weapon definition"); return false; }
            NewItem.AtlasCell = int32(Cell); NewItems.Add(NewItem);
        }
        Items = MoveTemp(NewItems);
        auto Number = [&Root](const TCHAR* Name, float Current, float Min, float Max)
        { double V; return Root->TryGetNumberField(Name, V) && FMath::IsFinite(V) ? FMath::Clamp(float(V), Min, Max) : Current; };
        Blur = Number(TEXT("blur"), Blur, 0, 20);
        Shadow = Number(TEXT("shadow"), Shadow, 0, .8f);
        ArcShadow = Number(TEXT("arc_shadow"), ArcShadow, 0, .8f);
        LabelShadow = Number(TEXT("label_shadow"), LabelShadow, 0, .8f);
        Radius = Number(TEXT("radius"), Radius, 240, 340);
        OverallSize = Number(TEXT("overall_size"), OverallSize, .45f, MaxOverallSize());
        SelectionGlow = Number(TEXT("selection_glow"), SelectionGlow, 0, 1.5f);
        const TArray<TSharedPtr<FJsonValue>>* ColorValues;
        if(Root->TryGetArrayField(TEXT("selection_color_linear"),ColorValues) && ColorValues->Num()==3)
        {
            double RGB[3]; bool Valid=true;
            for(int32 I=0;I<3;++I) Valid &= (*ColorValues)[I]->TryGetNumber(RGB[I]) && FMath::IsFinite(RGB[I]);
            if(Valid) SelectionColor=FLinearColor(FMath::Clamp(float(RGB[0]),0.f,1.f),FMath::Clamp(float(RGB[1]),0.f,1.f),FMath::Clamp(float(RGB[2]),0.f,1.f),1.f);
        }
        IconSize = Number(TEXT("icon_size"), IconSize, 110, 200);
        OrnamentOpacity = Number(TEXT("ornament_opacity"), OrnamentOpacity, .2f, 1);
        CenterBrightness = Number(TEXT("center_brightness"), 1.f, 0, 1);
        CenterFontSize = FMath::RoundToFloat(Number(TEXT("center_font_size"), 22.f, 12, 36));
        CenterDecorationSize = Number(TEXT("center_decoration_size"), 1.f, 0, 1.5f);
        CircleBrightness = Number(TEXT("circle_brightness"), OrnamentOpacity, 0, 1);
        ConnectingBrightness = Number(TEXT("connecting_brightness"), OrnamentOpacity, 0, 1);
        Selected = FMath::RoundToInt(Number(TEXT("selected"), float(Selected), 0, 7));
        Status = TEXT("Settings loaded"); return true;
    }
    bool Save()
    {
        auto Root = MakeShared<FJsonObject>();
        Root->SetNumberField(TEXT("blur"), Blur); Root->SetNumberField(TEXT("shadow"), Shadow);
        Root->SetNumberField(TEXT("arc_shadow"), ArcShadow); Root->SetNumberField(TEXT("label_shadow"), LabelShadow);
        Root->SetNumberField(TEXT("radius"), Radius); Root->SetNumberField(TEXT("icon_size"), IconSize);
        Root->SetNumberField(TEXT("overall_size"), OverallSize); Root->SetNumberField(TEXT("selection_glow"), SelectionGlow);
        Root->SetArrayField(TEXT("selection_color_linear"),{MakeShared<FJsonValueNumber>(SelectionColor.R),MakeShared<FJsonValueNumber>(SelectionColor.G),MakeShared<FJsonValueNumber>(SelectionColor.B)});
        Root->SetNumberField(TEXT("ornament_opacity"), OrnamentOpacity); Root->SetNumberField(TEXT("selected"), Selected);
        Root->SetNumberField(TEXT("center_brightness"), CenterBrightness);
        Root->SetNumberField(TEXT("center_font_size"), CenterFontSize);
        Root->SetNumberField(TEXT("center_decoration_size"), CenterDecorationSize);
        Root->SetNumberField(TEXT("circle_brightness"), CircleBrightness);
        Root->SetNumberField(TEXT("connecting_brightness"), ConnectingBrightness);
        TArray<TSharedPtr<FJsonValue>> List;
        for (const auto& Item : Items)
        {
            auto Obj = MakeShared<FJsonObject>(); Obj->SetStringField(TEXT("id"), Item.Id);
            Obj->SetStringField(TEXT("label"), Item.Label); Obj->SetNumberField(TEXT("atlas_cell"), Item.AtlasCell);
            List.Add(MakeShared<FJsonValueObject>(Obj));
        }
        Root->SetArrayField(TEXT("items"), List);
        FString Text; FJsonSerializer::Serialize(Root, TJsonWriterFactory<>::Create(&Text));
        const bool Saved = FFileHelper::SaveStringToFile(Text, *ConfigPath(), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        Status = Saved ? TEXT("Settings saved") : TEXT("Could not save settings"); return Saved;
    }
};
