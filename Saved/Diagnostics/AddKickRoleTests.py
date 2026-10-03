from pathlib import Path
r=Path(__file__).resolve().parents[2]
def edit(path,fn):
 p=r/path;s=p.read_text(encoding='utf-8');p.write_text(fn(s),encoding='utf-8')
def roles(s):
 i=s.rindex('#endif')
 return s[:i]+'''IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyTemperingFootRolesTest,"Prophecy.NN.LowerTempering.FootRoles",
    EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FProphecyTemperingFootRolesTest::RunTest(const FString&)
{
    using namespace ProphecyLowerTempering;
    using L=UProphecyLowerTemperingLibrary;
    UWorld* World=UWorld::CreateWorld(EWorldType::Editor,false);
    auto* Agent=World ? World->SpawnActor<AProphecyAgent>() : nullptr;
    if (!Agent) { if (World) World->DestroyWorld(false);return false; }
    auto Left=[&]() { const auto* S=Find(Agent);return S ? *S : FSettings{}; };
    auto Right=[&]() { const auto S=Left();return FSettings(RightFootSettings(Agent,S)); };
    auto Tick=[&](int Count) { for (int I=0;I<Count;++I) { FWorldDelegates::OnWorldPreActorTick.Broadcast(World,LEVELTICK_All,1.f/120);Find(Agent); } };
    L::SetLocomotionLowerBodyTempering(Agent,true,.25f,.5f,.75f,.2f,.4f,.6f);
    // Frozen kicking foot, untouched non-kicking foot; independent pelvis channels.
    L::SetKickLocomotionLowerBodyTempering(Agent,true,0,.2f,.4f,1,1,1,.3f,.5f,.7f);
    for (FName Family:{FName(TEXT("kickL")),FName(TEXT("kickR")),FName(TEXT("kickL"))})
    {
        SelectAttackProfile(Agent,Family);
        const bool R=Family==TEXT("kickR");
        auto Kick=[&]() { return R ? Right() : Left(); };
        auto Other=[&]() { return R ? Left() : Right(); };
        TestEqual(TEXT("Kicking XY maps to selected leg"),Kick().FeetTranslation,0.f);
        TestEqual(TEXT("Kicking Z maps to selected leg"),Kick().FeetTranslationZ,.2f);
        TestEqual(TEXT("Kicking rotation maps to selected leg"),Kick().FeetRotation,.4f);
        TestTrue(TEXT("Non-kicking foot remains untempered"),Other().FeetAreIdentity());
        TestEqual(TEXT("Pelvis remains independent of kick side"),Left().PelvisTranslation,.3f);
        L::BlendLocomotionLowerBodyTemperingToNormal(Agent,1,.5f,.5f,0);
        Tick(30);
        TestEqual(TEXT("Each kicking foot honors existing feet hold"),Kick().FeetTranslation,0.f);
        TestEqual(TEXT("Pelvis completes while kicking foot held"),Left().PelvisTranslation,1.f);
        Tick(30);
        TestTrue(TEXT("Kicking XY blends independently"),FMath::IsNearlyEqual(Kick().FeetTranslation,.5f));
        TestTrue(TEXT("Kicking Z blends independently"),FMath::IsNearlyEqual(Kick().FeetTranslationZ,.6f));
        TestTrue(TEXT("Kicking rotation blends independently"),FMath::IsNearlyEqual(Kick().FeetRotation,.7f));
        TestTrue(TEXT("Non-kicking foot was not frozen by other's blend"),Other().FeetAreIdentity());
        Tick(30);
        TestNull(TEXT("All normal removes primary entry"),Find(Agent));
        TestFalse(TEXT("All normal removes right sidecar"),RightValues.Contains(Agent));
        TestFalse(TEXT("All normal removes right timeline initial"),FeetReturnRightInitial.Contains(Agent));
    }
    // Right-only tempering must survive an identity left/pelvis through a shared timeline.
    L::SetKickLocomotionLowerBodyTempering(Agent,true,0,0,0,1,1,1,1,1,1);
    SelectAttackProfile(Agent,TEXT("kickR"));
    TestNotNull(TEXT("Identity left cannot retire active right"),Find(Agent));
    L::BlendLocomotionLowerBodyTemperingToNormal(Agent,1,0,1,0);
    L::BlendLocomotionPelvisTemperingToNormal(Agent,0,0);
    Tick(30);
    TestTrue(TEXT("Pelvis-only change preserves right shared schedule"),FMath::IsNearlyEqual(Right().FeetTranslation,.5f));
    L::BlendLocomotionFeetTemperingToNormal(Agent,.5f,0);
    Tick(15);
    TestTrue(TEXT("Retarget right feet return starts from current value"),FMath::IsNearlyEqual(Right().FeetTranslation,.75f));
    Tick(15);TestNull(TEXT("Retargeted right-only return retires"),Find(Agent));
    SelectAttackProfile(Agent,TEXT("kickL"));
    L::BlendLocomotionLowerBodyTemperingToNormal(Agent,0,0,0,0);
    TestNull(TEXT("Zero return bypasses both feet"),Find(Agent));
    SelectAttackProfile(Agent,TEXT("hookL"));
    TestTrue(TEXT("Non-kick selects regular symmetric settings"),Left().FeetTranslation==.25f && Right().FeetTranslation==.25f);
    ForgetProfiles(Agent);World->DestroyWorld(false);return !HasAnyErrors();
}
'''+s[i:]
edit('Source/GameAnimationSample3/Private/ProphecyLowerTemperingLibrary.cpp',roles)
def axes(s):
 a=s.index('bool FProphecyTemperingAxesTest::RunTest');b=s.index('    return !HasAnyErrors();',a)
 return s[:b]+'''    for (int32 O:{0,9,25}) WriteStateVec3(Target,O,FVector3f(5,6,7));
    Previous[24]=.1f;Target[24]=.9f;Previous[40]=.2f;Target[40]=.8f;
    const ProphecyLowerTempering::FSettings Left{0,0,1,1,.5f,1},Right{1,1,1,1,0,1};
    TemperLowerPose(Left,Previous,Target,&Right);
    TestTrue(TEXT("Left uses its own XY/Z values"),ReadStateVec3(Target,9).Equals(FVector3f(1,2,5)));
    TestTrue(TEXT("Right uses its own XY/Z values"),ReadStateVec3(Target,25).Equals(FVector3f(5,6,3)));
    TestEqual(TEXT("Left toe follows left rotation tempering"),Target[24],.1f);
    TestEqual(TEXT("Right toe follows right rotation tempering"),Target[40],.8f);
'''+s[b:]
edit('Source/GameAnimationSample3/Private/ProphecyLowerTempering.inl',axes)
def recovery(s):
 a=s.index('    const FPart Run{',s.index('bool FProphecyAttackRecoveryTest::RunTest'))
 return s[:a]+'''    const FSettings Roles{{E::Walk,.5f,.1f},{E::Walk,2,.25f},{E::Run,1,.5f}};
    const auto Mirrored=ResolveKickRoles(Roles,true);
    TestTrue(TEXT("Kicking role maps source, hold and duration together to right"),Mirrored.Right.Source==E::Walk && Mirrored.Right.Duration==2 && Mirrored.Right.Hold==.25f);
    TestTrue(TEXT("Non-kicking role maps source, hold and duration together to left"),Mirrored.Left.Source==E::Run && Mirrored.Left.Duration==1 && Mirrored.Left.Hold==.5f);
    TestTrue(TEXT("Mapping never swaps pelvis settings"),Mirrored.Pelvis.Source==Roles.Pelvis.Source && Mirrored.Pelvis.Duration==Roles.Pelvis.Duration && Mirrored.Pelvis.Hold==Roles.Pelvis.Hold);
'''+s[a:]
edit('Source/GameAnimationSample3/Private/ProphecyAttackRecoveryLibrary.cpp',recovery)
def reset(s):
 s=s.replace('    FString Error;\n    if (!TestTrue(TEXT("Capture baseline")', '    ProphecyLowerTempering::RestoreRightFootSettings(Agent,{.9f,.8f,1,1,.2f,1});\n    FString Error;\n    if (!TestTrue(TEXT("Capture baseline")',1)
 s=s.replace('        TestFalse(TEXT("Missing baseline entry remains absent")', '''        if (T)
        {
            const auto& R=ProphecyLowerTempering::RightFootSettings(Agent,*T);
            TestTrue(TEXT("Reset restores asymmetric right foot and cancels its blend"),R.FeetTranslation==.9f && R.FeetTranslationZ==.2f && R.FeetRotation==.8f);
        }
        TestFalse(TEXT("Missing baseline entry remains absent")''',1)
 return s
edit('Source/GameAnimationSample3/Private/ProphecyAgentResetPhysics.cpp',reset)
