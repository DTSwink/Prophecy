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
    UFUNCTION(BlueprintCallable, Category="Prophecy|Reach")
    static void SetReachVisualization(AProphecyAgent* Agent, bool Enabled=true);
};
