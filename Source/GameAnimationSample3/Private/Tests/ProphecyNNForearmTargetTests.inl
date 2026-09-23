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
    "Prophecy.NN.PhysicalTargets.ForearmRollFromHand",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FProphecyForearmTargetTest::RunTest(const FString& Parameters)
{
    for (float Side : { -1.0f, 1.0f })
    {
        const FVector3f LocalAxis(Side, 0, 0), LocalPole(0, Side, 0);
        const FQuat Base = FRotator(31, -47, 19).Quaternion();
        const FVector Aim = Base.RotateVector(FVector(LocalAxis));
        // Pronation must follow the hand through a complete turn, on both arms.
        for (int32 Degrees = -180; Degrees <= 180; Degrees += 5)
        {
            const FQuat Hand = FQuat(Aim, FMath::DegreesToRadians(double(Degrees))) * Base;
            const FQuat Forearm = MatrixToQuat(ForearmRotationFromHand(
                LocalAxis, FVector3f(Aim), LocalPole, QuatToMatrix(Hand)));
            TestTrue(TEXT("Aligned forearm follows hand roll, including the quaternion seam"),
                Forearm.AngularDistance(Hand) < 1.0e-5);
        }
        // A bent wrist is permitted, but must not introduce a separate twist.
        for (int32 Degrees = 0; Degrees <= 170; Degrees += 5)
        {
            const FQuat Bend(Base.RotateVector(FVector(LocalPole)), FMath::DegreesToRadians(double(Degrees)));
            const FQuat Hand = Bend * Base;
            const FQuat Forearm = MatrixToQuat(ForearmRotationFromHand(
                LocalAxis, FVector3f(Aim), LocalPole, QuatToMatrix(Hand)));
            TestTrue(TEXT("Forearm points along elbow-to-hand direction"),
                Forearm.RotateVector(FVector(LocalAxis)).Equals(Aim, 1.0e-5));
            const FQuat Relative = Forearm.Inverse() * Hand;
            TestTrue(TEXT("Hand-relative forearm reconstruction contains swing but no axial twist"),
                FMath::Abs(FVector::DotProduct(FVector(Relative.X, Relative.Y, Relative.Z), FVector(LocalAxis))) < 1.0e-5);
            TestTrue(TEXT("Wrist bend alone leaves forearm roll unchanged"), Forearm.AngularDistance(Base) < 1.0e-5);
        }
        const FMat3f Hand = QuatToMatrix(Base);
        for (const FVector3f Direction : { FVector3f::ZeroVector, FVector3f(-Aim) })
        {
            const FQuat Q = MatrixToQuat(ForearmRotationFromHand(LocalAxis, Direction, LocalPole, Hand));
            TestFalse(TEXT("Degenerate direction produces no NaN"), Q.ContainsNaN());
            TestTrue(TEXT("Degenerate direction produces a normalized rotation"), Q.IsNormalized());
            if (!Direction.IsNearlyZero())
                TestTrue(TEXT("Antiparallel fallback still aims at the hand"),
                    Q.RotateVector(FVector(LocalAxis)).Equals(-Aim, 1.0e-5));
        }
    }
    return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySpecialForearmBoundaryTest,
    "Prophecy.NN.PhysicalTargets.SpecialForearmBoundary",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecySpecialForearmBoundaryTest::RunTest(const FString&)
{
    for(float Side:{-1.f,1.f}) for(int32 Degrees=-180;Degrees<=180;Degrees+=15)
    {
        const FVector3f Axis(Side,0,0),Pole(0,Side,0);
        FTransform Forearm(FRotator(45,80,-120),FVector(15,30,90),FVector(1.1,1.1,1.1));
        const FTransform Before=Forearm;
        const FTransform Hand(FRotator(25,-30,Degrees),FVector(36,41,102),FVector(1.2,1.2,1.2));
        SetForearmRollFromHand(Axis,Pole,Forearm,Hand);
        const FVector Aim=(Hand.GetLocation()-Forearm.GetLocation()).GetSafeNormal();
        TestTrue(TEXT("Special forearm aims at wrist without changing position or scale"),
            Forearm.GetLocation()==Before.GetLocation() && Forearm.GetScale3D()==Before.GetScale3D() &&
            Forearm.GetRotation().RotateVector(FVector(Axis)).Equals(Aim,1.e-5));
        const FQuat Relative=Forearm.GetRotation().Inverse()*Hand.GetRotation();
        TestTrue(TEXT("Special wrist has swing but no independent roll"),FMath::Abs(Relative.X)<1.e-5);
        const FTransform Accepted=Forearm;
        SetForearmRollFromHand(Axis,Pole,Forearm,Hand);
        TestTrue(TEXT("Repeated publication does not accumulate rotation"),Forearm.Equals(Accepted,1.e-6));
    }
    return !HasAnyErrors();
}
