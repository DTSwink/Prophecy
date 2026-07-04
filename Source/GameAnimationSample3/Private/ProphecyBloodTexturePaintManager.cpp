#include "ProphecyBloodTexturePaintManager.h"

#include "Components/MeshComponent.h"
#include "Components/SkinnedMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "DrawDebugHelpers.h"
#include "Engine/SkinnedAsset.h"
#include "Engine/Canvas.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "Engine/TextureRenderTarget2D.h"
#include "Engine/World.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetRenderingLibrary.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "Rendering/SkeletalMeshLODRenderData.h"
#include "Rendering/SkeletalMeshRenderData.h"
#include "UObject/ConstructorHelpers.h"

#if WITH_EDITOR
#include "AssetToolsModule.h"
#include "HAL/FileManager.h"
#include "IAssetTools.h"
#include "MaterialEditingLibrary.h"
#include "Materials/Material.h"
#include "Materials/MaterialExpressionConstant.h"
#include "Materials/MaterialExpressionConstant3Vector.h"
#include "Materials/MaterialExpressionGetMaterialAttributes.h"
#include "Materials/MaterialExpressionLinearInterpolate.h"
#include "Materials/MaterialExpressionMaterialFunctionCall.h"
#include "Materials/MaterialExpressionMultiply.h"
#include "Materials/MaterialExpressionSaturate.h"
#include "Materials/MaterialExpressionScalarParameter.h"
#include "Materials/MaterialExpressionSetMaterialAttributes.h"
#include "Materials/MaterialExpressionTextureCoordinate.h"
#include "Materials/MaterialExpressionTextureSampleParameter2D.h"
#include "Materials/MaterialFunctionInterface.h"
#include "Engine/Texture.h"
#include "Materials/MaterialInstanceConstant.h"
#include "Misc/PackageName.h"
#include "Modules/ModuleManager.h"
#include "ObjectTools.h"
#include "PackageTools.h"
#endif

namespace
{
DEFINE_LOG_CATEGORY_STATIC(LogProphecyBloodTexturePaint, Log, All);

constexpr float SmallObjectExtentCm = 200.0f;
constexpr float MediumObjectExtentCm = 800.0f;
constexpr float MaxSkinnedMeshBrushDiameterPixels = 48.0f;

bool TryGetMeshLocalBounds(const UMeshComponent* Component, FBoxSphereBounds& OutBounds)
{
	if (const UStaticMeshComponent* StaticMeshComponent = Cast<UStaticMeshComponent>(Component))
	{
		if (const UStaticMesh* StaticMesh = StaticMeshComponent->GetStaticMesh())
		{
			OutBounds = StaticMesh->GetBounds();
			return true;
		}
	}

	if (const USkinnedMeshComponent* SkinnedMeshComponent = Cast<USkinnedMeshComponent>(Component))
	{
		if (const USkinnedAsset* SkinnedAsset = SkinnedMeshComponent->GetSkinnedAsset())
		{
			OutBounds = SkinnedAsset->GetBounds();
			return true;
		}
	}

	return false;
}

FVector ToVector(const FVector3f& Value)
{
	return FVector(Value.X, Value.Y, Value.Z);
}

float EstimateTriangleUVUnitsPerWorldUnit(const FProphecySkinnedPaintTriangle& Triangle, const FTransform& ComponentTransform)
{
	const FVector ABWorld = ComponentTransform.TransformVector(Triangle.B - Triangle.A);
	const FVector ACWorld = ComponentTransform.TransformVector(Triangle.C - Triangle.A);
	const FVector BCWorld = ComponentTransform.TransformVector(Triangle.C - Triangle.B);
	const FVector2D ABUV = Triangle.UVB - Triangle.UVA;
	const FVector2D ACUV = Triangle.UVC - Triangle.UVA;
	const FVector2D BCUV = Triangle.UVC - Triangle.UVB;

	const double WorldArea2 = FVector::CrossProduct(ABWorld, ACWorld).Size();
	const double UVArea2 = FMath::Abs(static_cast<double>(ABUV.X) * static_cast<double>(ACUV.Y) - static_cast<double>(ABUV.Y) * static_cast<double>(ACUV.X));
	if (WorldArea2 > KINDA_SMALL_NUMBER && UVArea2 > SMALL_NUMBER)
	{
		return static_cast<float>(FMath::Sqrt(UVArea2 / WorldArea2));
	}

	double RatioSum = 0.0;
	int32 RatioCount = 0;
	auto AddEdgeRatio = [&RatioSum, &RatioCount](const FVector& WorldEdge, const FVector2D& UVEdge)
	{
		const double WorldLength = WorldEdge.Size();
		const double UVLength = UVEdge.Size();
		if (WorldLength > KINDA_SMALL_NUMBER && UVLength > SMALL_NUMBER)
		{
			RatioSum += UVLength / WorldLength;
			RatioCount += 1;
		}
	};

	AddEdgeRatio(ABWorld, ABUV);
	AddEdgeRatio(ACWorld, ACUV);
	AddEdgeRatio(BCWorld, BCUV);
	return RatioCount > 0 ? static_cast<float>(RatioSum / static_cast<double>(RatioCount)) : 0.0f;
}

#if WITH_EDITOR
constexpr TCHAR BloodPaintSurfaceFunctionPath[] = TEXT("/Game/Prophecy/BloodTexturePainting/MF_BloodPaintSurface.MF_BloodPaintSurface");

FString MakeSafeGeneratedMaterialName(const UMaterialInterface* Material, const FString& Suffix)
{
	if (!Material)
	{
		return FString();
	}

	FString SourcePackageName = Material->GetOutermost() ? Material->GetOutermost()->GetName() : Material->GetName();
	SourcePackageName.RemoveFromStart(TEXT("/Game/"));
	SourcePackageName.ReplaceInline(TEXT("/"), TEXT("_"));
	SourcePackageName.ReplaceInline(TEXT("."), TEXT("_"));
	return SourcePackageName + Suffix;
}

FDateTime GetAssetPackageTimeStamp(const UObject* Asset)
{
	if (!Asset || !Asset->GetOutermost())
	{
		return FDateTime::MinValue();
	}

	FString Filename;
	if (!FPackageName::TryConvertLongPackageNameToFilename(Asset->GetOutermost()->GetName(), Filename, FPackageName::GetAssetPackageExtension()))
	{
		return FDateTime::MinValue();
	}

	return IFileManager::Get().GetTimeStamp(*Filename);
}

UMaterialExpressionMaterialFunctionCall* CreateBloodPaintSurfaceCall(UMaterial* Material, int32 NodeX, int32 NodeY)
{
	if (!Material)
	{
		return nullptr;
	}

	UMaterialFunctionInterface* BloodSurfaceFunction = LoadObject<UMaterialFunctionInterface>(nullptr, BloodPaintSurfaceFunctionPath);
	if (!BloodSurfaceFunction)
	{
		UE_LOG(LogProphecyBloodTexturePaint, Warning, TEXT("Missing blood surface material function %s"), BloodPaintSurfaceFunctionPath);
		return nullptr;
	}

	UMaterialExpressionMaterialFunctionCall* FunctionCall = Cast<UMaterialExpressionMaterialFunctionCall>(
		UMaterialEditingLibrary::CreateMaterialExpression(Material, UMaterialExpressionMaterialFunctionCall::StaticClass(), NodeX, NodeY));
	if (!FunctionCall)
	{
		return nullptr;
	}

	FunctionCall->SetMaterialFunction(BloodSurfaceFunction);
	FunctionCall->UpdateFromFunctionResource();
	return FunctionCall;
}

bool ConnectFunctionOutputByName(UMaterialExpressionMaterialFunctionCall* FunctionCall, FName OutputName, FExpressionInput& Destination)
{
	if (!FunctionCall)
	{
		return false;
	}

	for (int32 OutputIndex = 0; OutputIndex < FunctionCall->FunctionOutputs.Num(); ++OutputIndex)
	{
		if (FunctionCall->FunctionOutputs[OutputIndex].Output.OutputName.IsEqual(OutputName))
		{
			Destination.Connect(OutputIndex, FunctionCall);
			return true;
		}
	}

	UE_LOG(LogProphecyBloodTexturePaint, Warning, TEXT("Blood surface function output '%s' was not found"), *OutputName.ToString());
	return false;
}

int32 FindExpressionOutputIndexByName(UMaterialExpression* Expression, const FString& OutputName)
{
	if (!Expression || OutputName.IsEmpty())
	{
		return 0;
	}

	TArray<FExpressionOutput>& Outputs = Expression->GetOutputs();
	for (int32 OutputIndex = 0; OutputIndex < Outputs.Num(); ++OutputIndex)
	{
		if (Outputs[OutputIndex].OutputName.ToString().Equals(OutputName, ESearchCase::IgnoreCase))
		{
			return OutputIndex;
		}
	}

	return 0;
}
#endif
}

AProphecyBloodTexturePaintManager::AProphecyBloodTexturePaintManager()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BrushFinder(TEXT("/Game/Prophecy/BloodTexturePainting/M_BloodBrush_Circle.M_BloodBrush_Circle"));
	if (BrushFinder.Succeeded())
	{
		BrushMaterial = BrushFinder.Object;
	}

	static ConstructorHelpers::FObjectFinder<UMaterialInterface> BloodMaterialFinder(TEXT("/Game/Prophecy/BloodTexturePainting/M_BloodPaint_RuntimeTest.M_BloodPaint_RuntimeTest"));
	if (BloodMaterialFinder.Succeeded())
	{
		DefaultBloodMaterialTemplate = BloodMaterialFinder.Object;
	}
}

void AProphecyBloodTexturePaintManager::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (bFlushEveryTick)
	{
		FlushPendingBloodStamps();
	}
}

bool AProphecyBloodTexturePaintManager::TryPaintFromHit(const FHitResult& Hit, float BrushRadiusWorld, float Intensity, int32 OverrideMaterialSlot)
{
	UMeshComponent* Component = Cast<UMeshComponent>(Hit.GetComponent());
	if (!Component)
	{
		LogReject(TEXT("unsupported component: hit component is not a MeshComponent"));
		return false;
	}

	FString RejectReason;
	FVector2D UV = FVector2D::ZeroVector;
	int32 MaterialSlot = INDEX_NONE;
	float BrushUVUnitsPerWorldUnit = 0.0f;
	if (!FindPaintUV(Component, Hit, OverrideMaterialSlot, UV, MaterialSlot, BrushUVUnitsPerWorldUnit, RejectReason))
	{
		LogReject(RejectReason);
		return false;
	}

	UMaterialInterface* CurrentMaterial = Component->GetMaterial(MaterialSlot);
	if (!IsPaintableComponent(Component, CurrentMaterial, RejectReason))
	{
		LogReject(RejectReason);
		return false;
	}

	FProphecyBloodPaintState* State = EnsurePaintState(Component, MaterialSlot, RejectReason);
	if (!State || !State->bValid)
	{
		LogReject(RejectReason);
		return false;
	}

	const FString StateKey = MakeStateKey(Component, MaterialSlot);
	FProphecyBloodPaintStamp Stamp;
	Stamp.UV = UV;
	Stamp.BrushDrawSizePixels = ComputeWorldBrushDrawSize(Component, Hit, BrushRadiusWorld, State->RTResolution, BrushUVUnitsPerWorldUnit);
	Stamp.BrushSizePixels = FMath::Max(Stamp.BrushDrawSizePixels.X, Stamp.BrushDrawSizePixels.Y);
	Stamp.Intensity = FMath::Clamp(Intensity, 0.0f, 1.0f);
	Stamp.RotationDegrees = 0.0f;
	QueueStamp(StateKey, Stamp);

	State->LastUsedTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0f;

	if (bDebugDrawHitLocations && GetWorld())
	{
		DrawDebugSphere(GetWorld(), Hit.ImpactPoint, FMath::Max(4.0f, BrushRadiusWorld * 0.2f), 12, FColor::Red, false, 3.0f);
		DrawDebugString(GetWorld(), Hit.ImpactPoint + FVector(0.0f, 0.0f, 18.0f), FString::Printf(TEXT("Blood UV %.3f %.3f"), UV.X, UV.Y), nullptr, FColor::Red, 3.0f, true);
	}

	if (bDebugPrintHits)
	{
		DebugMessage(FString::Printf(TEXT("BloodPaint accepted: %s slot=%d UV=(%.3f, %.3f) radius=%.1f draw=(%.1f, %.1f) RT=%d"),
			*GetNameSafe(Component),
			MaterialSlot,
			UV.X,
			UV.Y,
			BrushRadiusWorld,
			Stamp.BrushDrawSizePixels.X,
			Stamp.BrushDrawSizePixels.Y,
			State->RTResolution));
	}

	return true;
}

bool AProphecyBloodTexturePaintManager::DebugPaintUV(UMeshComponent* Component, FVector2D UV, float BrushSizePixels, float Intensity, int32 MaterialSlot)
{
	if (!Component)
	{
		LogReject(TEXT("DebugPaintUV failed: missing component"));
		return false;
	}

	FString RejectReason;
	UMaterialInterface* CurrentMaterial = Component->GetMaterial(MaterialSlot);
	if (!IsPaintableComponent(Component, CurrentMaterial, RejectReason))
	{
		LogReject(RejectReason);
		return false;
	}

	FProphecyBloodPaintState* State = EnsurePaintState(Component, MaterialSlot, RejectReason);
	if (!State || !State->bValid)
	{
		LogReject(RejectReason);
		return false;
	}

	FProphecyBloodPaintStamp Stamp;
	Stamp.UV = UV;
	Stamp.BrushSizePixels = FMath::Max(1.0f, BrushSizePixels);
	Stamp.BrushDrawSizePixels = FVector2D(Stamp.BrushSizePixels, Stamp.BrushSizePixels);
	Stamp.Intensity = FMath::Clamp(Intensity, 0.0f, 1.0f);
	Stamp.RotationDegrees = 0.0f;
	QueueStamp(MakeStateKey(Component, MaterialSlot), Stamp);
	State->LastUsedTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0f;
	return true;
}

void AProphecyBloodTexturePaintManager::FlushPendingBloodStamps()
{
	StampsFlushedLastFrame = 0;
	StampsDeferredLastFrame = 0;
	StampsDroppedLastFrame = 0;

	if (PendingStampsByStateKey.Num() == 0)
	{
		QueuedStampCount = 0;
		return;
	}

	TArray<FString> EmptyKeys;
	for (TPair<FString, TArray<FProphecyBloodPaintStamp>>& PendingPair : PendingStampsByStateKey)
	{
		if (StampsFlushedLastFrame >= MaxStampsPerFrame)
		{
			break;
		}

		FProphecyBloodPaintState* State = PaintStatesByKey.Find(PendingPair.Key);
		if (!State || !State->bValid || !State->BloodRT || !BrushMaterial)
		{
			StampsDeferredLastFrame += PendingPair.Value.Num();
			continue;
		}

		UCanvas* Canvas = nullptr;
		FVector2D RTSize = FVector2D::ZeroVector;
		FDrawToRenderTargetContext DrawContext;
		UKismetRenderingLibrary::BeginDrawCanvasToRenderTarget(this, State->BloodRT, Canvas, RTSize, DrawContext);
		if (!Canvas)
		{
			StampsDeferredLastFrame += PendingPair.Value.Num();
			continue;
		}

		const int32 LocalLimit = FMath::Min3(PendingPair.Value.Num(), MaxStampsPerRTPerFrame, MaxStampsPerFrame - StampsFlushedLastFrame);
		for (int32 StampIndex = 0; StampIndex < LocalLimit; ++StampIndex)
		{
			const FProphecyBloodPaintStamp& Stamp = PendingPair.Value[StampIndex];
			FVector2D DrawSize = Stamp.BrushDrawSizePixels;
			if (DrawSize.X <= 0.0f || DrawSize.Y <= 0.0f)
			{
				DrawSize = FVector2D(Stamp.BrushSizePixels, Stamp.BrushSizePixels);
			}
			DrawSize.X = FMath::Max(1.0f, DrawSize.X);
			DrawSize.Y = FMath::Max(1.0f, DrawSize.Y);

			const float PixelX = Stamp.UV.X * RTSize.X;
			const float PixelY = (bFlipV ? (1.0f - Stamp.UV.Y) : Stamp.UV.Y) * RTSize.Y;
			const FVector2D DrawPosition(PixelX - DrawSize.X * 0.5f, PixelY - DrawSize.Y * 0.5f);

			Canvas->K2_DrawMaterial(BrushMaterial, DrawPosition, DrawSize, FVector2D::ZeroVector, FVector2D::UnitVector, Stamp.RotationDegrees, FVector2D(0.5f, 0.5f));
			State->NumStamps += 1;
			StampsFlushedLastFrame += 1;
		}

		UKismetRenderingLibrary::EndDrawCanvasToRenderTarget(this, DrawContext);
		PendingPair.Value.RemoveAt(0, LocalLimit, EAllowShrinking::No);

		if (PendingPair.Value.Num() == 0)
		{
			EmptyKeys.Add(PendingPair.Key);
		}
	}

	for (const FString& Key : EmptyKeys)
	{
		PendingStampsByStateKey.Remove(Key);
	}

	QueuedStampCount = 0;
	for (const TPair<FString, TArray<FProphecyBloodPaintStamp>>& PendingPair : PendingStampsByStateKey)
	{
		QueuedStampCount += PendingPair.Value.Num();
	}
	StampsDeferredLastFrame = QueuedStampCount;

	if (bDebugPrintHits && StampsFlushedLastFrame > 0)
	{
		UE_LOG(LogProphecyBloodTexturePaint, Log, TEXT("Flushed %d blood paint stamps; deferred=%d dropped=%d"), StampsFlushedLastFrame, StampsDeferredLastFrame, StampsDroppedLastFrame);
	}
}

void AProphecyBloodTexturePaintManager::ClearRuntimePaintState(bool bRestoreOriginalMaterials)
{
	if (bRestoreOriginalMaterials)
	{
		for (const TPair<FString, FProphecyBloodPaintState>& StatePair : PaintStatesByKey)
		{
			const FProphecyBloodPaintState& State = StatePair.Value;
			if (State.Component && OriginalMaterialsByKey.Contains(StatePair.Key))
			{
				State.Component->SetMaterial(State.MaterialSlot, OriginalMaterialsByKey[StatePair.Key]);
			}
		}
	}

	PaintStatesByKey.Reset();
	OriginalMaterialsByKey.Reset();
	PendingStampsByStateKey.Reset();
	ActivePaintStates = 0;
	QueuedStampCount = 0;
	StampsFlushedLastFrame = 0;
	StampsDeferredLastFrame = 0;
	StampsDroppedLastFrame = 0;
}

void AProphecyBloodTexturePaintManager::SetDebugShowMaskOnPaintedMaterials(bool bEnabled)
{
	bDebugShowMaskOnPaintedMaterials = bEnabled;

	for (TPair<FString, FProphecyBloodPaintState>& StatePair : PaintStatesByKey)
	{
		if (StatePair.Value.BloodMID)
		{
			StatePair.Value.BloodMID->SetScalarParameterValue(DebugShowMaskParameter, bEnabled ? 1.0f : 0.0f);
		}
	}
}

void AProphecyBloodTexturePaintManager::SetDebugMode(bool bEnabled, bool bShowMask)
{
	bDebugMode = bEnabled;
	bDebugPrintHits = bEnabled;
	bDebugDrawHitLocations = bEnabled;
	bDebugLogRejectedHits = bEnabled;
	SetDebugShowMaskOnPaintedMaterials(bEnabled && bShowMask);
}

FString AProphecyBloodTexturePaintManager::GetDebugStatsString() const
{
	const float EstimatedMB = ActivePaintStates * FMath::Square(DefaultRTResolutionMedium) * 4.0f / (1024.0f * 1024.0f);
	return FString::Printf(TEXT("BloodPaint states=%d queued=%d flushed=%d deferred=%d dropped=%d unsupported=%d estMB~%.1f"),
		ActivePaintStates,
		QueuedStampCount,
		StampsFlushedLastFrame,
		StampsDeferredLastFrame,
		StampsDroppedLastFrame,
		UnsupportedHitCount,
		EstimatedMB);
}

UTextureRenderTarget2D* AProphecyBloodTexturePaintManager::GetFirstPaintRenderTarget() const
{
	for (const TPair<FString, FProphecyBloodPaintState>& StatePair : PaintStatesByKey)
	{
		if (StatePair.Value.BloodRT)
		{
			return StatePair.Value.BloodRT;
		}
	}
	return nullptr;
}

FString AProphecyBloodTexturePaintManager::MakeStateKey(const UMeshComponent* Component, int32 MaterialSlot) const
{
	return FString::Printf(TEXT("%u_%d"), Component ? Component->GetUniqueID() : 0, MaterialSlot);
}

bool AProphecyBloodTexturePaintManager::IsPaintableComponent(const UMeshComponent* Component, UMaterialInterface* CurrentMaterial, FString& OutRejectReason) const
{
	if (!Component)
	{
		OutRejectReason = TEXT("component is null");
		return false;
	}

	if (const UStaticMeshComponent* StaticMeshComponent = Cast<UStaticMeshComponent>(Component))
	{
		if (!StaticMeshComponent->GetStaticMesh())
		{
			OutRejectReason = FString::Printf(TEXT("%s has no StaticMesh"), *GetNameSafe(Component));
			return false;
		}
	}
	else if (const USkinnedMeshComponent* SkinnedMeshComponent = Cast<USkinnedMeshComponent>(Component))
	{
		if (!SkinnedMeshComponent->GetSkinnedAsset())
		{
			OutRejectReason = FString::Printf(TEXT("%s has no SkinnedAsset"), *GetNameSafe(Component));
			return false;
		}
	}
	else
	{
		OutRejectReason = FString::Printf(TEXT("%s is a %s; runtime blood painting currently supports static and skinned mesh components"),
			*GetNameSafe(Component),
			*GetNameSafe(Component->GetClass()));
		return false;
	}

	if (bRequirePaintableTag)
	{
		const AActor* OwningActor = Component->GetOwner();
		if (!Component->ComponentHasTag(PaintableComponentTag) && (!OwningActor || !OwningActor->ActorHasTag(PaintableComponentTag)))
		{
			OutRejectReason = FString::Printf(TEXT("%s is not tagged %s"), *GetNameSafe(Component), *PaintableComponentTag.ToString());
			return false;
		}
	}

	const bool bCanResolveLater =
#if WITH_EDITOR
		bEditorAutoCreateBloodMaterials;
#else
		false;
#endif
	if (!ResolveBloodMaterialTemplate(CurrentMaterial) && !bCanResolveLater)
	{
		OutRejectReason = FString::Printf(TEXT("%s material %s has no blood-enabled template"), *GetNameSafe(Component), *GetNameSafe(CurrentMaterial));
		return false;
	}

	return true;
}

int32 AProphecyBloodTexturePaintManager::ResolveMaterialSlot(UMeshComponent* Component, const FHitResult& Hit, int32 OverrideMaterialSlot, FString& OutRejectReason) const
{
	if (!Component)
	{
		OutRejectReason = TEXT("missing component");
		return INDEX_NONE;
	}

	const int32 MaterialCount = Component->GetNumMaterials();
	if (MaterialCount <= 0)
	{
		OutRejectReason = FString::Printf(TEXT("%s has no material slots"), *GetNameSafe(Component));
		return INDEX_NONE;
	}

	if (OverrideMaterialSlot >= 0)
	{
		if (OverrideMaterialSlot < MaterialCount)
		{
			return OverrideMaterialSlot;
		}

		OutRejectReason = FString::Printf(TEXT("override material slot %d out of range for %s"), OverrideMaterialSlot, *GetNameSafe(Component));
		return INDEX_NONE;
	}

	if (MaterialCount == 1)
	{
		return 0;
	}

	int32 SectionIndex = INDEX_NONE;
	UMaterialInterface* FaceMaterial = Component->GetMaterialFromCollisionFaceIndex(Hit.FaceIndex, SectionIndex);
	if (FaceMaterial)
	{
		for (int32 SlotIndex = 0; SlotIndex < MaterialCount; ++SlotIndex)
		{
			if (Component->GetMaterial(SlotIndex) == FaceMaterial)
			{
				return SlotIndex;
			}
		}
	}

	OutRejectReason = FString::Printf(TEXT("%s has %d material slots; pass OverrideMaterialSlot for version 1"), *GetNameSafe(Component), MaterialCount);
	return INDEX_NONE;
}

bool AProphecyBloodTexturePaintManager::FindPaintUV(UMeshComponent* Component, const FHitResult& Hit, int32 OverrideMaterialSlot, FVector2D& OutUV, int32& OutMaterialSlot, float& OutBrushUVUnitsPerWorldUnit, FString& OutRejectReason) const
{
	OutBrushUVUnitsPerWorldUnit = 0.0f;

	if (!Component)
	{
		OutRejectReason = TEXT("missing component");
		return false;
	}

	FString MaterialRejectReason;
	const int32 ResolvedMaterialSlot = ResolveMaterialSlot(Component, Hit, OverrideMaterialSlot, MaterialRejectReason);
	if (ResolvedMaterialSlot >= 0)
	{
		FVector2D CollisionUV = FVector2D::ZeroVector;
		if (UGameplayStatics::FindCollisionUV(Hit, PaintUVChannel, CollisionUV))
		{
			OutUV = CollisionUV;
			OutMaterialSlot = ResolvedMaterialSlot;
			return true;
		}
	}

	if (USkinnedMeshComponent* SkinnedMeshComponent = Cast<USkinnedMeshComponent>(Component))
	{
		FString SkinnedRejectReason;
		if (FindSkinnedMeshPaintUV(SkinnedMeshComponent, Hit, PaintUVChannel, OverrideMaterialSlot, OutUV, OutMaterialSlot, OutBrushUVUnitsPerWorldUnit, SkinnedRejectReason))
		{
			return true;
		}

		if (ResolvedMaterialSlot < 0)
		{
			OutRejectReason = FString::Printf(TEXT("%s; skinned UV fallback failed: %s"), *MaterialRejectReason, *SkinnedRejectReason);
		}
		else
		{
			OutRejectReason = FString::Printf(TEXT("FindCollisionUV failed on %s using UV channel %d; skinned UV fallback failed: %s"),
				*GetNameSafe(Component),
				PaintUVChannel,
				*SkinnedRejectReason);
		}
		return false;
	}

	if (ResolvedMaterialSlot < 0)
	{
		OutRejectReason = MaterialRejectReason;
		return false;
	}

	OutRejectReason = FString::Printf(TEXT("FindCollisionUV failed on %s using UV channel %d"), *GetNameSafe(Component), PaintUVChannel);
	return false;
}

bool AProphecyBloodTexturePaintManager::FindSkinnedMeshPaintUV(USkinnedMeshComponent* Component, const FHitResult& Hit, int32 UVChannel, int32 OverrideMaterialSlot, FVector2D& OutUV, int32& OutMaterialSlot, float& OutBrushUVUnitsPerWorldUnit, FString& OutRejectReason) const
{
	OutBrushUVUnitsPerWorldUnit = 0.0f;

	if (!Component)
	{
		OutRejectReason = TEXT("missing skinned component");
		return false;
	}

	const int32 MaterialCount = Component->GetNumMaterials();
	if (MaterialCount <= 0)
	{
		OutRejectReason = FString::Printf(TEXT("%s has no material slots"), *GetNameSafe(Component));
		return false;
	}

	if (OverrideMaterialSlot >= MaterialCount)
	{
		OutRejectReason = FString::Printf(TEXT("override material slot %d out of range for %s"), OverrideMaterialSlot, *GetNameSafe(Component));
		return false;
	}

	USkinnedAsset* SkinnedAsset = Component->GetSkinnedAsset();
	if (!SkinnedAsset)
	{
		OutRejectReason = FString::Printf(TEXT("%s has no SkinnedAsset"), *GetNameSafe(Component));
		return false;
	}

	const FProphecySkinnedPaintMeshCache* Cache = GetOrBuildSkinnedPaintMeshCache(Component, UVChannel, OutRejectReason);
	if (!Cache)
	{
		return false;
	}

	const FVector HitWorldPosition = Hit.ImpactPoint.IsNearlyZero() ? Hit.Location : Hit.ImpactPoint;
	FVector ReferenceLocalHitPosition = Component->GetComponentTransform().InverseTransformPosition(HitWorldPosition);
	const int32 HitBoneIndex = Hit.BoneName != NAME_None ? Component->GetBoneIndex(Hit.BoneName) : INDEX_NONE;
	const TArray<int32>* CandidateTriangleIndices = nullptr;
	if (HitBoneIndex != INDEX_NONE)
	{
		CandidateTriangleIndices = Cache->TriangleIndicesByBone.Find(HitBoneIndex);

		const FTransform CurrentBoneWorldTransform = Component->GetBoneTransform(HitBoneIndex);
		const FTransform ReferenceBoneComponentTransform(SkinnedAsset->GetComposedRefPoseMatrix(HitBoneIndex));
		const FVector BoneLocalHitPosition = CurrentBoneWorldTransform.InverseTransformPosition(HitWorldPosition);
		ReferenceLocalHitPosition = ReferenceBoneComponentTransform.TransformPosition(BoneLocalHitPosition);
	}

	double BestDistanceSquared = TNumericLimits<double>::Max();
	FVector2D BestUV = FVector2D::ZeroVector;
	int32 BestMaterialSlot = INDEX_NONE;
	float BestBrushUVUnitsPerWorldUnit = 0.0f;
	const FTransform ComponentTransform = Component->GetComponentTransform();

	auto ConsiderTriangle = [OverrideMaterialSlot, ReferenceLocalHitPosition, ComponentTransform, &BestDistanceSquared, &BestUV, &BestMaterialSlot, &BestBrushUVUnitsPerWorldUnit](const FProphecySkinnedPaintTriangle& Triangle)
	{
		if (Triangle.MaterialSlot < 0 || (OverrideMaterialSlot >= 0 && Triangle.MaterialSlot != OverrideMaterialSlot))
		{
			return;
		}

		const FVector ClosestPoint = FMath::ClosestPointOnTriangleToPoint(ReferenceLocalHitPosition, Triangle.A, Triangle.B, Triangle.C);
		const double DistanceSquared = FVector::DistSquared(ReferenceLocalHitPosition, ClosestPoint);
		if (DistanceSquared >= BestDistanceSquared)
		{
			return;
		}

		FVector Barycentric = FVector::ZeroVector;
		if (!FMath::ComputeBarycentricTri(ClosestPoint, Triangle.A, Triangle.B, Triangle.C, Barycentric, KINDA_SMALL_NUMBER))
		{
			return;
		}

		BestUV = Triangle.UVA * Barycentric.X + Triangle.UVB * Barycentric.Y + Triangle.UVC * Barycentric.Z;
		BestMaterialSlot = Triangle.MaterialSlot;
		BestBrushUVUnitsPerWorldUnit = EstimateTriangleUVUnitsPerWorldUnit(Triangle, ComponentTransform);
		BestDistanceSquared = DistanceSquared;
	};

	if (CandidateTriangleIndices && CandidateTriangleIndices->Num() > 0)
	{
		for (int32 TriangleIndex : *CandidateTriangleIndices)
		{
			if (Cache->Triangles.IsValidIndex(TriangleIndex))
			{
				ConsiderTriangle(Cache->Triangles[TriangleIndex]);
			}
		}
	}

	if (BestMaterialSlot < 0)
	{
		for (const FProphecySkinnedPaintTriangle& Triangle : Cache->Triangles)
		{
			ConsiderTriangle(Triangle);
		}
	}

	if (BestMaterialSlot < 0)
	{
		OutRejectReason = OverrideMaterialSlot >= 0
			? FString::Printf(TEXT("%s found no render triangles for material slot %d"), *GetNameSafe(Component), OverrideMaterialSlot)
			: FString::Printf(TEXT("%s found no valid render triangles"), *GetNameSafe(Component));
		return false;
	}

	OutUV = BestUV;
	OutMaterialSlot = BestMaterialSlot;
	OutBrushUVUnitsPerWorldUnit = BestBrushUVUnitsPerWorldUnit;
	return true;
}

const FProphecySkinnedPaintMeshCache* AProphecyBloodTexturePaintManager::GetOrBuildSkinnedPaintMeshCache(USkinnedMeshComponent* Component, int32 UVChannel, FString& OutRejectReason) const
{
	if (!Component)
	{
		OutRejectReason = TEXT("missing skinned component");
		return nullptr;
	}

	USkinnedAsset* SkinnedAsset = Component->GetSkinnedAsset();
	if (!SkinnedAsset)
	{
		OutRejectReason = FString::Printf(TEXT("%s has no SkinnedAsset"), *GetNameSafe(Component));
		return nullptr;
	}

	const FString CacheKey = MakeSkinnedPaintMeshCacheKey(SkinnedAsset, UVChannel);
	if (FProphecySkinnedPaintMeshCache* ExistingCache = SkinnedPaintMeshCaches.Find(CacheKey))
	{
		return ExistingCache;
	}

	FSkeletalMeshRenderData* RenderData = SkinnedAsset->GetResourceForRendering();
	if (!RenderData || RenderData->LODRenderData.Num() == 0)
	{
		OutRejectReason = FString::Printf(TEXT("%s has no skeletal render data"), *GetNameSafe(SkinnedAsset));
		return nullptr;
	}

	const int32 LODIndex = 0;
	const FSkeletalMeshLODRenderData& LODData = RenderData->LODRenderData[LODIndex];
	if (UVChannel < 0 || UVChannel >= static_cast<int32>(LODData.GetNumTexCoords()))
	{
		OutRejectReason = FString::Printf(TEXT("%s does not have UV channel %d on LOD %d"), *GetNameSafe(SkinnedAsset), UVChannel, LODIndex);
		return nullptr;
	}

	if (!LODData.MultiSizeIndexContainer.IsIndexBufferValid())
	{
		OutRejectReason = FString::Printf(TEXT("%s has no CPU-readable index buffer for LOD %d"), *GetNameSafe(SkinnedAsset), LODIndex);
		return nullptr;
	}

	TArray<uint32> Indices;
	LODData.MultiSizeIndexContainer.GetIndexBuffer(Indices);
	if (Indices.Num() == 0)
	{
		OutRejectReason = FString::Printf(TEXT("%s returned no skeletal mesh indices"), *GetNameSafe(SkinnedAsset));
		return nullptr;
	}

	FProphecySkinnedPaintMeshCache NewCache;
	NewCache.AssetPath = SkinnedAsset->GetPathName();
	NewCache.UVChannel = UVChannel;
	NewCache.Triangles.Reserve(Indices.Num() / 3);

	const uint32 MaxInfluences = LODData.SkinWeightVertexBuffer.GetMaxBoneInfluences();
	auto AddVertexBones = [&LODData, MaxInfluences](const FSkelMeshRenderSection& Section, int32 VertexIndex, TSet<int32>& OutBoneIndices)
	{
		if (VertexIndex < 0 || static_cast<uint32>(VertexIndex) >= LODData.SkinWeightVertexBuffer.GetNumVertices())
		{
			return;
		}

		for (uint32 InfluenceIndex = 0; InfluenceIndex < MaxInfluences; ++InfluenceIndex)
		{
			const uint16 InfluenceWeight = LODData.SkinWeightVertexBuffer.GetBoneWeight(VertexIndex, InfluenceIndex);
			if (InfluenceWeight == 0)
			{
				continue;
			}

			const int32 SectionBoneMapIndex = static_cast<int32>(LODData.SkinWeightVertexBuffer.GetBoneIndex(VertexIndex, InfluenceIndex));
			if (Section.BoneMap.IsValidIndex(SectionBoneMapIndex))
			{
				OutBoneIndices.Add(static_cast<int32>(Section.BoneMap[SectionBoneMapIndex]));
			}
		}
	};

	for (const FSkelMeshRenderSection& Section : LODData.RenderSections)
	{
		const int32 SectionMaterialSlot = static_cast<int32>(Section.MaterialIndex);
		if (!Section.IsValid() || SectionMaterialSlot < 0)
		{
			continue;
		}

		for (uint32 SectionTriangleIndex = 0; SectionTriangleIndex < Section.NumTriangles; ++SectionTriangleIndex)
		{
			const uint32 IndexOffset = Section.BaseIndex + SectionTriangleIndex * 3;
			if (IndexOffset + 2 >= static_cast<uint32>(Indices.Num()))
			{
				continue;
			}

			const int32 Index0 = static_cast<int32>(Indices[IndexOffset]);
			const int32 Index1 = static_cast<int32>(Indices[IndexOffset + 1]);
			const int32 Index2 = static_cast<int32>(Indices[IndexOffset + 2]);
			if (Index0 < 0 || Index1 < 0 || Index2 < 0 ||
				static_cast<uint32>(Index0) >= LODData.StaticVertexBuffers.PositionVertexBuffer.GetNumVertices() ||
				static_cast<uint32>(Index1) >= LODData.StaticVertexBuffers.PositionVertexBuffer.GetNumVertices() ||
				static_cast<uint32>(Index2) >= LODData.StaticVertexBuffers.PositionVertexBuffer.GetNumVertices() ||
				static_cast<uint32>(Index0) >= LODData.StaticVertexBuffers.StaticMeshVertexBuffer.GetNumVertices() ||
				static_cast<uint32>(Index1) >= LODData.StaticVertexBuffers.StaticMeshVertexBuffer.GetNumVertices() ||
				static_cast<uint32>(Index2) >= LODData.StaticVertexBuffers.StaticMeshVertexBuffer.GetNumVertices())
			{
				continue;
			}

			FProphecySkinnedPaintTriangle Triangle;
			Triangle.A = ToVector(LODData.StaticVertexBuffers.PositionVertexBuffer.VertexPosition(Index0));
			Triangle.B = ToVector(LODData.StaticVertexBuffers.PositionVertexBuffer.VertexPosition(Index1));
			Triangle.C = ToVector(LODData.StaticVertexBuffers.PositionVertexBuffer.VertexPosition(Index2));
			Triangle.UVA = FVector2D(LODData.StaticVertexBuffers.StaticMeshVertexBuffer.GetVertexUV(Index0, UVChannel));
			Triangle.UVB = FVector2D(LODData.StaticVertexBuffers.StaticMeshVertexBuffer.GetVertexUV(Index1, UVChannel));
			Triangle.UVC = FVector2D(LODData.StaticVertexBuffers.StaticMeshVertexBuffer.GetVertexUV(Index2, UVChannel));
			Triangle.MaterialSlot = SectionMaterialSlot;

			const int32 NewTriangleIndex = NewCache.Triangles.Add(Triangle);
			TSet<int32> TriangleBoneIndices;
			AddVertexBones(Section, Index0, TriangleBoneIndices);
			AddVertexBones(Section, Index1, TriangleBoneIndices);
			AddVertexBones(Section, Index2, TriangleBoneIndices);
			for (int32 BoneIndex : TriangleBoneIndices)
			{
				NewCache.TriangleIndicesByBone.FindOrAdd(BoneIndex).Add(NewTriangleIndex);
			}
		}
	}

	if (NewCache.Triangles.Num() == 0)
	{
		OutRejectReason = FString::Printf(TEXT("%s produced no cached paint triangles"), *GetNameSafe(SkinnedAsset));
		return nullptr;
	}

	FProphecySkinnedPaintMeshCache& StoredCache = SkinnedPaintMeshCaches.Add(CacheKey, MoveTemp(NewCache));
	if (bDebugMode || bDebugPrintHits)
	{
		UE_LOG(LogProphecyBloodTexturePaint, Log, TEXT("Built skinned blood paint cache for %s UV%d: triangles=%d bones=%d"),
			*GetNameSafe(SkinnedAsset),
			UVChannel,
			StoredCache.Triangles.Num(),
			StoredCache.TriangleIndicesByBone.Num());
	}
	return &StoredCache;
}

FString AProphecyBloodTexturePaintManager::MakeSkinnedPaintMeshCacheKey(const USkinnedAsset* SkinnedAsset, int32 UVChannel) const
{
	return FString::Printf(TEXT("%s_UV%d_LOD0"), SkinnedAsset ? *SkinnedAsset->GetPathName() : TEXT("None"), UVChannel);
}

UMaterialInterface* AProphecyBloodTexturePaintManager::ResolveBloodMaterialTemplate(UMaterialInterface* CurrentMaterial) const
{
	for (const FProphecyBloodMaterialPair& Pair : BloodEnabledMaterialPairs)
	{
		if (Pair.CleanMaterial == CurrentMaterial && Pair.BloodMaterial)
		{
			return Pair.BloodMaterial;
		}
	}

	return bUseDefaultBloodMaterialTemplateForUnmappedMaterials ? DefaultBloodMaterialTemplate.Get() : nullptr;
}

UMaterialInterface* AProphecyBloodTexturePaintManager::ResolveOrCreateBloodMaterialTemplate(UMaterialInterface* CurrentMaterial)
{
	if (UMaterialInterface* ExistingTemplate = ResolveBloodMaterialTemplate(CurrentMaterial))
	{
		return ExistingTemplate;
	}

#if WITH_EDITOR
	if (bEditorAutoCreateBloodMaterials)
	{
		return EditorEnsureBloodMaterialTemplate(CurrentMaterial);
	}
#endif

	return nullptr;
}

#if WITH_EDITOR
UMaterialInterface* AProphecyBloodTexturePaintManager::EditorEnsureBloodMaterialTemplate(UMaterialInterface* CurrentMaterial)
{
	if (!CurrentMaterial)
	{
		return nullptr;
	}

	const FString GeneratedName = MakeSafeGeneratedMaterialName(CurrentMaterial, EditorGeneratedBloodMaterialSuffix);
	const FString GeneratedPath = EditorGeneratedBloodMaterialFolder / GeneratedName;
	const FString GeneratedObjectPath = FString::Printf(TEXT("%s.%s"), *GeneratedPath, *GeneratedName);
	UObject* ExistingAsset = LoadObject<UObject>(nullptr, *GeneratedObjectPath);

	const bool bMayOverwriteExistingAsset = bEditorAutoUpdateBloodMaterials && bEditorAllowGeneratedMaterialOverwrite;
	if (ExistingAsset && !bMayOverwriteExistingAsset)
	{
		if (UMaterialInterface* ExistingMaterial = Cast<UMaterialInterface>(ExistingAsset))
		{
			FProphecyBloodMaterialPair Pair;
			Pair.CleanMaterial = CurrentMaterial;
			Pair.BloodMaterial = ExistingMaterial;
			BloodEnabledMaterialPairs.Add(Pair);
			return ExistingMaterial;
		}
	}

	if (UMaterialInstanceConstant* SourceInstance = Cast<UMaterialInstanceConstant>(CurrentMaterial))
	{
		UMaterialInterface* SourceParent = SourceInstance->Parent;
		if (!SourceParent)
		{
			UE_LOG(LogProphecyBloodTexturePaint, Warning, TEXT("Editor auto blood material generation failed: %s has no parent material"), *GetNameSafe(SourceInstance));
			return nullptr;
		}

		UMaterialInterface* BloodParent = ResolveOrCreateBloodMaterialTemplate(SourceParent);
		if (!BloodParent)
		{
			UE_LOG(LogProphecyBloodTexturePaint, Warning, TEXT("Editor auto blood material generation failed: could not generate blood parent for %s"), *GetNameSafe(SourceInstance));
			return nullptr;
		}

		if (ExistingAsset)
		{
			TArray<UObject*> ObjectsToDelete;
			ObjectsToDelete.Add(ExistingAsset);
			ObjectTools::ForceDeleteObjects(ObjectsToDelete, false);
			ExistingAsset = nullptr;
		}

		FAssetToolsModule& AssetToolsModule = FModuleManager::LoadModuleChecked<FAssetToolsModule>(TEXT("AssetTools"));
		UObject* DuplicatedAsset = AssetToolsModule.Get().DuplicateAsset(GeneratedName, EditorGeneratedBloodMaterialFolder, SourceInstance);
		UMaterialInstanceConstant* GeneratedInstance = Cast<UMaterialInstanceConstant>(DuplicatedAsset);
		if (!GeneratedInstance)
		{
			UE_LOG(LogProphecyBloodTexturePaint, Warning, TEXT("Failed to duplicate material instance %s to %s"), *GetNameSafe(SourceInstance), *GeneratedPath);
			return nullptr;
		}

		UMaterialEditingLibrary::SetMaterialInstanceParent(GeneratedInstance, BloodParent);
		UMaterialEditingLibrary::UpdateMaterialInstance(GeneratedInstance);

		if (bEditorSaveGeneratedBloodMaterials)
		{
			TArray<UObject*> ObjectsToSave;
			ObjectsToSave.Add(GeneratedInstance);
			UPackageTools::SavePackagesForObjects(ObjectsToSave);
		}

		FProphecyBloodMaterialPair Pair;
		Pair.CleanMaterial = CurrentMaterial;
		Pair.BloodMaterial = GeneratedInstance;
		BloodEnabledMaterialPairs.Add(Pair);
		UE_LOG(LogProphecyBloodTexturePaint, Log, TEXT("Generated blood paint material instance %s for %s"), *GeneratedPath, *GetNameSafe(CurrentMaterial));
		return GeneratedInstance;
	}

	UMaterial* SourceMaterial = Cast<UMaterial>(CurrentMaterial);
	if (!SourceMaterial)
	{
		UE_LOG(LogProphecyBloodTexturePaint, Warning, TEXT("Editor auto blood material generation supports UMaterial and UMaterialInstanceConstant assets; %s is %s"),
			*GetNameSafe(CurrentMaterial),
			*GetNameSafe(CurrentMaterial->GetClass()));
		return nullptr;
	}

	if (ExistingAsset)
	{
		TArray<UObject*> ObjectsToDelete;
		ObjectsToDelete.Add(ExistingAsset);
		ObjectTools::ForceDeleteObjects(ObjectsToDelete, false);
		ExistingAsset = nullptr;
	}

	FAssetToolsModule& AssetToolsModule = FModuleManager::LoadModuleChecked<FAssetToolsModule>(TEXT("AssetTools"));
	UObject* DuplicatedAsset = AssetToolsModule.Get().DuplicateAsset(GeneratedName, EditorGeneratedBloodMaterialFolder, SourceMaterial);
	UMaterial* GeneratedMaterial = Cast<UMaterial>(DuplicatedAsset);
	if (!GeneratedMaterial)
	{
		UE_LOG(LogProphecyBloodTexturePaint, Warning, TEXT("Failed to duplicate %s to %s"), *GetNameSafe(SourceMaterial), *GeneratedPath);
		return nullptr;
	}

	UMaterialExpression* OriginalBaseNode = UMaterialEditingLibrary::GetMaterialPropertyInputNode(GeneratedMaterial, MP_BaseColor);
	FString OriginalBaseOutput = UMaterialEditingLibrary::GetMaterialPropertyInputNodeOutputName(GeneratedMaterial, MP_BaseColor);
	UMaterialExpression* OriginalRoughnessNode = UMaterialEditingLibrary::GetMaterialPropertyInputNode(GeneratedMaterial, MP_Roughness);
	FString OriginalRoughnessOutput = UMaterialEditingLibrary::GetMaterialPropertyInputNodeOutputName(GeneratedMaterial, MP_Roughness);
	UMaterialExpression* OriginalSpecularNode = UMaterialEditingLibrary::GetMaterialPropertyInputNode(GeneratedMaterial, MP_Specular);
	FString OriginalSpecularOutput = UMaterialEditingLibrary::GetMaterialPropertyInputNodeOutputName(GeneratedMaterial, MP_Specular);
	UMaterialExpression* OriginalMetallicNode = UMaterialEditingLibrary::GetMaterialPropertyInputNode(GeneratedMaterial, MP_Metallic);
	FString OriginalMetallicOutput = UMaterialEditingLibrary::GetMaterialPropertyInputNodeOutputName(GeneratedMaterial, MP_Metallic);
	UMaterialExpression* OriginalMaterialAttributesNode = UMaterialEditingLibrary::GetMaterialPropertyInputNode(GeneratedMaterial, MP_MaterialAttributes);
	FString OriginalMaterialAttributesOutput = UMaterialEditingLibrary::GetMaterialPropertyInputNodeOutputName(GeneratedMaterial, MP_MaterialAttributes);

	UMaterialExpressionTextureCoordinate* PaintUV = Cast<UMaterialExpressionTextureCoordinate>(
		UMaterialEditingLibrary::CreateMaterialExpression(GeneratedMaterial, UMaterialExpressionTextureCoordinate::StaticClass(), -1250, -250));
	if (PaintUV)
	{
		PaintUV->CoordinateIndex = PaintUVChannel;
	}

	UMaterialExpressionTextureSampleParameter2D* MaskTexture = Cast<UMaterialExpressionTextureSampleParameter2D>(
		UMaterialEditingLibrary::CreateMaterialExpression(GeneratedMaterial, UMaterialExpressionTextureSampleParameter2D::StaticClass(), -1040, -250));
	if (MaskTexture)
	{
		MaskTexture->ParameterName = BloodMaskTextureParameter;
		MaskTexture->Texture = LoadObject<UTexture>(nullptr, TEXT("/Engine/EngineResources/Black.Black"));
	}

	UMaterialExpressionScalarParameter* Intensity = Cast<UMaterialExpressionScalarParameter>(
		UMaterialEditingLibrary::CreateMaterialExpression(GeneratedMaterial, UMaterialExpressionScalarParameter::StaticClass(), -1040, -60));
	if (Intensity)
	{
		Intensity->ParameterName = BloodIntensityParameter;
		Intensity->DefaultValue = 1.0f;
	}

	UMaterialExpressionMaterialFunctionCall* BloodSurfaceCall = CreateBloodPaintSurfaceCall(GeneratedMaterial, -320, 170);
	if (!BloodSurfaceCall)
	{
		UE_LOG(LogProphecyBloodTexturePaint, Warning, TEXT("Could not inject shared blood surface function into %s"), *GeneratedPath);
		return nullptr;
	}

	UMaterialExpressionScalarParameter* DebugMaskParam = Cast<UMaterialExpressionScalarParameter>(
		UMaterialEditingLibrary::CreateMaterialExpression(GeneratedMaterial, UMaterialExpressionScalarParameter::StaticClass(), -1040, 330));
	if (DebugMaskParam)
	{
		DebugMaskParam->ParameterName = DebugShowMaskParameter;
		DebugMaskParam->DefaultValue = 0.0f;
	}

	UMaterialExpressionMultiply* Multiply = Cast<UMaterialExpressionMultiply>(
		UMaterialEditingLibrary::CreateMaterialExpression(GeneratedMaterial, UMaterialExpressionMultiply::StaticClass(), -760, -190));
	UMaterialExpressionSaturate* Saturate = Cast<UMaterialExpressionSaturate>(
		UMaterialEditingLibrary::CreateMaterialExpression(GeneratedMaterial, UMaterialExpressionSaturate::StaticClass(), -560, -190));
	UMaterialExpressionLinearInterpolate* BaseLerp = Cast<UMaterialExpressionLinearInterpolate>(
		UMaterialEditingLibrary::CreateMaterialExpression(GeneratedMaterial, UMaterialExpressionLinearInterpolate::StaticClass(), -80, -140));
	UMaterialExpressionLinearInterpolate* RoughnessLerp = Cast<UMaterialExpressionLinearInterpolate>(
		UMaterialEditingLibrary::CreateMaterialExpression(GeneratedMaterial, UMaterialExpressionLinearInterpolate::StaticClass(), -80, 110));
	UMaterialExpressionLinearInterpolate* SpecularLerp = Cast<UMaterialExpressionLinearInterpolate>(
		UMaterialEditingLibrary::CreateMaterialExpression(GeneratedMaterial, UMaterialExpressionLinearInterpolate::StaticClass(), -80, 300));
	UMaterialExpressionLinearInterpolate* MetallicLerp = Cast<UMaterialExpressionLinearInterpolate>(
		UMaterialEditingLibrary::CreateMaterialExpression(GeneratedMaterial, UMaterialExpressionLinearInterpolate::StaticClass(), -80, 490));
	UMaterialExpressionLinearInterpolate* DebugLerp = Cast<UMaterialExpressionLinearInterpolate>(
		UMaterialEditingLibrary::CreateMaterialExpression(GeneratedMaterial, UMaterialExpressionLinearInterpolate::StaticClass(), 180, -140));

	if (PaintUV && MaskTexture)
	{
		UMaterialEditingLibrary::ConnectMaterialExpressions(PaintUV, FString(), MaskTexture, TEXT("UVs"));
	}
	if (MaskTexture && Multiply)
	{
		UMaterialEditingLibrary::ConnectMaterialExpressions(MaskTexture, TEXT("R"), Multiply, TEXT("A"));
	}
	if (Intensity && Multiply)
	{
		UMaterialEditingLibrary::ConnectMaterialExpressions(Intensity, FString(), Multiply, TEXT("B"));
	}
	if (Multiply && Saturate)
	{
		UMaterialEditingLibrary::ConnectMaterialExpressions(Multiply, FString(), Saturate, FString());
	}

	if (!OriginalBaseNode)
	{
		UMaterialExpressionConstant3Vector* BaseFallback = Cast<UMaterialExpressionConstant3Vector>(
			UMaterialEditingLibrary::CreateMaterialExpression(GeneratedMaterial, UMaterialExpressionConstant3Vector::StaticClass(), -560, 40));
		if (BaseFallback)
		{
			BaseFallback->Constant = FLinearColor(0.5f, 0.5f, 0.5f, 1.0f);
			OriginalBaseNode = BaseFallback;
		}
	}

	if (!OriginalRoughnessNode)
	{
		UMaterialExpressionConstant* RoughnessFallback = Cast<UMaterialExpressionConstant>(
			UMaterialEditingLibrary::CreateMaterialExpression(GeneratedMaterial, UMaterialExpressionConstant::StaticClass(), -560, 390));
		if (RoughnessFallback)
		{
			RoughnessFallback->R = 0.55f;
			OriginalRoughnessNode = RoughnessFallback;
		}
	}

	if (!OriginalSpecularNode)
	{
		UMaterialExpressionConstant* SpecularFallback = Cast<UMaterialExpressionConstant>(
			UMaterialEditingLibrary::CreateMaterialExpression(GeneratedMaterial, UMaterialExpressionConstant::StaticClass(), -560, 580));
		if (SpecularFallback)
		{
			SpecularFallback->R = 0.5f;
			OriginalSpecularNode = SpecularFallback;
		}
	}

	if (!OriginalMetallicNode)
	{
		UMaterialExpressionConstant* MetallicFallback = Cast<UMaterialExpressionConstant>(
			UMaterialEditingLibrary::CreateMaterialExpression(GeneratedMaterial, UMaterialExpressionConstant::StaticClass(), -560, 770));
		if (MetallicFallback)
		{
			MetallicFallback->R = 0.0f;
			OriginalMetallicNode = MetallicFallback;
		}
	}

	UMaterialExpressionSetMaterialAttributes* SetBloodAttributesNode = nullptr;
	if (OriginalMaterialAttributesNode)
	{
		const int32 OriginalMaterialAttributesOutputIndex = FindExpressionOutputIndexByName(OriginalMaterialAttributesNode, OriginalMaterialAttributesOutput);
		UMaterialExpressionGetMaterialAttributes* GetAttributesNode = Cast<UMaterialExpressionGetMaterialAttributes>(
			UMaterialEditingLibrary::CreateMaterialExpression(GeneratedMaterial, UMaterialExpressionGetMaterialAttributes::StaticClass(), -560, 170));
		SetBloodAttributesNode = Cast<UMaterialExpressionSetMaterialAttributes>(
			UMaterialEditingLibrary::CreateMaterialExpression(GeneratedMaterial, UMaterialExpressionSetMaterialAttributes::StaticClass(), 260, 170));

		if (GetAttributesNode)
		{
			GetAttributesNode->MaterialAttributes.Connect(OriginalMaterialAttributesOutputIndex, OriginalMaterialAttributesNode);
		}
		if (SetBloodAttributesNode && SetBloodAttributesNode->Inputs.IsValidIndex(0))
		{
			SetBloodAttributesNode->Inputs[0].Connect(OriginalMaterialAttributesOutputIndex, OriginalMaterialAttributesNode);
		}

		auto ConnectAttributeLerp = [GetAttributesNode, SetBloodAttributesNode, BloodSurfaceCall, Saturate](EMaterialProperty Property, FName BloodOutputName, UMaterialExpressionLinearInterpolate* Lerp)
		{
			if (!Lerp || !GetAttributesNode || !SetBloodAttributesNode)
			{
				return;
			}

			const int32 OriginalOutputIndex = GetAttributesNode->CreateOrGetOutputAttribute(Property);
			Lerp->A.Connect(OriginalOutputIndex, GetAttributesNode);
			ConnectFunctionOutputByName(BloodSurfaceCall, BloodOutputName, Lerp->B);
			if (Saturate)
			{
				Lerp->Alpha.Connect(0, Saturate);
			}
			SetBloodAttributesNode->ConnectInputAttribute(Property, Lerp, 0);
		};

		ConnectAttributeLerp(MP_BaseColor, TEXT("BaseColorOut"), BaseLerp);
		ConnectAttributeLerp(MP_Roughness, TEXT("RoughnessOut"), RoughnessLerp);
		ConnectAttributeLerp(MP_Specular, TEXT("SpecularOut"), SpecularLerp);
		ConnectAttributeLerp(MP_Metallic, TEXT("MetallicOut"), MetallicLerp);
		if (SetBloodAttributesNode)
		{
			UMaterialEditingLibrary::ConnectMaterialProperty(SetBloodAttributesNode, FString(), MP_MaterialAttributes);
		}
	}
	else
	{
		if (OriginalBaseNode && BaseLerp)
		{
			UMaterialEditingLibrary::ConnectMaterialExpressions(OriginalBaseNode, OriginalBaseOutput, BaseLerp, TEXT("A"));
			UMaterialEditingLibrary::ConnectMaterialExpressions(BloodSurfaceCall, TEXT("BaseColorOut"), BaseLerp, TEXT("B"));
			UMaterialEditingLibrary::ConnectMaterialExpressions(Saturate, FString(), BaseLerp, TEXT("Alpha"));
		}
		if (OriginalRoughnessNode && RoughnessLerp)
		{
			UMaterialEditingLibrary::ConnectMaterialExpressions(OriginalRoughnessNode, OriginalRoughnessOutput, RoughnessLerp, TEXT("A"));
			UMaterialEditingLibrary::ConnectMaterialExpressions(BloodSurfaceCall, TEXT("RoughnessOut"), RoughnessLerp, TEXT("B"));
			UMaterialEditingLibrary::ConnectMaterialExpressions(Saturate, FString(), RoughnessLerp, TEXT("Alpha"));
		}
		if (OriginalSpecularNode && SpecularLerp)
		{
			UMaterialEditingLibrary::ConnectMaterialExpressions(OriginalSpecularNode, OriginalSpecularOutput, SpecularLerp, TEXT("A"));
			UMaterialEditingLibrary::ConnectMaterialExpressions(BloodSurfaceCall, TEXT("SpecularOut"), SpecularLerp, TEXT("B"));
			UMaterialEditingLibrary::ConnectMaterialExpressions(Saturate, FString(), SpecularLerp, TEXT("Alpha"));
		}
		if (OriginalMetallicNode && MetallicLerp)
		{
			UMaterialEditingLibrary::ConnectMaterialExpressions(OriginalMetallicNode, OriginalMetallicOutput, MetallicLerp, TEXT("A"));
			UMaterialEditingLibrary::ConnectMaterialExpressions(BloodSurfaceCall, TEXT("MetallicOut"), MetallicLerp, TEXT("B"));
			UMaterialEditingLibrary::ConnectMaterialExpressions(Saturate, FString(), MetallicLerp, TEXT("Alpha"));
		}
	}
	if (BaseLerp && DebugLerp)
	{
		UMaterialEditingLibrary::ConnectMaterialExpressions(BaseLerp, FString(), DebugLerp, TEXT("A"));
	}
	if (Saturate && DebugLerp)
	{
		UMaterialEditingLibrary::ConnectMaterialExpressions(Saturate, FString(), DebugLerp, TEXT("B"));
	}
	if (DebugMaskParam && DebugLerp)
	{
		UMaterialEditingLibrary::ConnectMaterialExpressions(DebugMaskParam, FString(), DebugLerp, TEXT("Alpha"));
	}

	if (OriginalMaterialAttributesNode && SetBloodAttributesNode && DebugLerp)
	{
		SetBloodAttributesNode->ConnectInputAttribute(MP_BaseColor, DebugLerp, 0);
		UMaterialEditingLibrary::ConnectMaterialProperty(SetBloodAttributesNode, FString(), MP_MaterialAttributes);
	}
	else if (DebugLerp)
	{
		UMaterialEditingLibrary::ConnectMaterialProperty(DebugLerp, FString(), MP_BaseColor);
	}
	if (!OriginalMaterialAttributesNode)
	{
		if (RoughnessLerp)
		{
			UMaterialEditingLibrary::ConnectMaterialProperty(RoughnessLerp, FString(), MP_Roughness);
		}
		if (SpecularLerp)
		{
			UMaterialEditingLibrary::ConnectMaterialProperty(SpecularLerp, FString(), MP_Specular);
		}
		if (MetallicLerp)
		{
			UMaterialEditingLibrary::ConnectMaterialProperty(MetallicLerp, FString(), MP_Metallic);
		}
	}

	bool bNeedsRecompile = false;
	UMaterialEditingLibrary::SetMaterialUsage(GeneratedMaterial, MATUSAGE_StaticMesh, bNeedsRecompile);
	UMaterialEditingLibrary::SetMaterialUsage(GeneratedMaterial, MATUSAGE_SkeletalMesh, bNeedsRecompile);
	UMaterialEditingLibrary::SetMaterialUsage(GeneratedMaterial, MATUSAGE_Nanite, bNeedsRecompile);
	UMaterialEditingLibrary::LayoutMaterialExpressions(GeneratedMaterial);
	UMaterialEditingLibrary::RecompileMaterial(GeneratedMaterial);

	if (bEditorSaveGeneratedBloodMaterials)
	{
		TArray<UObject*> ObjectsToSave;
		ObjectsToSave.Add(GeneratedMaterial);
		UPackageTools::SavePackagesForObjects(ObjectsToSave);
	}

	FProphecyBloodMaterialPair Pair;
	Pair.CleanMaterial = CurrentMaterial;
	Pair.BloodMaterial = GeneratedMaterial;
	BloodEnabledMaterialPairs.Add(Pair);
	UE_LOG(LogProphecyBloodTexturePaint, Log, TEXT("Generated blood paint material %s for %s"), *GeneratedPath, *GetNameSafe(CurrentMaterial));
	return GeneratedMaterial;
}
#endif

FProphecyBloodPaintState* AProphecyBloodTexturePaintManager::EnsurePaintState(UMeshComponent* Component, int32 MaterialSlot, FString& OutRejectReason)
{
	const FString StateKey = MakeStateKey(Component, MaterialSlot);
	if (FProphecyBloodPaintState* ExistingState = PaintStatesByKey.Find(StateKey))
	{
		return ExistingState;
	}

	if (PaintStatesByKey.Num() >= MaxActivePaintRTs)
	{
		OutRejectReason = FString::Printf(TEXT("paint budget exceeded: active RTs=%d max=%d"), PaintStatesByKey.Num(), MaxActivePaintRTs);
		return nullptr;
	}

	UMaterialInterface* OriginalMaterial = Component ? Component->GetMaterial(MaterialSlot) : nullptr;
	UMaterialInterface* BloodTemplate = ResolveOrCreateBloodMaterialTemplate(OriginalMaterial);
	if (!Component || !BloodTemplate)
	{
		OutRejectReason = FString::Printf(TEXT("could not resolve blood material for %s slot %d"), *GetNameSafe(Component), MaterialSlot);
		return nullptr;
	}

	const int32 Resolution = ChooseRTResolution(Component);
	UTextureRenderTarget2D* RT = UKismetRenderingLibrary::CreateRenderTarget2D(this, Resolution, Resolution, RTF_RGBA8, FLinearColor::Black, false, false);
	if (!RT)
	{
		OutRejectReason = FString::Printf(TEXT("failed to create blood RT for %s slot %d"), *GetNameSafe(Component), MaterialSlot);
		return nullptr;
	}

	RT->ClearColor = FLinearColor::Black;
	UKismetRenderingLibrary::ClearRenderTarget2D(this, RT, FLinearColor::Black);

	UMaterialInstanceDynamic* MID = Component->CreateDynamicMaterialInstance(MaterialSlot, BloodTemplate);
	if (!MID)
	{
		OutRejectReason = FString::Printf(TEXT("failed to create blood MID for %s slot %d"), *GetNameSafe(Component), MaterialSlot);
		return nullptr;
	}

	MID->SetTextureParameterValue(BloodMaskTextureParameter, RT);
	MID->SetScalarParameterValue(BloodIntensityParameter, 1.0f);
	MID->SetScalarParameterValue(DebugShowMaskParameter, bDebugShowMaskOnPaintedMaterials ? 1.0f : 0.0f);

	FProphecyBloodPaintState NewState;
	NewState.Component = Component;
	NewState.MaterialSlot = MaterialSlot;
	NewState.BloodRT = RT;
	NewState.BloodMID = MID;
	NewState.RTResolution = Resolution;
	NewState.LastUsedTime = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0f;
	NewState.NumStamps = 0;
	NewState.bValid = true;

	OriginalMaterialsByKey.Add(StateKey, OriginalMaterial);
	FProphecyBloodPaintState& StoredState = PaintStatesByKey.Add(StateKey, NewState);
	ActivePaintStates = PaintStatesByKey.Num();

	if (bDebugMode || bDebugPrintHits)
	{
		DebugMessage(FString::Printf(TEXT("Created BloodRT %dx%d for %s slot=%d"), Resolution, Resolution, *GetNameSafe(Component), MaterialSlot), FColor::Green);
	}
	return &StoredState;
}

int32 AProphecyBloodTexturePaintManager::ChooseRTResolution(const UMeshComponent* Component) const
{
	if (!Component)
	{
		return DefaultRTResolutionMedium;
	}

	const float MaxExtent = Component->Bounds.BoxExtent.GetMax() * 2.0f;
	if (MaxExtent < SmallObjectExtentCm)
	{
		return DefaultRTResolutionSmall;
	}

	if (MaxExtent < MediumObjectExtentCm)
	{
		return DefaultRTResolutionMedium;
	}

	return DefaultRTResolutionLarge;
}

FVector2D AProphecyBloodTexturePaintManager::ComputeWorldBrushDrawSize(const UMeshComponent* Component, const FHitResult& Hit, float BrushRadiusWorld, int32 RTResolution, float BrushUVUnitsPerWorldUnit) const
{
	const float FallbackSize = FMath::Max(1.0f, DefaultBrushSizePixels);
	const float BrushDiameterWorld = BrushRadiusWorld * 2.0f;
	if (BrushUVUnitsPerWorldUnit > SMALL_NUMBER && BrushDiameterWorld > 0.0f && RTResolution > 0)
	{
		const float BrushDiameterPixels = FMath::Max(1.0f, BrushDiameterWorld * BrushUVUnitsPerWorldUnit * static_cast<float>(RTResolution));
		return ClampBrushDrawSizeForComponent(Component, FVector2D(BrushDiameterPixels, BrushDiameterPixels));
	}

	FBoxSphereBounds LocalBounds;
	if (!Component || !TryGetMeshLocalBounds(Component, LocalBounds) || BrushRadiusWorld <= 0.0f || RTResolution <= 0)
	{
		return ClampBrushDrawSizeForComponent(Component, FVector2D(FallbackSize, FallbackSize));
	}

	const FTransform ComponentTransform = Component->GetComponentTransform();
	const FVector LocalExtent(
		FMath::Max(LocalBounds.BoxExtent.X, 0.001f),
		FMath::Max(LocalBounds.BoxExtent.Y, 0.001f),
		FMath::Max(LocalBounds.BoxExtent.Z, 0.001f));
	const FVector Scale = ComponentTransform.GetScale3D();
	const FVector AbsScale(
		FMath::Max(FMath::Abs(Scale.X), 0.001f),
		FMath::Max(FMath::Abs(Scale.Y), 0.001f),
		FMath::Max(FMath::Abs(Scale.Z), 0.001f));

	FVector LocalNormal = ComponentTransform.InverseTransformVectorNoScale(Hit.ImpactNormal).GetSafeNormal();
	if (LocalNormal.IsNearlyZero())
	{
		LocalNormal = FVector::UpVector;
	}

	const FVector AbsNormal(FMath::Abs(LocalNormal.X), FMath::Abs(LocalNormal.Y), FMath::Abs(LocalNormal.Z));
	int32 UAxis = 0;
	int32 VAxis = 1;
	if (AbsNormal.X >= AbsNormal.Y && AbsNormal.X >= AbsNormal.Z)
	{
		UAxis = 1;
		VAxis = 2;
	}
	else if (AbsNormal.Y >= AbsNormal.X && AbsNormal.Y >= AbsNormal.Z)
	{
		UAxis = 0;
		VAxis = 2;
	}

	auto AxisWorldSpan = [&LocalExtent, &AbsScale](int32 Axis)
	{
		switch (Axis)
		{
		case 0:
			return LocalExtent.X * 2.0f * AbsScale.X;
		case 1:
			return LocalExtent.Y * 2.0f * AbsScale.Y;
		default:
			return LocalExtent.Z * 2.0f * AbsScale.Z;
		}
	};

	const float Resolution = static_cast<float>(RTResolution);
	return ClampBrushDrawSizeForComponent(Component, FVector2D(
		FMath::Max(1.0f, BrushDiameterWorld / FMath::Max(AxisWorldSpan(UAxis), 0.001f) * Resolution),
		FMath::Max(1.0f, BrushDiameterWorld / FMath::Max(AxisWorldSpan(VAxis), 0.001f) * Resolution)));
}

FVector2D AProphecyBloodTexturePaintManager::ClampBrushDrawSizeForComponent(const UMeshComponent* Component, FVector2D DrawSize) const
{
	DrawSize.X = FMath::Max(1.0f, DrawSize.X);
	DrawSize.Y = FMath::Max(1.0f, DrawSize.Y);

	if (Cast<USkinnedMeshComponent>(Component) && MaxSkinnedMeshBrushDiameterPixels > 0.0f)
	{
		const float MaxAxis = FMath::Max(DrawSize.X, DrawSize.Y);
		if (MaxAxis > MaxSkinnedMeshBrushDiameterPixels)
		{
			DrawSize *= MaxSkinnedMeshBrushDiameterPixels / MaxAxis;
		}
	}

	return DrawSize;
}

void AProphecyBloodTexturePaintManager::QueueStamp(const FString& StateKey, const FProphecyBloodPaintStamp& Stamp)
{
	TArray<FProphecyBloodPaintStamp>& Stamps = PendingStampsByStateKey.FindOrAdd(StateKey);
	Stamps.Add(Stamp);
	QueuedStampCount += 1;
}

void AProphecyBloodTexturePaintManager::LogReject(const FString& Reason)
{
	UnsupportedHitCount += 1;
	if (bDebugMode || bDebugLogRejectedHits)
	{
		UE_LOG(LogProphecyBloodTexturePaint, Warning, TEXT("Blood paint rejected: %s"), *Reason);
	}

	if (bDebugPrintHits)
	{
		DebugMessage(FString::Printf(TEXT("BloodPaint rejected: %s"), *Reason), FColor::Yellow);
	}
}

void AProphecyBloodTexturePaintManager::DebugMessage(const FString& Message, FColor Color) const
{
	UE_LOG(LogProphecyBloodTexturePaint, Log, TEXT("%s"), *Message);

	if (GEngine && GetWorld())
	{
		GEngine->AddOnScreenDebugMessage(-1, 3.0f, Color, Message);
	}
}
