from pathlib import Path
p=Path('Plugins/ProphecyJolt/Source/ProphecyJolt/Private/ProphecyJoltVelocityServo.cpp');s=p.read_text().replace('Samples.SetNum(InTargets.Num()); // All allocation happens before Update.', '''Samples.SetNum(InTargets.Num()); // All allocation happens before Update.
    HasLocalTargets=Targets.ContainsByPredicate([](const FTarget& T){return T.WorldAlpha<1.f;});
    ParentSamples.SetNum(HasLocalTargets?Targets.Num():0);''');p.write_text(s)
p=Path('Plugins/ProphecyJolt/Source/ProphecyJolt/Private/Tests/ProphecyJoltVelocityServoTests.cpp');s=p.read_text();idx=s.rfind('#endif');s=s[:idx]+'''
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyJoltParentServoTest,
    "Prophecy.Jolt.Servo.LocalGlobalParent", ProphecyJolt::VelocityServoTests::Flags)
bool FProphecyJoltParentServoTest::RunTest(const FString&)
{
    using namespace ProphecyJolt;using namespace ProphecyJolt::Conversions;using namespace ProphecyJolt::VelocityServoTests;
    if(!RuntimeReady(*this))return false;
    for(float Mode:{0.f,.5f,1.f})for(bool Reverse:{false,true})
    {
        FServoFixture F;const JPH::RefConst<JPH::Shape> Shape=new JPH::SphereShape(.05f);
        const auto Parent=F.Add(Shape,FTransform(FQuat(FVector::UpVector,UE_PI/2),FVector(10,0,0)));
        const auto Child=F.Add(Shape,FTransform(FVector(20,0,0)));
        F.Bodies().SetLinearVelocity(Parent,ToJoltLinearVelocity(FVector(20,0,0)));
        FVelocityServo::FTarget P,C;P.Body=Parent;P.TargetPositionCm=FVector(30,0,0);
        P.TargetRotation=FQuat(FVector::UpVector,UE_PI/2);
        C.Body=Child;C.TargetPositionCm=FVector(10,0,0);C.Parent=Parent;C.WorldAlpha=Mode;
        TArray<FVelocityServo::FTarget> Targets=Reverse?TArray<FVelocityServo::FTarget>{C,P}:TArray<FVelocityServo::FTarget>{P,C};
        if(!F.Publish(*this,Targets,.1f) || !F.Step(*this,.1f) || !F.CheckSamples(*this,2))return false;
        const auto& Result=F.Listener().GetLastSamples()[Reverse?0:1];
        const FVector Expected(-100.+20.*(1.-Mode),100.*(1.-Mode),0);
        TestTrue(TEXT("Local/global position and parent velocity match analytic result in either order"),
            Result.LinearAfterCmPerSecond.Equals(Expected,.005));
        TestTrue(TEXT("Local/global rotation follows physical parent"),
            FMath::IsNearlyEqual(Result.AngularAfterRadiansPerSecond.Z,(1.-Mode)*UE_PI/2/.1,1.e-4));
        const auto& Root=F.Listener().GetLastSamples()[Reverse?1:0];
        TestTrue(TEXT("Parent with no parent remains world-driven"),Root.LinearAfterCmPerSecond.Equals(FVector(200,0,0),.005));
    }
    return !HasAnyErrors();
}

'''+s[idx:];p.write_text(s)
# Add native hold math coverage; existing profile tests exercise routing, reset, special snap and all contexts.
p=Path('Source/GameAnimationSample3/Private/ProphecyPhysicalContext.cpp');s=p.read_text();idx=s.index('IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecyDampingProfileMathTest');s=s[:idx]+'''IMPLEMENT_SIMPLE_AUTOMATION_TEST(FProphecySnapshotHoldTest,"Prophecy.Agent.PhysicalContext.SnapshotHold",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)
bool FProphecySnapshotHoldTest::RunTest(const FString&)
{
    using namespace ProphecyPhysicalContext;
    FCell C;C.Value={{.2f,.4f},false};C.Write({{1,2},true},1,0,1);
    C.Sample(.9);TestTrue(TEXT("Hold preserves exact value and disabled flag"),C.Value.Scales==FVector2f(.2f,.4f) && !C.Value.Enabled);
    C.Sample(1.5);TestTrue(TEXT("Blend begins after hold from effective disabled zero"),C.Value.Scales==FVector2f(.5f,1.f) && C.Value.Enabled);
    C.Sample(2);TestTrue(TEXT("Exact endpoint retires hold and blend"),C.Value.Scales==FVector2f(1,2) && C.Duration==0 && C.Hold==0);
    C.Write({{0,0},true},0,2,1);C.Sample(2.99);TestEqual(TEXT("Zero duration still holds"),C.Value.Scales.X,1.f);
    C.Sample(3);TestEqual(TEXT("Zero duration snaps at hold boundary"),C.Value.Scales.X,0.f);
    C.Write({{1,1},true},1,3,1);C.Write({{.3f,.3f},true},0,3.5);C.Sample(10);
    TestEqual(TEXT("Immediate replacement cancels pending hold"),C.Value.Scales.X,.3f);
    return !HasAnyErrors();
}
'''+s[idx:];p.write_text(s)
