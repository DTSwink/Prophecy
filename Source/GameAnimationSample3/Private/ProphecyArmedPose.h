#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyArmedPose
{
bool Active(const AProphecyAgent* Agent);
void Cancel(const AProphecyAgent* Agent);
bool Apply(const AProphecyAgent* Agent,TArrayView<FTransform> Previous,TArrayView<FTransform> Current,bool Advance);
}
