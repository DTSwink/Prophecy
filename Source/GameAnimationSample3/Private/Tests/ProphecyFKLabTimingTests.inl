#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFKLabTimingTest,"Prophecy.NN.FKReturn.AngleTimeAndWorldFrame",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFKLabTimingTest::RunTest(const FString&)
{
    using namespace ProphecyFKReturn;
    TArray<FName> Names;TArray<int32> Parents;TArray<FTransform> Idle;
    Names.Add(TEXT("pelvis"));Parents.Add(INDEX_NONE);Idle.Add(FTransform::Identity);
    for(const auto& D:Data::Bones)
    {
        const int32 Parent=Names.IndexOfByKey(FName(D.Parent));Parents.Add(Parent);Names.Add(FName(D.Name));
        Idle.Add(FTransform(FQuat(D.Q[0],D.Q[1],D.Q[2],D.Q[3]).GetNormalized(),FVector(D.P[0],D.P[1],D.P[2]))*Idle[Parent]);
    }
    auto End=Idle;const FTransform Turn(FQuat(FVector::UpVector,UE_DOUBLE_HALF_PI));
    for(int32 I=1;I<End.Num();++I)End[I]=End[I]*Turn;
    FProfile P;P.Duration=.28f;P.AngleTimeSeconds=.29f;P.WorldInertia=true;P.InertiaHold=.05f;P.InertiaDecay=.8f;
    P.Weights[0]=.31f; // Accepted lab spine inertia; legacy FProfile defaults disable it.
    FCurve C;Prepare(C,P,2,Names,Parents,Idle,End,1.f/30);C.SetAlphaHold(1);
    TestTrue(TEXT("90 degrees adds exactly .29 seconds"),FMath::IsNearlyEqual(1.f/C.InverseDuration,.57f,1.e-6f));
    P.Duration=.55f;FCurve Longer;Prepare(Longer,P,2,Names,Parents,Idle,End,1.f/30);
    TestTrue(TEXT("Extra angle seconds independent of base"),FMath::IsNearlyEqual(1.f/Longer.InverseDuration,.84f,1.e-6f));
    P.AngleTimeSeconds=0;Prepare(Longer,P,2,Names,Parents,Idle,End,1.f/30);
    TestTrue(TEXT("Zero adds no time"),FMath::IsNearlyEqual(1.f/Longer.InverseDuration,.55f,1.e-6f));
    const FQuat Frame(FVector(1,2,3).GetSafeNormal(),.7);auto A=End,B=End;
    C.Apply(.11f,A);
    for(auto& T:B)T=T*FTransform(Frame.Inverse());
    C.Apply(.11f,B,{},Frame);
    for(int32 I=0;I<A.Num();++I)
    {
        const FTransform World=B[I]*FTransform(Frame);
        TestTrue(TEXT("World inertia independent of component rebase"),World.Equals(A[I],.001));
    }
    auto StaticPelvis=End,MovingPelvis=End;constexpr float Dt=1.e-4f;
    MovingPelvis[0].SetRotation(FQuat(FVector::UpVector,3*Dt));
    C.Apply(Dt,StaticPelvis);C.Apply(Dt,MovingPelvis);
    TestTrue(TEXT("Moving pelvis does not add another initial angular impulse"),
        StaticPelvis[1].GetRotation().Equals(MovingPelvis[1].GetRotation(),1.e-5));
    TestEqual(TEXT("Full alpha hold excludes NN"),C.Weights(.56f).NN,0.f);
    TestEqual(TEXT("Untrimmed endpoint restores NN"),C.Weights(.58f).NN,1.f);
    return !HasAnyErrors();
}
#endif
