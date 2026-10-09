#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFKTwistInertiaTest,"Prophecy.NN.FKReturn.TwistInertia",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFKTwistInertiaTest::RunTest(const FString&)
{
    using namespace ProphecyFKReturn;
    for(const FVector3f Axis:{FVector3f(1,0,0),FVector3f(-1,0,0),FVector3f(1,2,3).GetSafeNormal()})
    {
        const FQuat4f Base(FVector3f(0,1,0),.7f);
        const FQuat4f Candidate=(Base*FQuat4f(FVector3f(1,2,-1).GetSafeNormal(),1.6f)).GetNormalized();
        for(float Amount:{.25f,.5f,1.f})
        {
            const auto Q=RemoveAxialInertia(Base,Candidate,Axis,Amount);
            TestTrue(TEXT("Finite swing preserved"),Q.RotateVector(Axis).Equals(Candidate.RotateVector(Axis),1.e-6f));
            if(Amount==1)
            {
                const auto Delta=Base.Inverse()*Q;
                TestTrue(TEXT("Axial correction removed"),FMath::Abs(FVector3f::DotProduct(FVector3f(Delta.X,Delta.Y,Delta.Z),Axis))<1.e-6f);
            }
        }
    }
    TArray<FName> Names{TEXT("pelvis")};TArray<int32> Parents{INDEX_NONE};
    TArray<FTransform> Previous{FTransform::Identity},Current{FTransform::Identity};
    for(int32 J=0;J<BoneCount;++J)
    {
        const auto& D=Data::Bones[J];const int32 Parent=Names.IndexOfByKey(FName(D.Parent));
        Names.Add(FName(D.Name));Parents.Add(Parent);
        const FQuat Q(D.Q[0],D.Q[1],D.Q[2],D.Q[3]);const FVector P(D.P[0],D.P[1],D.P[2]);
        const FQuat Tilt(FVector(1,2,3).GetSafeNormal(),.15+.015*J);
        Previous.Add(FTransform(Q* Tilt,P)*Previous[Parent]);
        Current.Add(FTransform(Q*FQuat(FVector(2,-1,1).GetSafeNormal(),.21+.017*J),P)*Current[Parent]);
    }
    for(bool World:{false,true})
    {
        FProfile P;P.Duration=.39f;P.Inertia=1;P.Easing=0;P.WorldInertia=World;
        for(auto& V:P.Weights)V=1;
        FCurve Base;TestTrue(TEXT("Prepare hierarchy"),Prepare(Base,P,1,Names,Parents,Previous,Current,1.f/30));
        Base.SetAlphaHold(1);
        for(float Amount:{0.f,.5f,1.f})for(float Fraction:{.01f,.2f,.5f,.9f})
        {
            FCurve Filtered=Base;Filtered.UpperArmTwistRemoval=Amount;
            auto A=Current,B=Current;const float Elapsed=Fraction/Base.InverseDuration;
            Base.Apply(Elapsed,A);Filtered.Apply(Elapsed,B);
            for(int32 J=0;J<BoneCount;++J)
            {
                const auto& Bone=Base.Bones[J];
                if(J!=8 && J!=12)TestTrue(TEXT("Shoulder/elbow and unrelated positions preserved"),A[Bone.Index].GetLocation().Equals(B[Bone.Index].GetLocation(),.0001));
                if(J!=6 && J!=10)
                    TestTrue(TEXT("Forearm/hand and unrelated local rotations preserved"),A[Bone.Index].GetRelativeTransform(A[Bone.Parent]).GetRotation().Equals(B[Bone.Index].GetRelativeTransform(B[Bone.Parent]).GetRotation(),1.e-6));
                if(Amount==0)TestTrue(TEXT("Disabled is exact"),A[Bone.Index].Equals(B[Bone.Index],0));
            }
            auto Finished=Current;Filtered.Apply(1.f/Filtered.InverseDuration,Finished);
            for(int32 J=0;J<Current.Num();++J)TestTrue(TEXT("No work at completed deadline"),Finished[J].Equals(Current[J],0));
        }
    }
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W->SpawnActor<AProphecyAgent>();
    ON_SCOPE_EXIT {Remove(A);ForgetReset(A);W->DestroyWorld(false);};
    const FName Slash(TEXT("slashLD")),Hook(TEXT("hookR"));const FConfig Empty;
    const auto Imported=CurrentProfile(Empty,Slash),Other=CurrentProfile(Empty,Hook);
    TestEqual(TEXT("Imported slash twist removal"),Imported.UpperArmTwistRemoval,.98f);
    TestEqual(TEXT("Other attacks remain unfiltered"),Other.UpperArmTwistRemoval,0.f);
    TestFalse(TEXT("Invalid input rejected"),UProphecyFKReturnLibrary::SetAttackFKReturnTwistInertia(A,Slash,1.1f));
    TestTrue(TEXT("Per attack setter"),UProphecyFKReturnLibrary::SetAttackFKReturnTwistInertia(A,Slash,.5f));
    auto Read=[&](FName Attack){return CurrentProfile(Configs.FindChecked(A),Attack);};
    TestEqual(TEXT("Duration preserved"),Read(Slash).Duration,Imported.Duration);
    TestEqual(TEXT("Inertia preserved"),Read(Slash).Inertia,Imported.Inertia);
    TestEqual(TEXT("Other family untouched"),Read(Hook).UpperArmTwistRemoval,0.f);
    CaptureReset(A);UProphecyFKReturnLibrary::SetAttackFKReturnTwistInertia(A,NAME_None,1);
    TestEqual(TEXT("All families option"),Read(Hook).UpperArmTwistRemoval,1.f);
    RestoreReset(A);TestEqual(TEXT("Reset restores attack value"),Read(Slash).UpperArmTwistRemoval,.5f);
    UProphecyFKReturnLibrary::SetAttackFKReturnValues(A,Slash,.7f,.2f,.3f);
    UProphecyFKReturnLibrary::SetAttackFKReturnInertiaProfile(A,Slash,FProphecyFKInertiaWeights(),.1f,.7f,true,.2f);
    TestEqual(TEXT("Other setters preserve twist removal"),Read(Slash).UpperArmTwistRemoval,.5f);
    return !HasAnyErrors();
}
#endif
