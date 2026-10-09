#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmMotorsTest, "Prophecy.Jolt.ArmsAntiJiggle.Lifecycle",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyArmMotorsTest::RunTest(const FString&)
{
    using namespace ProphecyJolt;
    FProphecyJoltWorldSettings Settings;
    Settings.WorkerThreads=0; Settings.GravityCmPerSecondSquared=FVector::ZeroVector;
    Settings.MaxBodies=16; Settings.MaxBodyPairs=32; Settings.MaxContactConstraints=32;
    FProphecyJoltWorldState State(Settings);
    FProphecyJoltBodyHandle Handles[6];
    JPH::Ref<JPH::BoxShape> Shape=new JPH::BoxShape(JPH::Vec3(.05f,.05f,.05f));
    for (int I=0; I<6; ++I)
    {
        FProphecyJoltFixtureBodySettings Body; Body.PositionCm=FVector(I*30.,0,0);
        TestTrue(TEXT("Create body"),State.Add(Shape.GetPtr(),Body,Handles[I]).IsSuccess());
    }
    auto ID=[&](int I){return State.Slots[Handles[I].Slot].Body;};
    TestNull(TEXT("Disabled default has no motor registry"),ArmMotors::Find(State.Physics));
    TestTrue(TEXT("Left excludes right"),!ArmMotorSettings::Wants({true,false},TEXT("hand_r")));
    TestTrue(TEXT("Right includes forearm"),ArmMotorSettings::Wants({false,true},TEXT("lowerarm_r")));
    TestTrue(TEXT("Both exclude clavicle"),!ArmMotorSettings::Wants({true,true},TEXT("clavicle_r")));
    for(int I=0; I<3; ++I) ArmMotors::Set(State.Physics,ID(I),true);
    TestEqual(TEXT("One arm adds three constraints"),int(State.Physics.GetConstraints().size()),3);
    for(int I=0; I<3; ++I) ArmMotors::Set(State.Physics,ID(I),true);
    TestEqual(TEXT("Repeated setting is idempotent"),int(State.Physics.GetConstraints().size()),3);
    for(int I=3; I<6; ++I) ArmMotors::Set(State.Physics,ID(I),true);
    TestEqual(TEXT("Both arms add six constraints"),int(State.Physics.GetConstraints().size()),6);
    FVelocityServo::FTarget Target; Target.Body=ID(0); Target.GravityCompensationCmPerSecondSquared=980;
    auto* Drives=ArmMotors::Find(State.Physics);
    {
        JPH::BodyLockWrite Lock(State.Physics.GetBodyLockInterface(),ID(0));
        auto& Body=Lock.GetBody(); const auto V=Body.GetLinearVelocity();
        TestTrue(TEXT("Selected body uses motor"),ArmMotors::Apply(Drives,Body,Target,1.f/60,
            JPH::Vec3(1,0,980.f/6000),JPH::Vec3(0,0,1),FVector::OneVector,FVector::OneVector));
        const auto& Motor=*Drives->FindChecked(ID(0).GetIndexAndSequenceNumber()).Motor;
        TestTrue(TEXT("Gravity compensation is retained without velocity rewrite"),Body.GetLinearVelocity().IsClose(V+JPH::Vec3(0,0,980.f/6000),1.e-9f));
        TestTrue(TEXT("Motor receives command minus gravity compensation"),Motor.GetTargetVelocityCS().IsClose(JPH::Vec3(1,0,0),1.e-9f));
        Target.LinearStrength=Target.AngularStrength=0;
        ArmMotors::Apply(Drives,Body,Target,1.f/60,JPH::Vec3::sZero(),JPH::Vec3::sZero(),FVector::OneVector,FVector::OneVector);
        TestTrue(TEXT("Zero strength does not become damping"),Motor.GetMotorState(JPH::SixDOFConstraint::EAxis::TranslationX)==JPH::EMotorState::Off && Motor.GetMotorState(JPH::SixDOFConstraint::EAxis::RotationX)==JPH::EMotorState::Off);
    }
    ArmMotors::Prepare(State.Physics,{});
    for(int I=0; I<3; ++I) ArmMotors::Set(State.Physics,ID(I),false);
    TestEqual(TEXT("Disable one arm preserves other"),int(State.Physics.GetConstraints().size()),3);
    State.DestroySlot(Handles[3].Slot);
    TestEqual(TEXT("Body retirement removes its motor"),int(State.Physics.GetConstraints().size()),2);
    ArmMotors::Clear(State.Physics);
    TestNull(TEXT("Disable all releases sparse registry"),ArmMotors::Find(State.Physics));
    TestEqual(TEXT("All extra constraints removed"),int(State.Physics.GetConstraints().size()),0);
    return true;
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmMotorDurationTest,"Prophecy.Jolt.ArmsAntiJiggle.TickDuration",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyArmMotorDurationTest::RunTest(const FString&)
{
    using namespace ProphecyJolt::ArmMotorSettings;
    using L=UProphecyJoltBodyDriveLibrary;
    const auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
        .CreateFXSystem(false).SetTransactional(false);
    auto* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);
    if (!TestNotNull(TEXT("World"),World)) return false;
    auto* Agent=World->SpawnActor<AActor>();
    if (!TestNotNull(TEXT("Agent"),Agent)) { World->DestroyWorld(false);return false; }
    for (float FPS:{30.f,60.f,120.f})
    {
        TestTrue(TEXT("Enable right only"),L::SetArmsAntiJiggle(Agent,false,true));
        TestTrue(TEXT("Temporary disable"),L::DisableArmsAntiJiggleForDuration(Agent,1.f));
        TestFalse(TEXT("Both disabled immediately"),Preferences.Contains(Agent));
        for(int I=0;I<59;++I) AdvanceHolds(World,LEVELTICK_All,1.f/FPS);
        AdvanceHolds(World,LEVELTICK_TimeOnly,1.f/FPS);AdvanceHolds(World,LEVELTICK_All,0);
        TestTrue(TEXT("Hold survives59ticks independent of delta"),Holds.Contains(Agent));
        AdvanceHolds(World,LEVELTICK_All,1.f/FPS);
        const auto Arms=Preferences.FindRef(Agent);
        TestTrue(TEXT("Restores asymmetric selection on60th tick"),Arms.Right && !Arms.Left && !Holds.Contains(Agent));
    }
    L::DisableArmsAntiJiggleForDuration(Agent,.1f);
    for(int I=0;I<3;++I)AdvanceHolds(World,LEVELTICK_All,.01f);
    L::DisableArmsAntiJiggleForDuration(Agent,.1f);
    for(int I=0;I<5;++I)AdvanceHolds(World,LEVELTICK_All,.01f);
    TestTrue(TEXT("Repeated disable retains restoration and restarts duration"),Holds.Contains(Agent) && Holds.FindChecked(Agent).Restore.Right);
    TestFalse(TEXT("Negative rejected"),L::DisableArmsAntiJiggleForDuration(Agent,-1));
    TestEqual(TEXT("Invalid request preserves timer"),Holds.FindChecked(Agent).Remaining,uint64(1));
    AdvanceHolds(World,LEVELTICK_All,.01f);
    TestTrue(TEXT("Decimal .1 is six ticks"),Preferences.FindRef(Agent).Right && !Holds.Contains(Agent));
    L::DisableArmsAntiJiggleForDuration(Agent,1);
    L::SetArmsAntiJiggle(Agent,true,false);
    for(int I=0;I<60;++I)AdvanceHolds(World,LEVELTICK_All,.01f);
    TestTrue(TEXT("Explicit setter cancels stale restore"),Preferences.FindRef(Agent).Left && !Preferences.FindRef(Agent).Right && !Holds.Contains(Agent));
    L::DisableArmsAntiJiggleForDuration(Agent,1);
    L::DisableArmsAntiJiggleForDuration(Agent,0);
    TestTrue(TEXT("Zero restores immediately"),Preferences.FindRef(Agent).Left && !Holds.Contains(Agent));
    L::SetArmsAntiJiggle(Agent,false,false);
    L::DisableArmsAntiJiggleForDuration(Agent,1);
    TestFalse(TEXT("Already disabled needs no timer"),Holds.Contains(Agent));
    L::SetArmsAntiJiggle(Agent,true,true);
    L::DisableArmsAntiJiggleForDuration(Agent,1);
    L::NotifyArmsAntiJiggleAttackWindow(Agent,true);
    ForgetWorld(World);
    TestFalse(TEXT("Cleanup cancels restoration"),Holds.Contains(Agent));
    TestFalse(TEXT("Cleanup cancels attack suppression"),AttackWindows.Contains(Agent));
    if(Holds.IsEmpty())TestFalse(TEXT("No dormant tick callback"),HoldTick.IsValid());
    World->DestroyWorld(false);
    return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyArmMotorAttackWindowTest,"Prophecy.Jolt.ArmsAntiJiggle.AttackWindow",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecyArmMotorAttackWindowTest::RunTest(const FString&)
{
    using namespace ProphecyJolt::ArmMotorSettings;
    using L=UProphecyJoltBodyDriveLibrary;
    const auto Init=UWorld::InitializationValues().AllowAudioPlayback(false).RequiresHitProxies(false)
        .CreatePhysicsScene(false).CreateNavigation(false).CreateAISystem(false).ShouldSimulatePhysics(false)
        .CreateFXSystem(false).SetTransactional(false);
    auto* World=UWorld::CreateWorld(EWorldType::Game,false,NAME_None,nullptr,true,ERHIFeatureLevel::Num,&Init);
    if (!TestNotNull(TEXT("World"),World)) return false;
    auto* Agent=World->SpawnActor<AActor>();
    if (!TestNotNull(TEXT("Agent"),Agent)) { World->DestroyWorld(false);return false; }
    L::SetArmsAntiJiggle(Agent,false,true);
    L::NotifyArmsAntiJiggleAttackWindow(Agent,true);
    TestNull(TEXT("Armed disables both motors without changing preference"),Effective(Agent));
    TestTrue(TEXT("Right preference retained"),Preferences.FindRef(Agent).Right);
    L::DisableArmsAntiJiggleForDuration(Agent,.1f);
    for(int I=0;I<6;++I)AdvanceHolds(World,LEVELTICK_All,.1f);
    TestNull(TEXT("Timed expiry cannot bypass armed window"),Effective(Agent));
    L::NotifyArmsAntiJiggleAttackWindow(Agent,false);
    TestTrue(TEXT("Hit restores asymmetric selection after timer expired"),Effective(Agent) && Effective(Agent)->Right && !Effective(Agent)->Left);
    L::NotifyArmsAntiJiggleAttackWindow(Agent,true);
    L::DisableArmsAntiJiggleForDuration(Agent,.1f);
    L::NotifyArmsAntiJiggleAttackWindow(Agent,false);
    TestNull(TEXT("Hit cannot bypass active timed hold"),Effective(Agent));
    for(int I=0;I<6;++I)AdvanceHolds(World,LEVELTICK_All,.1f);
    TestTrue(TEXT("Timer restores after hit"),Effective(Agent) && Effective(Agent)->Right);
    L::NotifyArmsAntiJiggleAttackWindow(Agent,true);
    L::SetArmsAntiJiggle(Agent,true,false);
    TestNull(TEXT("Setter during attack stays suppressed"),Effective(Agent));
    L::NotifyArmsAntiJiggleAttackWindow(Agent,false);
    TestTrue(TEXT("Hit restores newest explicit choices"),Effective(Agent) && Effective(Agent)->Left && !Effective(Agent)->Right);
    L::NotifyArmsAntiJiggleAttackWindow(Agent,true);
    L::SetArmsAntiJiggle(Agent,false,false);
    L::NotifyArmsAntiJiggleAttackWindow(Agent,false);
    TestNull(TEXT("Explicitly disabled arms stay off"),Effective(Agent));
    L::NotifyArmsAntiJiggleAttackWindow(Agent,true);
    L::NotifyArmsAntiJiggleAttackWindow(Agent,true);
    L::NotifyArmsAntiJiggleAttackWindow(Agent,false);
    TestFalse(TEXT("Repeated phases leave no stale window"),AttackWindows.Contains(Agent));
    ForgetWorld(World);World->DestroyWorld(false);
    return !HasAnyErrors();
}
#endif
