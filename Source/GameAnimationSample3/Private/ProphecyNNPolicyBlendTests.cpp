#include "ProphecyNNPolicyBlend.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyNNPolicyBlendTiming,
    "Prophecy.NN.PolicyBlend.DirectionalTiming", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyNNPolicyBlendTiming::RunTest(const FString&)
{
    TestFalse(TEXT("Auto run default leaves ordinary running speeds alone"), ProphecyAutoRun::Above(100., 100000.f));
    TestFalse(TEXT("Auto run equality retains ordinary selection"), ProphecyAutoRun::Above(25., 500.f));
    TestTrue(TEXT("Auto run above threshold overrides walk"), ProphecyAutoRun::Above(25.01, 500.f));
    TestFalse(TEXT("Zero speed never triggers zero threshold"), ProphecyAutoRun::Above(0., 0.f));
    TestFalse(TEXT("Disabled override retains running checkpoint at rest"), ProphecySelectWalkCheckpoint(true, 0, 0, -1));
    TestTrue(TEXT("Walk intent always keeps walk"), ProphecySelectWalkCheckpoint(false, 8, 0, -1));
    TestTrue(TEXT("100 cm/s below 150 threshold selects walk while running"), ProphecySelectWalkCheckpoint(true, 1, 0, 150));
    TestFalse(TEXT("Equality is not below threshold"), ProphecySelectWalkCheckpoint(true, 1.5, 0, 150));
    TestFalse(TEXT("Planar magnitude includes both axes"), ProphecySelectWalkCheckpoint(true, 1.2, 1.2, 150));
    TestTrue(TEXT("Reverse movement uses speed magnitude"), ProphecySelectWalkCheckpoint(true, -1, 0, 150));
    TestFalse(TEXT("Zero threshold does not override zero speed"), ProphecySelectWalkCheckpoint(true, 0, 0, 0));
    FProphecyNNPolicyBlend B;
    B.Reset(true);
    for (int32 I = 0; I < 15; ++I) B.Step(false, 1.f, 2.f, 1.f / 30.f);
    TestTrue(TEXT("Walk to run half-way after half its independent duration"), FMath::IsNearlyEqual(B.WalkWeight, .5f, 1.e-5f));
    const float BeforeReverse = B.WalkWeight;
    B.Step(true, 1.f, 2.f, 0.f);
    TestEqual(TEXT("Reversal starts from the actual mixture"), B.WalkWeight, BeforeReverse);
    for (int32 I = 0; I < 30; ++I) B.Step(true, 1.f, 2.f, 1.f / 30.f);
    TestTrue(TEXT("Reverse uses run-to-walk duration"), FMath::IsNearlyEqual(B.WalkWeight, .75f, 1.e-5f));
    for (int32 I = 0; I < 31; ++I) B.Step(true, 1.f, 2.f, 1.f / 30.f);
    TestFalse(TEXT("Finished blend leaves dual-policy path"), B.IsActive());
    TestEqual(TEXT("Exact walk endpoint"), B.WalkWeight, 1.f);
    B.Step(false, 0.f, 2.f, 1.f / 30.f);
    TestFalse(TEXT("Zero duration retains immediate switching"), B.IsActive());
    TestEqual(TEXT("Exact run endpoint"), B.WalkWeight, 0.f);
    B.Step(true, 1.f, 2.f, .2f);
    B.Step(true, 1.f, 0.f, 0.f);
    TestFalse(TEXT("Setting active direction to zero cancels its blend"), B.IsActive());
    B.Reset(false);
    TestFalse(TEXT("Full attack/admission reset retains no stale blend"), B.IsActive());
    B.Step(true, .1f, .01f, 1.f/30.f);
    TestFalse(TEXT("Sub-step duration completes without overshoot"), B.IsActive());
    TestEqual(TEXT("Completed sub-step reaches walk"), B.WalkWeight, 1.f);

    return true;
}
#endif
