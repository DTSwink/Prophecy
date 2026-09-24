IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyWalkPinningSpaceTest,"Prophecy.NN.WalkPinning.CoordinateSpace",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyWalkPinningSpaceTest::RunTest(const FString&)
{
    FMat3f Seed;
    Seed.Rows[0]=FVector3f(1,0,0);
    Seed.Rows[1]=FVector3f(0,0,-1);
    Seed.Rows[2]=FVector3f(0,1,0);
    const FVector3f NativeRoot(1,2,-3);
    const FVector Root(100,-300,200);
    const ProphecyWalkPinning::FBackwardBound Bound{20,60,0};
    for (float Yaw : {0.f,.7f,-1.4f,3.1f})
    {
        const FTransform RootTransform(FRotator(0,-FMath::RadiansToDegrees(Yaw),0),Root);
        const FVector Heading=ProphecyWalkPinning::BoundHeading(RootTransform);
        for (float Height : {.05f,.8f})
        {
            const FVector Actual=LowerPointToWorld(FVector3f(.1f,.4f,Height),Seed,NativeRoot,Yaw);
            const FVector Expected=RootTransform.TransformPosition(FVector(10,-40,Height*100));
            TestTrue(TEXT("Lower foot matches independently decoded component/world axes"),Actual.Equals(Expected,1.e-4));
            TestNearlyEqual(TEXT("40cm behind gives half pin regardless of yaw or foot height"),
                ProphecyWalkPinning::BoundPin(1,Bound,Actual,Root,Heading),.5f,1.e-5f);
            TestNearlyEqual(TEXT("Circle uses horizontal reach, not foot height"),
                ProphecyWalkPinning::CircleBoundPin(1,Bound,Actual,Root),float((60-FMath::Sqrt(1700.))/40),1.e-5f);
        }
    }
    return true;
}
