#include "ProphecyNNRootWindowSmoothing.h"
#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "ProphecyNNRootWindowLibrary.h"
#include "ProphecyAgent.h"
#include "Engine/World.h"
#include "Misc/ScopeExit.h"
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

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRootWindowDistanceTest,
    "Prophecy.NN.RootWindow.AccelerationDeceleration", EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyRootWindowDistanceTest::RunTest(const FString&)
{
    using namespace ProphecyNNRootWindow;
    auto Seed=[] { FSample S; double Yaw=0; S.Filter(FVector(10,0,0),Yaw,FVector::OneVector);return S; };
    auto S=Seed();double Yaw=0;
    TestEqual(TEXT("Growing distance uses acceleration factor"),S.Filter(FVector(20,0,0),Yaw,FVector(.25,1,1),.75f).X,12.5);
    TestEqual(TEXT("Shrinking distance uses deceleration factor"),S.Filter(FVector(2.5,0,0),Yaw,FVector(.25,1,1),.75f).X,5.);
    S=Seed();
    TestEqual(TEXT("Acceleration one must not bypass braking smoothing"),S.Filter(FVector::ZeroVector,Yaw,FVector::OneVector,.25f).X,7.5);
    S=Seed();
    TestEqual(TEXT("Zero braking retains outgoing step"),S.Filter(FVector::ZeroVector,Yaw,FVector::OneVector,0.f).X,10.);
    const FVector Short(3,4,2);
    TestEqual(TEXT("Braking one preserves exact candidate even with slow acceleration"),S.Filter(Short,Yaw,FVector(.25,1,1),1.f),Short);
    auto Inherited=Seed(),Explicit=Seed();
    for(const FVector V:{FVector(20,0,0),FVector(0,5,0),FVector::ZeroVector,FVector(-30,4,0)})
    {
        double A=.4,B=.4;
        TestEqual(TEXT("Inherited braking is exactly the shared-factor path"),
            Inherited.Filter(V,A,FVector(.25,.5,.75)),Explicit.Filter(V,B,FVector(.25,.5,.75),.25f));
        TestEqual(TEXT("Angular smoothing unaffected"),A,B);
    }
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);
    if(!TestNotNull(TEXT("Isolated test world"),W))return false;
    AProphecyAgent* Agent=W->SpawnActor<AProphecyAgent>();
    ON_SCOPE_EXIT {Remove(Agent);W->DestroyWorld(false);};
    if(!TestNotNull(TEXT("Test agent"),Agent))return false;
    using L=UProphecyNNRootWindowLibrary;
    TestTrue(TEXT("Braking-only smoothing enables state"),L::SetLocomotionRootWindowSmoothing(Agent,1,1,1,.25f));
    auto* State=Find(Agent);if(!TestNotNull(TEXT("Smoothing state"),State))return false;
    State->Samples[0].Distance=12.5;
    TestTrue(TEXT("Retuning succeeds"),L::SetLocomotionRootWindowSmoothing(Agent,.5,1,1,.75f));
    TestEqual(TEXT("Retuning keeps existing history"),Find(Agent)->Samples[0].Distance,12.5);
    TestFalse(TEXT("Invalid braking rejected atomically"),L::SetLocomotionRootWindowSmoothing(Agent,1,1,1,-.5f));
    float A,D,O,B;L::GetLocomotionRootWindowSmoothing(Agent,A,D,O,B);
    TestEqual(TEXT("Invalid call preserved acceleration"),A,.5f);
    TestEqual(TEXT("Getter exposes braking override"),B,.75f);
    TestTrue(TEXT("Old three-factor call inherits"),L::SetLocomotionRootWindowSmoothing(Agent,.5,1,1));
    TestEqual(TEXT("Inheritance removes override"),GetDistanceDeceleration(Agent),-1.f);
    TestTrue(TEXT("All resolved ones disable"),L::SetLocomotionRootWindowSmoothing(Agent,1,1,1,1));
    TestNull(TEXT("No smoothing work after disabling"),Find(Agent));
    TestEqual(TEXT("Override retired with state"),GetDistanceDeceleration(Agent),-1.f);
    return !HasAnyErrors();
}
#endif
