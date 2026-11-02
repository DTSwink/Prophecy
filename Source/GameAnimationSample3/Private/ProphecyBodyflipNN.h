#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyBodyflip
{
// Prepare retained model data/runtime on GT before invoking a worker. Heavy CPU
// model/session initialization is lazy in GenerateNN on that worker.
bool PrepareNN(const FString& Gait,bool bDrawn,FString& Error);
// Lab resume-service contract. Input includes two world/component-frame seed
// poses and the root command window; output is a fresh private CPU ORT rollout.
// Cancellation is polled between native stages/steps; an in-flight ORT call
// finishes before it can observe the request.
bool GenerateNN(AProphecyAgent* Agent,const FString& RequestJson,FString& ResponseJson,FString& Error,TFunction<bool()> IsCancelled={});
}
