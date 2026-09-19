#include "ProphecyJoltStepTiming.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "ProphecyJoltBlueprintLibrary.h"
#include "Engine/World.h"

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
    UWorld* World=UWorld::CreateWorld(EWorldType::Game,false);
    if (!TestNotNull(TEXT("Transient world"),World)) return false;
    TestEqual(TEXT("Default has no quality override"),MinimumSubsteps(World),1);
    TestTrue(TEXT("Enable two collision substeps"),UProphecyJoltBlueprintLibrary::SetJoltCollisionSubsteps(World,true,2));
    TestEqual(TEXT("Two detection/integration passes"),Count(1.f/60,Settings,World),2);
    TestNearlyEqual(TEXT("Drive matches actual physics substep"),Duration(1.f/60,Settings,World),1.f/120,1.e-8f);
    TestFalse(TEXT("Reject excessive step count"),UProphecyJoltBlueprintLibrary::SetJoltCollisionSubsteps(World,true,17));
    TestEqual(TEXT("Rejected input retains configuration"),MinimumSubsteps(World),2);
    Settings->bSubstepping=true;Settings->MaxSubsteps=64;
    TestEqual(TEXT("Higher existing count preserved"),Count(.1f,Settings,World),6);
    UProphecyJoltBlueprintLibrary::SetJoltCollisionSubsteps(World,false,2);
    TestEqual(TEXT("Disable restores project timing"),Count(1.f/60,Settings,World),1);
    World->DestroyWorld(false);
    return true;
}
#endif
