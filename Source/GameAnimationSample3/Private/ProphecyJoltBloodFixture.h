#pragma once

#include "CoreMinimal.h"

class FJsonObject;
class UWorld;
class USkeletalMeshComponent;
struct FHitResult;

namespace ProphecyJolt::BloodFixture
{
// Synchronous, game-thread diagnostic. The supplied hit must already resolve to the live PhysicalMesh
// and a real bone. Verifies native paint acceptance and RGBA8 mask pixels, then restores materials.
// Requires a real RHI; completes shader preparation without saving or changing source assets.
// An existing static-only fallback may be copied transiently for skeletal use and is reported explicitly.
// Success does not claim rasterized character appearance, motion attachment or production materials.
bool ValidateCharacterHit(UWorld& World, USkeletalMeshComponent& PhysicalMesh, const FHitResult& Hit,
    TSharedPtr<FJsonObject>& OutReport, FString& OutError);

// Independent retained UE-query check. Spawns a transient engine cube at the caller's clear placement,
// performs a complex world trace/FindCollisionUV, verifies its mask, and destroys the fixture actor.
bool ValidateStaticCube(UWorld& World, const FTransform& CubeToWorld,
    TSharedPtr<FJsonObject>& OutReport, FString& OutError);
}
