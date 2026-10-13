#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyReach
{
bool Active(const AProphecyAgent* Agent);
void Update(AProphecyAgent* Agent,int32 PoseId);
void Apply(int32 PoseId,TConstArrayView<FName> Names,TArrayView<FTransform> Pose,const FTransform& Space=FTransform::Identity);
void Fingers(const AProphecyAgent* Agent,TFunctionRef<void(FName,const FTransform&)> Visit);
void Remove(const AProphecyAgent* Agent);
}
