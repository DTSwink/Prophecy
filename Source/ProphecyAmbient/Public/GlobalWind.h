#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Subsystems/WorldSubsystem.h"
#include "GlobalWind.generated.h"

class UMaterialParameterCollection;
class UMaterialParameterCollectionInstance;
class UTextureRenderTarget2D;
class UMaterialInterface;

/** One wind burst travelling over the land. */
USTRUCT(BlueprintType)
struct FWindGust
{
	GENERATED_BODY()
	UPROPERTY(BlueprintReadOnly, Category = "Wind") int32 Id = 0;
	/** Centre of the gust front when it was born (cm). The front moves along Direction at Speed. */
	UPROPERTY(BlueprintReadOnly, Category = "Wind") FVector Origin = FVector::ZeroVector;
	/** Unit direction the gust blows (horizontal). */
	UPROPERTY(BlueprintReadOnly, Category = "Wind") FVector Direction = FVector::ForwardVector;
	/** Peak extra wind speed (m/s) on top of the mean wind. */
	UPROPERTY(BlueprintReadOnly, Category = "Wind") float Strength = 6.f;
	/** Speed of the front over the ground (m/s). */
	UPROPERTY(BlueprintReadOnly, Category = "Wind") float Speed = 6.f;
	/** Size (m): along the wind (the long decaying tail behind the front) and across it. */
	UPROPERTY(BlueprintReadOnly, Category = "Wind") float Length = 40.f;
	UPROPERTY(BlueprintReadOnly, Category = "Wind") float Width = 35.f;
	/** Lifetime (s) and age. */
	UPROPERTY(BlueprintReadOnly, Category = "Wind") float Life = 15.f;
	UPROPERTY(BlueprintReadOnly, Category = "Wind") float Age = 0.f;
	float Phase = 0.f;
	/** Front position now (cm). */
	FVector Front() const { return Origin + Direction * (Speed * 100.f * Age); }
	/** Growth / decay over the gust's life (0..1). */
	float Envelope() const;
};

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnWindGust, const FWindGust&, Gust);

/**
 * Global wind: a steady mean wind plus travelling wind bursts, the same field for every system.
 * - Vegetation: the bursts are drawn into a small camera-centred render target (RT_WindField, 128 x 128 texels over
 *   FieldSize) only while a gust is alive; foliage materials add MF_WindBurst to their own WPO (one texture fetch + a
 *   travelling canopy wave). No gust -> nothing is drawn, foliage keeps its own subtle motion.
 * - Gameplay (leaves, feathers, SFX): GetWindAt / GetGustIntensityAt evaluate the same field on the CPU.
 *
 * Burst model (Docs/Wind.md): a gust front sweeps downwind faster than the mean wind (coherent eddies travel at ~1.8 U(h),
 * Finnigan 2000); sharp leading edge, long decaying tail (the "ramp-cliff" structure of surface-layer gusts), a bowed
 * front, 2-3 surges inside a gust, slight veer of direction; on the vegetation it shows as waves running through the
 * canopy and grass at the shear-layer spacing ~8 L_s (~2.5 canopy heights, Raupach, Finnigan & Brunet 1996).
 */
UCLASS(meta = (DisplayName = "Global Wind"))
class PROPHECYAMBIENT_API AGlobalWind : public AActor
{
	GENERATED_BODY()

public:
	AGlobalWind();
	/** The world's wind (created on demand when bCreate). */
	static AGlobalWind* Get(const UObject* WorldContext, bool bCreate = true);

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wind") bool bEnabled = true;
	/** Where the wind blows to (yaw, degrees). The level's Wind Directional Source is used instead when there is one. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wind") float DirectionYaw = 30.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wind") bool bUseLevelWindDirection = true;
	/** Mean wind (m/s, ~10 m above ground). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wind") float MeanSpeed = 3.f;
	/** Small eddies on top of the mean wind for gameplay objects (fraction of MeanSpeed). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wind") float Turbulence = 0.2f;
	/** Average bursts per minute (Poisson; they come in groups now and then). 0 = only TriggerGust. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wind|Bursts") float GustsPerMinute = 4.f;
	/** Peak extra speed of a burst (m/s). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wind|Bursts") FVector2D GustStrength = FVector2D(5.f, 12.f);
	/** Burst size (m) along and across the wind. */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wind|Bursts") FVector2D GustLength = FVector2D(40.f, 110.f);
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wind|Bursts") FVector2D GustWidth = FVector2D(45.f, 120.f);
	/** Lifetime of a burst (s). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wind|Bursts") FVector2D GustLife = FVector2D(10.f, 20.f);
	/** Direction change of a burst against the mean wind (degrees, +-). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wind|Bursts") float GustVeerDeg = 18.f;
	/** Area covered by the vegetation field around the camera (cm). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wind|Field") float FieldSize = 25600.f;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wind|Field") TSoftObjectPtr<UMaterialParameterCollection> Collection;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wind|Field") TSoftObjectPtr<UTextureRenderTarget2D> FieldTarget;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wind|Field") TSoftObjectPtr<UMaterialInterface> FieldMaterial;
	/** Last frame's field and the material that copies it, for the vegetation's motion vectors (PreviousFrameSwitch). */
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wind|Field") TSoftObjectPtr<UTextureRenderTarget2D> FieldTargetPrev;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wind|Field") TSoftObjectPtr<UMaterialInterface> FieldCopyMaterial;
	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Wind") bool bDrawDebug = false;

	/** A burst was born (hook wind SFX here: Origin / Direction / Strength / Speed / Life). */
	UPROPERTY(BlueprintAssignable, Category = "Wind") FOnWindGust OnGustStarted;

	/** Wind velocity (cm/s) at a point: mean + bursts + small eddies. */
	UFUNCTION(BlueprintPure, Category = "Wind") FVector GetWindAt(FVector Location) const;
	/** Only the bursts (cm/s). */
	UFUNCTION(BlueprintPure, Category = "Wind") FVector GetGustAt(FVector Location) const;
	/** 0 = calm, 1 = inside the strongest possible burst (for SFX volume). */
	UFUNCTION(BlueprintPure, Category = "Wind") float GetGustIntensityAt(FVector Location) const;
	/** Start a burst now, upwind of the camera so it sweeps over it (strength m/s, <= 0 = random). Returns its id. */
	UFUNCTION(BlueprintCallable, Category = "Wind") int32 TriggerGust(float Strength = -1.f, float YawOffsetDeg = 0.f, float UpwindDistanceM = -1.f);
	UFUNCTION(BlueprintPure, Category = "Wind") TArray<FWindGust> GetGusts() const { return Gusts; }
	UFUNCTION(BlueprintPure, Category = "Wind") FVector GetMeanDirection() const { return MeanDir; }

	static constexpr int32 MaxGusts = 6;
	/** Game-thread cost of the wind tick (ms, averaged over the last second) and how often the field was redrawn. */
	UPROPERTY(BlueprintReadOnly, Category = "Wind") float AvgTickMs = 0.f;
	UPROPERTY(BlueprintReadOnly, Category = "Wind") int32 FieldDraws = 0;

protected:
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

private:
	TArray<FWindGust> Gusts;
	FVector MeanDir = FVector::ForwardVector;
	FVector FieldOrigin = FVector::ZeroVector;
	FVector CameraLoc = FVector::ZeroVector;
	float Time = 0.f, SpawnAccum = 0.f, NextGap = 1.f, DirCheck = 0.f;
	int32 NextId = 1;
	double TickMsSum = 0.0; int32 TickN = 0; float StatT = 0.f;
	bool bFieldDirty = true;
	FRandomStream Rng;
	UPROPERTY() TObjectPtr<UMaterialParameterCollectionInstance> MPC;
	UPROPERTY() TObjectPtr<UTextureRenderTarget2D> RT;
	UPROPERTY() TObjectPtr<UMaterialInterface> GenMat;
	UPROPERTY() TObjectPtr<UTextureRenderTarget2D> RTPrev;
	UPROPERTY() TObjectPtr<UMaterialInterface> CopyMat;
	FLinearColor LastOrigin = FLinearColor(0, 0, 25600, 0), LastMean = FLinearColor(1, 0, 3, 0);
	bool bHaveLast = false;
	int32 FieldTail = 2;
	void SpawnGust(float Strength, float YawOffsetDeg, float UpwindM);
	void PushParameters();
	static FVector GustVector(const FWindGust& G, const FVector& P, float* OutIntensity);
	/** Gust patches (same noise as MF_WindBurst): gain 0.3-1.5, veer (rad), patch value 0..1. */
	void GustPatches(const FVector& P, float& OutGain, float& OutVeer, float& OutPatch) const;
};

/** Creates the Global Wind in game worlds. */
UCLASS()
class PROPHECYAMBIENT_API UGlobalWindSubsystem : public UWorldSubsystem
{
	GENERATED_BODY()
public:
	virtual void OnWorldBeginPlay(UWorld& InWorld) override;
	virtual bool ShouldCreateSubsystem(UObject* Outer) const override;
};
