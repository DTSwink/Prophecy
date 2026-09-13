#include "ProphecyNNRootWindowSmoothing.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRootWindowSmoothingTest,
    "Prophecy.NN.RootWindow.IndependentFactors", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyRootWindowSmoothingTest::RunTest(const FString&)
{
    using namespace ProphecyNNRootWindow;
    auto Seed = [] { FSample S; double Yaw = 0; S.Filter(FVector(10,0,0), Yaw, FVector::OneVector); return S; };
    {
        auto S = Seed(); double Yaw = UE_HALF_PI;
        const auto V = S.Filter(FVector(0,20,0), Yaw, FVector(0,1,1));
        TestTrue(TEXT("Distance zero retains radius but accepts new direction"), V.Equals(FVector(0,10,0), 1.e-5));
        TestTrue(TEXT("Independent orientation accepts new yaw"), FMath::IsNearlyEqual(Yaw, double(UE_HALF_PI), 1.e-6));
    }
    {
        auto S = Seed(); double Yaw = UE_HALF_PI;
        const auto V = S.Filter(FVector(0,20,0), Yaw, FVector(1,0,0));
        TestTrue(TEXT("Direction zero retains heading while distance updates"), V.Equals(FVector(20,0,0), 1.e-5));
        TestEqual(TEXT("Orientation zero retains facing"), Yaw, 0.);
    }
    {
        auto S = Seed(); double Yaw = 2.;
        const FVector Input(3,17,0);
        TestEqual(TEXT("All-one identity retains exact incoming offset"), S.Filter(Input, Yaw, FVector::OneVector), Input);
        TestEqual(TEXT("All-one identity retains exact incoming yaw"), Yaw, 2.);
        const FVector Frozen(S.Distance*FMath::Cos(S.Direction), S.Distance*FMath::Sin(S.Direction),0);
        Yaw = -1.; const auto V = S.Filter(FVector(-44,3,0), Yaw, FVector::ZeroVector);
        TestTrue(TEXT("Zero freezes the previous offset"), V.Equals(Frozen, 1.e-6));
        TestEqual(TEXT("Zero freezes previous yaw"), Yaw, 2.);
        TestTrue(TEXT("Reattaching offset to a moved present root follows its translation"),
            (FVector(100,40,0)+V - (FVector(20,10,0)+Frozen)).Equals(FVector(80,30,0),1.e-6));
    }
    {
        FSample S; double Yaw = FMath::DegreesToRadians(179.);
        S.Filter(FVector(-10,.17455,0), Yaw, FVector::OneVector);
        Yaw = FMath::DegreesToRadians(-179.);
        S.Filter(FVector(-10,-.17455,0), Yaw, FVector(.5,.5,.5));
        TestTrue(TEXT("Facing follows the short arc across 180"), FMath::Abs(FMath::Abs(Yaw)-UE_PI)<1.e-5);
        TestTrue(TEXT("Travel direction follows the short arc across 180"), FMath::Abs(FMath::Abs(S.Direction)-UE_PI)<1.e-4);
    }
    return true;
}
#endif
