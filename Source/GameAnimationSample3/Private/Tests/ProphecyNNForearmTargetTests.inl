// Included beside the production reconstruction helper in its anonymous namespace.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySpecialCalfBoundaryTest,
    "Prophecy.NN.PhysicalTargets.SpecialCalfHinge",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecySpecialCalfBoundaryTest::RunTest(const FString&)
{
    for(float Side:{-1.f,1.f})
    {
        const FVector3f Axis(Side,0,0),Pole(0,Side,0);
        const FVector UEAxis(Side,0,0),UEPole(0,-Side,0);
        const FTransform Thigh(FRotator(31,-47,19),FVector(15,30,90));
        const FVector Hinge=Thigh.GetRotation().RotateVector(FVector::CrossProduct(UEAxis,UEPole));
        FQuat Previous=FQuat::Identity;bool HasPrevious=false;
        for(int32 Degrees=-180;Degrees<=180;Degrees+=5)
        {
            FTransform Calf(FRotator(45,80,-120),FVector(20,35,70),FVector(1.1));
            const FTransform Before=Calf;
            const FVector Aim=FQuat(Hinge,FMath::DegreesToRadians(double(Degrees))).RotateVector(Thigh.GetRotation().RotateVector(UEAxis));
            const FTransform Foot(FRotator(25,-30,Degrees),Calf.GetLocation()+Aim*42,FVector(1.2));
            SetCalfRollFromThigh(Axis,Axis,Pole,Pole,Thigh,Calf,Foot);
            TestTrue(TEXT("Calf keeps endpoint geometry and scale"),Calf.GetLocation()==Before.GetLocation() && Calf.GetScale3D()==Before.GetScale3D());
            TestTrue(TEXT("Calf aims knee to foot"),Calf.GetRotation().RotateVector(UEAxis).Equals(Aim,1.e-5));
            TestTrue(TEXT("Signed hinge does not flip through a folded knee"),Calf.GetRotation().RotateVector(FVector::CrossProduct(UEAxis,UEPole)).Equals(Hinge,1.e-5));
            if(HasPrevious) TestTrue(TEXT("Five degree bend never produces a roll jump"),Previous.AngularDistance(Calf.GetRotation())<FMath::DegreesToRadians(5.001));
            Previous=Calf.GetRotation();HasPrevious=true;
            SetCalfRollFromThigh(Axis,Axis,Pole,Pole,Thigh,Calf,Foot);
            TestTrue(TEXT("Repeated publication is idempotent"),Previous.AngularDistance(Calf.GetRotation())<1.e-5);
        }
    }
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyForearmTargetTest,
    "Prophecy.NN.PhysicalTargets.ForearmRollFromUpperArm",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyForearmTargetTest::RunTest(const FString&)
{
    for(int32 Side=0;Side<2;++Side)
    {
        const FVector3f Axis(Side==0?1.f:-1.f,0,0);
        const FQuat Parent=FRotator(31,-47,19).Quaternion();
        const FQuat Reference=Parent*ForearmIdleLocal(Side);
        const FVector Aim=Reference.RotateVector(FVector(Axis));
        const FQuat Idle=MatrixToQuat(ForearmRotationFromUpperArm(Axis,FVector3f(Aim),QuatToMatrix(Parent),Side));
        TestTrue(TEXT("Neutral animation's forearm local is preserved"),Idle.AngularDistance(Reference)<1.e-5);
        for(int32 Degrees=-170;Degrees<=170;Degrees+=5)
        {
            const FQuat Bend(Reference.RotateVector(FVector(0,1,0)),FMath::DegreesToRadians(double(Degrees)));
            const FVector Direction=Bend.RotateVector(Aim);
            const FQuat Q=MatrixToQuat(ForearmRotationFromUpperArm(Axis,FVector3f(Direction),QuatToMatrix(Parent),Side));
            TestTrue(TEXT("Forearm reaches the wrist by shortest swing from parent's neutral frame"),Q.AngularDistance(Bend*Reference)<1.e-5);
        }
        for(const FVector3f Direction:{FVector3f::ZeroVector,FVector3f(-Aim)})
        {
            const FQuat Q=MatrixToQuat(ForearmRotationFromUpperArm(Axis,Direction,QuatToMatrix(Parent),Side));
            TestTrue(TEXT("Degenerate directions remain finite and normalized"),!Q.ContainsNaN()&&Q.IsNormalized());
            if(!Direction.IsNearlyZero())TestTrue(TEXT("Opposite direction still reaches wrist"),Q.RotateVector(FVector(Axis)).Equals(-Aim,1.e-5));
        }
    }
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySpecialForearmBoundaryTest,
    "Prophecy.NN.PhysicalTargets.SpecialForearmBoundary",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecySpecialForearmBoundaryTest::RunTest(const FString&)
{
    for(int32 Side=0;Side<2;++Side)
    {
        const FVector3f Axis(Side==0?1.f:-1.f,0,0);
        const FTransform UpperArm(FRotator(31,-47,19),FVector(0,0,100));
        FQuat Accepted=FQuat::Identity;
        for(int32 Degrees=-180;Degrees<=180;Degrees+=15)
        {
            FTransform Forearm(FRotator(45,80,-120),FVector(15,30,90),FVector(1.1));
            const FTransform Before=Forearm;
            const FTransform Hand(FRotator(25,-30,Degrees),FVector(36,41,102),FVector(1.2));
            SetForearmRollFromUpperArm(Axis,Side,UpperArm,Forearm,Hand);
            const FVector Aim=(Hand.GetLocation()-Forearm.GetLocation()).GetSafeNormal();
            TestTrue(TEXT("Special correction keeps geometry and aims at wrist"),
                Forearm.GetLocation()==Before.GetLocation()&&Forearm.GetScale3D()==Before.GetScale3D()&&
                Forearm.GetRotation().RotateVector(FVector(Axis)).Equals(Aim,1.e-5));
            if(Degrees==-180)Accepted=Forearm.GetRotation();
            TestTrue(TEXT("A complete hand rotation never drags forearm roll"),Accepted.AngularDistance(Forearm.GetRotation())<1.e-5);
            const FTransform Once=Forearm;
            SetForearmRollFromUpperArm(Axis,Side,UpperArm,Forearm,Hand);
            TestTrue(TEXT("Repeated publication is idempotent"),Forearm.Equals(Once,1.e-6));
        }
    }
    return !HasAnyErrors();
}
