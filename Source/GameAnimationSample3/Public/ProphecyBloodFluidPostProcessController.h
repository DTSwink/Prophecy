#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ProphecyBloodFluidPostProcessController.generated.h"

class UMaterialInstanceDynamic;
class UMaterialInterface;
class UNiagaraSystem;
class UPostProcessComponent;

UCLASS(Blueprintable)
class GAMEANIMATIONSAMPLE3_API AProphecyBloodFluidPostProcessController : public AActor
{
	GENERATED_BODY()

public:
	AProphecyBloodFluidPostProcessController();

	virtual void OnConstruction(const FTransform& Transform) override;
	virtual void PostRegisterAllComponents() override;
	virtual void BeginPlay() override;
	virtual void Tick(float DeltaSeconds) override;

#if WITH_EDITOR
	virtual bool ShouldTickIfViewportsOnly() const override;
	virtual void PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent) override;
#endif

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Blood Fluid PP")
	void ApplyBloodFluidPostProcessSettings();

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Blood Fluid PP")
	void SetBloodFluidPostEnabled(bool bEnabled);

	UFUNCTION(BlueprintCallable, Category = "Prophecy|Blood Fluid PP")
	void SetBloodFluidStencilDebug(bool bEnabled);

	UFUNCTION(CallInEditor, BlueprintCallable, Category = "Prophecy|Blood Fluid PP")
	void TagBloodNiagaraComponentsForStencil();

	UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Prophecy|Blood Fluid PP")
	TObjectPtr<UPostProcessComponent> PostProcessComponent = nullptr;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Fluid PP")
	bool bBloodFluidPostEnabled = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Fluid PP")
	bool bShowStencilDebug = false;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Fluid PP")
	bool bUpdateParametersEveryTick = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Fluid PP|Editor Preview")
	bool bAutoTagBloodNiagaraInEditor = true;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Fluid PP|Editor Preview")
	TSoftObjectPtr<UNiagaraSystem> BloodNiagaraSystem;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Fluid PP|Editor Preview", meta = (ClampMin = "0", ClampMax = "255"))
	int32 BloodStencilValue = 42;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Fluid PP", meta = (ClampMin = "0.0", ClampMax = "32.0"))
	float BlurRadius = 4.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Fluid PP", meta = (ClampMin = "0.0", ClampMax = "1.0"))
	float Threshold = 0.32f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Fluid PP", meta = (ClampMin = "0.001", ClampMax = "0.5"))
	float Softness = 0.08f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Fluid PP", meta = (ClampMin = "0.0", ClampMax = "4.0", UIMin = "0.0", UIMax = "4.0", DisplayName = "Blur Sample Quality"))
	float BlurSampleQuality = 1.0f;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Fluid PP|Materials")
	TSoftObjectPtr<UMaterialInterface> SceneCopyMaterial;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Fluid PP|Materials")
	TSoftObjectPtr<UMaterialInterface> ExtractMaterial;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Fluid PP|Materials")
	TSoftObjectPtr<UMaterialInterface> BlurHMaterial;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Fluid PP|Materials")
	TSoftObjectPtr<UMaterialInterface> BlurVMaterial;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Fluid PP|Materials")
	TSoftObjectPtr<UMaterialInterface> CompositeMaterial;

	UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Prophecy|Blood Fluid PP|Materials")
	TSoftObjectPtr<UMaterialInterface> StencilDebugMaterial;

private:
	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> SceneCopyMID = nullptr;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> ExtractMID = nullptr;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> BlurHMID = nullptr;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> BlurVMID = nullptr;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> CompositeMID = nullptr;

	UPROPERTY(Transient)
	TObjectPtr<UMaterialInstanceDynamic> StencilDebugMID = nullptr;

	UMaterialInstanceDynamic* GetOrCreateMID(TObjectPtr<UMaterialInstanceDynamic>& Slot, const TSoftObjectPtr<UMaterialInterface>& MaterialAsset, const FName DebugName);
	void AddBlendable(UObject* BlendableObject, float Weight = 1.0f);
	void RebuildBlendables();
	void PushScalarAndVectorParameters();
	void AutoTagBloodNiagaraComponentsForEditor();
};
