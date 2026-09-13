#pragma once

#include "CoreMinimal.h"

class FJsonObject;
class USkeletalMeshComponent;
struct FProphecyJoltRigSnapshot;

namespace ProphecySterileBench::MultiJolt
{
// Benchmark only, after EndPhysics and outside world-tick timing. PreviousAgent is the preceding
// measured frame's immutable JSON row; null is allowed only for the first measured frame.
bool ValidatePostPhysicsQueries(USkeletalMeshComponent& Mesh, const FProphecyJoltRigSnapshot& SourceRig,
    const FJsonObject* PreviousAgent, FJsonObject& AgentRow, FString& OutError);
}
