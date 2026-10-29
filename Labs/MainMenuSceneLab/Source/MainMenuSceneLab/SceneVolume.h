#pragma once

#include "CoreMinimal.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Components/HeterogeneousVolumeComponent.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "Materials/MaterialInstanceDynamic.h"

// Native volume integration. The renderer samples a three-dimensional density
// material inside these bounds, with its normal lighting and shadow integration.
// SceneTime is driven by the lab so pause/replay also pause the smoke advection.
struct FSceneVolume
{
 AActor* Actor = nullptr;
 UHeterogeneousVolumeComponent* Volume = nullptr;
 UMaterialInstanceDynamic* MID = nullptr;
 AExponentialHeightFog* AtmosphereActor = nullptr;
 UExponentialHeightFogComponent* Atmosphere = nullptr;
 bool bSmokeVisible = false;

 void Build(UWorld* World, UMaterialInterface* Material)
 {
  if (!World || Volume) return;
  if (Material)
  {
   Actor = World->SpawnActor<AActor>();
   Actor->SetActorLabel(TEXT("Upper smoke - native heterogeneous volume"));
   Volume = NewObject<UHeterogeneousVolumeComponent>(Actor, TEXT("UpperSmokeVolume"));
   Actor->AddInstanceComponent(Volume);
   Actor->SetRootComponent(Volume);
   Volume->SetMobility(EComponentMobility::Movable);
   Volume->SetCollisionEnabled(ECollisionEnabled::NoCollision);
   Volume->bPivotAtCentroid = true;
   Volume->VolumeResolution = FIntVector(96,192,64);
   Volume->StepFactor = 1.f;
   Volume->ShadowStepFactor = 2.f;
   Volume->LightingDownsampleFactor = 2.f;
   Volume->SetCastShadow(true);
   MID = UMaterialInstanceDynamic::Create(Material, Volume);
   // Virtual call through the exported base API also works with this component's
   // MinimalAPI class in installed (precompiled) engine distributions.
   static_cast<UMeshComponent*>(Volume)->SetMaterial(0, MID);
   Volume->RegisterComponent();
   Volume->SetComponentTickEnabled(false); // No SVT animation/streaming to advance.
   Apply(.25f,500.f,1.4f,.6f);
  }

  AtmosphereActor = World->SpawnActor<AExponentialHeightFog>(FVector(0,0,100),FRotator::ZeroRotator);
  AtmosphereActor->SetActorLabel(TEXT("Rain atmosphere - volumetric height fog"));
  Atmosphere = AtmosphereActor->GetComponent();
  Atmosphere->SetMobility(EComponentMobility::Movable);
  Atmosphere->SetFogHeightFalloff(.035f);
  Atmosphere->SetFogInscatteringColor(FLinearColor(.045f,.052f,.066f));
  Atmosphere->SetFogMaxOpacity(.6f);
  Atmosphere->SetStartDistance(80.f);
  Atmosphere->SetVolumetricFogScatteringDistribution(.25f);
  Atmosphere->SetVolumetricFogAlbedo(FColor(205,215,230));
  Atmosphere->SetVolumetricFogEmissive(FLinearColor::Black);
  Atmosphere->SetVolumetricFogExtinctionScale(1.f);
  Atmosphere->SetVolumetricFogDistance(5000.f);
  Atmosphere->SetVolumetricFogStartDistance(80.f);
  Atmosphere->SetVolumetricFogNearFadeInDistance(160.f);
  ApplyAtmosphere(.25f);
 }

 void Apply(float Amount, float Height, float Spread, float Softness)
 {
  bSmokeVisible = MID && Volume && Amount > .0001f;
  if (!Volume || !MID) return;
  Volume->SetVisibility(bSmokeVisible);
  const float Width = FMath::Clamp(Spread,.2f,4.f);
  const FVector Center(850.f,140.f,FMath::Clamp(Height,80.f,1500.f));
  const FVector Extent(650.f*FMath::Sqrt(Width),1350.f*Width,350.f*FMath::Pow(Width,.2f));
  Volume->SetWorldLocation(Center);
  Volume->SetWorldScale3D(FVector(2*Extent.X/96.f,2*Extent.Y/192.f,2*Extent.Z/64.f));
  MID->SetVectorParameterValue(TEXT("VolumeCenter"),FLinearColor(Center.X,Center.Y,Center.Z,0));
  MID->SetVectorParameterValue(TEXT("VolumeExtent"),FLinearColor(Extent.X,Extent.Y,Extent.Z,0));
  // Extinction is in inverse centimetres: changing the real depth changes the
  // integrated optical thickness rather than merely changing a surface opacity.
  MID->SetScalarParameterValue(TEXT("SmokeDensity"),.0024f*FMath::Clamp(Amount,0.f,1.f));
  MID->SetScalarParameterValue(TEXT("SmokeSoftness"),FMath::Clamp(Softness,0.f,1.f));
 }

 void ApplyAtmosphere(float Amount)
 {
  if (!Atmosphere) return;
  const float Strength = FMath::Clamp(Amount,0.f,1.f);
  Atmosphere->SetVisibility(Strength>.0001f);
  Atmosphere->SetVolumetricFog(Strength>.0001f);
  Atmosphere->SetFogDensity(.25f*Strength);
 }

 void Tick(float Clock)
 {
  if (IsVisible()) MID->SetScalarParameterValue(TEXT("SceneTime"),Clock);
 }

 bool IsVisible() const { return bSmokeVisible; }
};
