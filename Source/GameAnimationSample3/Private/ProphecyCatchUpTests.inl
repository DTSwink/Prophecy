#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyCatchUpTest,"Prophecy.Physics.ComputeCatchUp",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyCatchUpTest::RunTest(const FString&)
{
    double Time=0.;FVector Velocity;
    const FVector Zero=FVector::ZeroVector;
    auto Check=[&](const TCHAR* Name,FVector R,FVector V,double Speed,bool Expected,double ExpectedTime)
    {
        const bool Can=UPhysicsHitVelocityLibrary::ComputeCatchUp(R,V,Zero,Speed,Time,Velocity);
        TestEqual(Name,Can,Expected);
        TestNearlyEqual(FString(Name)+TEXT(" time"),Time,ExpectedTime,1.e-7*FMath::Max(1.,ExpectedTime));
        if (Can && Time>0.)
        {
            TestTrue(FString(Name)+TEXT(" positions meet"),(Velocity*Time-R-V*Time).Size()<1.e-6*FMath::Max(1.,R.Size()));
            TestNearlyEqual(FString(Name)+TEXT(" speed"),Velocity.Size(),Speed,1.e-7);
        }
        else if (!Can && FMath::IsFinite(Speed) && Speed>=0. && R.SizeSquared()>0.)
        {
            TestNearlyEqual(FString(Name)+TEXT(" pursuit speed"),Velocity.Size(),Speed,1.e-7);
            TestTrue(FString(Name)+TEXT(" pursuit aims at current location"),Velocity.Equals(R.GetSafeNormal()*Speed,1.e-7));
        }
        else TestTrue(FString(Name)+TEXT(" zero velocity"),Velocity.IsZero());
    };
    Check(TEXT("Stationary"),FVector(1000,0,0),Zero,500,true,2.);
    Check(TEXT("Receding"),FVector(1000,0,0),FVector(200,0,0),500,true,1000./300.);
    Check(TEXT("Lateral lead"),FVector(1000,0,0),FVector(0,300,0),500,true,2.5);
    TestTrue(TEXT("Leads target"),Velocity.Equals(FVector(400,300,0),1.e-8));
    Check(TEXT("Vertical lead"),FVector(1000,0,0),FVector(0,0,300),500,true,2.5);
    Check(TEXT("Faster escaping"),FVector(1000,0,0),FVector(600,0,0),500,false,10000.);
    Check(TEXT("Oblique 3D pursuit"),FVector(300,400,1200),FVector(600,800,2400),100,false,10000.);
    Check(TEXT("Faster approaching earliest of two roots"),FVector(1000,0,0),FVector(-600,0,0),500,true,1000./1100.);
    Check(TEXT("Equal approaching"),FVector(1000,0,0),FVector(-500,0,0),500,true,1.);
    Check(TEXT("Equal escaping"),FVector(1000,0,0),FVector(500,0,0),500,false,10000.);
    Check(TEXT("Equal lateral"),FVector(1000,0,0),FVector(0,500,0),500,false,10000.);
    Check(TEXT("Tangent"),FVector(1000,0,0),FVector(-400,300,0),300,true,2.5);
    Check(TEXT("Outside intercept cone"),FVector(1000,0,0),FVector(-400,301,0),300,false,10000.);
    Check(TEXT("Stationary attacker crossed"),FVector(1000,0,0),FVector(-500,0,0),0,true,2.);
    Check(TEXT("Stationary attacker missed"),FVector(1000,0,0),FVector(-500,1,0),0,false,10000.);
    Check(TEXT("Both stationary apart"),FVector(1000,0,0),Zero,0,false,10000.);
    Check(TEXT("Already together"),Zero,FVector(500,0,0),0,true,0.);
    Check(TEXT("Negative speed invalid"),Zero,Zero,-1,false,10000.);
    Check(TEXT("Nearly equal speeds no artificial cutoff"),FVector(1000,0,0),FVector(499.999999,0,0),500,true,1000./(500.-499.999999));
    Check(TEXT("No 10000 second cap"),FVector(20000,0,0),Zero,1,true,20000.);
    Check(TEXT("Infinite speed invalid"),FVector(1,0,0),Zero,std::numeric_limits<double>::infinity(),false,10000.);
    Check(TEXT("NaN speed invalid"),FVector(1,0,0),Zero,std::numeric_limits<double>::quiet_NaN(),false,10000.);

    // Independent reachability bound: no point is reachable before the reported time.
    FRandomStream Random(73081);
    for (int32 I=0;I<250;++I)
    {
        const FVector R(Random.FRandRange(-3000,3000),Random.FRandRange(-3000,3000),Random.FRandRange(-3000,3000));
        const FVector V(Random.FRandRange(-600,600),Random.FRandRange(-600,600),Random.FRandRange(-600,600));
        const double Speed=Random.FRandRange(50,1200);
        const bool Can=UPhysicsHitVelocityLibrary::ComputeCatchUp(R,V,Zero,Speed,Time,Velocity);
        if (Can)
        {
            TestTrue(TEXT("Random intercept residual"),(Velocity*Time-R-V*Time).Size()<1.e-7);
            TestNearlyEqual(TEXT("Random speed"),Velocity.Size(),Speed,1.e-7);
            for (int32 J=0;J<20;++J)
            {
                const double Earlier=Time*J/20.;
                TestTrue(TEXT("Cannot intercept earlier"),(R+V*Earlier).SizeSquared()>FMath::Square(Speed*Earlier));
            }
        }
        else
        {
            TestEqual(TEXT("Random unreachable time"),Time,10000.);
            TestNearlyEqual(TEXT("Random pursuit speed"),Velocity.Size(),Speed,1.e-7);
            TestTrue(TEXT("Random pursuit direction"),Velocity.Equals(R.GetSafeNormal()*Speed,1.e-7));
        }
        double ShiftTime;FVector ShiftVelocity;
        const FVector Shift(1.e7,-2.e7,3.e7);
        TestEqual(TEXT("Translation keeps feasibility"),UPhysicsHitVelocityLibrary::ComputeCatchUp(R+Shift,V,Shift,Speed,ShiftTime,ShiftVelocity),Can);
        TestNearlyEqual(TEXT("Translation keeps time"),ShiftTime,Time,1.e-6);
        TestTrue(TEXT("Translation keeps velocity"),ShiftVelocity.Equals(Velocity,1.e-6));
    }
    return !HasAnyErrors();
}
#endif
