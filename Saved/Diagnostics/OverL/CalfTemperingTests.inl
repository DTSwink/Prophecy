#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyCalfTemperingTest,
    "Prophecy.NN.LowerTempering.CalfTwistContinuity",EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyCalfTemperingTest::RunTest(const FString&)
{
    const FVector Axis=FVector(.2,-.9,.05).GetSafeNormal();
    const FQuat Previous(FVector::UpVector,.7);
    const FQuat Swing(FVector::RightVector,.15);
    const FQuat Carried=(Swing*Previous).GetNormalized();
    const FVector Aim=Carried.RotateVector(Axis);
    const FQuat Decoded=(FQuat(Aim,.8)*Carried).GetNormalized();
    const FQuat Frozen=TemperCalfRotation(Previous,Decoded,Axis,0);
    for (float Follow:{0.f,.1f,.5f,.9f,1.f})
    {
        const FQuat Result=TemperCalfRotation(Previous,Decoded,Axis,Follow);
        TestTrue(TEXT("Following twist preserves the exact calf endpoint"),Result.RotateVector(Axis).Equals(Aim,1.e-6));
        TestTrue(TEXT("Finite normalized rotation"),!Result.ContainsNaN() && Result.IsNormalized());
        TestTrue(TEXT("Only twist difference is blended"),FMath::IsNearlyEqual(
            Result.AngularDistance(Decoded),Frozen.AngularDistance(Decoded)*(1.-Follow),1.e-6));
    }
    TestTrue(TEXT("Normal preserves decoder exactly"),TemperCalfRotation(Previous,Decoded,Axis,1)==Decoded);
    TestTrue(TEXT("Unchanged pose is a fixed point"),TemperCalfRotation(Previous,Previous,Axis,.1).Equals(Previous,1.e-6));
    FQuat Current=Previous;
    double LastError=Current.AngularDistance(Decoded);
    for (int32 I=0;I<30;++I)
    {
        Current=TemperCalfRotation(Current,Decoded,Axis,.1f);
        const double Error=Current.AngularDistance(Decoded);
        TestTrue(TEXT("Repeated following converges without oscillation"),Error<=LastError+1.e-6);
        LastError=Error;
    }
    TestTrue(TEXT("Repeated following approaches normal"),LastError<.04);
    return !HasAnyErrors();
}
#endif
