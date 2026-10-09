IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDodgeLowerTemperingTest,"Prophecy.NN.LowerTempering.DodgeIsolation",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyDodgeLowerTemperingTest::RunTest(const FString&)
{
    using namespace ProphecyLowerTempering;
    using L=UProphecyLowerTemperingLibrary;
    auto* W=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* A=W?W->SpawnActor<AProphecyAgent>():nullptr;if(!A)return false;
    auto Value=[&](){const auto* V=Find(A);return V?*V:FSettings{};};
    auto Tick=[&](int N){for(int I=0;I<N;++I){FWorldDelegates::OnWorldPreActorTick.Broadcast(W,LEVELTICK_All,1.f/120);Find(A);}};
    L::SetLocomotionLowerBodyTempering(A,true,.2,.3,.4,.5,.6,.7);
    L::SetDodgeLocomotionLowerBodyTempering(A,true,.8,.7,.6,.4,.3,.2);
    TestEqual(TEXT("Configuring Dodge leaves regular locomotion unchanged"),Value().FeetTranslation,.2f);
    L::BlendLocomotionLowerBodyTemperingToNormal(A,1,0,1,0);Tick(15);
    const float AttackBefore=Value().FeetTranslation;
    L::BlendDodgeLocomotionLowerBodyTemperingToNormal(A,0,0,0,0);
    TestEqual(TEXT("Dodge blend cannot cancel attack return"),Value().FeetTranslation,AttackBefore);
    TestTrue(TEXT("Attack clock remains running"),Returns.Contains(A));

    SelectDefenseProfile(A,true);
    TestEqual(TEXT("Dodge chooses its feet profile"),Value().FeetTranslation,.8f);
    TestEqual(TEXT("Dodge chooses its pelvis profile"),Value().PelvisTranslation,.4f);
    L::BlendDodgeLocomotionLowerBodyTemperingToNormal(A,1,.5,.5,0);
    Tick(15);
    const float PelvisBefore=Value().PelvisTranslation;
    // Typical shared Special Ended graph: all nodes may run without switches.
    L::SetLocomotionLowerBodyTempering(A,true,.1,.2,.3,.4,.5,.6);
    L::SetKickLocomotionLowerBodyTempering(A,true,0,0,0);
    L::BlendLocomotionLowerBodyTemperingToNormal(A,0,0,0,0);
    L::BlendKickLocomotionLowerBodyTemperingToNormal(A,0,0,0,0);
    L::BlendLocomotionFeetTemperingToNormal(A,0,0);
    L::BlendLocomotionPelvisTemperingToNormal(A,0,0);
    TestEqual(TEXT("Attack/kick calls preserve Dodge feet hold"),Value().FeetTranslation,.8f);
    TestEqual(TEXT("Attack/kick calls preserve Dodge pelvis timeline"),Value().PelvisTranslation,PelvisBefore);
    Tick(15);
    TestEqual(TEXT("Dodge pelvis finishes in 30 game ticks at 120 FPS"),Value().PelvisTranslation,1.f);
    TestEqual(TEXT("Dodge feet still held at 30 ticks"),Value().FeetTranslation,.8f);
    Tick(30);
    TestTrue(TEXT("Dodge feet halfway after hold plus 30 ticks"),FMath::IsNearlyEqual(Value().FeetTranslation,.9f));
    Tick(30);
    TestNull(TEXT("Dodge completion removes all pose work"),Find(A));
    TestTrue(TEXT("Dodge completion removes all return clocks"),!Returns.Contains(A)&&!FeetReturns.Contains(A)&&!PelvisReturns.Contains(A));

    SelectDefenseProfile(A,false);
    L::SetLocomotionLowerBodyTempering(A,true,.2,.3,.4,.5,.6,.7);
    L::SetDodgeLocomotionLowerBodyTempering(A,true,.8,.7,.6,.4,.3,.2);
    L::SetKickLocomotionLowerBodyTempering(A,true,0,0,0);
    L::BlendLocomotionLowerBodyTemperingToNormal(A,1,1,1,1);
    L::BlendDodgeLocomotionLowerBodyTemperingToNormal(A,1,1,1,1);
    L::BlendKickLocomotionLowerBodyTemperingToNormal(A,1,1,1,1);
    TestNull(TEXT("Parry ignores all tempering setters and blend nodes in common callback"),Find(A));
    TestTrue(TEXT("Parry creates no return clocks"),!Returns.Contains(A)&&!FeetReturns.Contains(A)&&!PelvisReturns.Contains(A));
    SelectAttackProfile(A,TEXT("jabR"));
    TestEqual(TEXT("Next attack still has independent configured profile"),Value().FeetTranslation,.2f);
    SelectDefenseProfile(A,true);
    TestEqual(TEXT("Next Dodge still has independent configured profile"),Value().FeetTranslation,.8f);
    L::SetDodgeLocomotionLowerBodyTempering(A,false);
    TestNull(TEXT("Disabling Dodge removes its active return"),Find(A));
    SelectAttackProfile(A,TEXT("jabR"));
    TestEqual(TEXT("Disabling Dodge leaves attack configured"),Value().FeetTranslation,.2f);
    SelectDefenseProfile(A,true);ClearAttackSelection(A);Remove(A);
    L::SetLocomotionLowerBodyTempering(A,true,.2,.3,.4,.5,.6,.7);
    TestEqual(TEXT("Reset clears defense selection and accepts regular baseline"),Value().FeetTranslation,.2f);
    ForgetProfiles(A);
    TestTrue(TEXT("Lifetime cleanup removes Dodge configuration and selection"),!DodgeProfiles.Contains(A)&&!DefenseSelected.Contains(A)&&!DodgeSelected.Contains(A));
    W->DestroyWorld(false);return !HasAnyErrors();
}
