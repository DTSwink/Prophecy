#include "FixedFrameRateLibrary.h"

#include "Engine/Engine.h"

void UFixedFrameRateLibrary::SetFixedFrameRateRuntime(float FPS)
{
	if (!GEngine)
	{
		return;
	}

	FPS = FMath::Max(FPS, 1.0f);

	GEngine->bUseFixedFrameRate = true;
	GEngine->FixedFrameRate = FPS;
}

void UFixedFrameRateLibrary::DisableFixedFrameRateRuntime()
{
	if (!GEngine)
	{
		return;
	}

	GEngine->bUseFixedFrameRate = false;
}
