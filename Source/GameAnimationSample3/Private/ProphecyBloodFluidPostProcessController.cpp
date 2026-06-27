#include "ProphecyBloodFluidPostProcessController.h"

#include "Components/PostProcessComponent.h"
#include "Engine/Scene.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/MaterialInterface.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"
#include "UObject/UObjectIterator.h"

AProphecyBloodFluidPostProcessController::AProphecyBloodFluidPostProcessController()
{
	PrimaryActorTick.bCanEverTick = true;
	PrimaryActorTick.bStartWithTickEnabled = true;

	PostProcessComponent = CreateDefaultSubobject<UPostProcessComponent>(TEXT("BloodFluidPostProcess"));
	SetRootComponent(PostProcessComponent);
	PostProcessComponent->bUnbound = true;
	PostProcessComponent->bEnabled = true;
	PostProcessComponent->BlendWeight = 1.0f;
	PostProcessComponent->Priority = 1000.0f;

	SceneCopyMaterial = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Game/_mygame/blood2/PP_Fluid/M_PP_Blood_SceneCopy.M_PP_Blood_SceneCopy")));
	ExtractMaterial = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Game/_mygame/blood2/PP_Fluid/M_PP_Blood_Extract.M_PP_Blood_Extract")));
	BlurHMaterial = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Game/_mygame/blood2/PP_Fluid/M_PP_Blood_BlurH.M_PP_Blood_BlurH")));
	BlurVMaterial = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Game/_mygame/blood2/PP_Fluid/M_PP_Blood_BlurV.M_PP_Blood_BlurV")));
	CompositeMaterial = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Game/_mygame/blood2/PP_Fluid/M_PP_Blood_Composite.M_PP_Blood_Composite")));
	StencilDebugMaterial = TSoftObjectPtr<UMaterialInterface>(FSoftObjectPath(TEXT("/Game/_mygame/blood2/PP_Fluid/M_PP_Blood_StencilDebug42.M_PP_Blood_StencilDebug42")));
	BloodNiagaraSystem = TSoftObjectPtr<UNiagaraSystem>(FSoftObjectPath(TEXT("/Game/_mygame/blood2/NS_bloodsplat.NS_bloodsplat")));
}

void AProphecyBloodFluidPostProcessController::OnConstruction(const FTransform& Transform)
{
	Super::OnConstruction(Transform);
	ApplyBloodFluidPostProcessSettings();
}

void AProphecyBloodFluidPostProcessController::PostRegisterAllComponents()
{
	Super::PostRegisterAllComponents();
	ApplyBloodFluidPostProcessSettings();
	AutoTagBloodNiagaraComponentsForEditor();
}

void AProphecyBloodFluidPostProcessController::BeginPlay()
{
	Super::BeginPlay();
	ApplyBloodFluidPostProcessSettings();
}

void AProphecyBloodFluidPostProcessController::Tick(float DeltaSeconds)
{
	Super::Tick(DeltaSeconds);

	if (bUpdateParametersEveryTick)
	{
		ApplyBloodFluidPostProcessSettings();
	}

	AutoTagBloodNiagaraComponentsForEditor();
}

#if WITH_EDITOR
bool AProphecyBloodFluidPostProcessController::ShouldTickIfViewportsOnly() const
{
	return true;
}

void AProphecyBloodFluidPostProcessController::PostEditChangeProperty(FPropertyChangedEvent& PropertyChangedEvent)
{
	Super::PostEditChangeProperty(PropertyChangedEvent);
	ApplyBloodFluidPostProcessSettings();
}
#endif

void AProphecyBloodFluidPostProcessController::SetBloodFluidPostEnabled(bool bEnabled)
{
	bBloodFluidPostEnabled = bEnabled;
	ApplyBloodFluidPostProcessSettings();
}

void AProphecyBloodFluidPostProcessController::SetBloodFluidStencilDebug(bool bEnabled)
{
	bShowStencilDebug = bEnabled;
	ApplyBloodFluidPostProcessSettings();
}

void AProphecyBloodFluidPostProcessController::TagBloodNiagaraComponentsForStencil()
{
	UWorld* World = GetWorld();
	if (!World)
	{
		return;
	}

	bool bUseFilter = bBloodFluidPostEnabled || bShowStencilDebug;
#if WITH_EDITOR
	bUseFilter = bUseFilter && !IsHiddenEd();
#endif
	bUseFilter = bUseFilter && !IsHidden();

	UNiagaraSystem* TargetSystem = BloodNiagaraSystem.LoadSynchronous();
	for (TObjectIterator<UNiagaraComponent> It; It; ++It)
	{
		UNiagaraComponent* Component = *It;
		if (!Component || Component->GetWorld() != World)
		{
			continue;
		}

		if (TargetSystem && Component->GetAsset() != TargetSystem)
		{
			continue;
		}

		const int32 ClampedStencilValue = FMath::Clamp(BloodStencilValue, 0, 255);
		if (Component->GetOwner() == World->GetWorldSettings())
		{
			if (Component->bRenderCustomDepth || !Component->bRenderInMainPass || !Component->bRenderInDepthPass)
			{
				Component->Modify();
				Component->SetRenderCustomDepth(false);
				Component->SetRenderInMainPass(true);
				Component->SetRenderInDepthPass(true);
				Component->MarkRenderStateDirty();
			}
			continue;
		}

		const bool bNeedsUpdate =
			Component->bRenderCustomDepth != bUseFilter ||
			Component->CustomDepthStencilValue != ClampedStencilValue ||
			!Component->bRenderInMainPass ||
			!Component->bRenderInDepthPass;

		if (bNeedsUpdate)
		{
			Component->Modify();
			Component->SetRenderCustomDepth(bUseFilter);
			Component->SetCustomDepthStencilValue(ClampedStencilValue);
			Component->SetRenderInMainPass(true);
			Component->SetRenderInDepthPass(true);
			Component->MarkRenderStateDirty();
		}
	}
}

void AProphecyBloodFluidPostProcessController::ApplyBloodFluidPostProcessSettings()
{
	if (!PostProcessComponent)
	{
		return;
	}

	RebuildBlendables();
	PushScalarAndVectorParameters();
}

UMaterialInstanceDynamic* AProphecyBloodFluidPostProcessController::GetOrCreateMID(
	TObjectPtr<UMaterialInstanceDynamic>& Slot,
	const TSoftObjectPtr<UMaterialInterface>& MaterialAsset,
	const FName DebugName)
{
	UMaterialInterface* Parent = MaterialAsset.LoadSynchronous();
	if (!Parent)
	{
		Slot = nullptr;
		return nullptr;
	}

	if (!Slot || Slot->Parent != Parent)
	{
		Slot = UMaterialInstanceDynamic::Create(Parent, this, DebugName);
	}

	return Slot;
}

void AProphecyBloodFluidPostProcessController::AddBlendable(UObject* BlendableObject, float Weight)
{
	if (!PostProcessComponent || !BlendableObject)
	{
		return;
	}

	PostProcessComponent->Settings.WeightedBlendables.Array.Add(FWeightedBlendable(Weight, BlendableObject));
}

void AProphecyBloodFluidPostProcessController::RebuildBlendables()
{
	PostProcessComponent->Settings.WeightedBlendables.Array.Reset();

	const bool bUsePostProcess = bBloodFluidPostEnabled || bShowStencilDebug;
	PostProcessComponent->bEnabled = bUsePostProcess;
	PostProcessComponent->BlendWeight = bUsePostProcess ? 1.0f : 0.0f;
	PostProcessComponent->bUnbound = true;
	PostProcessComponent->Priority = 1000.0f;

	if (!bUsePostProcess)
	{
		return;
	}

	if (bShowStencilDebug)
	{
		AddBlendable(GetOrCreateMID(StencilDebugMID, StencilDebugMaterial, TEXT("BloodStencilDebugMID")));
		return;
	}

	AddBlendable(GetOrCreateMID(CompositeMID, CompositeMaterial, TEXT("BloodCompositeMID")));
}

void AProphecyBloodFluidPostProcessController::PushScalarAndVectorParameters()
{
	if (BlurHMID)
	{
		BlurHMID->SetScalarParameterValue(TEXT("BlurRadius"), BlurRadius);
	}
	if (BlurVMID)
	{
		BlurVMID->SetScalarParameterValue(TEXT("BlurRadius"), BlurRadius);
	}
	if (CompositeMID)
	{
		CompositeMID->SetScalarParameterValue(TEXT("BlurRadius"), BlurRadius);
		CompositeMID->SetScalarParameterValue(TEXT("Threshold"), Threshold);
		CompositeMID->SetScalarParameterValue(TEXT("Softness"), Softness);
		CompositeMID->SetScalarParameterValue(TEXT("BlurSampleQuality"), BlurSampleQuality);
	}
}

void AProphecyBloodFluidPostProcessController::AutoTagBloodNiagaraComponentsForEditor()
{
	if (GetWorld() == nullptr || !bAutoTagBloodNiagaraInEditor)
	{
		return;
	}

	TagBloodNiagaraComponentsForStencil();
}
