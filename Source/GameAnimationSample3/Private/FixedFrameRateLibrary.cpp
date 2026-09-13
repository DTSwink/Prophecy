#include "FixedFrameRateLibrary.h"

#include "Engine/Engine.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformTime.h"
#include "Performance/MaxTickRateHandlerModule.h"

namespace
{
// UE's fixed-frame clock ignores t.MaxFPS when pacing frames. Use its pacing
// extension point to allow a lower debugging cap without changing game delta.
class FFixedClockDebugFrameLimiter final : public IMaxTickRateHandlerModule
{
public:
	FFixedClockDebugFrameLimiter()
	{
		IModularFeatures::Get().RegisterModularFeature(GetModularFeatureName(), this);
	}
	~FFixedClockDebugFrameLimiter()
	{
		IModularFeatures::Get().UnregisterModularFeature(GetModularFeatureName(), this);
	}
	void Initialize() override {}
	void SetEnabled(bool bInEnabled) override { bEnabled = bInEnabled; }
	bool GetEnabled() override { return bEnabled; }
	bool GetAvailable() override { return true; }
	void SetFlags(uint32 InFlags) override { Flags = InFlags; }
	uint32 GetFlags() override { return Flags; }
	bool HandleMaxTickRate(float DesiredMaxTickRate) override
	{
		const double Now = FPlatformTime::Seconds();
		const float Cap = GEngine ? GEngine->GetMaxFPS() : 0.0f;
		if (!bEnabled || !GEngine || !GEngine->bUseFixedFrameRate
			|| !FMath::IsFinite(Cap) || Cap <= 0.0f || Cap >= DesiredMaxTickRate)
		{
			LastFrameTime = Now;
			return false;
		}

		// Pace against actual elapsed wall time, including the preceding frame's
		// work. Never catch up missed frames or alter the fixed simulation delta.
		const double Deadline = LastFrameTime > 0.0 ? LastFrameTime + 1.0 / Cap : Now;
		const double Remaining = Deadline - Now;
		if (Remaining > 0.005)
		{
			FPlatformProcess::SleepNoStats(static_cast<float>(Remaining - 0.002));
		}
		while (FPlatformTime::Seconds() < Deadline)
		{
			FPlatformProcess::SleepNoStats(0.0f);
		}
		LastFrameTime = FPlatformTime::Seconds();
		return true;
	}

private:
	double LastFrameTime = 0.0;
	bool bEnabled = true;
	uint32 Flags = 0;
};

FFixedClockDebugFrameLimiter FixedClockDebugFrameLimiter;
}

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
