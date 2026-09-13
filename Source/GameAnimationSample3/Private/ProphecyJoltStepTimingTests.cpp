#include "ProphecyJoltStepTiming.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltStepTimingTest,
    "Prophecy.Jolt.Character.SubstepTiming", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyJoltStepTimingTest::RunTest(const FString&)
{
    using namespace ProphecyJolt::StepTiming;
    UPhysicsSettings* Settings = NewObject<UPhysicsSettings>();
    Settings->bSubstepping = true;
    Settings->MaxSubstepDeltaTime = 0.016667f;
    Settings->MaxSubsteps = 64;
    TestEqual(TEXT("Captured threshold crossing splits the frame"), Count(0.0170364007f, Settings), 2);
    TestEqual(TEXT("Captured next frame uses one step"), Count(0.0166667998f, Settings), 1);
    TestNearlyEqual(TEXT("Controller uses the actual half-frame duration"), Duration(0.0170364007f, Settings), 0.00851820035f, 1.e-8f);
    Settings->MaxSubsteps = 2;
    TestNearlyEqual(TEXT("Capped count still divides the entire frame"), Duration(0.1f, Settings), 0.05f, 1.e-8f);
    Settings->bSubstepping = false;
    TestEqual(TEXT("Disabled substepping uses one full frame"), Duration(0.1f, Settings), 0.1f);
    TestEqual(TEXT("Missing settings use one full frame"), Duration(0.1f, nullptr), 0.1f);
    return true;
}
#endif
