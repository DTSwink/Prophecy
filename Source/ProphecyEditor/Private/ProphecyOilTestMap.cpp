#include "CoreMinimal.h"
#include "HAL/IConsoleManager.h"
#include "Engine/World.h"
#include "Landscape.h"
#include "LandscapeComponent.h"
#include "LandscapeInfo.h"
#include "LandscapeLayerInfoObject.h"
#include "Materials/MaterialInterface.h"

// Called only by Tools/Oil/CreateTestMap.py in an isolated editor process.
static FAutoConsoleCommandWithWorld OilTerrain(TEXT("Prophecy.Oil.CreateTerrain"),TEXT("Create the isolated oil test Landscape."),
    FConsoleCommandWithWorldDelegate::CreateLambda([](UWorld* World)
    {
        if(!World || World->IsGameWorld() || !World->GetName().Equals(TEXT("M_OilTest")))return;
        ALandscape* Land=World->SpawnActor<ALandscape>();Land->SetActorLabel(TEXT("Oil_Landscape"));
        Land->LandscapeMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/_mygame/Tests/Oil/M_OilLabLandscape.M_OilLabLandscape"));
        Land->SetActorLocation(FVector(500,-600,-30));Land->SetActorScale3D(FVector(20,20,30));
        TMap<FGuid,TArray<uint16>> Height;auto& H=Height.Add(FGuid());H.SetNum(64*64);
        for(int Y=0;Y<64;++Y)for(int X=0;X<64;++X)H[Y*64+X]=32768+FMath::RoundToInt(120*FMath::Sin(X*.10)*FMath::Sin(Y*.08));
        TMap<FGuid,TArray<FLandscapeImportLayerInfo>> Layers;auto& Infos=Layers.Add(FGuid());
        FLandscapeImportLayerInfo Hole(TEXT("Visibility"));Hole.LayerInfo=ALandscapeProxy::VisibilityLayer;Hole.LayerData.Init(0,64*64);
        for(int Y=43;Y<54;++Y)for(int X=43;X<54;++X)Hole.LayerData[Y*64+X]=255;
        Infos.Add(MoveTemp(Hole));
        Land->Import(FGuid::NewGuid(),0,0,63,63,1,63,Height,nullptr,Layers,ELandscapeImportAlphamapType::Additive,{});
        Land->PostEditChange();Land->MarkPackageDirty();
    }));
