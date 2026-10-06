#pragma once
#include "CoreMinimal.h"
class AActor;
class UWorld;
class UPrimitiveComponent;
namespace JPH { class PhysicsSystem; class Body; class ObjectLayerPairFilter; class ContactImpulseListener; }

namespace ProphecyJolt::PHATSweeps
{
struct FSettings { float Strength = 1.f; int32 MaxIterations = 64; };
// Welded carrier=1, attached sword=2. A normal body uses either nonzero mask.
struct FBody { uint32 ID; FSettings Settings; uint8 Parts = 3; };
bool HasRequests(const UWorld* World);
const FSettings* Find(const AActor* Agent);
const FSettings* FindBody(const UPrimitiveComponent* Component, FName Bone);
void ForgetWorld(const UWorld* World);
void Publish(JPH::PhysicsSystem* Physics, const JPH::ObjectLayerPairFilter* Filter,
    TArray<FBody>&& Selected, TArray<uint32>&& Candidates);
void Forget(JPH::PhysicsSystem* Physics);
void AfterServo(JPH::PhysicsSystem* Physics, float Seconds);
// Native-only helper also exercised by a small isolated automation test.
bool Respond(JPH::PhysicsSystem& Physics, JPH::Body& A, JPH::Body& B, float Seconds, const FSettings& Settings,
    uint8 PartsA = 3, uint8 PartsB = 0);
}
