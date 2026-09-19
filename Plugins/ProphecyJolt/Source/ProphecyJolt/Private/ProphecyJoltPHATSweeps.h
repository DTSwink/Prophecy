#pragma once
#include "CoreMinimal.h"
class AActor;
class UWorld;
namespace JPH { class PhysicsSystem; class Body; class ObjectLayerPairFilter; class ContactImpulseListener; }

namespace ProphecyJolt::PHATSweeps
{
struct FSettings { float Strength = 1.f; int32 MaxIterations = 64; };
struct FBody { uint32 ID; FSettings Settings; };
bool HasRequests(const UWorld* World);
const FSettings* Find(const AActor* Agent);
void ForgetWorld(const UWorld* World);
void Publish(JPH::PhysicsSystem* Physics, const JPH::ObjectLayerPairFilter* Filter,
    TArray<FBody>&& Selected, TArray<uint32>&& Candidates, JPH::ContactImpulseListener* Listener);
void Forget(JPH::PhysicsSystem* Physics);
void AfterServo(JPH::PhysicsSystem* Physics, float Seconds);
// Native-only helper also exercised by a small isolated automation test.
bool Respond(JPH::PhysicsSystem& Physics, JPH::Body& A, JPH::Body& B, float Seconds, const FSettings& Settings,
    JPH::ContactImpulseListener* Listener = nullptr);
}
