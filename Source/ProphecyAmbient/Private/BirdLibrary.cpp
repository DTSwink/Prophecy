#include "BirdLibrary.h"
#include "Bird.h"
#include "BirdZone.h"
#include "Engine/World.h"

ABirdZone* UBirdLibrary::SpawnBirdZone(const UObject* WorldContext, FVector Location, FVector BoxExtent, EBirdSpecies Species, int32 BirdCount,
	FLinearColor PrimaryColour, FLinearColor SecondaryColour, float SizeMultiplier, float AirTime, bool bAmbientCries, FRotator Rotation,
	bool bShowInGame, int32 Seed)
{
	UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	if (!World) return nullptr;
	const FTransform T(Rotation, Location);
	ABirdZone* Z = World->SpawnActorDeferred<ABirdZone>(ABirdZone::StaticClass(), T, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
	if (!Z) return nullptr;
	Z->BoxExtent = BoxExtent;
	Z->Species = Species;
	Z->BirdCount = FMath::Clamp(BirdCount, 0, 64);
	Z->PrimaryColour = PrimaryColour;
	Z->SecondaryColour = SecondaryColour;
	Z->SizeMultiplier = FMath::Clamp(SizeMultiplier, 0.3f, 3.f);
	Z->AirTime = FMath::Clamp(AirTime, 0.f, 1.f);
	Z->bAmbientCries = bAmbientCries;
	Z->bShowInGame = bShowInGame;
	Z->Seed = Seed;
	Z->FinishSpawning(T);
	return Z;
}

void UBirdLibrary::BirdCry(ABird* Bird, float Duration, float Openness)
{
	if (Bird) Bird->Cry(Duration, Openness);
}

void UBirdLibrary::KillBird(ABird* Bird, FVector HitLocation, FVector Impulse)
{
	if (Bird) Bird->Kill(HitLocation, Impulse, nullptr, NAME_None);
}

void UBirdLibrary::AddBirdThreat(const UObject* WorldContext, AActor* Actor)
{
	if (ABirdFlock* F = ABirdFlock::Find(WorldContext, true)) F->AddThreatActor(Actor);
}

void UBirdLibrary::AddBirdLethalClass(const UObject* WorldContext, TSubclassOf<AActor> Class)
{
	if (ABirdFlock* F = ABirdFlock::Find(WorldContext, true)) F->AddLethalClass(Class);
}

TArray<ABird*> UBirdLibrary::GetAllBirds(const UObject* WorldContext)
{
	if (ABirdFlock* F = ABirdFlock::Find(WorldContext, false)) return F->GetBirds();
	return {};
}

void UBirdLibrary::SetBirdsEnabled(const UObject* WorldContext, bool bEnabled)
{
	if (ABirdFlock* F = ABirdFlock::Find(WorldContext, false)) F->bEnabled = bEnabled;
}

FBirdFlockStats UBirdLibrary::GetBirdStats(const UObject* WorldContext)
{
	if (ABirdFlock* F = ABirdFlock::Find(WorldContext, false)) return F->GetStats();
	return FBirdFlockStats();
}

void UBirdLibrary::SetBirdBleedCondition(const UObject* WorldContext, FBirdBleedCondition Condition)
{
	if (ABirdFlock* F = ABirdFlock::Find(WorldContext, true)) F->SetBleedCondition(Condition);
}

void UBirdLibrary::ClearBirdBleedCondition(const UObject* WorldContext)
{
	if (ABirdFlock* F = ABirdFlock::Find(WorldContext, false)) F->ClearBleedCondition();
}

void UBirdLibrary::AddBirdBloodStain(ABird* Bird, FVector WorldLocation, FVector Direction, float RadiusCm, bool bSplat)
{
	if (Bird) Bird->AddBloodStain(WorldLocation, Direction, RadiusCm, bSplat);
}

void UBirdLibrary::AddBirdWater(const UObject* WorldContext, AActor* WaterActor)
{
	if (ABirdFlock* F = ABirdFlock::Find(WorldContext, true)) F->AddWaterActor(WaterActor);
}

bool UBirdLibrary::SendBirdFishing(ABird* Bird)
{
	return Bird && Bird->GoFishing();
}
