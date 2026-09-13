#pragma once

#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "ProphecyJoltShapeAsset.generated.h"

/** Stable fixture identity, separate from Jolt's archive-local subshape bits. */
USTRUCT()
struct PROPHECYJOLT_API FProphecyJoltShapeChild
{
	GENERATED_BODY()

	UPROPERTY(VisibleAnywhere, Category = "Jolt")
	uint32 ChildId = 0;

	UPROPERTY(VisibleAnywhere, Category = "Jolt")
	FString MaterialId;

	UPROPERTY(VisibleAnywhere, Category = "Jolt")
	uint32 ArchiveSubShapeId = 0;

	UPROPERTY(VisibleAnywhere, Category = "Jolt")
	FVector LocalPositionCm = FVector::ZeroVector;

	UPROPERTY(VisibleAnywhere, Category = "Jolt")
	FQuat LocalRotation = FQuat::Identity;

	UPROPERTY(VisibleAnywhere, Category = "Jolt")
	FVector BoxHalfExtentCm = FVector::ZeroVector;
};

/** Phase 1 compound archive fixture. This is not a general Physics Asset cook. */
UCLASS()
class PROPHECYJOLT_API UProphecyJoltShapeAsset : public UDataAsset
{
	GENERATED_BODY()

public:
	UPROPERTY(VisibleAnywhere, Category = "Jolt|Provenance")
	int32 SchemaVersion = 0;

	UPROPERTY(VisibleAnywhere, Category = "Jolt|Provenance")
	FString JoltSourceRevision;

	UPROPERTY(VisibleAnywhere, Category = "Jolt|Provenance")
	FString ArchivePlatform;

	UPROPERTY(VisibleAnywhere, Category = "Jolt|Provenance")
	int32 WorldPositionBits = 0;

	UPROPERTY(VisibleAnywhere, Category = "Jolt|Provenance")
	FString ByteOrder;

	UPROPERTY(VisibleAnywhere, Category = "Jolt|Provenance")
	FString SourceDescriptor;

	UPROPERTY(VisibleAnywhere, Category = "Jolt|Provenance")
	FString SourceSha1;

	UPROPERTY(VisibleAnywhere, Category = "Jolt|Archive")
	int32 ArchiveByteCount = 0;

	/** Integrity digest for locally generated cooked data, not authentication. */
	UPROPERTY(VisibleAnywhere, Category = "Jolt|Archive")
	FString ArchiveSha1;

	/** Complete Shape::SaveWithChildren stream, including child shapes/materials. */
	UPROPERTY()
	TArray<uint8> ArchiveBytes;

	UPROPERTY(VisibleAnywhere, Category = "Jolt|Fixture")
	TArray<FProphecyJoltShapeChild> Children;

	/** All three vectors are in the original shape frame, in centimeters. */
	UPROPERTY(VisibleAnywhere, Category = "Jolt|Fixture")
	FVector ExpectedCenterOfMassCm = FVector::ZeroVector;

	UPROPERTY(VisibleAnywhere, Category = "Jolt|Fixture")
	FVector ExpectedBoundsMinCm = FVector::ZeroVector;

	UPROPERTY(VisibleAnywhere, Category = "Jolt|Fixture")
	FVector ExpectedBoundsMaxCm = FVector::ZeroVector;

#if WITH_EDITOR
	/** Builds in memory only. The caller owns any package creation/save. */
	bool BuildCompoundFixture(FString& OutError);
#endif

	/** Restores and checks the complete archive; also compiled in Shipping. */
	bool ValidateCompoundFixture(FString& OutError) const;
};
