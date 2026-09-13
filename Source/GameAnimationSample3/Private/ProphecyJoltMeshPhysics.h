#pragma once

#include "CoreMinimal.h"
#include "ProphecyJoltPhysicsCommand.h"
#include "Engine/EngineTypes.h"

class UPrimitiveComponent;
namespace ProphecyJolt::MeshPhysics
{
enum class ESelection : uint8 { Bone, All, Below, Radial };
struct FSelection
{
    ESelection Type = ESelection::Bone;
    FName Bone = NAME_None;
    bool bIncludeSelf = true;
    FVector Origin = FVector::ZeroVector;
    float Radius = 0;
    float Strength = 0;
    ERadialImpulseFalloff Falloff = RIF_Constant;
};
// True means Jolt owns this receiver, even if the request is invalid/faulted.
// False means the caller must execute its normal Chaos Super implementation.
bool Execute(UPrimitiveComponent& Component, const FProphecyJoltPhysicsCommand& Command, const FSelection& Selection);
}
