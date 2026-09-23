#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyRecoveryFootRotationFieldsTest,"Prophecy.NN.PolicyBlend.RecoveryFootRotationFields",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyRecoveryFootRotationFieldsTest::RunTest(const FString&)
{
    float Current[41]{},Run[43]{},Walk[43]{},Original[41],State[41];
    for(int32 I=0;I<41;++I) Original[I]=float(I)*.03f;
    for(int32 O:{12,28})
    {
        WriteRot6(QuatToMatrix(FQuat(FVector::UpVector,-.5)),Run+O);
        WriteRot6(QuatToMatrix(FQuat(FVector::UpVector,.5)),Walk+O);
    }
    for(const FVector2f Weights:{FVector2f(-1,-1),FVector2f(1,-1),FVector2f(.5,1)})
    {
        FMemory::Memcpy(State,Original,sizeof(State));
        OverrideRecoveryFootRotations(Current,Run,Walk,Weights,State);
        for(int32 I=0;I<41;++I)
        {
            const int32 Leg=I>=12 && I<18 ? 0 : I>=28 && I<34 ? 1 : -1;
            if(Leg<0 || Weights[Leg]<0) TestEqual(TEXT("Rotation source does not touch translation/pelvis/thigh/toe or inactive foot"),State[I],Original[I]);
        }
        for(int32 I=0;I<2;++I) if(Weights[I]>=0)
        {
            const FQuat Expected(FVector::UpVector,-.5+Weights[I]);
            TestTrue(TEXT("Only requested foot orientation comes from Walk or its normal return blend"),
                MatrixToQuat(MatrixFromRot6(State+12+16*I)).AngularDistance(Expected)<1.e-5);
        }
    }
    return !HasAnyErrors();
}
#endif
