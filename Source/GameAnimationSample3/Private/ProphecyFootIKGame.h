#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
class AProphecyNNLocomotionManager;

// Final terrain targets, separate from policy state and ordinary interpolation.
namespace ProphecyFootIKGame
{
void Update(AProphecyNNLocomotionManager& Manager,AProphecyAgent* Agent,int32 PoseId,uint64 GameTick);
void Remove(AProphecyAgent* Agent);
void ConfigurationChanged(AProphecyAgent* Agent);
void Suspend(AProphecyAgent* Agent);
// Retire the terrain carrier before a higher-priority action publishes roots.
void BeforeActions(AProphecyNNLocomotionManager& Manager,AProphecyAgent* Agent);
bool RefreshSurface(AProphecyAgent* Agent,const FVector& DesiredVelocity,FString& Error);
FString Error(const AProphecyAgent* Agent);
bool Preparing(const AProphecyAgent* Agent);
bool Returning(const AProphecyAgent* Agent);
int32 TerrainExits(const AProphecyAgent* Agent);
// Preserve the accepted full pose across the first post-exit publication.
void RestoreExitPredecessor(AProphecyAgent* Agent,double SourceTime,
    TConstArrayView<FName> Names,TArrayView<FTransform> Previous,const FTransform& Carrier);
// Safe on the animation worker. Identity carrier means World contains world poses.
void Apply(int32 PoseId,TConstArrayView<FName> Names,TArrayView<FTransform> World,
    const FTransform& Carrier=FTransform::Identity);
}
