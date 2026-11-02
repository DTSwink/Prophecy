#pragma once
#include "CoreMinimal.h"
#include "ProceduralMeshComponent.h"
#include "ProphecyOilLiquid.generated.h"

/** Small cosmetic, volume-preserving free surface. No fluid grid, collision or queries. */
UCLASS(ClassGroup=(Oil),meta=(BlueprintSpawnableComponent))
class UProphecyOilLiquid : public UProceduralMeshComponent
{
    GENERATED_BODY()
public:
    UProphecyOilLiquid(const FObjectInitializer& ObjectInitializer);
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil Inside",meta=(ClampMin="0",ClampMax="1")) float FillAmount=.65f;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil Inside",meta=(ClampMin="0",ClampMax="2")) float SloshStrength=1;
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil Inside",meta=(ClampMin=".1",ClampMax="2")) float SloshDamping=.4f;
    /** None reuses the bottle's airborne oil material, including its color/gloss. */
    UPROPERTY(EditAnywhere,BlueprintReadWrite,Category="Oil Inside") TObjectPtr<UMaterialInterface> LiquidMaterial;
    UPROPERTY(VisibleInstanceOnly,BlueprintReadOnly,Category="Oil Inside|Diagnostics") FVector SurfaceNormal=FVector::UpVector;
    UPROPERTY(VisibleInstanceOnly,BlueprintReadOnly,Category="Oil Inside|Diagnostics") int32 MeshUpdates=0;
    UPROPERTY(VisibleInstanceOnly,BlueprintReadOnly,Category="Oil Inside|Diagnostics") float LastUpdateMicroseconds=0;
    UPROPERTY(VisibleInstanceOnly,BlueprintReadOnly,Category="Oil Inside|Diagnostics") float VolumeError=0;
    UFUNCTION(BlueprintCallable,Category="Oil Inside") void RefreshLiquid();
    virtual void OnRegister() override;
    virtual void BeginPlay() override;
    virtual void OnUpdateTransform(EUpdateTransformFlags UpdateTransformFlags,ETeleportType Teleport) override;
    virtual void TickComponent(float DeltaTime,ELevelTick TickType,FActorComponentTickFunction* ThisTickFunction) override;
private:
    void BuildCavity();
    void UpdateSurface();
    TArray<FVector> Cavity,Vertices,Normals;
    TArray<int32> Faces,Triangles;
    TArray<FVector2D> UV;
    TArray<FLinearColor> Colors;
    TArray<FProcMeshTangent> Tangents;
    FVector Spring=FVector::UpVector,SpringVelocity=FVector::ZeroVector;
    FVector PreviousPosition=FVector::ZeroVector,PreviousVelocity=FVector::ZeroVector,DrawnNormal=FVector::ZeroVector;
    FTransform SampleTransform;
    double FullVolume=0;
    double UprightHeight=0,InvertedHeight=0;
    float HeightFill=-1;
    float DrawnFill=-1;
    int32 StillFrames=0;
    bool bReady=false,bSampled=false;
};
