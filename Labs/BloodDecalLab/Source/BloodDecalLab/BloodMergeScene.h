#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "RectangleMesher.h"
#include "BloodMergeScene.generated.h"

class UDecalComponent;
class UMaterialInterface;

struct FBloodLabRegion
{
    BloodRect::Mask Mask{};
    TArray<UDecalComponent*> Decals;
    bool Dirty=false;
};

UCLASS()
class BLOODDECALLAB_API ABloodMergeScene : public AActor
{
    GENERATED_BODY()
public:
    ABloodMergeScene();
    virtual void Tick(float DeltaSeconds) override;
    virtual void BeginPlay() override;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) TObjectPtr<UMaterialInterface> DecalMaterial;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float CellSize=12.5f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Depth=40.f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float Padding=1.0f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 MaxRegions=64;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 MaxDecals=4096;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 MaxRegionsPerUpdate=2;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) int32 MaxNewDecalsPerUpdate=16;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) float UpdateBudgetMs=0.25f;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool ShowBounds=false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool Spray=false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) bool LegacyComparison=false;
    UPROPERTY(EditAnywhere, BlueprintReadWrite) FName Pattern="filled";
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) int32 ActiveDecals=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) int32 Rebuilds=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) int32 CreatedComponents=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) int32 RejectedCells=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) int32 OccupiedCells=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) float LastUpdateMs=0;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly) bool CapacityBlocked=false;
    UFUNCTION(BlueprintCallable) bool AddCell(int32 X,int32 Y);
    UFUNCTION(BlueprintCallable) int32 AddStain(FVector WorldPosition,float Radius=5.f);
    UFUNCTION(BlueprintCallable) void ProcessChanges();
    UFUNCTION(BlueprintPure) bool HasPendingChanges() const { return DirtyHead<Dirty.Num() && !CapacityBlocked; }
    UFUNCTION(BlueprintCallable) void Clear();
    UFUNCTION(BlueprintCallable) void Populate(FName Shape);
    UFUNCTION(BlueprintCallable) FString Validate();
    UFUNCTION(BlueprintCallable) FString Benchmark();
private:
    TMap<FIntPoint,FBloodLabRegion> Regions;
    TArray<FIntPoint> Dirty;
    int32 DirtyHead=0;
    TArray<FIntVector> OldTiles;
    UPROPERTY(Transient) TArray<TObjectPtr<UDecalComponent>> OwnedDecals;
    TArray<UDecalComponent*> SpareDecals;
    std::vector<BloodRect::Rect> Scratch;
    FRandomStream Random{7291};
    float SprayAngle=0;
    float SprayClock=0;
    int32 CapacityLimitAtBlock=0;
    bool Rebuild(const FIntPoint& Key,FBloodLabRegion& Region,double Deadline,int32& NewThisUpdate);
    UDecalComponent* Acquire();
    UDecalComponent* CreateDecal();
    void Place(UDecalComponent* D,float X,float Y,float W,float H,bool LegacySize=false);
    void DrawBounds();
    void LegacyPopulate(FName Shape);
};
