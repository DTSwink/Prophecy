IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyReturnArmSettingsTest,"Prophecy.NN.SlashReturn.PerArmSettings",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyReturnArmSettingsTest::RunTest(const FString&)
{
    using namespace ProphecySlashReturn;using L=UProphecySlashReturnLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;
    if(!A)return false;
    L::SetBothArmsReturnToNeutralEnabled(A,true);
    L::SetAttackBothArmsReturnToNeutral(A,true,false,false,false,false,false,false,true);
    for(const TCHAR* Attack:{TEXT("slashL"),TEXT("jabL")})for(bool LeftLonger:{false,true})for(float FPS:{30.f,60.f,120.f})
    {
        L::SetSlashRightArmReturnToNeutral(A,true,0,LeftLonger?.1f:.3f,100,0,LeftLonger?.3f:.1f);
        Begin(A,Attack);TestEqual(TEXT("Both start with independent durations"),int32(ActiveArmMask(A)),3);
        for(int32 Tick=1;Tick<=18;++Tick)
        {
            FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/FPS);AdvanceFrame(A);
            if(Tick==6 || Tick==17)TestEqual(TEXT("Only the longer physical arm remains, regardless of primary attack arm"),int32(ActiveArmMask(A)),LeftLonger?1:2);
        }
        TestFalse(TEXT("The longer arm retires the shared clock"),Active(A));
    }
    L::SetSlashRightArmReturnToNeutral(A,true,.1f,.2f,100);Begin(A,TEXT("slashL"));
    TestEqual(TEXT("Default left hold inherits the existing pin"),ExtraReturns.FindChecked(A).Config.Hold,.1f);
    TestEqual(TEXT("Default left blend inherits the existing pin"),ExtraReturns.FindChecked(A).Config.Blend,.2f);
    L::SetSlashRightArmReturnToNeutral(A,true,0,.2f,100,0,0);Begin(A,TEXT("slashL"));
    TestEqual(TEXT("Explicit zero left duration leaves only right"),int32(ActiveArmMask(A)),2);
    L::SetSlashRightArmReturnToNeutral(A,true,0,0,100,0,.2f);Begin(A,TEXT("slashL"));
    TestEqual(TEXT("Left can return when right has zero duration"),int32(ActiveArmMask(A)),1);
    L::SetSlashRightArmReturnToNeutral(A,true,0,.3f,100,0,.2f,0,1);Begin(A,TEXT("slashL"));
    TestEqual(TEXT("Zero left alpha skips left pose work"),int32(ActiveArmMask(A)),2);
    TestFalse(TEXT("Zero left alpha allocates no extra return"),ExtraReturns.Contains(A));
    FTransform S(FVector(0,-17,0)),E(FVector(25,-17,0)),H(FVector(35,-27,-15));
    const FTransform Before[]={S,E,H};
    ApplyPose(A,0,1./30,FTransform::Identity,FTransform::Identity,17,S,E,H,S,E,H,H,S,E,H,FVector::UpVector);
    TestTrue(TEXT("Zero-alpha ApplyPose is an exact NN bypass"),S.Equals(Before[0],0)&&E.Equals(Before[1],0)&&H.Equals(Before[2],0));
    for(int32 Tick=0;Tick<3;++Tick) { FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/60);AdvanceFrame(A); }
    const double Elapsed=Returns.FindChecked(A).Elapsed;
    L::SetSlashRightArmReturnToNeutral(A,true,0,.3f,100,0,.2f,.4f,1);
    TestEqual(TEXT("Live alpha change preserves elapsed time"),Returns.FindChecked(A).Elapsed,Elapsed);
    TestEqual(TEXT("Enabling left during right return starts at the same elapsed time"),ExtraReturns.FindChecked(A).Elapsed,Elapsed);
    L::SetSlashRightArmReturnToNeutral(A,true,0,.3f,100,0,.2f,.4f,1);
    TestEqual(TEXT("Repeated setter preserves the timer"),Returns.FindChecked(A).Elapsed,Elapsed);
    CaptureReset(A);
    TestFalse(TEXT("Invalid left duration is rejected"),L::SetSlashRightArmReturnToNeutral(A,true,0,1,100,-.5f,1));
    TestEqual(TEXT("Invalid input leaves settings intact"),Options(A).LeftAlpha,.4f);
    L::SetSlashRightArmReturnToNeutral(A,false);RestoreReset(A);Begin(A,TEXT("jabL"));
    TestEqual(TEXT("Reset restores left duration on a left-primary attack"),Returns.FindChecked(A).Config.Blend,.2f);
    TestEqual(TEXT("Reset restores left influence"),Options(A).LeftAlpha,.4f);
    L::SetSlashRightArmReturnToNeutral(A,true,0,1,100,0,1,0,0);Begin(A,TEXT("slashL"));
    TestFalse(TEXT("Both zero alphas allocate no active return"),Active(A)||ExtraReturns.Contains(A));
    TestFalse(TEXT("Both zero alphas remove the configured pose path"),Configs.Contains(A));
    Remove(A);TestFalse(TEXT("Removal clears independent configuration and reset state"),ArmOptions.Contains(A)||ArmOptionBaselines.Contains(A));
    W->DestroyWorld(false);return !HasAnyErrors();
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyReturnArmInfluenceTest,"Prophecy.NN.SlashReturn.ArmInfluence",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyReturnArmInfluenceTest::RunTest(const FString&)
{
    using namespace ProphecySlashReturn;
    FTransform NN[3];NN[0]=FTransform(FRotator(10,20,-15),FVector(0,17,100));
    NN[1]=FTransform(FRotator(0,35,0),FVector(30,0,0))*NN[0];
    NN[2]=FTransform(FRotator(20,0,15),FVector(25,0,0))*NN[1];
    FTransform Full[3];Full[0]=FTransform(FRotator(10,80,-15),NN[0].GetLocation());
    Full[1]=FTransform(FRotator(0,80,0),FVector(30,0,0))*Full[0];
    Full[2]=FTransform(FRotator(40,20,60),FVector(25,0,0))*Full[1];
    const double ShoulderAngle=NN[0].GetRotation().AngularDistance(Full[0].GetRotation());
    for(double Alpha:{0.,.25,.5,.75,.999999,1.})
    {
        FTransform S=Full[0],E=Full[1],H=Full[2];BlendArmInfluence(NN,Alpha,S,E,H);
        TestTrue(TEXT("Partial influence preserves upper-arm length"),FMath::IsNearlyEqual(FVector::Distance(S.GetLocation(),E.GetLocation()),30.,1.e-7));
        TestTrue(TEXT("Partial influence preserves forearm length"),FMath::IsNearlyEqual(FVector::Distance(E.GetLocation(),H.GetLocation()),25.,1.e-7));
        TestTrue(TEXT("Shoulder angular influence is continuous"),FMath::IsNearlyEqual(NN[0].GetRotation().AngularDistance(S.GetRotation()),Alpha*ShoulderAngle,1.e-7));
        if(Alpha==0)TestTrue(TEXT("Zero restores all exact NN transforms"),S.Equals(NN[0],0)&&E.Equals(NN[1],0)&&H.Equals(NN[2],0));
        if(Alpha==1)TestTrue(TEXT("One retains the existing return exactly"),S.Equals(Full[0],0)&&E.Equals(Full[1],0)&&H.Equals(Full[2],0));
        if(Alpha==.999999)TestTrue(TEXT("Approach to full influence is continuous in position"),H.GetLocation().Equals(Full[2].GetLocation(),.0001));
    }
    return !HasAnyErrors();
}
