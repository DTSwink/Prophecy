#include "ProphecyJoltBlueprintLibrary.h"

#include "ProphecyJoltWorldSubsystem.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "PhysicsEngine/PhysicsSettings.h"

bool UProphecyJoltBlueprintLibrary::InitializeJoltWorld(const UObject* WorldContextObject,
    FString& OutError, int32 BodyCapacity, int32 WorkerThreads)
{
    OutError.Reset();
    if (!IsInGameThread()) { OutError = TEXT("Jolt world initialization requires the game thread."); return false; }
    UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull) : nullptr;
    auto* Owner = World && World->IsGameWorld() ? World->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr;
    if (!Owner || !World->GetPhysicsScene())
    { OutError = TEXT("Jolt requires a Game/PIE world with an initialized physics scene."); return false; }
    if (UPhysicsSettings::Get()->bTickPhysicsAsync)
    { OutError = TEXT("The current Jolt query bridge requires synchronous Unreal physics."); return false; }
    if (BodyCapacity < 1 || BodyCapacity > 131072 || WorkerThreads < 0 || WorkerThreads > 32)
    { OutError = TEXT("Jolt body capacity must be 1..131072 and worker count 0..32."); return false; }
    FProphecyJoltWorldSettings Settings;
    Settings.GravityCmPerSecondSquared = FVector(0.0, 0.0, World->GetGravityZ());
    Settings.MaxBodies = uint32(BodyCapacity);
    Settings.MaxBodyPairs = FMath::Max(uint32(1024), uint32(BodyCapacity) * 8);
    Settings.MaxContactConstraints = FMath::Max(uint32(1024), uint32(BodyCapacity) * 16);
    // Pinned Jolt reserves its full contact workspace on the first active step:
    // 480 bytes/contact plus index/island buffers, even when few contacts exist.
    // Keep a conservative 1 KiB/contact budget for this rigid-body startup path
    // instead of reducing contact capacity or allocating a fallback during a step.
    const uint64 ScratchBytes = FMath::Max(uint64(32) * 1024 * 1024,
        uint64(Settings.MaxContactConstraints) * 1024);
    if (ScratchBytes > MAX_uint32)
    { OutError = TEXT("Selected collision capacity exceeds the fixed scratch allocator's addressable size."); return false; }
    Settings.TempAllocatorBytes = uint32(ScratchBytes);
    Settings.WorkerThreads = WorkerThreads;
    const auto Result = Owner->InitializeSimulation(Settings);
    OutError = Result.Message;
    return Result.IsSuccess();
}

bool UProphecyJoltBlueprintLibrary::IsJoltWorldReady(const UObject* WorldContextObject)
{
    if (!IsInGameThread()) return false;
    UWorld* World = GEngine ? GEngine->GetWorldFromContextObject(WorldContextObject, EGetWorldErrorMode::ReturnNull) : nullptr;
    auto* Owner = World && World->IsGameWorld() ? World->GetSubsystem<UProphecyJoltWorldSubsystem>() : nullptr;
    FProphecyJoltWorldDiagnostics Diagnostics;
    return Owner && Owner->GetDiagnostics(Diagnostics).IsSuccess() && Diagnostics.bInitialized && !Diagnostics.bFaulted;
}
