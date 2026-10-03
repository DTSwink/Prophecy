IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyInertiaRegionalSettingsTest,"Prophecy.NN.UpperBodyInertia.CoreArmSettings",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyInertiaRegionalSettingsTest::RunTest(const FString&)
{
    using namespace ProphecyUpperBodyInertia;using L=UProphecyUpperBodyInertiaLibrary;
    UWorld* W=UWorld::CreateWorld(EWorldType::Editor,false);auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    const TArray<FName> Names={TEXT("pelvis"),TEXT("clavicle_l"),TEXT("upperarm_l"),TEXT("lowerarm_l"),TEXT("hand_l"),
        TEXT("clavicle_r"),TEXT("upperarm_r"),TEXT("lowerarm_r"),TEXT("hand_r")};
    const TArray<FName> Core={TEXT("clavicle_l"),TEXT("clavicle_r")};
    const TArray<int32> Parents={INDEX_NONE,0,1,2,3,0,5,6,7};
    TArray<FTransform> Base;Base.Init(FTransform::Identity,9);
    for(int32 S=0;S<2;++S)
    {
        const int32 B=1+S*4;const double Y=S?20.:-20.;
        Base[B]=Base[B+1]=FTransform(FVector(0,Y,100));
        Base[B+2]=FTransform(FVector(30,Y,100));Base[B+3]=FTransform(FVector(30,Y,70));
    }
    TArray<FTransform> Goal=Base;
    const FQuat Turn(FVector::UpVector,.4);
    for(int32 S=0;S<2;++S)for(int32 J=0;J<4;++J)
    {
        const int32 B=1+S*4;
        Goal[B+J]=FTransform(Turn,Base[B].GetLocation()+Turn.RotateVector(Base[B+J].GetLocation()-Base[B].GetLocation()));
    }
    auto Step=[&](float FPS)
    {
        FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/FPS);
        Advance(A);TArray<FTransform> Pose=Goal;
        Apply(A,Parents,Names,Core,FTransform::Identity,Pose,1./30);
        ApplyArms(A,FTransform::Identity,Pose,1./30,FVector2D(30,30));
        return Pose;
    };
    for(bool FastCore:{true,false})
    {
        L::SetAttackUpperBodyInertia(A,true,FastCore?.05f:.8f,1,.5,0,ESpace::RootLocal,1,FastCore?.8f:.05f,.5);
        Begin(A,Base,Base,Names,Core,1./30);const auto Pose=Step(60);
        const double CoreAngle=FQuat::Identity.AngularDistance(Pose[1].GetRotation());
        const double ArmAngle=FQuat::Identity.AngularDistance(Pose[2].GetRotation());
        TestTrue(TEXT("Core and arms use their independently selected spring response"),FastCore?CoreAngle>5*ArmAngle:ArmAngle>5*CoreAngle);
        TestTrue(TEXT("Both arms use the same response"),Pose[2].GetRotation().AngularDistance(Pose[6].GetRotation())<1.e-6);
    }
    TArray<FTransform> Inherited;
    for(bool Explicit:{false,true})
    {
        L::SetAttackUpperBodyInertia(A,true,.4,0,.6,0,ESpace::RootLocal,1,Explicit?.4f:-1.f,Explicit?.6f:-1.f);
        Begin(A,Base,Base,Names,Core,1./30);const auto Pose=Step(60);
        if(!Explicit)Inherited=Pose;
        else for(int32 B=0;B<Pose.Num();++B)TestTrue(TEXT("Inherited arm values exactly match explicit shared values"),Pose[B].Equals(Inherited[B],1.e-8));
    }
    for(float FPS:{30.f,60.f,120.f})for(bool LongArms:{true,false})
    {
        L::SetAttackUpperBodyInertia(A,true,.3,.1,LongArms?.2f:.5f,0,ESpace::RootLocal,1,.7,LongArms?.5f:.2f);
        Begin(A,Base,Base,Names,Core,1./30);
        for(int32 Tick=1;Tick<=36;++Tick)
        {
            const auto Pose=Step(FPS);
            TestEqual(TEXT("Core retires on its own authored tick"),CoreActive(A),Tick<(LongArms?18:36));
            TestEqual(TEXT("Arms retire on their own authored tick"),ArmsActive(A),Tick<(LongArms?36:18));
            if(!CoreActive(A))TestTrue(TEXT("Finished core leaves normal core pose untouched"),Pose[1].Equals(Goal[1],1.e-8));
            if(!ArmsActive(A))TestTrue(TEXT("Finished arms leave normal arm pose untouched"),Pose[8].Equals(Goal[8],1.e-8));
        }
        TestFalse(TEXT("Last region retires shared return and clock"),Active(A));
        TestFalse(TEXT("Arm timing sidecar retires"),ActiveArmTimings.Contains(A));
    }
    for(bool CoreOnly:{true,false})for(bool ZeroResponse:{true,false})
    {
        const float CoreResponse=!CoreOnly && ZeroResponse?0.f:.3f;
        const float CoreBlend=!CoreOnly && !ZeroResponse?0.f:.5f;
        const float ArmsResponse=CoreOnly && ZeroResponse?0.f:.7f;
        const float ArmsBlend=CoreOnly && !ZeroResponse?0.f:.5f;
        L::SetAttackUpperBodyInertia(A,true,CoreResponse,0,CoreBlend,0,ESpace::RootLocal,1,ArmsResponse,ArmsBlend);
        Begin(A,Base,Base,Names,Core,1./30);Step(60);
        TestEqual(TEXT("Core can bypass independently"),CoreActive(A),CoreOnly);
        TestEqual(TEXT("Arms can bypass independently"),ArmsActive(A),!CoreOnly);
    }
    L::SetAttackUpperBodyInertia(A,true,.3,.1,.2,0,ESpace::RootLocal,1,.7,.8);CaptureReset(A);
    Begin(A,Base,Base,Names,Core,1./30);Step(60);const double Elapsed=Returns.FindChecked(A).Elapsed;
    L::SetAttackUpperBodyInertia(A,true,.3,.1,.2,0,ESpace::RootLocal,.5,.7,.8);
    TestEqual(TEXT("Alpha-only edits preserve regional clock"),Returns.FindChecked(A).Elapsed,Elapsed);
    TestFalse(TEXT("Invalid arm response rejected"),L::SetAttackUpperBodyInertia(A,true,.3,.1,.2,0,ESpace::RootLocal,1,-.5,.8));
    L::SetAttackUpperBodyInertia(A,true,.3,.1,.2,0,ESpace::RootLocal,1,.2,.1);RestoreReset(A);
    TestEqual(TEXT("Reset restores arm response"),ArmTimings.FindChecked(A).Response,.7f);
    TestEqual(TEXT("Reset restores arm blend"),ArmTimings.FindChecked(A).Blend,.8f);
    TestFalse(TEXT("Reset restores configuration without active motion"),Active(A));
    // A nearly frozen spring isolates pose influence from response and fade.
    for(float Weight:{0.f,.25f,1.f,-1.f})
    {
        L::SetAttackUpperBodyInertia(A,true,80000,1,.5,0,ESpace::RootLocal,.6,-1,-1,Weight);
        Begin(A,Base,Base,Names,Core,1./30);const auto Pose=Step(60);
        const double Expected=.4*(1.-(Weight<0?.6:Weight));
        TestTrue(TEXT("Arms alpha affects both arm rotations equally"),
            FMath::Abs(FQuat::Identity.AngularDistance(Pose[2].GetRotation())-Expected)<1.e-6 &&
            FMath::Abs(FQuat::Identity.AngularDistance(Pose[6].GetRotation())-Expected)<1.e-6);
        TestTrue(TEXT("Arms alpha leaves core influence unchanged"),
            FMath::Abs(FQuat::Identity.AngularDistance(Pose[1].GetRotation())-.16)<1.e-6);
        TestEqual(TEXT("Zero arm alpha seeds no arm springs"),ArmsActive(A),Weight!=0);
    }
    L::SetAttackUpperBodyInertia(A,true,.3,.1,.5,1,ESpace::RootLocal,.6,-1,-1,.8);
    Begin(A,Base,Base,Names,Core,1./30);Step(60);
    const double AlphaElapsed=Returns.FindChecked(A).Elapsed;
    const FMotion ArmBefore=Arms.FindChecked(A).Side[0].Upper;
    L::SetAttackUpperBodyInertia(A,true,.3,.1,.5,1,ESpace::RootLocal,.6,-1,-1,.2);
    TestEqual(TEXT("Arms-alpha-only changes preserve elapsed time"),Returns.FindChecked(A).Elapsed,AlphaElapsed);
    TestTrue(TEXT("Arms-alpha-only changes preserve spring state"),
        Arms.FindChecked(A).Side[0].Upper.Rotation.Equals(ArmBefore.Rotation,1.e-12) &&
        Arms.FindChecked(A).Side[0].Upper.Velocity.Equals(ArmBefore.Velocity,1.e-12));
    L::SetAttackUpperBodyInertia(A,true,.3,.1,.5,1,ESpace::RootLocal,0,-1,-1,.2);
    TestTrue(TEXT("Zero core alpha retires core while preserving arms"),!CoreActive(A) && ArmsActive(A));
    TestFalse(TEXT("Zero core retires outgoing core handoff"),Handoffs.Contains(A));
    TestEqual(TEXT("Zero core preserves arm clock"),Returns.FindChecked(A).Elapsed,AlphaElapsed);
    CaptureReset(A);
    L::SetAttackUpperBodyInertia(A,true,.3,.1,.5,1,ESpace::RootLocal,0,-1,-1,.9);RestoreReset(A);
    TestEqual(TEXT("Reset restores separate arms alpha"),ArmOverride(A),.2f);
    Begin(A,Base,Base,Names,Core,1./30);
    TestTrue(TEXT("Arms can start with core alpha zero"),ArmsActive(A) && !CoreActive(A));
    L::SetAttackUpperBodyInertia(A,true,.3,.1,.5,1,ESpace::RootLocal,0,-1,-1,0);
    TestFalse(TEXT("Both alpha zero cancel all motion"),Active(A));
    TestFalse(TEXT("Invalid negative arm alpha rejected"),L::SetAttackUpperBodyInertia(A,true,.3,.1,.5,1,ESpace::RootLocal,1,-1,-1,-.5));
    L::SetAttackUpperBodyInertia(A,true,.3,.1,.5,1,ESpace::RootLocal,.6,-1,-1,.8);
    Begin(A,Base,Base,Names,Core,1./30);Step(60);
    L::SetAttackUpperBodyInertia(A,true,.3,.1,.5,1,ESpace::RootLocal,.6,-1,-1,0);
    TestTrue(TEXT("Zero arms alpha retires arms while preserving core"),CoreActive(A) && !ArmsActive(A));
    Remove(A);
    TestFalse(TEXT("Removal cleans arm influence and baseline"),ArmInfluences.Contains(A)||ArmInfluenceBaselines.Contains(A));
    TestFalse(TEXT("Removal cleans arm overrides and reset baseline"),ArmTimings.Contains(A)||ArmTimingBaselines.Contains(A)||ActiveArmTimings.Contains(A));
    W->DestroyWorld(false);return !HasAnyErrors();
}
