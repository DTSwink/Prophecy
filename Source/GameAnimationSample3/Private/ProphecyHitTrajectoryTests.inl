#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyHitTrajectoryTest,"Prophecy.Physics.HitTrajectory",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyHitTrajectoryTest::RunTest(const FString&)
{
    using namespace ProphecyHitTrajectory;
    const FVector Zero=FVector::ZeroVector;
    auto R=Solve(FVector(1000,0,0),Zero,45,-980,10000,10);
    TestTrue(TEXT("Stationary target exact hit"),R.Exact);
    TestNearlyEqual(TEXT("Analytic 45-degree speed"),R.Velocity.Size(),FMath::Sqrt(980000.),1.e-5);
    TestNearlyEqual(TEXT("Analytic flight time"),R.Time,FMath::Sqrt(2000./980.),1.e-7);
    const FVector Launch(700,350,900),Moving(120,-40,65);
    const FVector D=(Launch-Moving)*1.7+FVector(0,0,-490*1.7*1.7);
    const double Angle=FMath::RadiansToDegrees(FMath::Atan2(Launch.Z,Launch.Size2D()));
    R=Solve(D,Moving,Angle,-980,10000,10);
    TestTrue(TEXT("Moving target includes lateral and vertical velocity"),R.Exact);
    TestTrue(TEXT("Ball and predicted target coincide"),
        (R.Velocity*R.Time+FVector(0,0,-490*R.Time*R.Time)-D-Moving*R.Time).Size()<1.e-5);
    R=Solve(FVector(1000,0,0),Zero,0,-980,1000,10);
    TestFalse(TEXT("Flat same-height shot cannot hit at finite speed"),R.Exact);
    TestNearlyEqual(TEXT("Fallback retains flat elevation"),R.Velocity.Z,0.,1.e-8);
    TestNearlyEqual(TEXT("Flat fallback uses bounded maximum speed"),R.Velocity.Size(),1000.,1.e-5);
    TestTrue(TEXT("Closest pass occurs before passing target horizontally"),R.Time>.5 && R.Time<1.);
    TestNearlyEqual(TEXT("Flat fallback is stationary point of miss"),
        1000000.*(R.Time-1.)+480200.*R.Time*R.Time*R.Time,0.,1.e-3);
    R=Solve(FVector(1000,0,0),FVector(-100,0,0),90,-980,10000,12);
    TestTrue(TEXT("Vertical shot catches target crossing launch axis"),R.Exact);
    TestNearlyEqual(TEXT("Vertical interception time"),R.Time,10.,1.e-6);
    TestNearlyEqual(TEXT("Vertical shot has no horizontal velocity"),R.Velocity.Size2D(),0.,1.e-8);
    R=Solve(FVector(1000,0,0),FVector(100,0,0),0,0,1000,10);
    TestTrue(TEXT("Zero gravity flat intercept"),R.Exact);
    TestNearlyEqual(TEXT("Chooses earliest exact solution"),R.Time,1000./900.,1.e-6);
    R=Solve(FVector(1000,0,0),Zero,45,-980,100,1);
    TestFalse(TEXT("Unreachable under speed and time bounds"),R.Exact);
    TestTrue(TEXT("Bounds retained"),R.Velocity.Size()<=100.00001 && R.Time<=1.);
    TestEqual(TEXT("Invalid inputs report invalid miss"),Solve(Zero,Zero,0,-980,0,10).Miss,-1.);

    // Independent coarse exhaustive time oracle: analytic extrema must beat every sampled pass.
    FRandomStream Random(9127);
    for (int32 Case=0;Case<80;++Case)
    {
        const FVector Offset(Random.FRandRange(-2000,2000),Random.FRandRange(-2000,2000),Random.FRandRange(-1000,1000));
        const FVector TargetV(Random.FRandRange(-600,600),Random.FRandRange(-600,600),Random.FRandRange(-200,200));
        const double Elevation=Case%10==0 ? 90. : Random.FRandRange(-80,85);
        const double Limit=Random.FRandRange(200,3500),Horizon=Random.FRandRange(.5,10);
        R=Solve(Offset,TargetV,Elevation,-980,Limit,Horizon);
        const double C=FMath::Cos(FMath::DegreesToRadians(Elevation)),S=FMath::Sin(FMath::DegreesToRadians(Elevation));
        double SampleMiss=Offset.Size();
        for (int32 I=1;I<=4000;++I)
        {
            const double T=Horizon*I/4000.;
            const FVector Q=Offset+TargetV*T+FVector(0,0,490*T*T);
            const double H=Q.Size2D(),Distance=FMath::Clamp(C*H+S*Q.Z,0.,Limit*T);
            const double Error=FMath::Sqrt(FMath::Square(H-C*Distance)+FMath::Square(Q.Z-S*Distance));
            SampleMiss=FMath::Min(SampleMiss,Error);
        }
        TestTrue(FString::Printf(TEXT("Closest pass beats sampled oracle %d"),Case),R.Miss>=0. && R.Miss<=SampleMiss+1.e-4);
        TestTrue(FString::Printf(TEXT("Speed cap %d"),Case),R.Velocity.Size()<=Limit+1.e-6);
        if (R.Velocity.Size()>1.e-6)
            TestNearlyEqual(FString::Printf(TEXT("Elevation preserved %d"),Case),
                FMath::RadiansToDegrees(FMath::Atan2(R.Velocity.Z,R.Velocity.Size2D())),Elevation,1.e-7);
    }
    return !HasAnyErrors();
}
#endif
