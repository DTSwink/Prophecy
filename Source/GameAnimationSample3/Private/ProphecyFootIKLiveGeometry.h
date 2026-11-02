#pragma once
#include "CoreMinimal.h"
#include "Dom/JsonObject.h"

// A moving overlap query is not a geometry revision. Reuse a prediction only
// where both captures prove the same physical faces; actual edits still reject.
namespace ProphecyFootIKLiveGeometry
{
struct FTile
{
    TArray<double,TInlineAllocator<14>> Values;
    FBox Bounds{ForceInit};
    bool Equals(const FTile& Other) const { return Values==Other.Values; }
};
struct FSnapshot
{
    FBox Query{ForceInit};
    FBox WorldQuery{ForceInit};
    TMap<FString,FTile> Tiles;
    bool Valid=false;
};
inline bool Numbers(const TSharedPtr<FJsonObject>& Object,const TCHAR* Key,int32 Count,TArray<double,TInlineAllocator<14>>& Out)
{
    const TArray<TSharedPtr<FJsonValue>>* A=nullptr;
    if(!Object->TryGetArrayField(Key,A)||A->Num()!=Count)return false;
    for(const auto& V:*A){if(!V||V->Type!=EJson::Number||!FMath::IsFinite(V->AsNumber()))return false;Out.Add(V->AsNumber());}return true;
}
inline FSnapshot Read(const TSharedPtr<FJsonObject>& Object)
{
    FSnapshot S;if(!Object)return S;
    TArray<double,TInlineAllocator<14>> Bounds;
    if(!Numbers(Object,TEXT("captureBounds"),6,Bounds))return S;
    S.Query=FBox(FVector(Bounds[0],Bounds[1],Bounds[2]),FVector(Bounds[3],Bounds[4],Bounds[5]));
    if(S.Query.Min.X>=S.Query.Max.X||S.Query.Min.Y>=S.Query.Max.Y||S.Query.Min.Z>=S.Query.Max.Z)return S;
    Bounds.Reset();if(!Numbers(Object,TEXT("captureWorldBounds"),6,Bounds))return S;
    S.WorldQuery=FBox(FVector(Bounds[0],Bounds[1],Bounds[2]),FVector(Bounds[3],Bounds[4],Bounds[5]));
    if(S.WorldQuery.Min.X>=S.WorldQuery.Max.X||S.WorldQuery.Min.Y>=S.WorldQuery.Max.Y||S.WorldQuery.Min.Z>=S.WorldQuery.Max.Z)return S;
    const TArray<TSharedPtr<FJsonValue>>* Records=nullptr;if(!Object->TryGetArrayField(TEXT("tiles"),Records))return S;
    for(const auto& V:*Records)
    {
        if(!V||V->Type!=EJson::Object)return S;const auto T=V->AsObject();FString Id;
        if(!T||!T->TryGetStringField(TEXT("id"),Id)||S.Tiles.Contains(Id))return S;
        FTile Tile;
        if(T->HasField(TEXT("point")))
        {
            if(!Numbers(T,TEXT("point"),3,Tile.Values)||!Numbers(T,TEXT("u"),3,Tile.Values)||!Numbers(T,TEXT("v"),3,Tile.Values)||!Numbers(T,TEXT("bounds"),4,Tile.Values))return S;
            bool Shaped=true;T->TryGetBoolField(TEXT("shaped"),Shaped);Tile.Values.Add(Shaped?1.:0.);
            const auto& N=Tile.Values;const FVector P(N[0],N[1],N[2]),U(N[3],N[4],N[5]),W(N[6],N[7],N[8]);
            if(N[9]>=N[10]||N[11]>=N[12])return S;
            for(double X:{N[9],N[10]})for(double Y:{N[11],N[12]})Tile.Bounds+=P+U*X+W*Y;
        }
        else
        {
            for(const TCHAR* Key:{TEXT("x0"),TEXT("x1"),TEXT("z0"),TEXT("z1"),TEXT("y")})
            {double Number=0;if(!T->TryGetNumberField(Key,Number)||!FMath::IsFinite(Number))return S;Tile.Values.Add(Number);}
            const auto& N=Tile.Values;if(N[0]>=N[1]||N[2]>=N[3])return S;
            Tile.Bounds=FBox(FVector(N[0],N[4],N[2]),FVector(N[1],N[4],N[3]));
        }
        S.Tiles.Add(Id,MoveTemp(Tile));
    }
    S.Valid=true;return S;
}
inline bool Compatible(const FSnapshot& Prediction,const FSnapshot& Current)
{
    if(!Prediction.Valid||!Current.Valid)return false;
    for(const auto& Old:Prediction.Tiles)
    {
        if(const auto* Now=Current.Tiles.Find(Old.Key)){if(!Old.Value.Equals(*Now))return false;}
        else if(Old.Value.Bounds.Intersect(Current.Query))return false;
    }
    for(const auto& Now:Current.Tiles)
        if(!Prediction.Tiles.Contains(Now.Key)&&Now.Value.Bounds.Intersect(Prediction.Query))return false;
    return true;
}
}
