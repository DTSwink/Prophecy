#include "ProphecyRootSpeedLimitsLibrary.h"
#include "ProphecyRootSpeedLimits.h"
#include "ProphecyAgent.h"

namespace ProphecyRootSpeedLimits
{
// New identity: do not reuse live allocation layouts from the initial compile.
static TMap<TWeakObjectPtr<const AProphecyAgent>, FSettings> SettingsWithStepYaw;
FSettings* Find(const AProphecyAgent* Agent) { return SettingsWithStepYaw.IsEmpty() ? nullptr : SettingsWithStepYaw.Find(Agent); }
void Remove(const AProphecyAgent* Agent) { SettingsWithStepYaw.Remove(Agent); }
void LimitWindow(FSettings& Value, float* Window, const double* Yaw, int32 Count,
    float PositionScale, float Dt, const ProphecyRootMagic::FVelocity* Magic, float& VerticalVelocity)
{
    double LinearScale = 1., AngularScale = 1.;
    FVector Previous = FVector::ZeroVector;
    double PreviousYaw = 0.;
    for (int32 I = 0; I < Count; ++I)
    {
        const double Scale = (I + 1) * double(PositionScale);
        const FVector Position(Window[4*I] * Scale, VerticalVelocity * (I+1) * double(Dt), Window[4*I+1] * Scale);
        const double Distance = (Position - Previous).Size();
        const double Angle = FMath::Abs(Yaw[I] - PreviousYaw);
        if (Distance > Value.Linear * Dt) LinearScale = FMath::Min(LinearScale, Value.Linear * Dt / Distance);
        if (Angle > Value.Angular * Dt) AngularScale = FMath::Min(AngularScale, Value.Angular * Dt / Angle);
        Previous = Position;
        PreviousYaw = Yaw[I];
    }
    Value.bClamped = LinearScale < 1. || AngularScale < 1.;
    Value.NextYawDelta = Count > 0 ? Yaw[0] * AngularScale : 0.;
    Value.AppliedMagic = Magic ? *Magic : ProphecyRootMagic::FVelocity{};
    if (!Value.bClamped) return;
    Value.AppliedMagic.Linear *= float(LinearScale);
    Value.AppliedMagic.Yaw *= AngularScale;
    VerticalVelocity *= float(LinearScale);
    for (int32 I = 0; I < Count; ++I)
    {
        if (LinearScale < 1.) { Window[4*I] *= float(LinearScale); Window[4*I+1] *= float(LinearScale); }
        if (AngularScale < 1.)
        {
            Window[4*I+2] = float(FMath::Cos(Yaw[I] * AngularScale));
            Window[4*I+3] = float(FMath::Sin(Yaw[I] * AngularScale));
        }
    }
}
}

bool UProphecyRootSpeedLimitsLibrary::SetRootVelocityLimits(AProphecyAgent* Agent, float Linear, float Angular, bool bEnabled)
{
    if (!IsInGameThread() || !IsValid(Agent) || Agent->IsActorBeingDestroyed()) return false;
    if (!bEnabled) { ProphecyRootSpeedLimits::Remove(Agent); return true; }
    if (!FMath::IsFinite(Linear) || !FMath::IsFinite(Angular) || Linear < 0.f || Angular < 0.f) return false;
    auto& Value = ProphecyRootSpeedLimits::SettingsWithStepYaw.FindOrAdd(Agent);
    Value.Linear = double(Linear) * .01;
    Value.Angular = FMath::DegreesToRadians(double(Angular));
    Value.bClamped = false;
    return true;
}
void UProphecyRootSpeedLimitsLibrary::GetRootVelocityLimits(AProphecyAgent* Agent, bool& bEnabled, float& Linear, float& Angular)
{
    const auto* Value = IsInGameThread() && IsValid(Agent) ? ProphecyRootSpeedLimits::Find(Agent) : nullptr;
    bEnabled = Value != nullptr;
    Linear = Value ? float(Value->Linear * 100.) : 1000000.f;
    Angular = Value ? float(FMath::RadiansToDegrees(Value->Angular)) : 1000000.f;
}

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRootSpeedLimitsTest, "Prophecy.Root.VelocityLimits.CombinedWindow",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyRootSpeedLimitsTest::RunTest(const FString&)
{
    using namespace ProphecyRootSpeedLimits;
    FSettings Config;
    Config.Linear = 5.; Config.Angular = .5;
    float Window[] = {3,0,1,0, 3,0,1,0};
    const double Yaw[] = {2.,4.};
    ProphecyRootMagic::FVelocity Magic;
    Magic.Linear = FVector3f(3,4,0); Magic.Yaw = 1.;
    float Vertical = 4.;
    LimitWindow(Config,Window,Yaw,2,1.f,.5f,&Magic,Vertical);
    const FVector Delta(Window[0],Vertical*.5,Window[1]);
    TestTrue(TEXT("Combined XYZ step is limited"), FMath::IsNearlyEqual(Delta.Size()/.5,5.,1.e-5));
    TestTrue(TEXT("Yaw step limited before encoding"), FMath::IsNearlyEqual(double(FMath::Atan2(Window[3],Window[2]))/.5,.5,1.e-5));
    TestTrue(TEXT("Magic yaw contribution scales too"), FMath::IsNearlyEqual(Config.AppliedMagic.Yaw,.125,1.e-8));
    TestTrue(TEXT("Source magic is unchanged"), Magic.Linear == FVector3f(3,4,0) && Magic.Yaw == 1.);
    Config.Linear = Config.Angular = 0.;
    LimitWindow(Config,Window,Yaw,2,1.f,.5f,&Magic,Vertical);
    TestTrue(TEXT("Zero caps stop both channels"), Window[0]==0 && Window[1]==0 && Window[2]==1 && Window[3]==0 && Vertical==0);
    Config = FSettings{};
    float Original[] = {1,2,.5f,.75f};
    const double OriginalYaw[] = {.5}; Vertical=2;
    LimitWindow(Config,Original,OriginalYaw,1,1.f,1.f,&Magic,Vertical);
    TestTrue(TEXT("High defaults leave input bitwise unchanged"), !Config.bClamped && Original[0]==1 && Original[1]==2 && Original[2]==.5f && Original[3]==.75f && Vertical==2);
    return true;
}
#endif
