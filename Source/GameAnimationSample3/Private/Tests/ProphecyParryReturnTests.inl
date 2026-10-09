#if WITH_DEV_AUTOMATION_TESTS
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyParryReturnTest,"Prophecy.NN.DefenseReturn.ParryIsolation",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyParryReturnTest::RunTest(const FString&)
{
    using namespace ProphecyFKReturn;using L=UProphecyFKReturnLibrary;
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    TArray<FName> Names;TArray<int32> Parents;TArray<FTransform> Idle;
    Names.Add(TEXT("pelvis"));Parents.Add(INDEX_NONE);Idle.Add(FTransform::Identity);
    for(const auto& D:Data::Bones)
    {
        const int32 Parent=Names.IndexOfByKey(FName(D.Parent));Parents.Add(Parent);Names.Add(FName(D.Name));
        Idle.Add(FTransform(FQuat(D.Q[0],D.Q[1],D.Q[2],D.Q[3]).GetNormalized(),FVector(D.P[0],D.P[1],D.P[2]))*Idle[Parent]);
    }
    auto Outgoing=Idle;Outgoing.Last().SetRotation(FQuat(FVector::UpVector,.4)*Outgoing.Last().GetRotation());
    auto StartParry=[&]{BeginParry(A,Names,Parents,Idle,Outgoing,0,1.f/30);};
    auto StartAttack=[&]{Begin(A,TEXT("hookR"),Names,Parents,Idle,Outgoing,0,1.f/30);};
    StartParry();TestFalse(TEXT("Parry is opt-in"),IsActive(A));
    StartAttack();const auto Reference=Active.FindChecked(A).Curve;
    TestTrue(TEXT("Configure independent parry"),L::SetParryFKReturn(A,true,.8f,.3f,.9f,FVector2D(.2,.1),2));
    StartAttack();const auto After=Active.FindChecked(A).Curve;
    for(int32 I=0;I<=20;++I)
    {
        auto Expected=Idle,Actual=Idle,EL=Idle,AL=Idle;
        Reference.Apply(I*.02f,Expected,EL);After.Apply(I*.02f,Actual,AL);
        for(int32 B=0;B<Idle.Num();++B)TestTrue(TEXT("Attack curve unchanged by parry settings"),Expected[B].Equals(Actual[B],0));
    }
    L::SetAttackFKReturn(A,false);StartParry();TestTrue(TEXT("Parry independent of disabled attacks"),IsActive(A)&&ParryActive.Contains(A));
    TestEqual(TEXT("Parry easing"),Active.FindChecked(A).Curve.Easing,.9f);
    TestEqual(TEXT("Parry coefficient"),Active.FindChecked(A).Curve.Coefficient,2.f);
    L::SetAttackFKReturn(A,false);TestTrue(TEXT("Disabling attacks cannot cancel parry"),IsActive(A));
    TestFalse(TEXT("Invalid settings rejected atomically"),L::SetParryFKReturn(A,true,.8f,-1));
    TestEqual(TEXT("Invalid write preserves profile"),ParryConfigs.FindChecked(A).Profile.Inertia,.3f);
    CaptureReset(A);L::SetParryFKReturn(A,true,.3f,0);RestoreReset(A);
    TestFalse(TEXT("Reset cancels active state"),IsActive(A));TestEqual(TEXT("Reset restores parry profile"),ParryConfigs.FindChecked(A).Profile.Inertia,.3f);
    L::SetAttackFKReturn(A,true);StartAttack();L::SetParryFKReturn(A,false);
    TestTrue(TEXT("Disabling parry cannot cancel attack"),IsActive(A));
    StartParry();TestFalse(TEXT("Disabled parry stays inactive"),IsActive(A));
    L::SetParryFKReturn(A,true);StartParry();L::SetParryFKReturn(A,false);TestFalse(TEXT("Disable cancels own active return"),IsActive(A));
    Remove(A);TestFalse(TEXT("Remove clears all parry settings"),ParryConfigs.Contains(A)||ParryBaselines.Contains(A)||ParryActive.Contains(A));
    W->DestroyWorld(false);return !HasAnyErrors();
}
#endif
