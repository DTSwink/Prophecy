#pragma once
#include "CoreMinimal.h"

class USkeletalMeshComponent;

// Shared by the gallows rope helpers (ProphecyPhysicsConstraintBlueprintLibrary.cpp) and the noose.
namespace ProphecyPotenceRope
{
// World reel geometry: the fixed wood anchor, the direction the rope is reeled in and its full length.
bool GetReelGeometry(const USkeletalMeshComponent* Rope, FTransform& AnchorWorld, FVector& RetractionDirectionWorld, float& LengthWorld);
// Last reel amount applied to this rope (0 = fully paid out, 1 = fully reeled in).
float GetAmount(const USkeletalMeshComponent* Rope);
}
