#pragma once
#include "CoreMinimal.h"
class AProphecyNNLocomotionManager;
class FProphecyDefenseNetwork;

// Shared selection; binding occurs only at lazy defense initialization. The
// existing runtime retains its model object and unchanged per-tick batch path.
namespace ProphecyDefenseCheckpoint
{
bool Set(AProphecyNNLocomotionManager* Manager,bool Dodge,int32 Index,FString& Error);
int32 Get(const AProphecyNNLocomotionManager* Manager,bool Dodge);
bool Initialize(AProphecyNNLocomotionManager* Manager,bool Dodge,FProphecyDefenseNetwork& Network,FString& Error);
void Remove(const AProphecyNNLocomotionManager* Manager);
}
