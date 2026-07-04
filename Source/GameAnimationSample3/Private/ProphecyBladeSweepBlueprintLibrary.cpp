#include "ProphecyBladeSweepBlueprintLibrary.h"

namespace
{
constexpr int32 MaxBladeDepthSweepSamples = 10000;

void AddDepthSample(TArray<float>& Samples, float Depth)
{
	if (Samples.Num() == 0 || !FMath::IsNearlyEqual(Samples.Last(), Depth, KINDA_SMALL_NUMBER))
	{
		Samples.Add(Depth);
	}
}
}

TArray<float> UProphecyBladeSweepBlueprintLibrary::BuildBladeDepthSweepSamples(float PreviousDepth, float CurrentDepth, float Interval)
{
	TArray<float> Samples;

	if (!FMath::IsFinite(PreviousDepth) || !FMath::IsFinite(CurrentDepth) || !FMath::IsFinite(Interval))
	{
		return Samples;
	}

	const float MinDepth = FMath::Min(PreviousDepth, CurrentDepth);
	const float MaxDepth = FMath::Max(PreviousDepth, CurrentDepth);
	AddDepthSample(Samples, MinDepth);

	if (FMath::IsNearlyEqual(MinDepth, MaxDepth, KINDA_SMALL_NUMBER))
	{
		return Samples;
	}

	const float Step = FMath::Abs(Interval);
	if (Step <= KINDA_SMALL_NUMBER)
	{
		AddDepthSample(Samples, MaxDepth);
		return Samples;
	}

	const int32 InteriorStepCount = FMath::FloorToInt((MaxDepth - MinDepth) / Step);
	for (int32 StepIndex = 1; StepIndex <= InteriorStepCount && Samples.Num() < MaxBladeDepthSweepSamples; ++StepIndex)
	{
		const float Depth = MinDepth + static_cast<float>(StepIndex) * Step;
		if (Depth < MaxDepth - KINDA_SMALL_NUMBER)
		{
			AddDepthSample(Samples, Depth);
		}
	}

	AddDepthSample(Samples, MaxDepth);
	return Samples;
}
