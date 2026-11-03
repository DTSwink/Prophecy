#include "GlobalWind.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialParameterCollection.h"
#include "Materials/MaterialParameterCollectionInstance.h"
#include "Kismet/KismetRenderingLibrary.h"
#include "GameFramework/PlayerController.h"
#include "Camera/PlayerCameraManager.h"
#include "SceneInterface.h"
#include "DrawDebugHelpers.h"
#include "HAL/IConsoleManager.h"

static TAutoConsoleVariable<int32> CVarWindEnable(TEXT("wind.Enable"), 1, TEXT("0 = no wind bursts"));
static TAutoConsoleVariable<int32> CVarWindAuto(TEXT("wind.Auto"), 1, TEXT("1 = create the Global Wind automatically in game worlds"));
static TAutoConsoleVariable<float> CVarWindGustRate(TEXT("wind.GustRateScale"), 1.f, TEXT("Multiplier on GustsPerMinute"));

namespace
{
	const TCHAR* WindDir = TEXT("/Game/Prophecy/Ambient/Wind");
	FName GustA[AGlobalWind::MaxGusts], GustB[AGlobalWind::MaxGusts];
	struct FNames { FNames() { for (int32 i = 0; i < AGlobalWind::MaxGusts; ++i) { GustA[i] = *FString::Printf(TEXT("Gust%dA"), i); GustB[i] = *FString::Printf(TEXT("Gust%dB"), i); } } } GNames;
}

// ---------------------------------------------------------------------------------------------------- turbulence
// The same value noise as MF_WindBurst (hash12 by Dave Hoskins), so gameplay feels the same gust patches the grass shows.
namespace WindTurb
{
	FORCEINLINE float Frac(float X) { return X - FMath::FloorToFloat(X); }
	FORCEINLINE float Hash(float X, float Y)
	{
		float A = Frac(X * 0.1031f), B = Frac(Y * 0.1031f), C = Frac(X * 0.1031f);
		const float D = A * (B + 33.33f) + B * (C + 33.33f) + C * (A + 33.33f);
		A += D; B += D; C += D;
		return Frac((A + B) * C);
	}
	FORCEINLINE float Noise(float X, float Y)
	{
		const float Ix = FMath::FloorToFloat(X), Iy = FMath::FloorToFloat(Y);
		const float Fx = X - Ix, Fy = Y - Iy;
		const float Ux = Fx * Fx * (3.f - 2.f * Fx), Uy = Fy * Fy * (3.f - 2.f * Fy);
		const float A = Hash(Ix, Iy), B = Hash(Ix + 1.f, Iy), C = Hash(Ix, Iy + 1.f), D = Hash(Ix + 1.f, Iy + 1.f);
		return FMath::Lerp(FMath::Lerp(A, B, Ux), FMath::Lerp(C, D, Ux), Uy);
	}
}

void AGlobalWind::GustPatches(const FVector& P, float& OutGain, float& OutVeer, float& OutPatch) const
{
	// Gusts are not uniform: inside a burst the wind comes in patches ("cat's paws") from a few metres to ~20 m,
	// stretched along the wind and drifting downwind; amplitude per octave ~ k^(-1/3) (Kolmogorov -5/3 spectrum).
	const float T = GetWorld() ? float(GetWorld()->GetTimeSeconds()) : Time;
	const float Vt = 1.4f * MeanSpeed + 3.f;
	const float Qx = float(P.X) * 0.01f - float(MeanDir.X) * Vt * T;
	const float Qy = float(P.Y) * 0.01f - float(MeanDir.Y) * Vt * T;
	const float A = (Qx * float(MeanDir.X) + Qy * float(MeanDir.Y)) * 0.5f;
	const float N = -Qx * float(MeanDir.Y) + Qy * float(MeanDir.X);
	float Nz = 0.55f * WindTurb::Noise(A / 7.f, N / 7.f) + 0.30f * WindTurb::Noise(A / 3.f + 17.3f, N / 3.f + 17.3f) + 0.15f * WindTurb::Noise(A / 1.3f + 41.7f, N / 1.3f + 41.7f);
	Nz = FMath::Clamp((Nz - 0.5f) * 1.8f + 0.5f, 0.f, 1.f);
	OutPatch = Nz;
	OutGain = FMath::Lerp(0.3f, 1.5f, Nz);
	OutVeer = (WindTurb::Noise(A / 9.f + 5.1f, N / 9.f + 5.1f) - 0.5f) * 0.5f;
}

float FWindGust::Envelope() const
{
	// a burst develops quickly (sweeps come down from aloft) and dies out more slowly
	const float T = FMath::Clamp(Age / FMath::Max(Life, 0.1f), 0.f, 1.f);
	return FMath::SmoothStep(0.f, 0.12f, T) * (1.f - FMath::SmoothStep(0.55f, 1.f, T));
}

AGlobalWind::AGlobalWind()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.TickGroup = TG_PrePhysics;
	RootComponent = CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
	Collection = TSoftObjectPtr<UMaterialParameterCollection>(FSoftObjectPath(FString::Printf(TEXT("%s/MPC_GlobalWind.MPC_GlobalWind"), WindDir)));
	FieldTarget = TSoftObjectPtr<UTextureRenderTarget2D>(FSoftObjectPath(FString::Printf(TEXT("%s/RT_WindField.RT_WindField"), WindDir)));
	FieldMaterial = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(FString::Printf(TEXT("%s/M_WindFieldGen.M_WindFieldGen"), WindDir)));
	FieldTargetPrev = TSoftObjectPtr<UTextureRenderTarget2D>(FSoftObjectPath(FString::Printf(TEXT("%s/RT_WindFieldPrev.RT_WindFieldPrev"), WindDir)));
	FieldCopyMaterial = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(FString::Printf(TEXT("%s/M_WindFieldCopy.M_WindFieldCopy"), WindDir)));
}

AGlobalWind* AGlobalWind::Get(const UObject* WorldContext, bool bCreate)
{
	UWorld* W = WorldContext ? WorldContext->GetWorld() : nullptr;
	if (!W) return nullptr;
	for (TActorIterator<AGlobalWind> It(W); It; ++It) return *It;
	if (!bCreate || !W->IsGameWorld()) return nullptr;
	FActorSpawnParameters P;
	P.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
	P.ObjectFlags |= RF_Transient;
	return W->SpawnActor<AGlobalWind>(FVector::ZeroVector, FRotator::ZeroRotator, P);
}

void AGlobalWind::BeginPlay()
{
	Super::BeginPlay();
	Rng.Initialize(int32(GetUniqueID() * 2654435761u));
	MeanDir = FRotator(0.f, DirectionYaw, 0.f).Vector();
	if (UMaterialParameterCollection* C = Collection.LoadSynchronous()) MPC = GetWorld()->GetParameterCollectionInstance(C);
	RT = FieldTarget.LoadSynchronous();
	GenMat = FieldMaterial.LoadSynchronous();
	RTPrev = FieldTargetPrev.LoadSynchronous();
	CopyMat = FieldCopyMaterial.LoadSynchronous();
	if (RT) UKismetRenderingLibrary::ClearRenderTarget2D(this, RT, FLinearColor(0.5f, 0.5f, 0.f, 0.f));		// encoded zero wind
	if (RTPrev) UKismetRenderingLibrary::ClearRenderTarget2D(this, RTPrev, FLinearColor(0.5f, 0.5f, 0.f, 0.f));
	NextGap = -FMath::Loge(FMath::Max(1.f - Rng.FRand(), 1e-4f));
	PushParameters();
}

// ---------------------------------------------------------------------------------------------------- field
FVector AGlobalWind::GustVector(const FWindGust& G, const FVector& P, float* OutIntensity)
{
	// gust frame: s along the wind (> 0 ahead of the front), n across. Metres.
	const FVector F = G.Front();
	const FVector D = G.Direction;
	const FVector Pp(-D.Y, D.X, 0.f);
	const float Rx = float(P.X - F.X) * 0.01f, Ry = float(P.Y - F.Y) * 0.01f;
	const float N = Rx * float(Pp.X) + Ry * float(Pp.Y);
	const float S = Rx * float(D.X) + Ry * float(D.Y) - 0.15f * N * N / G.Width;		// the front bows forward in the middle
	// sharp leading edge (the "cliff"), long decaying tail behind it (the "ramp")
	const float Along = S > 0.f ? FMath::Exp(-FMath::Square(S / (0.15f * G.Length))) : FMath::Exp(-FMath::Square(S / G.Length));
	const float Across = FMath::Exp(-FMath::Square(FMath::Square(N / G.Width)));
	const float V = G.Strength * G.Envelope() * Along * Across;
	if (OutIntensity) *OutIntensity = V;
	return D * (V * 100.f);
}

FVector AGlobalWind::GetGustAt(FVector Location) const
{
	if (!bEnabled || Gusts.Num() == 0) return FVector::ZeroVector;
	FVector Sum = FVector::ZeroVector;
	for (const FWindGust& G : Gusts) Sum += GustVector(G, Location, nullptr);
	if (Sum.IsNearlyZero()) return Sum;
	float Gain, Veer, Patch;
	GustPatches(Location, Gain, Veer, Patch);
	return Sum.RotateAngleAxisRad(Veer, FVector::UpVector) * Gain;
}

float AGlobalWind::GetGustIntensityAt(FVector Location) const
{
	float Best = 0.f;
	for (const FWindGust& G : Gusts) { float I = 0.f; GustVector(G, Location, &I); Best = FMath::Max(Best, I); }
	if (Best <= 0.f) return 0.f;
	float Gain, Veer, Patch;
	GustPatches(Location, Gain, Veer, Patch);		// the gust patches: what you hear rises and falls with what the grass shows
	return FMath::Clamp(Best * Gain / FMath::Max(GustStrength.Y, 1.f), 0.f, 1.f);
}

FVector AGlobalWind::GetWindAt(FVector Location) const
{
	if (!bEnabled) return FVector::ZeroVector;
	// mean wind with small eddies drifting downwind (two incommensurate scales, a few metres to ~20 m)
	const float Ux = float(Location.X) * 0.01f - float(MeanDir.X) * MeanSpeed * Time;
	const float Uy = float(Location.Y) * 0.01f - float(MeanDir.Y) * MeanSpeed * Time;
	const float E1 = FMath::Sin(Ux * 0.31f + Uy * 0.17f + Time * 0.7f) * FMath::Sin(Uy * 0.23f - Ux * 0.11f);
	const float E2 = FMath::Sin(Ux * 0.83f - Uy * 0.61f + Time * 1.9f);
	const float Ed = FMath::Sin(Ux * 0.19f + Uy * 0.41f + Time * 0.5f);
	const FVector Pp(-MeanDir.Y, MeanDir.X, 0.f);
	const FVector Mean = (MeanDir * (1.f + Turbulence * (0.7f * E1 + 0.3f * E2)) + Pp * (Turbulence * 0.6f * Ed)) * (MeanSpeed * 100.f);
	return Mean + GetGustAt(Location);
}

// ---------------------------------------------------------------------------------------------------- bursts
int32 AGlobalWind::TriggerGust(float Strength, float YawOffsetDeg, float UpwindDistanceM)
{
	SpawnGust(Strength, YawOffsetDeg, UpwindDistanceM);
	return Gusts.Num() ? Gusts.Last().Id : 0;
}

void AGlobalWind::SpawnGust(float Strength, float YawOffsetDeg, float UpwindM)
{
	if (Gusts.Num() >= MaxGusts) Gusts.RemoveAt(0);		// the oldest makes room
	FWindGust G;
	G.Id = NextId++;
	G.Strength = Strength > 0.f ? Strength : Rng.FRandRange(GustStrength.X, GustStrength.Y);
	G.Direction = MeanDir.RotateAngleAxis(YawOffsetDeg + Rng.FRandRange(-GustVeerDeg, GustVeerDeg), FVector::UpVector);
	// fronts run ahead of the mean wind (coherent structures travel at ~1.8 U(h) at the canopy top; a burst brings
	// faster air down from aloft)
	G.Speed = FMath::Max(3.f, MeanSpeed * 1.4f + 0.35f * G.Strength);
	G.Length = Rng.FRandRange(GustLength.X, GustLength.Y);
	G.Width = Rng.FRandRange(GustWidth.X, GustWidth.Y);
	G.Life = Rng.FRandRange(GustLife.X, GustLife.Y);
	G.Phase = Rng.FRandRange(0.f, 2.f * PI);
	const float Up = UpwindM > 0.f ? UpwindM : Rng.FRandRange(25.f, 80.f);
	const FVector Side(-G.Direction.Y, G.Direction.X, 0.f);
	G.Origin = CameraLoc - G.Direction * (Up * 100.f) + Side * (Rng.FRandRange(-0.6f, 0.6f) * G.Width * 100.f);
	G.Origin.Z = CameraLoc.Z;
	Gusts.Add(G);
	bFieldDirty = true;
	OnGustStarted.Broadcast(G);
}

void AGlobalWind::PushParameters()
{
	if (!MPC) return;
	const float Size = FieldSize;
	// snap the field to its texels so the vegetation does not swim as the camera moves
	const float Texel = Size / 128.f;
	FieldOrigin = FVector(FMath::GridSnap(CameraLoc.X, double(Texel)), FMath::GridSnap(CameraLoc.Y, double(Texel)), 0.0);
	const FLinearColor Origin(float(FieldOrigin.X), float(FieldOrigin.Y), Size, Time);
	const FLinearColor Mean(float(MeanDir.X), float(MeanDir.Y), bEnabled ? MeanSpeed : 0.f, Gusts.Num() > 0 ? 1.f : 0.f);
	// last frame's values: the materials evaluate the previous frame's bend with them (correct motion vectors, no TSR smearing)
	MPC->SetVectorParameterValue(TEXT("WindOriginPrev"), bHaveLast ? LastOrigin : Origin);
	MPC->SetVectorParameterValue(TEXT("WindMeanPrev"), bHaveLast ? LastMean : Mean);
	MPC->SetVectorParameterValue(TEXT("WindOrigin"), Origin);
	MPC->SetVectorParameterValue(TEXT("WindMean"), Mean);
	LastOrigin = Origin; LastMean = Mean; bHaveLast = true;
	for (int32 i = 0; i < MaxGusts; ++i)
	{
		if (Gusts.IsValidIndex(i))
		{
			const FWindGust& G = Gusts[i];
			const FVector F = G.Front();
			MPC->SetVectorParameterValue(GustA[i], FLinearColor(float(F.X), float(F.Y), float(G.Direction.X), float(G.Direction.Y)));
			MPC->SetVectorParameterValue(GustB[i], FLinearColor(G.Strength * G.Envelope(), G.Length, G.Width, G.Phase));
		}
		else MPC->SetVectorParameterValue(GustB[i], FLinearColor(0.f, 1.f, 1.f, 0.f));
	}
}

void AGlobalWind::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);
	const double T0 = FPlatformTime::Seconds();
	if (!bEnabled || CVarWindEnable.GetValueOnGameThread() == 0)
	{
		if (Gusts.Num()) { Gusts.Reset(); bFieldDirty = true; }
	}
	Time += DeltaSeconds;
	if (const APlayerController* PC = GetWorld()->GetFirstPlayerController())
	{
		if (PC->PlayerCameraManager) CameraLoc = PC->PlayerCameraManager->GetCameraLocation();
	}
	DirCheck -= DeltaSeconds;
	if (DirCheck <= 0.f)
	{
		DirCheck = 1.f;
		MeanDir = FRotator(0.f, DirectionYaw, 0.f).Vector();
		if (bUseLevelWindDirection && GetWorld()->Scene)
		{
			FVector WDir = FVector::ZeroVector; float WSpeed = 0.f, WMin = 0.f, WMax = 0.f;
			GetWorld()->Scene->GetWindParameters_GameThread(CameraLoc, WDir, WSpeed, WMin, WMax);
			const FVector Hd(WDir.X, WDir.Y, 0.f);
			if (WSpeed > 0.f && !Hd.IsNearlyZero()) MeanDir = Hd.GetSafeNormal();
		}
	}
	if (bEnabled && CVarWindEnable.GetValueOnGameThread() != 0)
	{
		// bursts: a Poisson process, with a chance of a follow-up burst soon after (gusts come in groups)
		SpawnAccum += DeltaSeconds * GustsPerMinute * CVarWindGustRate.GetValueOnGameThread() / 60.f;
		if (SpawnAccum >= NextGap)
		{
			SpawnAccum = 0.f;
			NextGap = Rng.FRand() < 0.35f ? Rng.FRandRange(0.05f, 0.25f) : -FMath::Loge(FMath::Max(1.f - Rng.FRand(), 1e-4f));
			SpawnGust(-1.f, 0.f, -1.f);
		}
	}
	for (int32 i = Gusts.Num() - 1; i >= 0; --i)
	{
		Gusts[i].Age += DeltaSeconds;
		if (Gusts[i].Age >= Gusts[i].Life) { Gusts.RemoveAt(i); bFieldDirty = true; }
	}
	PushParameters();
	// the vegetation field is redrawn only while a burst is alive (and once more to clear it)
	// (and for two frames after the last one, so the previous-frame copy settles to calm as well)
	if (Gusts.Num() > 0 || bFieldDirty) FieldTail = 2;
	if (RT && GenMat && FieldTail > 0)
	{
		if (RTPrev && CopyMat) UKismetRenderingLibrary::DrawMaterialToRenderTarget(this, RTPrev, CopyMat);		// last frame's field
		if (Gusts.Num() > 0) { UKismetRenderingLibrary::DrawMaterialToRenderTarget(this, RT, GenMat); ++FieldDraws; }
		else { UKismetRenderingLibrary::ClearRenderTarget2D(this, RT, FLinearColor(0.5f, 0.5f, 0.f, 0.f)); --FieldTail; }
		bFieldDirty = false;
	}
	TickMsSum += (FPlatformTime::Seconds() - T0) * 1000.0; ++TickN; StatT += DeltaSeconds;
	if (StatT >= 1.f) { AvgTickMs = float(TickMsSum / FMath::Max(TickN, 1)); TickMsSum = 0.0; TickN = 0; StatT = 0.f; }
	if (bDrawDebug)
	{
		for (const FWindGust& G : Gusts)
		{
			const FVector F = G.Front() + FVector(0, 0, 200);
			DrawDebugDirectionalArrow(GetWorld(), F, F + G.Direction * G.Strength * G.Envelope() * 100.f, 200.f, FColor::Cyan, false, -1.f, 0, 8.f);
			const FVector Side(-G.Direction.Y, G.Direction.X, 0.f);
			DrawDebugLine(GetWorld(), F - Side * G.Width * 100.f, F + Side * G.Width * 100.f, FColor::Cyan, false, -1.f, 0, 4.f);
		}
	}
}

// ---------------------------------------------------------------------------------------------------- auto-create
bool UGlobalWindSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
	const UWorld* W = Cast<UWorld>(Outer);
	return W && (W->WorldType == EWorldType::Game || W->WorldType == EWorldType::PIE);
}

void UGlobalWindSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
	Super::OnWorldBeginPlay(InWorld);
	if (CVarWindAuto.GetValueOnGameThread() != 0) AGlobalWind::Get(&InWorld, true);
}
