#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FFKPerAttackTimingTest,"Prophecy.NN.FKReturn.PerAttackHoldTrim",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FFKPerAttackTimingTest::RunTest(const FString&)
{
    using namespace ProphecyFKReturn;
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    TArray<FName> Names;TArray<int32> Parents;TArray<FTransform> Idle;
    Names.Add(TEXT("pelvis"));Parents.Add(INDEX_NONE);Idle.Add(FTransform::Identity);
    for(const auto& D:Data::Bones)
    {
        const int32 Parent=Names.IndexOfByKey(FName(D.Parent));Parents.Add(Parent);Names.Add(FName(D.Name));
        Idle.Add(FTransform(FQuat(D.Q[0],D.Q[1],D.Q[2],D.Q[3]).GetNormalized(),FVector(D.P[0],D.P[1],D.P[2]))*Idle[Parent]);
    }
    // Defaults apply even when no Blueprint has called the node.
    for(const auto& P:Data::Profiles)
    {
        Begin(A,FName(P.Attack),Names,Parents,Idle,Idle,0,1.f/30);
        const auto& C=Active.FindChecked(A).Curve;
        TestEqual(TEXT("Default hold per family"),C.AlphaHold,.1f);
        TestEqual(TEXT("Default trim per family"),C.TakeoverTimeScale,1.f/(1.f-.34f));
    }
    FVector2D T[AttackCount];for(int32 I=0;I<AttackCount;++I)T[I]=FVector2D(double(I)/32.,double(I)/40.);
    auto Set=[&](){return UProphecyFKReturnLibrary::SetAttackFKReturn(A,true,2,
        T[0],T[1],T[2],T[3],T[4],T[5],T[6],T[7],T[8],T[9],T[10],T[11],T[12],T[13],T[14],T[15]);};
    TestTrue(TEXT("Accept independent family values"),Set());CaptureReset(A);
    for(int32 I=0;I<AttackCount;++I)
    {
        const auto& P=Data::Profiles[I];Begin(A,FName(P.Attack),Names,Parents,Idle,Idle,0,1.f/30);
        const auto C=Active.FindChecked(A).Curve;
        TestEqual(TEXT("X selects this family's hold"),C.AlphaHold,float(T[I].X));
        TestEqual(TEXT("Y selects this family's trim"),C.TakeoverTimeScale,1.f/(1.f-float(T[I].Y)));
        const uint64 Limit=uint64(FMath::Max(1.,FMath::CeilToDouble((1./double(C.InverseDuration))*(1.-double(float(T[I].Y)))*60.-1.e-5)));
        TestEqual(TEXT("Family deadline uses its trim"),TickPhases.FindChecked(A).Limit,Limit);
        const float End=(1.f/C.InverseDuration)/C.TakeoverTimeScale;
        TestTrue(TEXT("Family hold is fraction of trimmed window"),C.Weights(End*C.AlphaHold*.99f).NN<1.e-6f);
        TestTrue(TEXT("Coefficient shapes family's remaining window"),FMath::IsNearlyEqual(C.Weights(End*(C.AlphaHold+(1-C.AlphaHold)*.5f)).NN,.25f,1.e-5f));
    }
    const auto Latched=Active.FindChecked(A).Curve;
    const auto SavedLast=T[15];T[15].Y=1.1;
    TestFalse(TEXT("Reject invalid last family atomically"),Set());
    TestEqual(TEXT("Invalid set preserves earlier family"),Configs.FindChecked(A).Timing[0],FVector2f(T[0]));
    TestEqual(TEXT("Invalid set preserves last family"),Configs.FindChecked(A).Timing[15],FVector2f(SavedLast));
    T[15]=SavedLast;
    TestTrue(TEXT("Default node invocation resets all family timings"),UProphecyFKReturnLibrary::SetAttackFKReturn(A));
    for(const auto& V:Configs.FindChecked(A).Timing)TestEqual(TEXT("Reflected defaults are .1/.34"),V,FVector2f(.1f,.34f));
    TestEqual(TEXT("New values do not retime active return"),Active.FindChecked(A).Curve.TakeoverTimeScale,Latched.TakeoverTimeScale);
    RestoreReset(A);TestFalse(TEXT("Reset cancels active return"),IsActive(A));
    for(int32 I=0;I<AttackCount;++I)TestEqual(TEXT("Reset restores every family pair"),Configs.FindChecked(A).Timing[I],FVector2f(T[I]));
    T[0]=FVector2D(1,1);TestTrue(TEXT("Full trim accepted for one family"),Set());
    Begin(A,FName(Data::Profiles[0].Attack),Names,Parents,Idle,Idle,0,1.f/30);
    TestFalse(TEXT("Full trim bypasses selected family"),IsActive(A));
    Begin(A,FName(Data::Profiles[1].Attack),Names,Parents,Idle,Idle,0,1.f/30);
    TestTrue(TEXT("Neighbor family remains enabled"),IsActive(A));
    UProphecyFKReturnLibrary::SetAttackFKReturn(A,false);
    TestFalse(TEXT("Disable still cancels immediately"),IsActive(A));
    Remove(A);TestFalse(TEXT("Remove clears configuration and baseline"),Configs.Contains(A)||Baselines.Contains(A));
    W->DestroyWorld(false);return !HasAnyErrors();
}
#endif
