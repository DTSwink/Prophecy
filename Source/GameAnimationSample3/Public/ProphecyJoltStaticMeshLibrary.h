#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyJoltStaticMeshLibrary.generated.h"
class UStaticMeshComponent;

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyJoltStaticMeshLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Transfer an existing independent simulated mesh to the initialized shared Jolt world.
     * Call AFTER Set Static Mesh, Simulate Physics, mass, transform, velocity and CCD setup.
     * Keeps the same component, owner, materials and UE query receiver. Supports components added
     * to a pawn, without making them its root. True means admitted or safely queued.
     * Subsequent standard force/velocity nodes require a ProphecyPhysicsStaticMeshComponent;
     * a stock StaticMeshComponent's native methods remain Chaos-only after this one-time handoff. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Jolt")
    static bool EnableJoltStaticMeshPhysics(UStaticMeshComponent* Mesh, FString& OutError);

    /** Retire this library's adapter, leaving the original component with simulation off.
     * Configure/re-enable Chaos normally afterward if desired. Safe to call before Destroy Component. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Jolt")
    static void DisableJoltStaticMeshPhysics(UStaticMeshComponent* Mesh);

    UFUNCTION(BlueprintPure, Category="Prophecy|Jolt")
    static bool IsJoltStaticMeshPhysicsEnabled(UStaticMeshComponent* Mesh);
};
