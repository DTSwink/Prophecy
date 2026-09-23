#pragma once
#include "CoreMinimal.h"
class AProphecyAgent;
namespace ProphecyKickFootLeeway
{
void Begin(AProphecyAgent* Agent,FName Attack);
void End(AProphecyAgent* Agent);
void Cancel(AProphecyAgent* Agent);
void Remove(AProphecyAgent* Agent);
bool Reapply(AProphecyAgent* Agent,FString& Error);
float Current(const AProphecyAgent* Agent);
}
