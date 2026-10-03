// Compile the accepted mover implementation into the Unreal runtime module.
// Keeping one source implementation prevents the standalone and Unreal movers
// from silently diverging.
#include "../../../StandaloneSim/sim_core/src/locomotion.cpp"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRootWorldDirectionTest,
    "Prophecy.NN.RootWindow.WorldDirectionForecast",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyRootWorldDirectionTest::RunTest(const FString&)
{
    using namespace prophecy::sim;
    for (auto Mode : {LocomotionMode::Walk, LocomotionMode::Run, LocomotionMode::Crawl})
    for (double Yaw : {-3.13, -1.23, 0., 3.13})
    for (double Amplitude : {0., 1.})
    for (bool Momentum : {false, true})
    {
        constexpr double Dt=1./30.;
        LocomotionState State;
        State.position={-1.,.5};State.velocity={.12,2.54};
        State.yaw_radians=Yaw;State.previous_yaw_radians=Yaw-.18;
        LocomotionIntent Intent{Mode,SignedAngleDelta(Yaw,.27),Amplitude,.6,1.,1.};
        const auto Predicted=PredictFutureRoots(State,Intent,Dt,Momentum);
        auto Actual=State;auto Step=Intent;
        const double World=Yaw+Intent.speed_direction_radians;
        for (int I=0;I<8;++I)
        {
            if(I)Step.speed_direction_radians=SignedAngleDelta(Actual.yaw_radians,World);
            StepLocomotion(Actual,Step,Dt,nullptr,Momentum);
            TestTrue(TEXT("Forecast matches repeated world-input steps"),
                FMath::Abs(Predicted[I].position.x-Actual.position.x)<1.e-12 &&
                FMath::Abs(Predicted[I].position.z-Actual.position.z)<1.e-12 &&
                FMath::Abs(Predicted[I].yaw_radians-Actual.yaw_radians)<1.e-12);
            if(I==0)
            {
                auto Next=Intent;Next.speed_direction_radians=SignedAngleDelta(Actual.yaw_radians,World);
                const auto Rolled=PredictFutureRoots(Actual,Next,Dt,Momentum);
                for(int J=0;J<7;++J)TestTrue(TEXT("Rolling forecasts meet without replanning drift"),
                    FMath::Abs(Rolled[J].position.x-Predicted[J+1].position.x)<1.e-10 &&
                    FMath::Abs(Rolled[J].position.z-Predicted[J+1].position.z)<1.e-10);
            }
        }
    }
    return !HasAnyErrors();
}
#endif
