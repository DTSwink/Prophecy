IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyFootPoleTest,"Prophecy.NN.AttackEntry.FootLocomotionPole",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyFootPoleTest::RunTest(const FString&)
{
    using namespace ProphecyAttackFootLocomotion;
    // Same bent chain, but different foot-local pole directions and foot yaw.
    FTransform Attack[4]={FTransform(FVector(0,0,80)),FTransform(FVector(0,20,45)),FTransform(FVector(0,0,10)),FTransform(FVector(12,0,10))};
    FTransform Loco[4];for(int32 B=0;B<4;++B)Loco[B]=Attack[B];
    Loco[1].SetLocation(FVector(20,0,45));
    Loco[2].SetRotation(FRotator(0,90,0).Quaternion());
    Loco[3]=FTransform(FVector(12,0,0))*Loco[2];
    const FVector LP=FootLocalPole(Loco),AP=FootLocalPole(Attack);
    for(float Alpha:{0.f,.25f,.5f,.75f,1.f})for(float FootAlpha:{0.f,.5f,1.f})
    {
        FTransform Result[4];for(int32 B=0;B<4;++B)Result[B]=Attack[B];
        AuthorLeg(Result,Loco,1,FootAlpha,Alpha);
        const FVector Expected=FQuat(FVector(0,0,-1),UE_DOUBLE_PI*Alpha).RotateVector(LP);
        TestTrue(TEXT("Pole blends in foot local, including attack-only foot rotation"),FootLocalPole(Result).Equals(Expected,1.e-5));
        TestTrue(TEXT("Hip fixed"),Result[0].GetLocation().Equals(Attack[0].GetLocation(),1.e-6));
        TestTrue(TEXT("Ankle fixed"),Result[2].GetLocation().Equals(Loco[2].GetLocation(),1.e-6));
        for(int32 B=0;B<2;++B)TestTrue(TEXT("Both bone lengths preserved"),FMath::IsNearlyEqual(
            (Result[B+1].GetLocation()-Result[B].GetLocation()).Length(),(Loco[B+1].GetLocation()-Loco[B].GetLocation()).Length(),1.e-5));
        const FTransform Carrier(FRotator(25,123,-30),FVector(300,-800,50));
        FTransform MovedAttack[4],MovedLoco[4];
        for(int32 B=0;B<4;++B){MovedAttack[B]=Attack[B]*Carrier;MovedLoco[B]=Loco[B]*Carrier;}
        AuthorLeg(MovedAttack,MovedLoco,1,FootAlpha,Alpha);
        for(int32 B=0;B<4;++B)TestTrue(TEXT("Common world rotation cannot change local result"),MovedAttack[B].Equals(Result[B]*Carrier,1.e-5));
    }
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    using L=UProphecyAttackFootLocomotionLibrary;
    const FName Names[]={TEXT("pelvis"),TEXT("thigh_l"),TEXT("calf_l"),TEXT("foot_l"),TEXT("ball_l"),TEXT("thigh_r"),TEXT("calf_r"),TEXT("foot_r"),TEXT("ball_r")};
    FTransform Pose[9];for(auto& T:Pose)T=FTransform(FVector(0,0,A->GetRootLowPoint().Z+10));
    Pose[3].AddToTranslation(FVector(-100,0,0));
    for(float FPS:{30.f,60.f,120.f})
    {
        L::SetAttackFootLocomotion(A,true,EProphecyAttackFootLocomotionMode::Run,40,15,0,0,0,0,.2f);
        Begin(A,INDEX_NONE,MakeArrayView(Names),MakeArrayView(Pose),FTransform::Identity,FVector(100,0,0));
        float Alpha[2];AdvancePoles(A,1,Alpha);
        TestTrue(TEXT("Drag starts pole immediately; direct attack bypasses"),Alpha[0]==0 && Alpha[1]==-1);
        auto Tick=[&](int32 N){for(int32 I=0;I<N;++I)FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1/FPS);};
        Tick(6);AdvancePoles(A,1,Alpha);TestTrue(TEXT("Six ticks reach midpoint regardless of FPS"),FMath::IsNearlyEqual(Alpha[0],.5f));
        Suspend(A,true);Tick(30);Suspend(A,false);AdvancePoles(A,1,Alpha);
        TestTrue(TEXT("Half mode pauses pole clock"),FMath::IsNearlyEqual(Alpha[0],.5f));
        Tick(6);AdvancePoles(A,1,Alpha);TestEqual(TEXT("Twelve ticks reach attack-local pole"),Alpha[0],1.f);
        TestEqual(TEXT("Completed blend retires clocks while keeping local attack direction"),PoleBlends.FindChecked(A).Running,uint8(0));
        AdvancePoles(A,0,Alpha);TestFalse(TEXT("Last ownership release retires pole state"),PoleBlends.Contains(A));
        End(A);
    }
    CaptureReset(A);RestoreReset(A);TestTrue(TEXT("Reset preserves configured duration"),PoleSettings.Contains(A));
    L::SetAttackFootLocomotion(A,true,EProphecyAttackFootLocomotionMode::Run,40,15);
    Begin(A,INDEX_NONE,MakeArrayView(Names),MakeArrayView(Pose),FTransform::Identity,FVector(100,0,0));
    TestFalse(TEXT("Zero duration creates no pole state"),PoleBlends.Contains(A));
    TestFalse(TEXT("Zero duration keeps no pole settings"),PoleSettings.Contains(A));
    Remove(A);W->DestroyWorld(false);return !HasAnyErrors();
}
