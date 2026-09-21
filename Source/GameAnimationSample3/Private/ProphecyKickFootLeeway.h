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
// Actual outgoing extension, fading on the same clock as the joint allowance.
// Zero outside a return. Side 0 is left; side 1 is right. Centimetres.
float ReturningExtension(const AProphecyAgent* Agent,int32 Side);
inline FVector Target(const FVector& Original,const FVector& Clamped,const FVector& End,const FVector& Axis,float Leeway)
{
    // Extension only: do not grant compression or sideways translation.
    const double Extension=FMath::Clamp(FVector::DotProduct(Original-End,Axis),0.,double(Leeway));
    if (Extension==0) return Clamped; // Preserve any separately configured general target leeway.
    const double Existing=FVector::DotProduct(Clamped-End,Axis);
    return Clamped+Axis*FMath::Max(0.,Extension-Existing);
}
}
