#include "BumblebeeLibrary.h"
#include "BumblebeeZone.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "HAL/IConsoleManager.h"

ABumblebeeZone* UBumblebeeLibrary::SpawnBumblebeeZone(const UObject* WorldContext, FVector Location, FVector BoxExtent, int32 BeeCount,
	float Preference, float SizeMultiplier, float WingBeatHz, float WalkSpeed, float AirTime, FRotator Rotation, bool bAvoidIndoors, bool bShowInGame)
{
	UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	if (!World) return nullptr;
	const FTransform T(Rotation, Location);
	ABumblebeeZone* Z = World->SpawnActorDeferred<ABumblebeeZone>(ABumblebeeZone::StaticClass(), T, nullptr, nullptr, ESpawnActorCollisionHandlingMethod::AlwaysSpawn);
	if (!Z) return nullptr;
	Z->BoxExtent = BoxExtent;
	Z->BeeCount = BeeCount;
	Z->Preference = Preference;
	Z->BeeSizeMultiplier = SizeMultiplier;
	Z->WingBeatHz = FMath::Clamp(WingBeatHz, 1.f, 400.f);
	Z->WalkSpeed = FMath::Clamp(WalkSpeed, 0.1f, 30.f);
	Z->AirTime = FMath::Clamp(AirTime, 0.f, 1.f);
	Z->bAvoidIndoors = bAvoidIndoors;
	Z->bShowInGame = bShowInGame;
	Z->FinishSpawning(T);
	return Z;
}

void UBumblebeeLibrary::SetBumblebeeSize(const UObject* WorldContext, float Scale)
{
	if (ABumblebeeSwarm* S = ABumblebeeSwarm::GetOrCreate(WorldContext)) S->SetBeeScale(Scale);
}

void UBumblebeeLibrary::AddBumblebeeThreat(const UObject* WorldContext, AActor* Actor)
{
	if (ABumblebeeSwarm* S = ABumblebeeSwarm::GetOrCreate(WorldContext)) S->AddThreatActor(Actor);
}

void UBumblebeeLibrary::RemoveBumblebeeThreat(const UObject* WorldContext, AActor* Actor)
{
	if (ABumblebeeSwarm* S = ABumblebeeSwarm::Find(WorldContext)) S->RemoveThreatActor(Actor);
}

void UBumblebeeLibrary::SetBumblebeesEnabled(const UObject* WorldContext, bool bEnabled)
{
	if (IConsoleVariable* V = IConsoleManager::Get().FindConsoleVariable(TEXT("bumblebees.Enable"))) V->Set(bEnabled ? 1 : 0, ECVF_SetByCode);
}

void UBumblebeeLibrary::ShowBumblebeeZones(const UObject* WorldContext, bool bShow)
{
	UWorld* World = WorldContext ? WorldContext->GetWorld() : nullptr;
	if (!World) return;
	for (TActorIterator<ABumblebeeZone> It(World); It; ++It) It->SetShowInGame(bShow);
}

FBumblebeeStats UBumblebeeLibrary::GetBumblebeeStats(const UObject* WorldContext)
{
	const ABumblebeeSwarm* S = ABumblebeeSwarm::Find(WorldContext);
	return S ? S->GetStats() : FBumblebeeStats();
}
