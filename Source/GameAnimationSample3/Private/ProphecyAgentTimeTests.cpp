#include "ProphecyAgentTime.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "ProphecyContinuousRootWindow.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAgentTimeClockTest,"Prophecy.Agent.TimeDilation.Clocks",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyAgentTimeClockTest::RunTest(const FString&)
{
    using namespace ProphecyAgentTime;
    constexpr double H=1./30.;
    for (int32 FPS:{30,60,120})
    {
        FClocks Clocks;Clocks.Set(0,2.);Clocks.Set(1,.5);Clocks.Set(2,1.25);
        int32 Counts[4]={};int32 Shared=0;
        double LastPresented[4]={};
        for (int32 Tick=0;Tick<FPS*4;++Tick)
        {
            int32 Feedback[4]={};double LastEvent=-1.;
            Clocks.Advance(1./FPS,H,4,32,[&](FStep& Event)
            {
                TestTrue(TEXT("Batches are chronological"),Event.ElapsedSeconds>=LastEvent);
                LastEvent=Event.ElapsedSeconds;
                if (Event.SharedBoundary) ++Shared;
                for (int32 I=0;I<4;++I)
                {
                    if (Event.Due[I]) ++Counts[I];
                    if (Event.SamplePhysics[I]) ++Feedback[I];
                    TestTrue(TEXT("No feedback on a skipped lane"),!Event.SamplePhysics[I] || Event.Due[I]);
                }
                TestEqual(TEXT("Normal neighbour only on shared steps"),bool(Event.Due[3]),Event.SharedBoundary);
            });
            const double Rates[]={2.,.5,1.25,1.};
            for (int32 I=0;I<4;++I)
            {
                const double Presented=Counts[I]+Clocks.Alpha(I);
                TestTrue(TEXT("Continuous motion advances by rate*dt with no alternate-frame hold"),
                    FMath::Abs(Presented-LastPresented[I]-Rates[I]*30./FPS)<1.e-6);
                TestTrue(TEXT("Completed physics sample consumed at most once per game tick"),Feedback[I]<=1);
                LastPresented[I]=Presented;
            }
        }
        TestEqual(TEXT("Double speed takes twice the trained steps"),Counts[0],240);
        TestEqual(TEXT("Half speed takes half the trained steps"),Counts[1],60);
        TestEqual(TEXT("Fractional speed preserves remainder"),Counts[2],150);
        TestEqual(TEXT("Neighbour unchanged"),Counts[3],120);
        TestEqual(TEXT("Special clock remains 30Hz"),Shared,120);
    }
    FClocks C;C.SharedPhase=.25;C.Set(0,2.);
    C.Advance(H*.2,H,2,32,[](FStep&){});
    const double Before=C.Alpha(0);
    C.Set(0,1.);
    TestEqual(TEXT("Getter immediately resets to 1"),C.Rate(0),1.);
    TestEqual(TEXT("Changing speed never jumps the existing interpolation phase"),C.Alpha(0),Before);
    C.Advance(H*.6,H,2,32,[](FStep&){});
    TestTrue(TEXT("Return to normal retires at the next shared boundary"),C.Lanes.IsEmpty());
    C.Set(0,1.);
    TestTrue(TEXT("Setting normal while normal creates no work"),C.Lanes.IsEmpty());

    // A defender can activate on Armed during a step where its slow locomotion
    // lane was not due. Remaining local deadlines must be discarded immediately.
    FClocks Switch;Switch.Set(0,2.);Switch.Set(1,.5);
    bool Armed=false;int32 After=0;
    Switch.Advance(H*3.,H,3,32,[&](FStep& E)
    {
        if (Armed && E.Due[0]) { ++After;TestTrue(TEXT("Special never advances on an extra step"),E.SharedBoundary); }
        if (!Armed && E.SharedBoundary)
        { Armed=true;Switch.Set(0,1.);Switch.Set(1,1.); }
    });
    TestEqual(TEXT("Special has two subsequent normal steps"),After,2);
    TestTrue(TEXT("No hidden old speed restored after special"),Switch.Lanes.IsEmpty());
    FClocks Hitch;Hitch.Set(0,1000.);
    int32 Count=0;Hitch.Advance(10.,H,1,32,[&](FStep&){++Count;});
    TestTrue(TEXT("Debugger hitch is bounded"),Count<=64);
    TestTrue(TEXT("Hitch leaves valid phase"),Hitch.Alpha(0)>=0. && Hitch.Alpha(0)<1.);
    return true;
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyAgentTimeWindowTest,"Prophecy.Agent.TimeDilation.Window",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyAgentTimeWindowTest::RunTest(const FString&)
{
    for (float Rate:{.5f,1.f,2.f,3.25f})
    {
        TArray<FTransform> Roots;TArray<float> Times;
        for (int32 I=0;I<10;++I) Roots.Emplace(FQuat::Identity,FVector(I*10.,0,0));
        const float H=(1.f/30.f)/Rate;
        ProphecyContinuousRootWindow::Resample(Roots,Times,.35f,H,FTransform(FVector(3.5,0,0)));
        TestTrue(TEXT("Index zero is the currently applied root"),Roots[0].GetLocation().Equals(FVector(3.5,0,0)));
        TestTrue(TEXT("dx/dt predicts accelerated world velocity"),
            FMath::IsNearlyEqual((Roots[1].GetLocation().X-Roots[0].GetLocation().X)/Times[1],300.*Rate,.001));
        TestTrue(TEXT("Horizon timestamps use world seconds"),FMath::IsNearlyEqual(Times[8],8.f*H,1.e-6f));
    }
    return true;
}
#endif
