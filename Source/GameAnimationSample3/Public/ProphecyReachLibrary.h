#pragma once
#include "CoreMinimal.h"
#include "Kismet/BlueprintFunctionLibrary.h"
#include "ProphecyDoubleReachTypes.h"
#include "ProphecyReachLibrary.generated.h"

class AProphecyAgent;
class UPrimitiveComponent;
class USkeletalMeshComponent;

UENUM(BlueprintType)
enum class EProphecyReachHand : uint8 { Left, Right };

USTRUCT(BlueprintType)
struct FProphecyGrabStatus
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) bool Active=false;
    UPROPERTY(BlueprintReadOnly) bool Gripped=false;
    UPROPERTY(BlueprintReadOnly) bool PhysicalGrip=false;
    UPROPERTY(BlueprintReadOnly) FVector SurfacePoint=FVector::ZeroVector;
    UPROPERTY(BlueprintReadOnly) float DistanceCm=0;
    UPROPERTY(BlueprintReadOnly) int32 ContactFingers=0;
};

UCLASS()
class GAMEANIMATIONSAMPLE3_API UProphecyReachLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()
public:
    /** Persistent world target. Calling for the other hand enables both; repeated updates do not restart reaching. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Reach", meta=(DisplayName="Reach Target", AdvancedDisplay="MaxRotationSpeed"))
    static bool ReachTarget(AProphecyAgent* Agent, EProphecyReachHand Hand, FTransform Target,
        float MaxReachSpeed=300, float MaxRotationSpeed=360);
    /** Both hands share the original double-reach body solve. Off releases both. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Reach", meta=(AdvancedDisplay="MaxRotationSpeed"))
    static bool DoubleReach(AProphecyAgent* Agent, EProphecyDoubleReachMode Mode,
        FTransform LeftTarget, FTransform RightTarget, float MaxReachSpeed=300, float MaxRotationSpeed=360);
    /** Uses simple collision. Optional point is world space on the collider surface; stored component-local internally. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Grab", meta=(DisplayName="Grab Object", AdvancedDisplay="UseSurfacePoint,SurfacePoint,MaxRotationSpeed"))
    static bool GrabObject(AProphecyAgent* Agent, EProphecyReachHand Hand, UPrimitiveComponent* Object,
        float MaxReachSpeed=300, bool UseSurfacePoint=false, FVector SurfacePoint=FVector::ZeroVector, float MaxRotationSpeed=360);
    /** World-space collider surface point is stored bone-local and follows that bone. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Grab", meta=(DisplayName="Grab Bone", AdvancedDisplay="MaxRotationSpeed"))
    static bool GrabBone(AProphecyAgent* Agent, EProphecyReachHand Hand, USkeletalMeshComponent* Mesh,
        FName BoneName, FVector SurfacePoint, float MaxReachSpeed=300, float MaxRotationSpeed=360);
    UFUNCTION(BlueprintCallable, Category="Prophecy|Grab", meta=(AdvancedDisplay="ReturnSeconds"))
    static void ReleaseGrab(AProphecyAgent* Agent, EProphecyReachHand Hand, float ReturnSeconds=.25f);
    UFUNCTION(BlueprintCallable, Category="Prophecy|Reach", meta=(AdvancedDisplay="ReturnSeconds"))
    static void StopReaching(AProphecyAgent* Agent, float ReturnSeconds=.25f);
    UFUNCTION(BlueprintPure, Category="Prophecy|Grab")
    static FProphecyGrabStatus GetGrabStatus(AProphecyAgent* Agent, EProphecyReachHand Hand);
    /** Maximum orientation error in degrees for finger closure and grip acquisition (commanded and actual wrist).
     * Applies to both hands immediately and persists across grabs for this agent's world lifetime.
     * Call in BeginPlay or before Grab Object / Grab Bone. Finite values from 0 to 180 are accepted; invalid input changes nothing.
     * Does not change PHAT limits, distance tolerances or release an existing grip. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Grab", meta=(ClampMin="0.0", ClampMax="180.0"))
    static bool SetGrabAngleTolerances(AProphecyAgent* Agent, float ClosureAngleDegrees=8, float GripAngleDegrees=6);
    UFUNCTION(BlueprintPure, Category="Prophecy|Grab")
    static void GetGrabAngleTolerances(AProphecyAgent* Agent, float& ClosureAngleDegrees, float& GripAngleDegrees);
    /** Shared lab motion controls, each 0..1. Sync 0 preserves the angular speed cap;
     * 1 slows rotation to the estimated reach arrival. Elbow 0 uses the original
     * outward preference, 1 the lower-elbow preference. PHAT remains authoritative.
     * Applies immediately to both hands and persists across requests in this world. */
    UFUNCTION(BlueprintCallable, Category="Prophecy|Reach", meta=(ClampMin="0.0", ClampMax="1.0"))
    static bool SetReachMotionTuning(AProphecyAgent* Agent, float SyncRotation=0, float ElbowDownBlend=1);
    UFUNCTION(BlueprintPure, Category="Prophecy|Reach")
    static void GetReachMotionTuning(AProphecyAgent* Agent, float& SyncRotation, float& ElbowDownBlend);
    UFUNCTION(BlueprintCallable, Category="Prophecy|Reach")
    static void SetReachVisualization(AProphecyAgent* Agent, bool Enabled=true);
};
